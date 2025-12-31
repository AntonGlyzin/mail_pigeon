import sys
from pathlib import Path
path = Path(__file__)
tests_dir = path.parent
sys.path.insert(0, str(tests_dir.parent.parent))
from mail_pigeon import MailClient, logger
from mail_pigeon.queue import FilesBox
from mail_pigeon.security import TypesEncryptors
import threading
import json

import logging
logger.setLevel(logging.INFO)

name = 'app3'

start = threading.Event()
start.set()

q = Path(__file__).parent / 'queue' / name
f = FilesBox(str(q))

apps_cert = str(Path(__file__).parent.parent / 'apps_cert')
cipher = TypesEncryptors.HMAC('qwe34')
client = MailClient(name, is_master=False, out_queue=f, cert_dir=apps_cert, encryptor=cipher)
client.wait_server()

file = Path(__file__).parent.parent / 'data' / 'app3.json'
txt = file.read_text('utf-8')
data = {i['id']:i for i in json.loads(txt)}

print('============= App3 =================\n')
while start.is_set():
    msg = client.get()
    if msg is None:
        continue
    print(f'sender - <{msg.sender}> | recipient - <{msg.recipient}>')
    print(f'---- content ----\n <{msg.content}> \n ------ \n')
    if msg.sender == 'app2':
        reciv = json.loads(msg.content)
        item = data.get(reciv['id'])
        if item is None:
            continue
        new_data = {**reciv, **item}
        client.send('app4', json.dumps(new_data))