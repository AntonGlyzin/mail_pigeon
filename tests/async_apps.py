import sys
from pathlib import Path
import shutil
import asyncio
path = Path(__file__)
tests_dir = path.parent
sys.path.insert(0, str(tests_dir.parent))
from anyio import Path as AsyncPath

from mail_pigeon import AsyncMailClient, logger as mail_logger
from mail_pigeon.queue import AsyncFilesBox
import time
from multiprocessing import Process, Event
from mail_pigeon.security import TypesEncryptors
import json

import logging
mail_logger.setLevel(logging.INFO)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(console_handler)

file_handler = logging.FileHandler(tests_dir / 'async_apps_test.log', mode='a', encoding='utf8')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)

start = Event()
start.set()

def app1(start, encryptor=None):
    async def main():
        q = AsyncPath(__file__).parent / 'queue' /'app1'
        f = AsyncFilesBox(str(q))
        await f.init()
        client = AsyncMailClient(
                'app1', 
                is_master=True, 
                out_queue=f, 
                encryptor=encryptor, 
                port_server=5577
            )
        await client.wait_server()
        file = AsyncPath(__file__).parent / 'data' / 'app1.json'
        txt = await file.read_text('utf-8')
        for item in json.loads(txt):
            res = await client.send('app2', json.dumps(item), True)
            logger.info(f'app1. Ответ от app2: {res.content}')
            await client.send('app3', res.content)
        app_data = []
        while True:
            res = await client.get(timeout=1)
            logger.info(f'app1. Количество: {len(app_data)}')
            if len(app_data) == 10:
                break
            if not res:
                continue
            data = json.loads(res.content)
            logger.info(f'app1. Ответ от app4: {data}')
            app_data.append(data)
        start.clear()
        await asyncio.sleep(1.5)
        file = AsyncPath(__file__).parent / 'data' / 'res_app1.json'
        await file.write_text(json.dumps(app_data), 'utf-8')
        await client.stop()
    asyncio.run(main())

def app2(start, encryptor=None):
    async def main():
        q = AsyncPath(__file__).parent / 'queue' / 'app2'
        f = AsyncFilesBox(str(q))
        await f.init()
        client = AsyncMailClient(
                'app2', 
                is_master=False,
                out_queue=f, 
                encryptor=encryptor, 
                port_server=5577
            )
        await client.wait_server()
        file = AsyncPath(__file__).parent / 'data' / 'app2.json'
        txt = await file.read_text('utf-8')
        data = {}
        for item in json.loads(txt):
            data[item['id']] = item
        while start.is_set():
            res = await client.get(timeout=1)
            if not res:
                continue
            content = json.loads(res.content)
            content['company'] = data[content['id']]['company']
            await client.send('app1', json.dumps(content))
        await client.stop()
    asyncio.run(main())

def app3(start, encryptor=None):
    async def main():
        client = AsyncMailClient(
                'app3',
                is_master=False, 
                encryptor=encryptor, 
                port_server=5577
            )
        await client.wait_server()
        file = AsyncPath(__file__).parent / 'data' / 'app3.json'
        txt = await file.read_text('utf-8')
        data = {}
        for item in json.loads(txt):
            data[item['id']] = item
        while start.is_set():
            res = await client.get(timeout=1)
            if not res:
                continue
            content = json.loads(res.content)
            logger.info(f'app3. Ответ от app1: {content}')
            content['address'] = data[content['id']]['address']
            await client.send('app4', json.dumps(content))
        await client.stop()
    asyncio.run(main())

def app4(start, encryptor=None):
    async def main():
        client = AsyncMailClient(
                'app4', 
                is_master=False, 
                encryptor=encryptor, 
                port_server=5577
            )
        await client.wait_server()
        file = AsyncPath(__file__).parent / 'data' / 'app4.json'
        txt = await file.read_text('utf-8')
        data = {}
        for item in json.loads(txt):
            data[item['id']] = item
        while start.is_set():
            res = await client.get(timeout=1)
            if not res:
                continue
            content = json.loads(res.content)
            logger.info(f'app4. Ответ от app3: {content}')
            content['address']['geo'] = data[content['id']]['address']['geo']
            await client.send('app1', json.dumps(content))
        await client.stop()
    asyncio.run(main())

def check():
    for i in ['app1', 'app2', ]:
        q = Path(__file__).parent / 'queue' / i
        if q.exists():
            q.rmdir()
    file = Path(__file__).parent / 'data' / 'res_app1.json'
    txt = file.read_text('utf-8')
    data = json.loads(txt)
    if len(data) != 10:
        raise ValueError('Не все данные были записаны в файл.')
    cuurent=0
    for i in data:
        if cuurent < int(i['id']):
            cuurent = int(i['id'])
        else:
            raise ValueError('Список данных записан не в последовательном порядке.')
    file.unlink()


if __name__ == "__main__":
    arg = sys.argv[1]
    if int(arg) == 1:
        logger.info('1. Отправка сообщений между процессами.')
        proc1 = Process(target=app1, daemon=True, args=(start,))
        proc1.start()
        time.sleep(1)
        proc2 = Process(target=app2, daemon=True, args=(start,))
        proc2.start()
        proc3 = Process(target=app3, daemon=True, args=(start,))
        proc3.start()
        proc4 = Process(target=app4, daemon=True, args=(start,))
        proc4.start()
        proc1.join()
        proc2.join()
        proc3.join()
        proc4.join()
        check()
    
    if int(arg) == 2:
        logger.info('2. Отправка сообщений между процессами в шифрованном виде HMAC.')
        encript = TypesEncryptors.HMAC('admin')
        proc1 = Process(target=app1, args=(start, encript,), daemon=True)
        proc1.start()
        time.sleep(1)
        proc2 = Process(target=app2, args=(start, encript,), daemon=True)
        proc2.start()
        encript2 = TypesEncryptors.HMAC('admin')
        proc3 = Process(target=app3, args=(start, encript2,), daemon=True)
        proc3.start()
        proc4 = Process(target=app4, args=(start, encript2,), daemon=True)
        proc4.start()
        proc1.join()
        proc2.join()
        proc3.join()
        proc4.join()
        check()
        
    if int(arg) == 0:
        q = Path(__file__).parent / 'queue'
        if q.exists():
            shutil.rmtree(str(q))
        file = Path(__file__).parent / 'data' / 'res_app1.json'
        if file.exists():
            file.unlink()
    logger.info("-------------------------------------------------------")
    logger.info('Тест завершен.')
    sys.exit(0)