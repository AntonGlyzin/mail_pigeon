from __future__ import annotations
import time
from typing import Type, TYPE_CHECKING
from abc import ABC, abstractmethod
from mail_pigeon.exceptions import CommandCodeNotFound
from mail_pigeon.mail_server.commands import CommandsCode, MessageCommand

if TYPE_CHECKING:
    from mail_pigeon.async_server.mail_server import AsyncMailServer


class Command(ABC):
    
    def __init__(self, server: AsyncMailServer, client: str):
        self.server = server
        self.client = client

    @abstractmethod
    async def run(self): ...


class ConnectClient(Command):
    """
        Добавляет клиента в комнату ожиданий подключения.
    """    
    
    code = CommandsCode.CONNECT_CLIENT
    
    async def run(self):
        """
            Добавляет клиента в список ожидающих 
            пока он не подтвердит свое присутствие.
        """
        await self.server.add_wait_client(self.client)
        # отдать подключаемому клиенту список участников
        names = await self.server.clients_names()
        data = MessageCommand(self.code, names).to_bytes()
        await self.server.send_message(self.client, self.server.SERVER_NAME, data, True)


class ConfirmConnection(Command):
    """
        Подтверждение подключения от клиента.
    """    
    
    code = CommandsCode.CONFIRM_CONNECT
    
    async def run(self):
        """
            Подтверждение от клиента, что он присоединился.
            Посылаем оповещение другим клиентам.
        """
        await self.server.del_wait_client(self.client)
        await self.server.add_client(self.client,  int(time.time()))
        data = MessageCommand(CommandsCode.CONFIRM_CONNECT).to_bytes()
        await self.server.send_message(self.client, self.server.SERVER_NAME, data)
        names = await self.server.clients_names()
        for client in names:
            if client == self.client:
                continue
            data = MessageCommand(CommandsCode.NOTIFY_NEW_CLIENT, self.client).to_bytes()
            await self.server.send_message(client, self.server.SERVER_NAME, data)


class DisconnectClient(Command):
    """
        Разрывает логическое соединение клиента с сервером.
    """ 
    
    code = CommandsCode.DISCONNECT_CLIENT
    
    async def run(self):
        """
            Удаляет клиента из списка и посылает уведомление другим участникам.
        """
        await self.server.del_wait_client(self.client)
        await self.server.del_client(self.client)
        names = await self.server.clients_names()
        for client in names:
            if client == self.client:
                continue
            data = MessageCommand(CommandsCode.NOTIFY_DISCONNECT_CLIENT, self.client).to_bytes()
            await self.server.send_message(client, self.server.SERVER_NAME, data)


class GetConnectedClients(Command):
    """
        Отправляет клиенту список участников.
    """ 
    
    code = CommandsCode.GET_CONNECTED_CLIENTS
    
    async def run(self):
        """
            Отправляет подключеному клиенту список участников.
        """
        names = await self.server.clients_names()
        data = MessageCommand(self.code, names).to_bytes()
        await self.server.send_message(self.client, self.server.SERVER_NAME, data)


class PingServer(Command):
    """
        Ping от клиента.
    """ 
    
    code = CommandsCode.PING
    
    async def run(self):
        """
            Обработка сигнала от клиента что он еще жив.
        """
        names = await self.server.clients_names()
        for client in names:
            if client == self.client:
                await self.server.add_client(client, int(time.time()))
        if self.client not in names:
            connect = ConnectClient(self.server, self.client)
            await connect.run()
        data = MessageCommand(CommandsCode.PONG).to_bytes()
        await self.server.send_message(self.client, self.server.SERVER_NAME, data, True)


class Commands(object):
    
    CMD = {
        ConnectClient.code: ConnectClient, # клиент присоединяется
        ConfirmConnection.code: ConfirmConnection, # клиент подтверждает соединение
        DisconnectClient.code: DisconnectClient, # клиент отсоединяется
        GetConnectedClients.code: GetConnectedClients, # клиент запрашивает список участников
        PingServer.code: PingServer # ping от клиента для сервера
    }
    
    def __init__(self, server: AsyncMailServer):
        self._server = server
    
    async def run_command(self, sender: str, code: str) -> Type[Command]:
        """Запуск команды.

        Args:
            sender (str): Отправитель.
            code (str): Код.

        Raises:
            CommandCodeNotFound: Команда не найдена.
        """        
        cmd: Type[Command] = self.CMD.get(code)
        if not cmd:
            raise CommandCodeNotFound(code)
        await cmd(self._server, sender).run()