from __future__ import annotations
import logging
import json
from typing import Union
from dataclasses import dataclass, asdict

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger('mail_pigeon')


@dataclass
class Auth:
    CURVE_PUBLICKEY: str
    CURVE_SECRETKEY: str


class TypeMessage(object):
    REQUEST = 'request'
    REPLY = 'reply'


@dataclass
class Message(object):
    key: str # ключ сообщения в очереди
    type: str 
    wait_response: bool # является ли запрос ожидающим ответом
    is_response: bool # является ли это сообщение ответным
    sender: str
    recipient: str
    content: str
    
    def to_dict(self):
        return asdict(self)
    
    def to_bytes(self):
        return json.dumps(self.to_dict()).encode()
    
    @classmethod
    def parse(cls, msg: Union[bytes, str]) -> Message:
        return cls(**json.loads(msg))