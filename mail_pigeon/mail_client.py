from __future__ import annotations
import zmq
import zmq.auth
import json
import time
import socket
from pathlib import Path
from typing import Optional, List, Union, Dict, Tuple
from threading import Thread, Event, RLock
from mail_pigeon.queue import BaseQueue, SimpleBox
from mail_pigeon.mail_server import MailServer, CommandsCode, MessageCommand                
from mail_pigeon.exceptions import PortAlreadyOccupied
from mail_pigeon.security import IEncryptor
from mail_pigeon.translate import _
from mail_pigeon.utils import logger, TypeMessage, Message, Auth


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
            encryptor: Optional[IEncryptor] = None,
            cert_dir: Optional[str] = None
        ):
        """
        Args:
            name_client (str): Название клиента латиницей без пробелов.
            host_server (str, optional): Адрес. По умолчанию - '127.0.0.1'.
            port_server (int, optional): Порт подключения. По умолчанию - 5555.
            is_master (Optional[bool], optional): Будет ли этот клиент сервером.
            out_queue (Optional[BaseQueue], optional): Очередь писем на отправку.
            encryptor (bool, optional): Шифрует сообщение до отправки на сервер.
            cert_dir (str, optional): Путь до сертификата или 
                до пустой директории для генерации ключа.
        """        
        self.class_name = f'{self.__class__.__name__}-{self.number_client}-{name_client}'
        self.name_client = name_client
        self.host_server = host_server
        self.port_server = port_server
        self.is_master = is_master
        self._cert_dir = Path(cert_dir) if cert_dir else None
        self._context: Optional[zmq.Context] = None
        self._lock_socket = RLock()
        self._socket: Optional[zmq.Socket] = None
        self._in_poll = None
        self._encryptor = encryptor
        self._server: Optional[MailServer] = None
        self._clients: List[str] = []
        self._out_queue = out_queue or SimpleBox() # очередь для отправки
        self._in_queue = SimpleBox() # очередь для принятия сообщений
        self._waiting_mails: Dict[str, str] = {} # ключи писем для ожидающих клиентов
        self._is_start = Event()
        self._is_start.set()
        self._server_started = Event() # если нужно пересоздать сокет
        self._server_started.clear()
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
    def clients(self):
        return list(self._clients)
    
    def wait_server(self):
        """ Ожидание подключения к серрверу. """
        self._server_started.wait()
    
    def stop(self):
        """
            Завершение клиента.
        """
        if self._server:
            self._server.stop()
        self._disconnect_message()
        self._is_start.clear()
        self._server_started.set()
        self._destroy_socket()
    
    def send(
            self, recipient: str, content: str, 
            wait: bool = False, timeout: Optional[float] = None
        ) -> Optional[Message]:
        """Отправляет сообщение в другой клиент.

        Args:
            recipient (str): Получатель.
            content (str): Содержимое.
            wait (bool, optional): Ожидать ли получения ответа от запроса.
            timeout (float, optional): Сколько в секундах ждать результата. 

        Returns:
            Optional[Message]: Сообщение или ничего.
        """
        key = None
        is_response = False
        if recipient in self._waiting_mails:
            key = self._waiting_mails[recipient]
            is_response = True
        key = key or self._out_queue.gen_key()
        if self._encryptor:
            content = self._encryptor.encrypt(content.encode()).decode()
        data = Message(
                key = key, 
                type = TypeMessage.REQUEST,
                wait_response = True if wait else False,
                is_response = is_response,
                sender = self.name_client,
                recipient = recipient,
                content = content
            ).to_bytes()
        self._out_queue.put(data.decode(), f'{recipient}-{key}')
        if recipient in self._waiting_mails:
            del self._waiting_mails[recipient]
        if not wait:
            return None
        res = self._in_queue.get(f'{recipient}-{key}', timeout=timeout)
        if not res:
            self._out_queue.done(f'{recipient}-{key}')
            return None
        self._in_queue.done(res[0])
        data = Message(**json.loads(res[1]))
        if self._encryptor:
            try:
                data.content = self._encryptor.decrypt(data.content.encode()).decode()
            except Exception:
                logger.error(
                    _("{}: Не удалось расшифровать сообщение от <{}>.").format(self.class_name, data.sender)
                )
                return None
        if data.wait_response:
            self._waiting_mails[data.sender] = data.key
        return data
    
    def get(self, timeout: Optional[float] = None) -> Optional[Message]:
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
        msg = Message(**json.loads(res[1]))
        if self._encryptor:
            try:
                msg.content = self._encryptor.decrypt(msg.content.encode()).decode()
            except Exception:
                logger.error(
                    _("{}: Не удалось расшифровать сообщение от <{}>.").format(self.class_name, msg.sender)
                )
                return None
        if msg.wait_response:
            self._waiting_mails[msg.sender] = msg.key
        return msg
    
    def __del__(self):
        self._is_start.clear()
        self._server_started.set()
        self._destroy_socket()
    
    def _generate_keys(self, cert_dir: Path) -> Tuple[bytes, bytes]:
        """Генерирует пару ключей или выдает существующие из директории.

        Args:
            cert_dir (Optional[Path], optional): Путь до директории.

        Returns:
            Tuple[bytes, bytes]: Пара ключей public_key, secret_key.
        """
        if not cert_dir.exists():
            cert_dir.mkdir(exist_ok=True)
        cert = cert_dir / f'{self.name_client}.key_secret'
        if not cert.exists():
            zmq.auth.create_certificates(cert_dir, self.name_client)
        k1, k2 = zmq.auth.load_certificate(cert)
        if k2 is None:
            return k1, b''
        return k1, k2
    
    def _load_server_key(self) -> bytes:
        """Возвращает публичный ключ сервера.

        Raises:
            FileNotFoundError: Нет файла ключа.

        Returns:
            (bytes): Ключ.
        """
        if self._cert_dir is None:
            return b''   
        server_public = self._cert_dir / "server.key"
        if not server_public.exists():
            raise FileNotFoundError(_("Ключ сервера не найден: <{}>").format(server_public))
        key, none = zmq.auth.load_certificate(server_public)
        return key
    
    def _check_client(self, client: str) -> bool:
        """Есть ли такой клиент в подключенном списке.

        Args:
            client (str): Клиент.
        """        
        with self._rlock:
            if client not in self._clients:
                return False
            else:
                return True
    
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
        self._out_queue.to_waiting_queue()
        self._server_started.clear()
    
    def _disconnect_message(self) -> bool:
        """ Отправить сообщение на сервер о завершение работы. """        
        return self._send_message(MailServer.SERVER_NAME, CommandsCode.DISCONNECT_CLIENT)
    
    def _connect_message(self) -> bool:
        """ Отправить сообщение на сервер о присоединение. """        
        return self._send_message(MailServer.SERVER_NAME, CommandsCode.CONNECT_CLIENT)
    
    def _once_start_client(self):
        """ Запуск клиента. """
        self._create_server()
        self._create_socket()

    def _create_socket(self):
        """ Создание сокета. """
        self._context = zmq.Context()
        self._socket = self._context.socket(zmq.DEALER)
        self._socket.setsockopt_string(zmq.IDENTITY, self.name_client)
        self._socket.setsockopt(zmq.SNDHWM, 1500) # ограничить буфер на отправку
        self._socket.setsockopt(zmq.SNDBUF, 65536) # системный буфер
        self._socket.setsockopt(zmq.IMMEDIATE, 1) # не буферизовать для неготовых
        self._socket.setsockopt(zmq.LINGER, 1000) # милисек. сброс перед закрытием
        self._socket.setsockopt(zmq.HEARTBEAT_IVL, 10000) # милисек. сделать ping если нет трафика
        self._socket.setsockopt(zmq.HEARTBEAT_TIMEOUT, 20000) # если так и нет трафика или pong, то разрыв
        self._socket.setsockopt(zmq.SNDTIMEO, 2000)  # милисек. если не удается отправить сообщение EAGAIN
        if self._cert_dir:
            keys = self._generate_keys(self._cert_dir)
            self._socket.setsockopt(zmq.CURVE_PUBLICKEY, keys[0])
            self._socket.setsockopt(zmq.CURVE_SECRETKEY, keys[1])
            serv_key = self._load_server_key()
            self._socket.setsockopt(zmq.CURVE_SERVERKEY, serv_key)
        self._socket.connect(f'tcp://{self.host_server}:{self.port_server}')
        self._in_poll = zmq.Poller()
        self._in_poll.register(self._socket, zmq.POLLIN)
    
    def _destroy_socket(self):
        """ Закрытие сокета. """
        try:
            if self._socket:
                self._socket.disconnect(f'tcp://{self.host_server}:{self.port_server}')
        except Exception as e:
            logger.debug(f'{self.class_name}: closing the socket. <{e}>.')
        try:
            if self._in_poll:
                self._in_poll.unregister(self._socket)
        except Exception as e:
            logger.debug(f'{self.class_name}: closing the socket. <{e}>.')
        try:
            if self._socket:
                self._socket.close()
        except Exception as e:
            logger.debug(f'{self.class_name}: closing the socket. <{e}>.')
        try:
            if self._context:
                self._context.term()
        except Exception as e:
            logger.debug(f'{self.class_name}: destroy the socket. <{e}>.')
    
    def _create_server(self) -> bool:
        """Пересоздание сервера в клиенте.

        Returns:
            bool: Результат.
        """
        try:
            is_use_port = self._is_use_port()
            if is_use_port and self.is_master:
                raise PortAlreadyOccupied(self.port_server)
            if is_use_port:
                return False
            if self.is_master is False:
                return False
            auth: Optional[Auth] = None
            if self._cert_dir:
                k1, k2 = MailServer.generate_keys(self._cert_dir)
                auth = Auth(k1, k2)
            if self._server:
                self._server.stop()
            self._server = MailServer(self.port_server, auth)
            logger.debug(f'{self.class_name}: server has been created.')
            return True
        except Exception:
            return False

    def _send_message(self, recipient: str, content: str) -> bool:
        """Отправка сообщения к другому клиенту через сервер.
        Пытается отправить пока не получиться или пока есть сокет.

        Args:
            recipient (str): Получатель.
            content (str): Контент.

        Raises:
            zmq.ZMQError: Ошибка при отправки.

        Returns:
            bool: Результат.
        """
        if self._socket is None:
            return False
        try:
            with self._lock_socket:
                self._socket.send_multipart(
                        [recipient.encode(), content.encode()], 
                        flags=zmq.NOBLOCK
                    )
            return True
        except zmq.ZMQError as e:
            # закрыт сокет
            if e.errno == zmq.ENOTSOCK:
                self._stop_message()
            # сервер закрыл соединение или переполнен исходящий буфер
            if e.errno == zmq.EAGAIN:
                self._stop_message()
            return False
        except Exception:
            return False
    
    def _is_use_port(self) -> bool:
        """ Используется ли порт. """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(1)
                sock.bind(('0.0.0.0', int(self.port_server)))
                return False
        except Exception:
            return True

    def _ping_server(self) -> bool:
        """ Отправляет пинг на сервер. """
        return self._send_message(MailServer.SERVER_NAME, CommandsCode.PING)
    
    def _check_server(self):
        """ Пересоздание клиента в случае отключения. """        
        while self._is_start.is_set():
            try:
                if not self._server_started.is_set():
                    logger.debug(f'{self.class_name}: reconnecting to server...')
                    self._clear_clients()
                    self._in_queue.del_wait_key()
                    self._destroy_socket()
                    time.sleep(1)
                    self._once_start_client()
                    time.sleep(1)
                    res = self._connect_message()
                    if not res:
                        time.sleep(1)
                        continue
                    self._out_queue.to_queue()
                    self._server_started.set()
            except Exception as e:
                logger.error(_("{}: Непредвиденная ошибка - <{}>.").format(self.class_name, e), exc_info=True)
            time.sleep(2)
    
    def _pull_message(self):
        """ Цикл получения сообщений. """        
        while self._is_start.is_set():
            try:
                #  Принимать сообщение, только если работает сервер.
                self._server_started.wait()
                socks = dict(self._in_poll.poll(MailServer.INTERVAL_HEARTBEAT*2000))
                if socks.get(self._socket) == zmq.POLLIN:
                    sender, msg = self._socket.recv_multipart()
                    sender = sender.decode()
                    msg = msg.decode()
                    logger.debug(f'{self.class_name}: received message <{msg}> from "{sender or 'MailServer'}".')
                    if sender == MailServer.SERVER_NAME:
                        self._process_server_commands(msg)
                    else:
                        self._process_msg_client(msg, sender)
                else:
                    # истек таймаут получения сообщений
                    logger.debug(f'{self.class_name}: server disconnected.')
                    self._stop_message()
            except zmq.ZMQError as e:
                # закрыт сокет
                if e.errno == zmq.ENOTSOCK:
                    self._stop_message()
                    continue
                logger.error(f'{self.class_name}.recv: ZMQError - <{e}>. Errno - <{e.errno}>')
            except Exception as e:
                logger.error(
                        (_('{}: Ошибка в главном цикле получения сообщений. ').format(self.class_name) +
                        _('Контекст ошибки: <{}>. ').format(e)), exc_info=True
                    )
    
    def _mailer(self):
        """ Отправка сообщений из очереди. """
        while self._is_start.is_set():
            try:
                # Перед тем как отправлять сообщение клиент 
                # должен быть подключен и сервер запущен.
                self._server_started.wait()
                res = self._out_queue.get(timeout=1)
                if not res:
                    continue
                recipient, key = res[0].split('-')
                exist_client = self._check_client(recipient)
                if not exist_client:
                    # на ожидание
                    self._out_queue.put_waiting_queue(res[0])
                    self._out_queue.to_waiting_queue(f'{recipient}-')
                    continue
                msg = res[1]
                res = self._send_message(recipient, msg)
                if not res:
                    self._out_queue.put_waiting_queue(res[0])
            except Exception as e:
                logger.error(
                        (_('{}: Ошибка в цикле отправки сообщений. ').format(f'{self.class_name}-Mailer') +
                        _('Контекст ошибки: <{}>. ').format(e)), exc_info=True
                    )
    
    def _process_server_commands(self, msg: Union[bytes, str]):
        """Обработка уведомлений от команд сервера.

        Args:
            msg (bytes): Сообщение.
        """
        msg_cmd = MessageCommand.parse(msg)
        if CommandsCode.NOTIFY_NEW_CLIENT == msg_cmd.code:
            client = msg_cmd.data
            self._add_client(client)
            self._out_queue.to_queue(f'{client}-')
        elif CommandsCode.NOTIFY_DISCONNECT_CLIENT == msg_cmd.code:
            client = msg_cmd.data
            self._del_client(client)
            self._out_queue.to_waiting_queue(f'{client}-')
            self._in_queue.del_wait_key(f'{client}-')
        elif CommandsCode.NOTIFY_STOP_SERVER == msg_cmd.code:
            self._stop_message()
        elif CommandsCode.GET_CONNECTED_CLIENTS == msg_cmd.code:
            self._set_clients(msg_cmd.data)
            for client in self.clients:
                self._out_queue.to_queue(f'{client}-')
        elif CommandsCode.CONNECT_CLIENT == msg_cmd.code:
            self._set_clients(msg_cmd.data)
            self._out_queue.to_queue()
    
    def _process_msg_client(self, msg: str, sender: str):
        """Обработка сообщений от клиентов.

        Args:
            msg (bytes): Сообщение.
        """
        data = Message.parse(msg)
        # если сообщение не достигло противоположного клиента
        if sender == self.name_client:
            self._del_client(data.recipient)
            # на ожидание
            self._out_queue.put_waiting_queue(f'{data.recipient}-{data.key}')
            self._out_queue.to_waiting_queue(f'{data.recipient}-')
            self._in_queue.del_wait_key(f'{data.recipient}-')
            self._send_message(MailServer.SERVER_NAME, CommandsCode.GET_CONNECTED_CLIENTS)
            return None
        if data.type == TypeMessage.REPLY:
            # реакция на автоматический ответ, что сообщение доставлено
            self._out_queue.done(f'{data.sender}-{data.key}')
        elif data.type == TypeMessage.REQUEST:
            # пришло сообщение с другого клиента
            self._in_queue.put(
                    msg, 
                    key=f'{data.sender}-{data.key}', 
                    use_get_key=data.is_response
                )
            recipient = data.sender
            data_msg = Message(
                    key=data.key,
                    type=TypeMessage.REPLY,
                    wait_response=False,
                    is_response=True,
                    sender=self.name_client,
                    recipient=recipient,
                    content=''
                ).to_bytes()
            # отправляем автоматический ответ на пришедшее сообщение
            self._send_message(recipient, data_msg.decode())