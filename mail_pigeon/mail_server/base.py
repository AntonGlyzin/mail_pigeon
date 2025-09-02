from typing import List, Optional, Dict
from abc import ABC, abstractmethod


class BaseMailServer(ABC):
    
    SERVER_NAME = b''
    
    @property
    def clients(self) -> Dict[bytes, int]:
        ...
    
    @property
    def clients_names(self) -> List[bytes]:
        ...
    
    @property
    def clients_wait_connect(self) -> List[bytes]:
        ...
    
    @abstractmethod
    def stop(self):
        """
            Завершение главного цикла.
        """
        ...

    @abstractmethod
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
            Optional[bool]: Результат.
        """        
        ...


class Command(ABC):
    
    def __init__(self, server: BaseMailServer, client: bytes):
        self.server = server
        self.client = client

    @abstractmethod
    def run(self):
        """ 
            Команда запускаемая на ссервере.
        """
        ...