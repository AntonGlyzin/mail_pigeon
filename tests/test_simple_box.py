from settings import logger, BaseTest
from mail_pigeon.queue import SimpleBox, AsyncSimpleBox
from threading import Thread
import asyncio
import json
import time

class TestSimpleBox(BaseTest):
    
    @classmethod
    def filename_test(cls):
        return 'test_simple_box.log'
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.fb = SimpleBox()
        cls.loop = asyncio.new_event_loop()
        cls.asyncfb = AsyncSimpleBox()
    
    @classmethod
    def tearDownClass(cls):
        cls.fb.clear()
        cls.loop.run_until_complete(cls.asyncfb.clear())
    
    def test_case_1(self):
        logger.info('1. Запись и получение данных из одного потока.')
        logger.info('----Запись значений в очередь.')
        data1 = {'id': 1, 'name': 'Leanne Graham', 'username': 'Bret', 'email': 'Sincere@april.biz', 'address': {'street': 'Kulas Light', 'suite': 'Apt. 556', 'city': 'Gwenborough', 'zipcode': '92998-3874', 'geo': {'lat': '-37.3159', 'lng': '81.1496'}}, 'phone': '1-770-736-8031 x56442', 'website': 'hildegard.org', 'company': {'name': 'Romaguera-Crona', 'catchPhrase': 'Multi-layered client-server neural-net', 'bs': 'harness real-time e-markets'}}
        key1 = self.fb.put(json.dumps(data1))
        data2 = {'postId': 1, 'id': 1, 'name': 'id labore ex et quam laborum', 'email': 'Eliseo@gardner.biz', 'body': 'laudantium enim quasi est quidem magnam voluptate ipsam eos\ntempora quo necessitatibus\ndolor quam autem quasi\nreiciendis et nam sapiente accusantium'}
        key2 = self.fb.put(json.dumps(data2))
        logger.info('----Проверка ключей.')
        logger.info(f"----k1={key1} and k2={key2}.")
        self.assertNotEqual(key1, key2)
        self.assertTrue(key1)
        self.assertTrue(key2)
        self.assertEqual(self.fb.size(), 2)
        logger.info('----Получение из очереди.')
        k1, d1 = self.fb.get()
        self.assertEqual(d1, json.dumps(data1))
        self.assertEqual(self.fb.size(), 2)
        self.fb.done(k1)
        self.assertEqual(self.fb.size(), 1)
        logger.info('----Запись в ожидающую очередь.')
        data3 = {'userId': 1, 'id': 1, 'title': 'delectus aut autem', 'completed': False}
        key3 = self.fb.put(json.dumps(data3), use_get_key=True)
        self.assertEqual(self.fb.size(), 2)
        logger.info('----Получение из живой(общей) очереди.')
        k2, d2 = self.fb.get()
        self.assertEqual(d2, json.dumps(data2))
        self.assertEqual(self.fb.size(), 2)
        self.fb.done(key2)
        self.assertEqual(self.fb.size(), 1)
        logger.info('----Получение из живой(общей) очереди по timeout.')
        self.assertIsNone(self.fb.get(timeout=1))
        logger.info('----Получение из очереди по ключу.')
        k3, d3 = self.fb.get(key=key3)
        self.assertEqual(d3, json.dumps(data3))
        self.assertEqual(self.fb.size(), 1)
        self.fb.done(k3)
        self.assertEqual(self.fb.size(), 0)
        logger.info('----Запоздать в обработке сообщения.')
        data4 = {'userId': 2, 'id': 4, 'title': 'delectus aut autem', 'completed': True}
        key4 = self.fb.put(json.dumps(data3))
        k4, d4 = self.fb.get()
        self.assertEqual(k4, key4)
        self.fb.done(key4)
        self.assertEqual(self.fb.size(), 0)
        logger.info("-------------------------------------------------------")
        
    def test_case_2(self):
        logger.info('2. Обработка сообщений с несколькими потоками.')
        def func1():
            data1 = {'id': 1, 'name': 'Leanne Graham', 'username': 'Bret', 'email': 'Sincere@april.biz', 'address': {'street': 'Kulas Light', 'suite': 'Apt. 556', 'city': 'Gwenborough', 'zipcode': '92998-3874', 'geo': {'lat': '-37.3159', 'lng': '81.1496'}}, 'phone': '1-770-736-8031 x56442', 'website': 'hildegard.org', 'company': {'name': 'Romaguera-Crona', 'catchPhrase': 'Multi-layered client-server neural-net', 'bs': 'harness real-time e-markets'}}
            data2 = {'postId': 1, 'id': 1, 'name': 'id labore ex et quam laborum', 'email': 'Eliseo@gardner.biz', 'body': 'laudantium enim quasi est quidem magnam voluptate ipsam eos\ntempora quo necessitatibus\ndolor quam autem quasi\nreiciendis et nam sapiente accusantium'}
            data3 = {'userId': 1, 'id': 1, 'title': 'delectus aut autem', 'completed': False}
            self.fb.put(json.dumps(data1))
            time.sleep(.5)
            self.fb.put(json.dumps(data2))
            time.sleep(.5)
            self.fb.put(json.dumps(data3))
            
        def func2():
            data4 = {'userId': 2, 'id': 4, 'title': 'delectus aut autem', 'completed': True}
            key4 = self.fb.put(json.dumps(data4), use_get_key=True)
            k, c = self.fb.get(key4)
            time.sleep(1.1)
            self.fb.done(k)
            
        def func3():
            while True:
                r = self.fb.get(timeout=1.1)
                if r is None:
                    return
                time.sleep(1.1)
                self.fb.done(r[0])
                
        def func4():
            while True:
                r = self.fb.get(timeout=1.1)
                if r is None:
                    return
                self.fb.done(r[0])
                
        th1 = Thread(target=func1)
        th1.start()
        
        th2 = Thread(target=func2)
        th2.start()
        
        th3 = Thread(target=func3)
        th3.start()
        
        th4 = Thread(target=func4)
        th4.start()
        
        th1.join()
        th2.join()
        th3.join()
        th4.join()
        self.assertEqual(self.fb.size(), 0)
        logger.info('----Все сообщения были обработаны.')
        
        logger.info("-------------------------------------------------------")
    
    def test_case_3(self):
        logger.info('3. Запись и получение данных из одной корутины. ')
        async def main3():
            await self.asyncfb.init()
            logger.info('----Запись значений в очередь.')
            data1 = {'id': 1, 'name': 'Leanne Graham', 'username': 'Bret', 'email': 'Sincere@april.biz', 'address': {'street': 'Kulas Light', 'suite': 'Apt. 556', 'city': 'Gwenborough', 'zipcode': '92998-3874', 'geo': {'lat': '-37.3159', 'lng': '81.1496'}}, 'phone': '1-770-736-8031 x56442', 'website': 'hildegard.org', 'company': {'name': 'Romaguera-Crona', 'catchPhrase': 'Multi-layered client-server neural-net', 'bs': 'harness real-time e-markets'}}
            key1 = await self.asyncfb.put(json.dumps(data1))
            data2 = {'postId': 1, 'id': 1, 'name': 'id labore ex et quam laborum', 'email': 'Eliseo@gardner.biz', 'body': 'laudantium enim quasi est quidem magnam voluptate ipsam eos\ntempora quo necessitatibus\ndolor quam autem quasi\nreiciendis et nam sapiente accusantium'}
            key2 = await self.asyncfb.put(json.dumps(data2))
            logger.info('----Проверка ключей.')
            logger.info(f"----k1={key1} and k2={key2}.")
            self.assertNotEqual(key1, key2)
            self.assertTrue(key1)
            self.assertTrue(key2)
            s=await self.asyncfb.size()
            self.assertEqual(s, 2)
            logger.info('----Получение из очереди.')
            k1, d1 = await self.asyncfb.get()
            self.assertEqual(d1, json.dumps(data1))
            s=await self.asyncfb.size()
            self.assertEqual(s, 2)
            await self.asyncfb.done(k1)
            s=await self.asyncfb.size()
            self.assertEqual(s, 1)
            logger.info('----Запись в ожидающую очередь.')
            data3 = {'userId': 1, 'id': 1, 'title': 'delectus aut autem', 'completed': False}
            key3 = await self.asyncfb.put(json.dumps(data3), use_get_key=True)
            s=await self.asyncfb.size()
            self.assertEqual(s, 2)
            logger.info('----Получение из живой(общей) очереди.')
            k2, d2 = await self.asyncfb.get()
            self.assertEqual(d2, json.dumps(data2))
            s=await self.asyncfb.size()
            self.assertEqual(s, 2)
            await self.asyncfb.done(key2)
            s=await self.asyncfb.size()
            self.assertEqual(s, 1)
            logger.info('----Получение из живой(общей) очереди по timeout.')
            s=await self.asyncfb.get(timeout=1)
            self.assertIsNone(s)
            logger.info('----Получение из очереди по ключу.')
            k3, d3 = await self.asyncfb.get(key=key3)
            self.assertEqual(d3, json.dumps(data3))
            s=await self.asyncfb.size()
            self.assertEqual(s, 1)
            await self.asyncfb.done(k3)
            s=await self.asyncfb.size()
            self.assertEqual(s, 0)
            logger.info('----Запоздать в обработке сообщения.')
            data4 = {'userId': 2, 'id': 4, 'title': 'delectus aut autem', 'completed': True}
            key4 = await self.asyncfb.put(json.dumps(data3))
            k4, d4 = await self.asyncfb.get()
            self.assertEqual(k4, key4)
            await self.asyncfb.done(key4)
            s=await self.asyncfb.size()
            self.assertEqual(s, 0)
            logger.info("-------------------------------------------------------")
        self.loop.run_until_complete(main3())
    
    def test_case_4(self):
        logger.info('4. Обработка сообщений с несколькими корутинами.')
        async def func1():
            data1 = {'id': 1, 'name': 'Leanne Graham', 'username': 'Bret', 'email': 'Sincere@april.biz', 'address': {'street': 'Kulas Light', 'suite': 'Apt. 556', 'city': 'Gwenborough', 'zipcode': '92998-3874', 'geo': {'lat': '-37.3159', 'lng': '81.1496'}}, 'phone': '1-770-736-8031 x56442', 'website': 'hildegard.org', 'company': {'name': 'Romaguera-Crona', 'catchPhrase': 'Multi-layered client-server neural-net', 'bs': 'harness real-time e-markets'}}
            data2 = {'postId': 1, 'id': 1, 'name': 'id labore ex et quam laborum', 'email': 'Eliseo@gardner.biz', 'body': 'laudantium enim quasi est quidem magnam voluptate ipsam eos\ntempora quo necessitatibus\ndolor quam autem quasi\nreiciendis et nam sapiente accusantium'}
            data3 = {'userId': 1, 'id': 1, 'title': 'delectus aut autem', 'completed': False}
            await self.asyncfb.put(json.dumps(data1))
            await asyncio.sleep(.5)
            await self.asyncfb.put(json.dumps(data2))
            await asyncio.sleep(.5)
            await self.asyncfb.put(json.dumps(data3))
        
        async def func2():
            data4 = {'userId': 2, 'id': 4, 'title': 'delectus aut autem', 'completed': True}
            key4 = await self.asyncfb.put(json.dumps(data4), use_get_key=True)
            k, c = await self.asyncfb.get(key4)
            await asyncio.sleep(1.1)
            await self.asyncfb.done(k)
        
        async def func3():
            while True:
                r = await self.asyncfb.get(timeout=1.1)
                if r is None:
                    return
                await asyncio.sleep(1.1)
                await self.asyncfb.done(r[0])
        
        async def func4():
            while True:
                r = await self.asyncfb.get(timeout=1.1)
                if r is None:
                    return
                await self.asyncfb.done(r[0])
        
        async def main4():
            await self.asyncfb.init()
            tasks = [
                asyncio.create_task(func1()),
                asyncio.create_task(func2()),
                asyncio.create_task(func3()),
                asyncio.create_task(func4())
            ]
            await asyncio.gather(*tasks)
            s=await self.asyncfb.size()
            self.assertEqual(s, 0)
        self.loop.run_until_complete(main4())
        logger.info('----Все сообщения были обработаны.')
        logger.info("-------------------------------------------------------")


if __name__ == "__main__":
    TestSimpleBox.start()