from abc import ABC, abstractmethod


class IEncryptor(ABC):
    
    def __init__(self, secret_word: str):
        """
        Args:
            secret_word (str): Секретное слово для шифрования.
        """        
        self.secret_word = secret_word
    
    @abstractmethod
    def encrypt(self, message: bytes) -> bytes:
        """Шифрует сообщение.

        Args:
            message (bytes): Сообщение.

        Returns:
            bytes: Защифрованное сообщение.
        """        
        ...
    
    @abstractmethod
    def decrypt(self, encrypted: bytes) -> bytes:
        """Расшифровывает сообщение.

        Args:
            encrypted (bytes): Зашифрованное сообщение.

        Returns:
            bytes: Сообщение.
        """        
        ...