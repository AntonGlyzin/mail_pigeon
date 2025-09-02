import sys
from pathlib import Path
path = Path(__file__)
tests_dir = path.parent
sys.path.insert(0, str(tests_dir.parent.parent))
import time
from mail_pigeon import MailClient, logger
from mail_pigeon.queue import FilesBox

import logging
# logger.setLevel(logging.DEBUG)

name = 'master'

q = Path(__file__).parent / name
f = FilesBox(str(q))
client = MailClient(name, is_master=True, wait_server=True, out_queue=f)

print('=============Server master=================')
while True:
    print('==============================')
    print(f'Clients server: {client._server.clients_names}')
    print(f'Clients wait connect: {client._server._clients_wait_connect}')
    print('')
    print(f'Clients: {client._clients}')
    print(f'Client connected: {client._client_connected.is_set()}')
    print(f'Server started: {client._server_started.is_set()}')
    print(f'In queue size: {client._in_queue.size()}')
    print('==============================')
    m=client.get(3)
    if not m:
        continue
    print(f'Msg: {m}')
    if m.sender == 'app1':
        client.send(m.sender, 'hello from master', key_response=m.key)
    else:
        client.send(m.sender, 'hello from master')