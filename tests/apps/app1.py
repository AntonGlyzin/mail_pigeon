import sys
from pathlib import Path
path = Path(__file__)
tests_dir = path.parent
sys.path.insert(0, str(tests_dir.parent.parent))

from mail_pigeon import MailClient
from mail_pigeon.queue import FilesBox

name = 'app1'

print(f'Client: {name}')

q = Path(__file__).parent / name
f = FilesBox(str(q))
client = MailClient(name, is_master=False, wait_server=True, out_queue=f)
msg = f'This is {name}'

while True:
    recipient = input('Enter recipient: ')
    res = client.send(recipient, msg, True)
    print(f'Response: {res}')