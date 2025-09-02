import zmq
import time
from typing import List, Optional, Dict
from threading import Thread, Event, RLock
from mail_pigeon.exceptions import CommandCodeNotFound
from mail_pigeon.mail_server.base import BaseMailServer
from mail_pigeon.mail_server.commands import Commands, CommandsCode, MessageCommand
from mail_pigeon.translate import _
from mail_pigeon import logger


class MailServer(BaseMailServer):
    """
        Сервер с переадресацией сообщений.
    """
    
    INTERVAL_HEARTBEAT = 4
    
    def __init__(self, port: int = 5555):
        """
        Args:
            port (int, optional): Открытый порт для клиентов.
        """        
        self.class_name = self.__class__.__name__
        self._clients: Dict[bytes, int] = {} # уже подключенные для получения сообщений
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
        self._server = Thread(target=self._run, name=self.class_name, daemon=True)
        self._server.start()
        self._server_heartbeat = Thread(
                target=self._heartbeat_clients, 
                name=f'{self.class_name}-Heartbeat', daemon=True
            )
        self._server_heartbeat.start()
    
    @property
    def clients(self) -> Dict[bytes, int]:
        return self._clients

    @property
    def clients_names(self) -> List[bytes]:
        return [*self._clients.keys()]

    @property
    def clients_wait_connect(self) -> List[bytes]:
        return self._clients_wait_connect

    def stop(self):
        """
            Завершение работы сервера.
        """
        for client in self.clients_names:
            data = MessageCommand(CommandsCode.NOTIFY_STOP_SERVER, b'').to_bytes()
            self.send_message(client, self.SERVER_NAME, data)
        self._is_start.clear()
        self._heartbeat.clear()
        with self._rlock:
            self._clients.clear()
            self._clients_wait_connect.clear()
            self._poll_in.unregister(self._socket)
            self._socket.close()
            self._context.destroy()
            self._context.term()

    def send_message(
            self, recipient: bytes, sender: bytes, 
            msg: bytes, is_unknown_recipient: bool = False
        ) -> Optional[bool]:
        """Отправить сообщение получателю, если он есть в списке на сервере.

        Args:
            recipient (bytes): Получатель.
            sender (bytes): Отправитель.
            msg (bytes): Сообщение.
            is_unknown_recipient (bool, optional): Неизвестный получатель.

        Returns:
            res (Optional[bool]): Результат.
        """        
        try:
            if not is_unknown_recipient and recipient not in self.clients:
                return False
            self._socket.send_multipart(
                [recipient, sender, msg], flags=zmq.NOBLOCK
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

    def _heartbeat_clients(self):
        """
            Генерирует пинги для клиентов. 
            В случае просроченного понга, удаляет клиента из списка клиентов.
        """        
        while self._heartbeat.is_set():
            try:
                time.sleep(self.INTERVAL_HEARTBEAT)
                with self._rlock:
                    current_time = int(time.time())
                    for client in self.clients_names:
                        t = self.clients[client]
                        if self.INTERVAL_HEARTBEAT*2 < (current_time - t):
                            code = CommandsCode.DISCONNECT_CLIENT
                            self._commands.run_command(client, code)
                            continue
                        code = CommandsCode.NOTIFY_PING_CLIENT
                        data = MessageCommand(code, b'').to_bytes()
                        self.send_message(client, self.SERVER_NAME, data)
            except zmq.ZMQError as e:
                if str(e) == 'not a socket':
                    self._heartbeat.clear()
                    continue
            except Exception as e:
                logger.error(
                        _("{}: Непредвиденная ошибка в мониторинге: {}").format(self.class_name, str(e)), 
                        exc_info=True
                    )

    def _run(self):
        """
            Главный цикл получения сообщений.
        """
        while self._is_start.is_set():
            try:
                socks = dict(self._poll_in.poll())
                with self._rlock:
                    if socks.get(self._socket) == zmq.POLLIN:
                        data = self._socket.recv_multipart(flags=zmq.DONTWAIT)
                        logger.debug(f'{self.class_name}.recv: {data}')
                        self._message_processing(data)
            except zmq.ZMQError as e:
                if str(e) == 'not a socket':
                    self._is_start.clear()
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
        sender = data.pop(0)
        recipient = data.pop(0)
        msg = data.pop(0)
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
                [sender, sender, msg], flags=zmq.NOBLOCK
            )
            return True
        except zmq.Again:
            logger.error(
                _('{}: Не удалось отправить обратно сообщение. ').format(self.class_name) +
                _('Отправитель: "{}".').format(sender)
            )
        return False

    def _run_commands(self, sender: bytes, code: bytes) -> Optional[bool]:
        """Запуск команд сервера.

        Args:
            sender (bytes): Отправитель команды.
            command (bytes): Команда.

        Returns:
            Optional[bool]: Результат.
        """        
        try:
            self._commands.run_command(sender, code)
            return True
        except CommandCodeNotFound as e:
            logger.warning(
                f'{self.class_name}: {e}. ' +
                _('Отправитель: "{}". ').format(sender.decode())
            )
        except Exception as e:
            logger.error(
                _('{}: Не удалось выполнить команду "{}". ').format(self.class_name, code.decode()) +
                _('Отправитель: "{}". ').format(sender.decode()) +
                _('Контекст ошибки: "{}".').format(e), 
                exc_info=True
            )
        return False