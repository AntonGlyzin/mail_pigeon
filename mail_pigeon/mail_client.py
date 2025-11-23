from __future__ import annotations
import zmq
from typing import Optional, List, Union
import json
import time
from dataclasses import dataclass, asdict
from threading import Thread, Event, RLock
from mail_pigeon.queue import BaseQueue, SimpleBox
from mail_pigeon.mail_server import MailServer, CommandsCode, MessageCommand                
from mail_pigeon.exceptions import PortAlreadyOccupied, ServerNotRunning
from mail_pigeon.security import IEncryptor
from mail_pigeon.translate import _
from mail_pigeon import logger


class TypeMessage(object):
    REQUEST = 'request'
    REPLY = 'reply'


@dataclass
class Message(object):
    key: str # ключ сообщения в очереди
    type: str 
    wait_response: bool # является ли запрос ожидающим ответом
    sender: str
    recipient: str
    content: str
    
    def to_dict(self):
        return asdict(self)
    
    def to_bytes(self):
        return json.dumps(self.to_dict()).encode()
    
    @classmethod
    def parse(cls, msg: Union[bytes, str]) -> Message:
        return cls(**json.loads(msg))


class MailClient(object):
    
    number_client = 0
    
    def __new__(cls, *args, **kwargs):
        cls.number_client += 1
        return super().__new__(cls)
    
    def __init__(
            self, name_client: str,
            host_server: str = '127.0.0.1', 
            port_server: int = 5555,
            is_master: Optional[bool] = False,
            out_queue: Optional[BaseQueue] = None,
            wait_server: bool = True,
            encryptor: Optional[IEncryptor] = None
        ):
        """
        Args:
            name_client (str): Название клиента латиницей без пробелов.
            host_server (str, optional): Адрес. По умолчанию - '127.0.0.1'.
            port_server (int, optional): Порт подключения. По умолчанию - 5555.
            is_master (Optional[bool], optional): Будет ли этот клиент сервером.
            out_queue (Optional[BaseQueue], optional): Очередь писем на отправку.
            wait_server (bool, optional): Стоит ли ждать включения сервера.
            encryptor (bool, optional): Шифратор сообщений.

        Raises:
            PortAlreadyOccupied: Нельзя создать сервер на занятом порту.
            ServerNotRunning: Сервер не запущен. Если мы решили не ждать запуска сервера.
        """        
        self.class_name = f'{self.__class__.__name__}-{self.number_client}'
        self._encryptor = encryptor
        self._server = None
        self.name_client = name_client
        self.host_server = host_server
        self.port_server = port_server
        self.is_master = is_master
        self.waitserver = wait_server
        self._clients: List[str] = []
        self._out_queue = out_queue or SimpleBox() # очередь для отправки
        self._in_queue = SimpleBox() # очередь для принятия сообщений
        self._is_start = Event()
        self._is_start.set()
        self._server_started = Event()
        self._server_started.clear()
        self._client_connected = Event()
        self._client_connected.clear()
        self._last_ping = 0
        self._rlock = RLock()
        self._client = Thread(
                target=self._pull_message, 
                name=self.class_name, 
                daemon=True
            )
        self._client.start()
        self._sender_mails = Thread(
                target=self._mailer, 
                name=f'{self.class_name}-Mailer', 
                daemon=True
            )
        self._sender_mails.start()
        self._heartbeat_server = Thread(
                target=self._check_server, 
                name=f'{self.class_name}-Heartbeat-Server', 
                daemon=True
            )
        self._heartbeat_server.start()
    
    @property
    def last_ping(self):
        with self._rlock:
            return self._last_ping
    
    @last_ping.setter
    def last_ping(self, num: int):
        with self._rlock:
            self._last_ping = num
    
    @property
    def clients(self):
        with self._rlock:
            return list(self._clients)
    
    def wait_server(self):
        """Ожидает подключение или выбрасывает исключение.

        Raises:
            PortAlreadyOccupied: Порт занят.
            ServerNotRunning: Сервер не запущен.
        """            
        is_use_port = self._is_use_port()
        if is_use_port and self.is_master:
            raise PortAlreadyOccupied(self.port_server)
        elif self.is_master:
            self._server = MailServer(self.port_server)
        elif self.is_master is None and not is_use_port:
            self._server = MailServer(self.port_server)
        while self.waitserver:
            is_use_port = self._is_use_port()
            if is_use_port:
                break
            time.sleep(.1)
        if not self._server and not is_use_port:
            raise ServerNotRunning(self.port_server)
    
    def stop(self):
        """
            Завершение клиента.
        """
        if self._server:
            self._server.stop()
        self._is_start.clear()
        self._server_started.set()
        self._client_connected.set()
        self._destroy_socket()
    
    def send(
            self, recipient: str, content: str, 
            wait: bool = False, timeout: float = None,
            key_response: str = None
        ) -> Optional[Message]:
        """Отправляет сообщение в другой клиент.
        Сообщения могут ожидаться по команде `get()` или `send()`.

        Args:
            recipient (str): Получатель.
            content (str): Содержимое.
            wait (bool, optional): Ожидать ли получения ответа от запроса из команды send().
            timeout (float, optional): Сколько времени ожидать сообщения.
            key_response (str, optional): Ключи из запроса. Обработаный ответ на запрос. Обратные сообщения 
                не блокируются по wait.

        Returns:
            Optional[Message]: Сообщение или ничего.
        """
        key = key_response or self._out_queue.gen_key()
        data = Message(
                key=key, 
                type=TypeMessage.REQUEST,
                wait_response = True if key_response else False,
                sender=self.name_client,
                recipient=recipient,
                content=content
            ).to_bytes()
        self._out_queue.put(data.decode(), f'{recipient}-{key}')
        if not wait:
            return None
        if key_response:
            return None
        res = self._in_queue.get(f'{recipient}-{key}', timeout)
        if not res:
            return None
        self._in_queue.done(res[0])
        return Message(**json.loads(res[1]))
    
    def get(self, timeout: float = None) -> Optional[Message]:
        """Получение сообщений из принимающей очереди. 
        Метод блокируется, если нет timeout.

        Args:
            timeout (float, optional): Время ожидания сообщения.

        Returns:
            Optional[Message]: Сообщение или ничего.
        """        
        res = self._in_queue.get(timeout=timeout)
        if not res:
            return None
        self._in_queue.done(res[0])
        return Message(**json.loads(res[1]))
    
    def __del__(self):
        self._destroy_socket()
    
    def _add_client(self, client: str):
        """Добавление клиента в список.

        Args:
            client (str): Клиент.
        """        
        with self._rlock:
            if client not in self._clients:
                self._clients.append(client)
    
    def _set_clients(self, clients: List[str]):
        """Добавление клиентов.

        Args:
            client (str): Клиент.
        """        
        with self._rlock:
            self._clients = list(clients)

    def _clear_clients(self):
        """Очищение клиентов.

        Args:
            client (str): Клиент.
        """        
        with self._rlock:
            self._clients.clear()
    
    def _del_client(self, client: str):
        """Удаление клиента из списка.

        Args:
            client (str): Клиент.
        """        
        with self._rlock:
            if client in self._clients:
                self._clients.remove(client)
    
    def _stop_message(self):
        """ Останавливает отправку и принятие сообщений. """
        self._server_started.clear()
        self._client_connected.clear()
    
    def _disconnect_message(self):
        """ Отправить сообщение на сервер о завершение работы. """        
        self._send_message(MailServer.SERVER_NAME, CommandsCode.DISCONNECT_CLIENT)
    
    def _connect_message(self):
        """ Отправить сообщение на сервер о присоединение. """        
        self._send_message(MailServer.SERVER_NAME, CommandsCode.CONNECT_CLIENT)

    def _create_socket(self):
        """ Создание сокета. """
        self._context = zmq.Context()
        self._socket = self._context.socket(zmq.DEALER)
        self._socket.setsockopt_string(zmq.IDENTITY, self.name_client)
        self._socket.setsockopt(zmq.IMMEDIATE, 1)
        self._socket.connect(f'tcp://{self.host_server}:{self.port_server}')
        self._in_poll = zmq.Poller()
        self._in_poll.register(self._socket, zmq.POLLIN)
    
    def _destroy_socket(self):
        """ Закрытие сокета. """
        try:
            self._socket.disconnect(f'tcp://{self.host_server}:{self.port_server}')
            self._in_poll.unregister(self._socket)
        except Exception as e:
            logger.debug(f'{self.class_name}: closing the socket. Error <{e}>.')
        try:
            self._socket.close()
        except Exception as e:
            logger.debug(f'{self.class_name}: closing the socket. Error <{e}>.')
        try:
            self._context.term()
        except Exception as e:
            logger.debug(f'{self.class_name}: destroy the socket. Error <{e}>.')
        
    
    def _create_server(self) -> bool:
        """Пересоздание сервера в клиенте.

        Returns:
            bool: Результат.
        """
        try:
            is_use_port = self._is_use_port()
            if is_use_port:
                return False
            if self.is_master is False:
                return False
            self._server = MailServer(self.port_server)
            return True
        except Exception:
            return False

    def _send_message(self, recipient: str, content: str) -> bool:
        """Отправка сообщения к другому клиенту через сервер.

        Args:
            recipient (str): Получатель.
            content (str): Контент.

        Raises:
            zmq.ZMQError: Ошибка при отправки.

        Returns:
            bool: Результат.
        """        
        try:
            if not self._server_started.is_set():
                return False
            if not self._socket.poll(100, zmq.POLLOUT):  # Готов ли сокет к отправке
                raise zmq.ZMQError
            self._socket.send_multipart(
                    [recipient.encode(), content.encode()], 
                    flags=zmq.NOBLOCK
                )
            return True
        except zmq.ZMQError:
            return False

    def _is_use_port(self) -> bool:
        """Проверить порт подключения.

        Returns:
            bool: Результат.
        """        
        try:
            if not self._socket.poll(100, zmq.POLLOUT):  # Готов ли сокет к отправке
                raise zmq.ZMQError
            self._socket.send_multipart(
                    [MailServer.SERVER_NAME.encode(), CommandsCode.PING.encode()], 
                    flags=zmq.NOBLOCK
                )
            return True
        except zmq.ZMQError:
            return False
    
    def _check_server(self):
        """Делает пинги на сервер и пересоздает сокет.
        
        Если связь прервется, то будет сделано 3 пинга, 
        а потом на 10 сек. пересоздан сокет.
        """        
        while self._is_start.is_set():
            try:
                current_time = int(time.time())
                if MailServer.INTERVAL_HEARTBEAT*2 < int(current_time - self.last_ping):
                    time.sleep(.1)
                    logger.debug(f'{self.class_name}: destroy socket and server.')
                    self._clear_clients()
                    self._stop_message()
                    if self._server:
                        self._server.stop()
                        self._create_server()
                    self._destroy_socket()
                    self._create_socket()
                    time.sleep(.1)
                    self.wait_server()
                    logger.debug(f'{self.class_name}: connected server.')
                    self._server_started.set()
                    self._connect_message()
                    self.last_ping = current_time
                if MailServer.INTERVAL_HEARTBEAT < int(current_time - self.last_ping):
                    if not self._is_use_port():
                        self.last_ping = 0
            except zmq.ZMQError as e:
                if 'not a socket' in str(e):
                    self.last_ping = 0
            except Exception as e:
                logger.error(_("{}: Непредвиденная ошибка: {}").format(self.class_name, e), exc_info=True)
            time.sleep(2)
    
    def _pull_message(self):
        """ Цикл получения сообщений. """        
        while self._is_start.is_set():
            try:
                #  Принимать сообщение, только если работает сервер.
                self._server_started.wait()
                if not self._is_start.is_set():
                    return
                socks = dict(self._in_poll.poll(MailServer.INTERVAL_HEARTBEAT*1000))
                if socks.get(self._socket) == zmq.POLLIN:
                    sender, msg = self._socket.recv_multipart()
                    sender = sender.decode()
                    msg = msg.decode()
                    logger.debug(f'{self.class_name}: received message <{msg}> from "{sender}".')
                    if sender == MailServer.SERVER_NAME:
                        self._process_server_commands(msg)
                    else:
                        self._process_msg_client(msg, sender)
            except zmq.ZMQError as e:
                if 'not a socket' in str(e):
                    self.last_ping = 0
                    self._stop_message()
                    continue
                logger.error(f'{self.class_name}.recv: ZMQError - {e}')
            except Exception as e:
                logger.error(
                        (_('{}: Ошибка в главном цикле получения сообщений. ').format(self.class_name) +
                        _('Контекст ошибки: {}. ').format(e)), exc_info=True
                    )
    
    def _mailer(self):
        """ Отправка сообщений из очереди. """        
        while self._is_start.is_set():
            try:
                # Перед тем как отправлять сообщение клиент 
                # должен быть подключен.
                self._client_connected.wait()
                if not self._is_start.is_set():
                    return
                res = self._out_queue.get(timeout=1)
                if not res:
                    continue
                recipient, hex = res[0].split('-')
                recipient = recipient
                if recipient not in self.clients:
                    continue
                msg = res[1]
                if self._encryptor:
                    msg = self._encryptor.encrypt(msg.encode())
                    msg = msg.decode()
                if not self._send_message(recipient, msg):
                    self.last_ping = 0
                    self._stop_message()
            except Exception as e:
                logger.error(
                        (_('{}: Ошибка в цикле отправки сообщений. ').format(f'{self.class_name}-Mailer') +
                        _('Контекст ошибки: {}. ').format(e)), exc_info=True
                    )
    
    def _process_server_commands(self, msg: Union[bytes, str]):
        """Обработка уведомлений от команд сервера.

        Args:
            msg (bytes): Сообщение.
        """
        msg_cmd = MessageCommand.parse(msg)
        logger.debug(f'{self.class_name}: command from server <{msg}>.')
        if CommandsCode.NOTIFY_NEW_CLIENT == msg_cmd.code:
            client = msg_cmd.data
            self._add_client(client)
            self._out_queue.move_active_to_live(f'{client}-', True)
        elif CommandsCode.NOTIFY_DISCONNECT_CLIENT == msg_cmd.code:
            self._del_client(msg_cmd.data)
        elif CommandsCode.PONG == msg_cmd.code:
            self.last_ping = int(time.time())
        elif CommandsCode.NOTIFY_STOP_SERVER == msg_cmd.code:
            self.last_ping = 0
        elif CommandsCode.GET_CONNECTED_CLIENTS == msg_cmd.code:
            self._set_clients(msg_cmd.data)
        elif CommandsCode.CONNECT_CLIENT == msg_cmd.code:
            self._set_clients(msg_cmd.data)
            self._send_message(MailServer.SERVER_NAME, CommandsCode.CONFIRM_CONNECT)
        elif CommandsCode.CONFIRM_CONNECT == msg_cmd.code:
            self._client_connected.set()
            self._out_queue.move_active_to_live(startswith=True)
    
    def _process_msg_client(self, msg: str, sender: str):
        """Обработка сообщений от клиентов.

        Args:
            msg (bytes): Сообщение.
        """
        if self._encryptor:
            try:
                msg = self._encryptor.decrypt(msg.encode())
            except Exception:
                logger.error(
                    _("{}: Не удалось расшифровать сообщение от '{}'.").format(self.class_name, sender)
                )
                return None
        data = Message.parse(msg)
        if sender == self.name_client:
            self._del_client(data.recipient)
            self._send_message(MailServer.SERVER_NAME, CommandsCode.GET_CONNECTED_CLIENTS)
            return None
        if data.type == TypeMessage.REPLY:
            self._out_queue.done(f'{data.sender}-{data.key}')
        elif data.type == TypeMessage.REQUEST:
            self._in_queue.put(
                    msg, 
                    key=f'{data.sender}-{data.key}', 
                    use_get_key=data.wait_response
                )
            recipient = data.sender
            # автоматический ответ для отправителя,
            # что его сообщение доставлено.
            data = Message(
                    key=data.key,
                    type=TypeMessage.REPLY,
                    wait_response=False,
                    sender=self.name_client,
                    recipient=data.sender,
                    content=''
                ).to_bytes()
            if self._encryptor:
                data = self._encryptor.encrypt(data)
            self._send_message(recipient, data.decode())