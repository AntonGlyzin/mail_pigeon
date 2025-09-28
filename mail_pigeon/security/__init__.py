from mail_pigeon.security.base import IEncryptor
from mail_pigeon.security.hmac import HMACEncryptor

class TypesEncryptors:
    HMAC = HMACEncryptor

__all__ = [
    'IEncryptor',
    'TypesEncryptors'
]

