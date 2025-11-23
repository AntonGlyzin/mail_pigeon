from typing import List, Optional, Dict, Protocol
from abc import ABC, abstractmethod


class BaseMailServer(Protocol):
    
    SERVER_NAME = ''
    
    @property
    def clients(self) -> Dict[str, int]:
        ...
    
    @property
    def clients_names(self) -> List[str]:
        ...
    
    @property
    def clients_wait_connect(self) -> List[str]:
        ...
    
    def add_client(self, client: str, time: int):
        """Добавление клиента для связи.

        Args:
            client (str): Клиент.
            time (int): Время добавление.
        """        
        ...
    
    def del_client(self, client: str):
        """Удаление клиента.

        Args:
            client (str): Клиент.
        """        
        ...
    
    def add_wait_client(self, client: str):
        """Добавление клиента в комнату ожиданий.

        Args:
            client (str): Клиент.
        """        
        ...
    
    def del_wait_client(self, client: str):
        """Удаление клиента из комнаты ожиданий.

        Args:
            client (str): Клиент.
        """        
        ...
    
    @abstractmethod
    def stop(self):
        """
            Завершение главного цикла.
        """
        ...

    @abstractmethod
    def send_message(
            self, recipient: str, sender: str, 
            msg: str, is_unknown_recipient: bool = False
        ) -> Optional[bool]:
        """Отправить сообщение получателю, если он есть в списке на сервере.

        Args:
            recipient (str): Получатель.
            sender (str): Отправитель.
            msg (str): Сообщение.
            is_unknown_recipient (bool, optional): Неизвестный получатель.

        Returns:
            Optional[bool]: Результат.
        """        
        ...


class Command(ABC):
    
    def __init__(self, server: BaseMailServer, client: str):
        self.server = server
        self.client = client

    @abstractmethod
    def run(self):
        """ 
            Команда запускаемая на сервере.
        """
        ...