import sys
from pathlib import Path
path = Path(__file__)
tests_dir = path.parent
sys.path.insert(0, str(tests_dir.parent.parent))

from mail_pigeon import MailClient, logger
from mail_pigeon.queue import FilesBox
from threading import Thread
import json
import logging
# logger.setLevel(logging.DEBUG)

name = 'app2'

print(f'Client: {name}')

q = Path(__file__).parent / name
f = FilesBox(str(q))
client = MailClient(name, is_master=False, out_queue=f)
msg = f'This is {name}'
data1 = {'id': 1, 'name': 'Leanne Graham', 'username': 'Bret', 'email': 'Sincere@april.biz', 'address': {'street': 'Kulas Light', 'suite': 'Apt. 556', 'city': 'Gwenborough', 'zipcode': '92998-3874', 'geo': {'lat': '-37.3159', 'lng': '81.1496'}}, 'phone': '1-770-736-8031 x56442', 'website': 'hildegard.org', 'company': {'name': 'Romaguera-Crona', 'catchPhrase': 'Multi-layered client-server neural-net', 'bs': 'harness real-time e-markets'}}
def app2():
    while True:
        m=client.get()
        print('')
        print(f'============{m.sender}=============')
        print(f'Msg: {m}')
        print('===========')
        if m.sender == 'app1':
            client.send(m.sender, json.dumps(data1), key_response=m.key)
        
Thread(target=app2, daemon=True).start()

while True:
    recipient = input('Enter recipient: ')
    client.send(recipient, msg)