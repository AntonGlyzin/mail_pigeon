from settings import logger, BaseTest
from mail_pigeon import MailClient, logger as mail_logger
from mail_pigeon.queue import FilesBox
import time
from pathlib import Path
from threading import Thread
import json

import logging
mail_logger.setLevel(logging.DEBUG)


class TestMailClient(BaseTest):
    
    @classmethod
    def filename_test(cls):
        return 'test_mail_client.log'
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
    
    @classmethod
    def tearDownClass(cls):
        ...
    
    def test_case_1(self):
        logger.info('1. Иницилизация клиентов.')
        q = Path(__file__).parent / 'queue'
        f = FilesBox(str(q))
        client1 = MailClient('client1', is_master=None, wait_server=True, out_queue=f)
        data1 = {'id': 1, 'name': 'Leanne Graham', 'username': 'Bret', 'email': 'Sincere@april.biz', 'address': {'street': 'Kulas Light', 'suite': 'Apt. 556', 'city': 'Gwenborough', 'zipcode': '92998-3874', 'geo': {'lat': '-37.3159', 'lng': '81.1496'}}, 'phone': '1-770-736-8031 x56442', 'website': 'hildegard.org', 'company': {'name': 'Romaguera-Crona', 'catchPhrase': 'Multi-layered client-server neural-net', 'bs': 'harness real-time e-markets'}}
        data2 = {'postId': 1, 'id': 1, 'name': 'id labore ex et quam laborum', 'email': 'Eliseo@gardner.biz', 'body': 'laudantium enim quasi est quidem magnam voluptate ipsam eos\ntempora quo necessitatibus\ndolor quam autem quasi\nreiciendis et nam sapiente accusantium'}
        logger.info('2. Отправка сообщений на client2.')
        client1.send('client2', json.dumps(data1))
        time.sleep(.1)
        client1.send('client2', json.dumps(data2))
        time.sleep(.1)
        client2 = MailClient('client2', is_master=None)
        logger.info('3. Получения сообщений из client1.')
        m=client2.get()
        self.assertDictEqual(json.loads(m.content), data1)
        m=client2.get()
        self.assertDictEqual(json.loads(m.content), data2)
        time.sleep(.1)
        self.assertEqual(client1._out_queue.size(), 0)
        
        logger.info('4. Запускаем еще клиент в отдельном потоке и посылаем сообщение с ожиданием.')
        client3 = MailClient('client3', is_master=None)
        time.sleep(.1)
        def fclient4():
            t=client3.send('client2', json.dumps(data2), wait=True)
            time.sleep(.1)
            logger.info('6. Ответ из потока на команду send.')
            self.assertDictEqual(json.loads(t.content), data1)
        
        th_client3 = Thread(target=fclient4)
        th_client3.start()
        time.sleep(.1)
        m1=client2.get()
        self.assertDictEqual(json.loads(m1.content), data2)
        
        logger.info('5. Отправляем ответ в поток из основоного потока.')
        client2.send('client3', json.dumps(data1), key_response=m1.key)
        time.sleep(.1)
        th_client3.join()
        
        logger.info("-------------------------------------------------------")
        
if __name__ == "__main__":
    TestMailClient.start()