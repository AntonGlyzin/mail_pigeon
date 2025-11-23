from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
from mail_pigeon.security import IEncryptor


class HMACEncryptor(IEncryptor):
    
    def __init__(self, secret_word: str):
        """
        Args:
            secret_word (str): Секретное слово для шифрования.
        """   
        super().__init__(secret_word)
        self.salt = b'pigeon'
        self.kdf = PBKDF2HMAC(
            algorithm=SHA256(),
            length=32,
            salt=self.salt,
            iterations=1000,
        )
        self.key = base64.urlsafe_b64encode(self.kdf.derive(secret_word.encode()))
        self.cipher = Fernet(self.key)
    
    def encrypt(self, message: bytes) -> bytes:
        """Шифрует сообщение.

        Args:
            message (bytes): Сообщение.

        Returns:
            bytes: Защифрованное сообщение.
        """
        return self.cipher.encrypt(message)
    
    def decrypt(self, message: bytes) -> bytes:
        """Расшифровывает сообщение.

        Args:
            encrypted (bytes): Зашифрованное сообщение.

        Returns:
            bytes: Сообщение.
        """
        return self.cipher.decrypt(message)