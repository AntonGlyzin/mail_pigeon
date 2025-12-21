from __future__ import annotations
import time
import json
from abc import ABC, abstractmethod
from typing import Type, Any, TYPE_CHECKING, Union, Dict, Optional
from dataclasses import dataclass, asdict
from mail_pigeon.exceptions import CommandCodeNotFound

if TYPE_CHECKING:
    from mail_pigeon.mail_server.mail_server import MailServer


class Command(ABC):
    
    def __init__(self, server: MailServer, client: str):
        self.server = server
        self.client = client

    @abstractmethod
    def run(self): ...


@dataclass
class MessageCommand:
    code: str
    data: Any = None
    
    def to_bytes(self) -> bytes:
        return json.dumps(asdict(self)).encode()
    
    @classmethod
    def parse(cls, msg: Union[bytes, str]) -> MessageCommand:
        return cls(**json.loads(msg))


@dataclass
class CommandsCode:
    CONNECT_CLIENT = 'connect' # клиент отправляет команду когда соединяется
    CONFIRM_CONNECT = 'confirm' # клиент подтверждает соединение
    DISCONNECT_CLIENT = 'disconnect' # клиент хочет отсоединиться
    GET_CONNECTED_CLIENTS = 'get_clients' # клиент запрашивает список участников
    NOTIFY_NEW_CLIENT = 'new_client' # событие от сервера для клиента о новом подключение
    NOTIFY_DISCONNECT_CLIENT = 'disconnect_client' # событие от сервера для клиента об ушедшем клиенте
    PING = 'ping' # ping от клиента для сервера
    PONG = 'pong' # pong от сервера
    NOTIFY_STOP_SERVER = 'stop_server' # событие от сервера


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
        self.server.add_wait_client(self.client)
        # отдать подключаемому клиенту список участников
        data = MessageCommand(self.code, self.server.clients_names).to_bytes()
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
        self.server.del_wait_client(self.client)
        self.server.add_client(self.client,  int(time.time()))
        data = MessageCommand(CommandsCode.CONFIRM_CONNECT).to_bytes()
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
        self.server.del_wait_client(self.client)
        self.server.del_client(self.client)
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
            Отправляет подключеному клиенту список участников.
        """
        data = MessageCommand(self.code, self.server.clients_names).to_bytes()
        self.server.send_message(self.client, self.server.SERVER_NAME, data)


class PingServer(Command):
    """
        Ping от клиента.
    """ 
    
    code = CommandsCode.PING
    
    def run(self):
        """
            Обработка сигнала от клиента что он еще жив.
        """
        for client in self.server.clients_names:
            if client == self.client:
                self.server.add_client(client, int(time.time()))
        if self.client not in self.server.clients_names:
            ConnectClient(self.server, self.client).run()
        data = MessageCommand(CommandsCode.PONG).to_bytes()
        self.server.send_message(self.client, self.server.SERVER_NAME, data, True)


class Commands(object):
    
    CMD: Dict[str, Type[Command]] = {
        ConnectClient.code: ConnectClient, # клиент присоединяется
        ConfirmConnection.code: ConfirmConnection, # клиент подтверждает соединение
        DisconnectClient.code: DisconnectClient, # клиент отсоединяется
        GetConnectedClients.code: GetConnectedClients, # клиент запрашивает список участников
        PingServer.code: PingServer # ping от клиента для сервера
    }
    
    def __init__(self, server: MailServer):
        self._server = server
    
    def run_command(self, sender: str, code: str):
        """Запуск команды.

        Args:
            sender (str): Отправитель.
            code (str): Код.

        Raises:
            CommandCodeNotFound: Команда не найдена.
        """        
        cmd: Optional[Type[Command]] = self.CMD.get(code)
        if not cmd:
            raise CommandCodeNotFound(code)
        cmd(self._server, sender).run()