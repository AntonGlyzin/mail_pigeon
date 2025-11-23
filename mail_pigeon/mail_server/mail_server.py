import zmq
import time
from typing import List, Optional, Dict, Union
from threading import Thread, Event, RLock
from mail_pigeon.exceptions import CommandCodeNotFound
from mail_pigeon.mail_server.base import BaseMailServer
from mail_pigeon.mail_server.commands import Commands, CommandsCode, MessageCommand
from mail_pigeon.translate import _
from mail_pigeon import logger


class MailServer(BaseMailServer):
    """ Сервер с переадресацией сообщений. """
    
    INTERVAL_HEARTBEAT = 4
    
    def __init__(self, port: int = 5555):
        """
        Args:
            port (int, optional): Открытый порт для клиентов.
        """        
        self.class_name = self.__class__.__name__
        self._clients: Dict[str, int] = {} # уже подключенные для получения сообщений
        self._clients_wait_connect = [] # ожидающие подключения
        self._port = port
        self._commands = Commands(self)
        self._is_start = Event()
        self._is_start.set()
        self._heartbeat = Event()
        self._heartbeat.set()
        self._rlock = RLock()
        self._context = zmq.Context()
        self._socket = self._context.socket(zmq.ROUTER)
        self._socket.setsockopt(zmq.TCP_KEEPALIVE, 1)
        self._socket.setsockopt(zmq.IMMEDIATE, 1)
        self._port = port
        self._socket.bind(f"tcp://*:{self._port}")
        self._poll_in = zmq.Poller()
        self._poll_in.register(self._socket, zmq.POLLIN)
        self._server = Thread(
                target=self._run, 
                name=self.class_name, 
                daemon=True
            )
        self._server.start()
        self._server_heartbeat = Thread(
                target=self._heartbeat_clients, 
                name=f'{self.class_name}-Heartbeat', 
                daemon=True
            )
        self._server_heartbeat.start()
    
    @property
    def clients(self) -> Dict[str, int]:
        with self._rlock:
            return tuple(self._clients.items())

    @property
    def clients_names(self) -> List[str]:
        with self._rlock:
            return list(self._clients.keys())

    @property
    def clients_wait_connect(self) -> List[str]:
        with self._rlock:
            return list(self._clients_wait_connect)
    
    def add_client(self, client: str, time: int):
        """Добавление клиента для связи.

        Args:
            client (str): Клиент.
            time (int): Время добавление.
        """        
        with self._rlock:
            self._clients[client] = time
    
    def del_client(self, client: str):
        """Удаление клиента.

        Args:
            client (str): Клиент.
        """        
        with self._rlock:
            if client in self._clients:
                self._clients.pop(client)
    
    def add_wait_client(self, client: str):
        """Добавление клиента в комнату ожиданий.

        Args:
            client (str): Клиент.
        """        
        with self._rlock:
            if client not in self._clients_wait_connect:
                self._clients_wait_connect.append(client)
    
    def del_wait_client(self, client: str):
        """Удаление клиента из комнаты ожиданий.

        Args:
            client (str): Клиент.
        """        
        with self._rlock:
            if client in self._clients_wait_connect:
                self._clients_wait_connect.remove(client)

    def stop(self):
        """
            Завершение работы сервера.
        """
        for client in self.clients_names:
            data = MessageCommand(CommandsCode.NOTIFY_STOP_SERVER).to_bytes()
            self.send_message(client, self.SERVER_NAME, data)
        time.sleep(.1)
        self._close_socket()

    def send_message(
            self, recipient: Union[str, bytes], sender: Union[str, bytes], 
            msg: Union[str, bytes], is_unknown_recipient: bool = False
        ) -> Optional[bool]:
        """Отправить сообщение получателю, если он есть в списке на сервере.

        Args:
            recipient (str): Получатель.
            sender (str): Отправитель.
            msg (str): Сообщение.
            is_unknown_recipient (bool, optional): Неизвестный получатель.

        Returns:
            res (Optional[bool]): Результат.
        """        
        try:
            if not is_unknown_recipient and recipient not in self.clients_names:
                return False
            if isinstance(recipient, str):
                recipient = recipient.encode()
            if isinstance(sender, str):
                sender = sender.encode()
            if isinstance(msg, str):
                msg = msg.encode()
            self._socket.send_multipart(
                [recipient, sender, msg], 
                flags=zmq.NOBLOCK
            )
            return True
        except zmq.Again:
            logger.error(
                _('{}: Не удалось переадресовать сообщение. ').format(self.class_name) +
                _('Отправитель: "{}". Получатель: "{}".').format(sender, recipient)
            )
        except zmq.ZMQError as e:
            logger.error(_("{}: ZMQ ошибка при отправки сообщения: {}").format(self.class_name, e))
        except zmq.ContextTerminated:
            logger.error(_("{}: Контекст ZMQ завершен при отправки сообщения.").format(self.class_name))
        except Exception as e:
            logger.error(_("{}: Непредвиденная ошибка: {}").format(self.class_name, e), exc_info=True)
        return False
    
    def __del__(self):
        self._close_socket()
    
    def _close_socket(self):
        """ Закрытие сокета. """        
        self._is_start.clear()
        self._heartbeat.clear()
        self._clients.clear()
        self._clients_wait_connect.clear()
        try:
            self._poll_in.unregister(self._socket)
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
    
    def _heartbeat_clients(self):
        """В случае просроченного понга от клиента, 
        удаляет его из списка и поссылает другим участникам о его уходе.
        """        
        while self._heartbeat.is_set():
            try:
                current_time = int(time.time())
                for client, t in self.clients:
                    if self.INTERVAL_HEARTBEAT*2 < (current_time - t):
                        code = CommandsCode.DISCONNECT_CLIENT
                        self._commands.run_command(client, code)
            except zmq.ZMQError as e:
                if str(e) == 'not a socket':
                    self._close_socket()
            except Exception as e:
                logger.error(
                        _("{}: Непредвиденная ошибка в мониторинге: {}").format(self.class_name, str(e)), 
                        exc_info=True
                    )
            time.sleep(1)

    def _run(self):
        """ Главный цикл получения сообщений. """
        while self._is_start.is_set():
            try:
                socks = dict(self._poll_in.poll())
                if socks.get(self._socket) == zmq.POLLIN:
                    data = self._socket.recv_multipart(flags=zmq.DONTWAIT)
                    if not data:
                        continue
                    logger.debug(f'{self.class_name}: received message <{data}>.')
                    self._message_processing(data)
            except zmq.ZMQError as e:
                if str(e) == 'not a socket':
                    self._close_socket()
                    continue
                logger.error(_("{}: ZMQ ошибка '{}' в цикле обработки сообщений.").format(self.class_name, e))
            except zmq.ContextTerminated:
                logger.error(_("{}: Контекст ZMQ завершен при обработке сообщений.").format(self.class_name))
            except Exception as e:
                logger.error(
                        _('{}: Ошибка в цикле обработке сообщений. ').format(self.class_name) +
                        _('Контекст ошибки: "{}". ').format(e), 
                        exc_info=True
                    )

    def _message_processing(self, data: List[bytes]) -> Optional[bool]:
        """Обработчик сообщений.

        Args:
            data (List[bytes]): Список данных из сокета.

        Returns:
            Optional[bool]: Результат.
        """
        if len(data) < 3:
            return False
        sender = data.pop(0).decode()
        recipient = data.pop(0).decode()
        msg = data.pop(0).decode()
        # если нет получателя, то это команда для сервера
        if not recipient:
            return self._run_commands(sender, msg)
        if self.send_message(recipient, sender, msg):
            return True
        try:
            # Если такого клиента нет,
            # то нужно отправить обратно отправителю
            # с указанием на самого себя.
            self._socket.send_multipart(
                [sender, sender, msg], 
                flags=zmq.NOBLOCK
            )
            return True
        except zmq.ZMQError:
            logger.error(
                _('{}: Не удалось отправить обратно сообщение. ').format(self.class_name) +
                _('Отправитель: "{}".').format(sender)
            )
        return False

    def _run_commands(self, sender: str, code: str) -> Optional[bool]:
        """Запуск команд сервера.

        Args:
            sender (str): Отправитель команды.
            command (str): Команда.

        Returns:
            Optional[bool]: Результат.
        """        
        try:
            logger.debug(f'{self.class_name}: run command <{code}> for {sender}.')
            self._commands.run_command(sender, code)
            return True
        except CommandCodeNotFound as e:
            logger.warning(
                f'{self.class_name}: {e}. ' +
                _('Отправитель: "{}". ').format(sender)
            )
        except Exception as e:
            logger.error(
                _('{}: Не удалось выполнить команду "{}". ').format(self.class_name, code) +
                _('Отправитель: "{}". ').format(sender) +
                _('Контекст ошибки: "{}".').format(e), 
                exc_info=True
            )
        return False