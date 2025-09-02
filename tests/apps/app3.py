import sys
from pathlib import Path
path = Path(__file__)
tests_dir = path.parent
sys.path.insert(0, str(tests_dir.parent.parent))
import time
from mail_pigeon import MailClient, logger
from mail_pigeon.queue import FilesBox
import json
import logging
# logger.setLevel(logging.DEBUG)



name = 'app3'

q = Path(__file__).parent / name
f = FilesBox(str(q))
client = MailClient(name, is_master=None, wait_server=True, out_queue=f)
data2 = {'postId': 1, 'id': 1, 'name': 'id labore ex et quam laborum', 'email': 'Eliseo@gardner.biz', 'body': 'laudantium enim quasi est quidem magnam voluptate ipsam eos\ntempora quo necessitatibus\ndolor quam autem quasi\nreiciendis et nam sapiente accusantium'}
print('=============app3=================')
while True:
    print('==============================')
    print(f'Server: {client._server}')
    if client._server:
        n1=getattr(client._server, 'clients_names', '')
        n2=getattr(client._server, '_clients_wait_connect', '')
        print(f'Clients server: {n1}')
        print(f'Clients wait connect: {n2}')
    print('')
    print(f'Clients: {client._clients}')
    print(f'Client connected: {client._client_connected.is_set()}')
    print(f'Server started: {client._server_started.is_set()}')
    print(f'Client is start: {client._is_start.is_set()}')
    print(f'In queue size: {client._in_queue.size()}')
    print('==============================')
    m=client.get(3)
    if not m:
        continue
    print(f'Msg: {m}')
    if m.sender == 'app1':
        client.send(m.sender, json.dumps(data2), key_response=m.key)