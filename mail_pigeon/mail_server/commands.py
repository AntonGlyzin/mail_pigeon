import time
from typing import List, Type
from dataclasses import dataclass
from mail_pigeon.mail_server.base import Command, BaseMailServer
from mail_pigeon.exceptions import CommandCodeNotFound


@dataclass
class MessageCommand:
    code: bytes
    data: bytes
    
    def to_bytes(self) -> bytes:
        code = self.code.decode()
        data = self.data.decode()
        return f'{code}:{data}'.encode()
    
    @classmethod
    def parse(cls, msg: bytes) -> 'MessageCommand':
        msg: List[str] = msg.decode().split(':')
        return cls(msg[0].encode(), msg[1].encode())


@dataclass
class CommandsCode:
    CONNECT_CLIENT = b'connect' # клиент отправляет команду когда соединяется
    CONFIRM_CONNECT = b'confirm' # клиент подтверждает соединение
    DISCONNECT_CLIENT = b'disconnect' # клиент хочет отсоединиться
    GET_CONNECTED_CLIENTS = b'get_clients' # клиент запрашивает список подключенных клиентов
    NOTIFY_NEW_CLIENT = b'new_client' # событие от сервера для клиента о новом клиенте
    NOTIFY_DISCONNECT_CLIENT = b'disconnect_client' # событие от сервера для клиента об ушедшем клиенте
    NOTIFY_PING_CLIENT = b'ping_client' # событие от сервера для клиента
    PONG_SERVER = b'pong_server' # pong от клиента для сервера
    NOTIFY_STOP_SERVER = b'stop_server' # событие от сервера
    ECHO_SERVER = b'echo_server' # запрос серверу от клиента


class ConnectClient(Command):
    """
        Добавляет клиента в комнату ожиданий подключения.
    """    
    
    code = CommandsCode.CONNECT_CLIENT
    
    def run(self):
        """
            Добавляет клиента в список ожидающих 
            пока он не подтвердит свое присутствие.
        """        
        if self.client in self.server.clients:
            return True
        if self.client not in self.server.clients_wait_connect:
            self.server.clients_wait_connect.append(self.client)
        # отдать подключаемому клиенту список участников
        data = MessageCommand(self.code, str(self.server.clients_names).encode()).to_bytes()
        self.server.send_message(self.client, self.server.SERVER_NAME, data, True)


class ConfirmConnection(Command):
    """
        Подтверждение подключения от клиента.
    """    
    
    code = CommandsCode.CONFIRM_CONNECT
    
    def run(self):
        """
            Подтверждение от клиента, что он присоединился.
            Посылаем оповещение другим клиентам.
        """
        if self.client in self.server.clients_wait_connect:
            self.server.clients_wait_connect.remove(self.client)
        self.server.clients[self.client] = int(time.time())
        data = MessageCommand(CommandsCode.CONFIRM_CONNECT, b'').to_bytes()
        self.server.send_message(self.client, self.server.SERVER_NAME, data)
        for client in self.server.clients_names:
            if client == self.client:
                continue
            data = MessageCommand(CommandsCode.NOTIFY_NEW_CLIENT, self.client).to_bytes()
            self.server.send_message(client, self.server.SERVER_NAME, data)


class DisconnectClient(Command):
    """
        Разрывает логическое соединение клиента с сервером.
    """ 
    
    code = CommandsCode.DISCONNECT_CLIENT
    
    def run(self):
        """
            Удаляет клиента из списка и посылает уведомление другим участникам.
        """
        if self.client in self.server.clients_wait_connect:
            self.server.clients_wait_connect.remove(self.client)
        if self.client in self.server.clients:
            self.server.clients.pop(self.client)
        for client in self.server.clients_names:
            if client == self.client:
                continue
            data = MessageCommand(CommandsCode.NOTIFY_DISCONNECT_CLIENT, self.client).to_bytes()
            self.server.send_message(client, self.server.SERVER_NAME, data)


class GetConnectedClients(Command):
    """
        Отправляет клиенту список участников.
    """ 
    
    code = CommandsCode.GET_CONNECTED_CLIENTS
    
    def run(self):
        """
            Отправляет подключеннуму клиенту список участников.
        """
        data = MessageCommand(
                self.code, str(self.server.clients_names).encode()
            ).to_bytes()
        self.server.send_message(
            self.client, self.server.SERVER_NAME, data
        )


class PongServer(Command):
    """
        Pong от клиента.
    """ 
    
    code = CommandsCode.PONG_SERVER
    
    def run(self):
        """
            Обработка сигнала от клиента что он еще жив.
        """
        for client in self.server.clients_names:
            if client == self.client:
                self.server.clients[client] = int(time.time())


class EchoServer(Command):
    """
        Пинг серверу от клиента.
    """ 
    
    code = CommandsCode.ECHO_SERVER
    
    def run(self):
        """
            Отправить клиенту что сервер работает.
        """
        data = MessageCommand(self.code, b'').to_bytes()
        self.server.send_message(self.client, self.server.SERVER_NAME, data, True)


class Commands(object):
    
    CMD = {
        ConnectClient.code: ConnectClient,
        ConfirmConnection.code: ConfirmConnection,
        DisconnectClient.code: DisconnectClient,
        GetConnectedClients.code: GetConnectedClients,
        EchoServer.code: EchoServer,
        PongServer.code: PongServer
    }
    
    def __init__(self, server: BaseMailServer):
        self._server = server
    
    def run_command(
            self, sender: bytes, code: bytes
        ) -> Type[Command]:
        """Запуск команды.

        Args:
            sender (bytes): Отправитель.
            code (bytes): Код.

        Raises:
            CommandCodeNotFound: Команда не найдена.
        """        
        cmd: Type[Command] = self.CMD.get(code)
        if not cmd:
            raise CommandCodeNotFound(code)
        cmd(self._server, sender).run()