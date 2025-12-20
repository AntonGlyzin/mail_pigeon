import zmq
import zmq.auth
import zmq.asyncio
import asyncio
import sys
import time
from typing import List, Optional, Dict, Union, Tuple
from pathlib import Path
import uuid
from mail_pigeon.exceptions import CommandCodeNotFound
from mail_pigeon.mail_server.commands import CommandsCode, MessageCommand
from mail_pigeon.async_server.commands import Commands
from mail_pigeon.translate import _
from mail_pigeon.utils import logger, Auth

if sys.platform == 'win32':
    # устанавливаем правильную политику event loop для ZMQ
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


class AsyncMailServer(object):
    """ Сервер с переадресацией сообщений. """
    
    INTERVAL_HEARTBEAT = 4
    
    SERVER_NAME = '' # должно остаться пустым
    
    def __init__(self, port: int = 5555, auth: Optional[Auth] = None):
        """
        Args:
            port (int, optional): Открытый порт для клиентов.
            auth (Auth, optional): аутентификация на основе открытого и закрытого ключа.
        """
        self.server_id = uuid.uuid4().hex
        self.class_name = self.__class__.__name__
        self._auth = auth
        self._clients: Dict[str, int] = {} # уже подключенные для получения сообщений
        self._clients_wait_connect = [] # ожидающие подключения
        self._port = port
        self._commands = Commands(self)
        self._is_start = asyncio.Event()
        self._is_start.set()
        self._heartbeat = asyncio.Event()
        self._heartbeat.set()
        self._lock = asyncio.Lock()
        self._context = zmq.asyncio.Context()
        self._lock_socket = asyncio.Lock()
        self._socket = self._context.socket(zmq.ROUTER)
        self._socket.setsockopt(zmq.IMMEDIATE, 1) # не буферизовать для неготовых
        self._socket.setsockopt(zmq.TCP_KEEPALIVE, 1) # отслеживать мертвое соединение
        self._socket.setsockopt(zmq.TCP_KEEPALIVE_IDLE, 15) # сек. начать проверку если нет активности
        self._socket.setsockopt(zmq.TCP_KEEPALIVE_INTVL, 10) # сек. повторная проверка
        self._socket.setsockopt(zmq.TCP_KEEPALIVE_CNT, 3) # количество проверок
        self._socket.setsockopt(zmq.HEARTBEAT_IVL, 10000) # милисек. сделать ping если нет трафика
        self._socket.setsockopt(zmq.HEARTBEAT_TIMEOUT, 20000) # если так и нет трафика или pong, то разрыв
        self._socket.setsockopt(zmq.LINGER, 100) # милисек. ждать при закрытии
        self._socket.setsockopt(zmq.ROUTER_MANDATORY, 1)  # знать об отключениях
        self._socket.setsockopt(zmq.ROUTER_HANDOVER, 1) # использовать одинаковые ID для переподплючения
        self._socket.setsockopt(zmq.MAXMSGSIZE, -1)  # снимаем ограничение на размер одного сообщения
        if self._auth:
            self._socket.setsockopt(zmq.CURVE_PUBLICKEY, self._auth.CURVE_PUBLICKEY)
            self._socket.setsockopt(zmq.CURVE_SECRETKEY, self._auth.CURVE_SECRETKEY)
            self._socket.setsockopt(zmq.CURVE_SERVER, True)
        self._socket.bind(f"tcp://*:{self._port}")
        self._poll_in = zmq.asyncio.Poller()
        self._poll_in.register(self._socket, zmq.POLLIN)
        self._server = asyncio.create_task(
                coro=self._run(), 
                name=self.class_name
            )
        self._server_heartbeat = asyncio.create_task(
                coro=self._heartbeat_clients(), 
                name=f'{self.class_name}-Heartbeat'
            )
    
    async def clients(self) -> Dict[str, int]:
        async with self._lock:
            return tuple(self._clients.items())

    async def clients_names(self) -> List[str]:
        async with self._lock:
            return list(self._clients.keys())

    async def clients_wait_connect(self) -> List[str]:
        return list(self._clients_wait_connect)
    
    async def add_client(self, client: str, time: int):
        """Добавление клиента для связи.

        Args:
            client (str): Клиент.
            time (int): Время добавление.
        """        
        async with self._lock:
            self._clients[client] = time
    
    async def update_time_client(self, client: str, time: int):
        """Обновления времени клиента.

        Args:
            client (str): Клиент.
            time (int): Время добавление.
        """
        async with self._lock:
            if client in self._clients:
                self._clients[client] = time
    
    async def del_client(self, client: str):
        """Удаление клиента.

        Args:
            client (str): Клиент.
        """        
        async with self._lock:
            if client in self._clients:
                self._clients.pop(client)
    
    async def add_wait_client(self, client: str):
        """Добавление клиента в комнату ожиданий.

        Args:
            client (str): Клиент.
        """        
        async with self._lock:
            if client not in self._clients_wait_connect:
                self._clients_wait_connect.append(client)
    
    async def del_wait_client(self, client: str):
        """Удаление клиента из комнаты ожиданий.

        Args:
            client (str): Клиент.
        """        
        async with self._lock:
            if client in self._clients_wait_connect:
                self._clients_wait_connect.remove(client)

    async def stop(self):
        """
            Завершение работы сервера.
        """
        names = await self.clients_names()
        for client in names:
            data = MessageCommand(CommandsCode.NOTIFY_STOP_SERVER).to_bytes()
            await self.send_message(client, self.SERVER_NAME, data)
        await asyncio.sleep(.1)
        self._close_socket()

    async def send_message(
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
            async with self._lock:
                if not is_unknown_recipient and recipient not in self._clients.keys():
                    return False
            if isinstance(recipient, str):
                recipient = recipient.encode()
            if isinstance(sender, str):
                sender = sender.encode()
            if isinstance(msg, str):
                msg = msg.encode()
            async with self._lock_socket:
                await self._socket.send_multipart(
                    [recipient, sender, msg], 
                    flags=zmq.NOBLOCK
                )
            return True
        except zmq.ZMQError as e:
            logger.error(
                    _('{}: Не удалось переадресовать сообщение. ').format(self.class_name) +
                    _('Отправитель: <{}>. Получатель: <{}>.').format(sender, recipient)
                )
        except Exception as e:
            logger.error(_("{}: Непредвиденная ошибка - <{}>.").format(self.class_name, e), exc_info=True)
        return False
    
    def __del__(self):
        self._close_socket()
    
    @classmethod
    def generate_keys(cls, cert_dir: Optional[Path] = None) -> Optional[Tuple[bytes, bytes]]:
        """Генерирует пару ключей или выдает существующие из директории.

        Args:
            cert_dir (Optional[Path], optional): Путь до директории.

        Returns:
            Optional[Tuple[str, str]]: Пара ключей public_key, secret_key.
        """        
        if not cert_dir:
            return None
        if not cert_dir.exists():
            cert_dir.mkdir(exist_ok=True)
        cert = cert_dir / 'server.key_secret'
        if not cert.exists():
            zmq.auth.create_certificates(cert_dir, 'server')
        return zmq.auth.load_certificate(cert)
    
    def _close_socket(self):
        """ Закрытие сокета. """        
        self._is_start.clear()
        self._heartbeat.clear()
        self._clients.clear()
        self._clients_wait_connect.clear()
        try:
            if self._poll_in:
                self._poll_in.unregister(self._socket)
            self._poll_in = None
        except Exception as e:
            logger.debug(f'{self.class_name}: closing the socket. Error <{e}>.')
        try:
            if self._socket:
                self._socket.close()
            self._socket = None
        except Exception as e:
            logger.debug(f'{self.class_name}: closing the socket. Error <{e}>.')
        try:
            if self._context:
                self._context.term()
            self._context = None
        except Exception as e:
            logger.debug(f'{self.class_name}: destroy the socket. Error <{e}>.')
    
    async def _heartbeat_clients(self):
        """В случае просроченного понга от клиента, 
        удаляет его из списка и поссылает другим участникам о его уходе.
        """        
        while self._heartbeat.is_set():
            try:
                current_time = int(time.time())
                lost_clients = []
                async with self._lock:
                    for client, t in self._clients.items():
                        # отключение клиента на 12 секунде
                        if self.INTERVAL_HEARTBEAT*3 <= (current_time - t):
                            lost_clients.append(client)
                for client in lost_clients:
                    code = CommandsCode.DISCONNECT_CLIENT
                    await self._commands.run_command(client, code)
            except asyncio.CancelledError:
                logger.debug(f'{self.class_name}: cancelled error is <._heartbeat_clients> method.')
                break
            except zmq.ZMQError as e:
                if str(e) == 'not a socket':
                    self._close_socket()
            except Exception as e:
                logger.error(
                        _("{}: Непредвиденная ошибка <{}> в мониторинге.").format(self.class_name, str(e)), 
                        exc_info=True
                    )
            await asyncio.sleep(2)

    async def _run(self):
        """ Главный цикл получения сообщений. """
        while self._is_start.is_set():
            try:
                socks = await self._poll_in.poll()
                if dict(socks).get(self._socket) == zmq.POLLIN:
                    data = await self._socket.recv_multipart(flags=zmq.DONTWAIT)
                    if not data:
                        continue
                    logger.debug(f'{self.class_name}: received message <{data}>.')
                    await self._message_processing(data)
            except asyncio.CancelledError:
                logger.debug(f'{self.class_name}: cancelled error is <._run> method.')
                break
            except zmq.ZMQError as e:
                if str(e) == 'not a socket':
                    self._close_socket()
                    continue
                logger.error(_("{}: ZMQ ошибка <{}> в цикле обработки сообщений.").format(self.class_name, e))
            except Exception as e:
                logger.error(
                        _('{}: Ошибка в цикле обработке сообщений. ').format(self.class_name) +
                        _('Контекст ошибки: <{}>. ').format(e), 
                        exc_info=True
                    )

    async def _message_processing(self, data: List[bytes]) -> Optional[bool]:
        """Обработчик сообщений.

        Args:
            data (List[bytes]): Список данных из сокета.

        Returns:
            Optional[bool]: Результат.
        """
        if len(data) < 3:
            return False
        sender = data[0].decode()
        recipient = data[1].decode()
        msg = data[2].decode()
        # если нет получателя, то это команда для сервера
        if not recipient:
            res = await self._run_commands(sender, msg)
            return res
        # клиент отправил сообщение - значит на этот момент он еще жив
        await self.update_time_client(sender, int(time.time()))
        # отправляем получателю
        res = await self.send_message(recipient, sender, msg)
        if res:
            return True
        else:
            # отправляем обратно
            await self.send_message(sender, sender, msg)
            return False

    async def _run_commands(self, sender: str, code: str) -> Optional[bool]:
        """Запуск команд сервера.

        Args:
            sender (str): Отправитель команды.
            command (str): Команда.

        Returns:
            Optional[bool]: Результат.
        """        
        try:
            logger.debug(f'{self.class_name}: run command <{code}> for {sender}.')
            await self._commands.run_command(sender, code)
            return True
        except CommandCodeNotFound as e:
            logger.warning(
                f'{self.class_name}: {e}. ' +
                _('Отправитель: <{}>. ').format(sender)
            )
        except Exception as e:
            logger.error(
                _('{}: Не удалось выполнить команду - <{}>. ').format(self.class_name, code) +
                _('Отправитель: <{}>. ').format(sender) +
                _('Контекст ошибки: <{}>.').format(e), 
                exc_info=True
            )
        return False