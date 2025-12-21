import sys
from anyio import Path
path = Path(__file__)
tests_dir = path.parent
sys.path.insert(0, str(tests_dir.parent.parent))
from mail_pigeon import AsyncMailClient, logger
from mail_pigeon.queue import AsyncFilesBox
import asyncio
import json

import logging
logger.setLevel(logging.DEBUG)

name = 'app2'

start = asyncio.Event()
start.set()

loop = asyncio.new_event_loop()

async def main():
    q = Path(__file__).parent / 'queue' / name
    f = AsyncFilesBox(str(q))
    apps_cert = str(Path(__file__).parent.parent / 'apps_cert')
    
    client = AsyncMailClient(name, is_master=False, out_queue=f, cert_dir=apps_cert)
    await client.wait_server()
    
    file = Path(__file__).parent.parent / 'data' / 'app2.json'
    txt = await file.read_text('utf-8')
    data = {i['id']:i for i in json.loads(txt)}
    
    print('============= App2 =================\n')
    while start.is_set():
        msg = await client.get()
        if msg is None:
            continue
        print(f'sender - <{msg.sender}> | recipient - <{msg.recipient}>')
        print(f'---- content ----\n <{msg.content}> \n ------ \n')
        if msg.sender == 'app1':
            reciv = json.loads(msg.content)
            item = data.get(reciv['id'])
            if item is None:
                continue
            new_data = {**reciv, **item}
            await client.send('app3', json.dumps(new_data))
        elif msg.sender == 'app4':
            await client.send('app1', msg.content)


loop.run_until_complete(main())