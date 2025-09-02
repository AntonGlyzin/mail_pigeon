from settings import logger, BaseTest
from mail_pigeon.queue import FilesBox
from threading import Thread
import json
import time

class TestFilesBox(BaseTest):
    
    @classmethod
    def filename_test(cls):
        return 'test_files_box.log'
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.fb = FilesBox(timeout_processing=2)
        
    @classmethod
    def tearDownClass(cls):
        cls.fb.clear()
    
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
        time.sleep(1.5)
        k5, d5 = self.fb.get(k4)
        self.assertEqual(k4, k5)
        time.sleep(1.5)
        self.fb.done(k5)
        self.fb.done(k5) # если запоздал в обработке, но захочет удалить
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


if __name__ == "__main__":
    TestFilesBox.start()