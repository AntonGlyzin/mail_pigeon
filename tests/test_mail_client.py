from settings import logger, BaseTest
from mail_pigeon import MailClient, AsyncMailClient, logger as mail_logger
from mail_pigeon.queue import FilesBox, AsyncFilesBox
import asyncio
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
        cls.loop = asyncio.new_event_loop()
    
    @classmethod
    def tearDownClass(cls):
        ...
    
    def test_case_1(self):
        logger.info('1.1. Иницилизация клиентов.')
        q = Path(__file__).parent / 'queue'
        f = FilesBox(str(q))
        client1 = MailClient('client1', is_master=True, out_queue=f)
        client1.wait_server()
        time.sleep(1)
        p=client1._is_use_port()
        self.assertTrue(p)
        data1 = {'id': 1, 'name': 'Leanne Graham', 'username': 'Bret', 'email': 'Sincere@april.biz', 'address': {'street': 'Kulas Light', 'suite': 'Apt. 556', 'city': 'Gwenborough', 'zipcode': '92998-3874', 'geo': {'lat': '-37.3159', 'lng': '81.1496'}}, 'phone': '1-770-736-8031 x56442', 'website': 'hildegard.org', 'company': {'name': 'Romaguera-Crona', 'catchPhrase': 'Multi-layered client-server neural-net', 'bs': 'harness real-time e-markets'}}
        data2 = {'postId': 1, 'id': 1, 'name': 'id labore ex et quam laborum', 'email': 'Eliseo@gardner.biz', 'body': 'laudantium enim quasi est quidem magnam voluptate ipsam eos\ntempora quo necessitatibus\ndolor quam autem quasi\nreiciendis et nam sapiente accusantium'}
        logger.info('1.2. Отправка сообщений на client2.')
        client1.send('client2', json.dumps(data1))
        time.sleep(.1)
        client1.send('client2', json.dumps(data2))
        time.sleep(.1)
        logger.info('1.3. Получения сообщений из client1.')
        client2 = MailClient('client2', is_master=None)
        time.sleep(1)
        m=client2.get()
        self.assertDictEqual(json.loads(m.content), data1)
        time.sleep(.1)
        m=client2.get()
        self.assertDictEqual(json.loads(m.content), data2)
        time.sleep(.1)
        self.assertEqual(client1._out_queue.size(), 0)
        self.assertEqual(client2._in_queue.size(), 0)
        m=client2.get(timeout=1)
        self.assertIsNone(m)
        
        logger.info('1.4. Запускаем еще клиент в отдельном потоке и посылаем сообщение с ожиданием.')
        client3 = MailClient('client3', is_master=None)
        time.sleep(1)
        def fclient4():
            t=client3.send('client2', json.dumps(data2), wait=True)
            time.sleep(.1)
            logger.info('1.6. Ответ из потока на команду send.')
            self.assertDictEqual(json.loads(t.content), data1)
        
        th_client3 = Thread(target=fclient4)
        th_client3.start()
        time.sleep(.1)
        m1=client2.get()
        self.assertDictEqual(json.loads(m1.content), data2)
        
        logger.info('1.5. Отправляем ответ в поток из основоного потока.')
        client2.send('client3', json.dumps(data1))
        time.sleep(.1)
        th_client3.join()
        logger.info('1.7. Завершение.')
        logger.info("-------------------------------------------------------")
        
    def test_case_2(self):
        async def main():
            logger.info('2.2. Иницилизация асинхронного клиента.')
            q = Path(__file__).parent / 'async_queue'
            f = AsyncFilesBox(str(q))
            client1 = AsyncMailClient('client1', is_master=True, out_queue=f, port_server=5566)
            await client1.wait_server()
            await asyncio.sleep(1)
            p=await client1._is_use_port()
            self.assertTrue(p)
            data1 = {'id': 1, 'name': 'Leanne Graham', 'username': 'Bret', 'email': 'Sincere@april.biz', 'address': {'street': 'Kulas Light', 'suite': 'Apt. 556', 'city': 'Gwenborough', 'zipcode': '92998-3874', 'geo': {'lat': '-37.3159', 'lng': '81.1496'}}, 'phone': '1-770-736-8031 x56442', 'website': 'hildegard.org', 'company': {'name': 'Romaguera-Crona', 'catchPhrase': 'Multi-layered client-server neural-net', 'bs': 'harness real-time e-markets'}}
            data2 = {'postId': 1, 'id': 1, 'name': 'id labore ex et quam laborum', 'email': 'Eliseo@gardner.biz', 'body': 'laudantium enim quasi est quidem magnam voluptate ipsam eos\ntempora quo necessitatibus\ndolor quam autem quasi\nreiciendis et nam sapiente accusantium'}
            logger.info('2.2. Отправка сообщений на client2.')
            await client1.send('client2', json.dumps(data1))
            await asyncio.sleep(.1)
            await client1.send('client2', json.dumps(data2))
            await asyncio.sleep(.1)
            logger.info('2.3. Получения сообщений из client1.')
            client2 = AsyncMailClient('client2', is_master=None, port_server=5566)
            await asyncio.sleep(1)
            m=await client2.get()
            self.assertDictEqual(json.loads(m.content), data1)
            await asyncio.sleep(.1)
            m=await client2.get()
            self.assertDictEqual(json.loads(m.content), data2)
            await asyncio.sleep(.1)
            r1=await client1._out_queue.size()
            r2=await client2._in_queue.size()
            self.assertEqual(r1, 0)
            self.assertEqual(r2, 0)
            m=await client2.get(timeout=1)
            self.assertIsNone(m)
            
            logger.info('2.4. Запускаем еще клиент в отдельном потоке и посылаем сообщение с ожиданием.')
            client3 = AsyncMailClient('client3', is_master=None, port_server=5566)
            await asyncio.sleep(1)
            async def fclient4():
                t=await client3.send('client2', json.dumps(data2), wait=True)
                await asyncio.sleep(.1)
                logger.info('2.6. Ответ из потока на команду send.')
                self.assertDictEqual(json.loads(t.content), data1)
            
            th_client3 = asyncio.create_task(fclient4())
            await asyncio.sleep(.1)
            m1=await client2.get()
            self.assertDictEqual(json.loads(m1.content), data2)
            
            logger.info('2.5. Отправляем ответ в поток из основоного потока.')
            await client2.send('client3', json.dumps(data1))
            await asyncio.sleep(.1)
            await asyncio.wait([th_client3])
            await client1.stop()
            await client2.stop()
            await client3.stop()
            logger.info('2.7. Завершение.')
            logger.info("-------------------------------------------------------")
        self.loop.run_until_complete(main())


if __name__ == "__main__":
    TestMailClient.start()