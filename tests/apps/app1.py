import sys
from pathlib import Path
path = Path(__file__)
tests_dir = path.parent
sys.path.insert(0, str(tests_dir.parent.parent))
from mail_pigeon import MailClient, logger
from mail_pigeon.queue import FilesBox
from threading import Event
import json

import logging
logger.setLevel(logging.INFO)

name = 'app1'

start = Event()
start.set()

q = Path(__file__).parent / 'queue' / name
f = FilesBox(str(q))

apps_cert = str(Path(__file__).parent.parent / 'apps_cert')

client = MailClient(name, is_master=None, out_queue=f, cert_dir=apps_cert)
client.wait_server()

file = Path(__file__).parent.parent / 'data' / 'app1.json'
txt = file.read_text('utf-8')
data = {i['id']:i for i in json.loads(txt)}

print('============= App1 =================\n')
while start.is_set():
    inp = input('Введите номер от 1 до 10: ')
    try:
        if int(inp) > 10:
            continue
    except:
        continue
    msg_master = data.get(int(inp))
    if msg_master is None:
        continue
    msg = client.send(recipient='app2', content=json.dumps(msg_master), wait=True)
    if msg is None:
        continue
    reciv = json.loads(msg.content)
    print(f'sender - <{msg.sender}> | recipient - <{msg.recipient}>')
    print(f'---- content ----\n <{reciv}> \n ------ \n')
    