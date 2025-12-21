import sys
from pathlib import Path
import shutil

path = Path(__file__)
tests_dir = path.parent
sys.path.insert(0, str(tests_dir.parent))

from mail_pigeon import MailClient, logger as mail_logger
from mail_pigeon.queue import FilesBox
import time
from multiprocessing import Process, Event
from mail_pigeon.security import TypesEncryptors
import json

import logging
mail_logger.setLevel(logging.DEBUG)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(console_handler)

file_handler = logging.FileHandler(tests_dir / 'apps_test.log', mode='a', encoding='utf8')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)

start = Event()
start.set()

def app1(port, start, encryptor=None, cert_dir=None):
    q = Path(__file__).parent / 'queue' /'app1'
    f = FilesBox(str(q))
    client = MailClient(
            'app1',
            is_master=True, 
            out_queue=f, 
            encryptor=encryptor, 
            port_server=port,
            cert_dir=cert_dir
        )
    client.wait_server()
    file = Path(__file__).parent / 'data' / 'app1.json'
    txt = file.read_text('utf-8')
    data = json.loads(txt)
    for item in (data*10):
        res = client.send('app2', json.dumps(item), True)
        logger.info(f'app1. Ответ от app2: {res.content}')
        client.send('app3', res.content)
    app_data = []
    while True:
        res = client.get(timeout=1)
        logger.info(f'app1. Количество: {len(app_data)}')
        if len(app_data) == 100:
            break
        if not res:
            continue
        data = json.loads(res.content)
        logger.info(f'app1. Ответ от app4: {data}')
        app_data.append(data)
    start.clear()
    time.sleep(1.5)
    file = Path(__file__).parent / 'data' / 'res_app1.json'
    file.write_text(json.dumps(app_data), 'utf-8')
    client.stop()

def app2(port, start, encryptor=None, cert_dir=None):
    q = Path(__file__).parent / 'queue' / 'app2'
    f = FilesBox(str(q))
    client = MailClient(
            'app2', 
            is_master=False, 
            out_queue=f, 
            encryptor=encryptor, 
            port_server=port,
            cert_dir=cert_dir
        )
    client.wait_server()
    file = Path(__file__).parent / 'data' / 'app2.json'
    txt = file.read_text('utf-8')
    data = {}
    for item in json.loads(txt):
        data[item['id']] = item
    while start.is_set():
        res = client.get(timeout=1)
        if not res:
            continue
        content = json.loads(res.content)
        content['company'] = data[content['id']]['company']
        client.send('app1', json.dumps(content))
    client.stop()

def app3(port, start, encryptor=None, cert_dir=None):
    client = MailClient(
            'app3', 
            is_master=False, 
            encryptor=encryptor,
            port_server=port,
            cert_dir=cert_dir
        )
    client.wait_server()
    file = Path(__file__).parent / 'data' / 'app3.json'
    txt = file.read_text('utf-8')
    data = {}
    for item in json.loads(txt):
        data[item['id']] = item
    while start.is_set():
        res = client.get(timeout=1)
        if not res:
            continue
        content = json.loads(res.content)
        logger.info(f'app3. Ответ от app1: {content}')
        content['address'] = data[content['id']]['address']
        client.send('app4', json.dumps(content))
    client.stop()

def app4(port, start, encryptor=None, cert_dir=None):
    client = MailClient(
            'app4', 
            is_master=False, 
            encryptor=encryptor, 
            port_server=port,
            cert_dir=cert_dir
        )
    client.wait_server()
    file = Path(__file__).parent / 'data' / 'app4.json'
    txt = file.read_text('utf-8')
    data = {}
    for item in json.loads(txt):
        data[item['id']] = item
    while start.is_set():
        res = client.get(timeout=1)
        if not res:
            continue
        content = json.loads(res.content)
        logger.info(f'app4. Ответ от app3: {content}')
        content['address']['geo'] = data[content['id']]['address']['geo']
        client.send('app1', json.dumps(content))
    client.stop()

def check():
    for i in ['app1', 'app2', ]:
        q = Path(__file__).parent / 'queue' / i
        if q.exists():
            q.rmdir()
    file = Path(__file__).parent / 'data' / 'res_app1.json'
    txt = file.read_text('utf-8')
    data = json.loads(txt)
    if len(data) != 100:
        raise ValueError('Не все данные были записаны в файл.')
    cuurent=0
    for i in data:
        if cuurent < int(i['id']):
            cuurent = int(i['id'])
        elif int(i['id']) == 1:
            cuurent = 1
        else:
            raise ValueError('Список данных записан не в последовательном порядке.')
    file.unlink()


if __name__ == "__main__":
    arg = sys.argv[1]
    
    q = Path(__file__).parent / 'queue'
    if q.exists():
        shutil.rmtree(str(q))
    file = Path(__file__).parent / 'data' / 'res_app1.json'
    if file.exists():
        file.unlink()
    file = Path(__file__).parent / 'apps_cert'
    if file.exists():
        shutil.rmtree(str(file))
    
    if int(arg) == 1:
        t1 = time.time()
        logger.info('1. Отправка сообщений между процессами.')
        proc1 = Process(target=app1, daemon=True, args=(5588, start,))
        proc1.start()
        time.sleep(1)
        proc2 = Process(target=app2, daemon=True, args=(5588, start,))
        proc2.start()
        proc3 = Process(target=app3, daemon=True, args=(5588, start,))
        proc3.start()
        proc4 = Process(target=app4, daemon=True, args=(5588, start,))
        proc4.start()
        proc1.join()
        proc2.join()
        proc3.join()
        proc4.join()
        logger.info('----Время выполнения: {}'.format(time.time()-t1))
        check()
    
    if int(arg) == 2:
        t1 = time.time()
        logger.info('2. Отправка сообщений между процессами в шифрованном виде HMAC.')
        encript = TypesEncryptors.HMAC('admin')
        proc1 = Process(target=app1, args=(5599, start, encript,), daemon=True)
        proc1.start()
        time.sleep(1)
        proc2 = Process(target=app2, args=(5599, start, encript,), daemon=True)
        proc2.start()
        encript2 = TypesEncryptors.HMAC('admin')
        proc3 = Process(target=app3, args=(5599, start, encript2,), daemon=True)
        proc3.start()
        proc4 = Process(target=app4, args=(5599, start, encript2,), daemon=True)
        proc4.start()
        proc1.join()
        proc2.join()
        proc3.join()
        proc4.join()
        logger.info('----Время выполнения: {}'.format(time.time()-t1))
        check()
    
    if int(arg) == 3:
        t1 = time.time()
        logger.info('3. Отправка сообщений между процессами с CURVE аутентификацией.')
        apps_cert = Path(__file__).parent / 'apps_cert'
        proc1 = Process(target=app1, daemon=True, args=(5600, start,), kwargs={'cert_dir': apps_cert})
        proc1.start()
        time.sleep(1)
        proc2 = Process(target=app2, daemon=True, args=(5600, start,), kwargs={'cert_dir': apps_cert})
        proc2.start()
        proc3 = Process(target=app3, daemon=True, args=(5600, start,), kwargs={'cert_dir': apps_cert})
        proc3.start()
        proc4 = Process(target=app4, daemon=True, args=(5600, start,), kwargs={'cert_dir': apps_cert})
        proc4.start()
        proc1.join()
        proc2.join()
        proc3.join()
        proc4.join()
        logger.info('----Время выполнения: {}'.format(time.time()-t1))
        check()
    
    if int(arg) == 4:
        t1 = time.time()
        logger.info('4. Отправка сообщений между процессами с CURVE аутентификацией и шифрованием сообщений.')
        apps_cert = Path(__file__).parent / 'apps_cert'
        encript = TypesEncryptors.HMAC('admin')
        proc1 = Process(target=app1, daemon=True, args=(5601, start, encript), kwargs={'cert_dir': apps_cert})
        proc1.start()
        time.sleep(1)
        proc2 = Process(target=app2, daemon=True, args=(5601, start, encript), kwargs={'cert_dir': apps_cert})
        proc2.start()
        encript2 = TypesEncryptors.HMAC('admin')
        proc3 = Process(target=app3, daemon=True, args=(5601, start, encript2), kwargs={'cert_dir': apps_cert})
        proc3.start()
        proc4 = Process(target=app4, daemon=True, args=(5601, start, encript2), kwargs={'cert_dir': apps_cert})
        proc4.start()
        proc1.join()
        proc2.join()
        proc3.join()
        proc4.join()
        logger.info('----Время выполнения: {}'.format(time.time()-t1))
    
    logger.info("-------------------------------------------------------")
    logger.info('Тест завершен.')
    sys.exit(0)