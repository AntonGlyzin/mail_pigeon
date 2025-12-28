from settings import logger, BaseTest
from mail_pigeon import logger as mail_logger
import asyncio
import time
import zmq

import logging
mail_logger.setLevel(logging.INFO)

class TestZMQ(BaseTest):
    
    @classmethod
    def filename_test(cls):
        return 'test_zmq.log'
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.loop = asyncio.new_event_loop()
        cls.context = zmq.Context()
    
    @classmethod
    def tearDownClass(cls):
        cls.context.term()
        
    def _get_server(self):
        socketsrv = self.context.socket(zmq.ROUTER)
        # socketsrv.setsockopt(zmq.IMMEDIATE, 1) # не буферизовать для неготовых
        socketsrv.setsockopt(zmq.TCP_KEEPALIVE, 1) # отслеживать мертвое соединение
        socketsrv.setsockopt(zmq.TCP_KEEPALIVE_IDLE, 15) # сек. начать проверку если нет активности
        socketsrv.setsockopt(zmq.TCP_KEEPALIVE_INTVL, 10) # сек. повторная проверка
        socketsrv.setsockopt(zmq.TCP_KEEPALIVE_CNT, 3) # количество проверок
        socketsrv.setsockopt(zmq.HEARTBEAT_IVL, 10000) # милисек. сделать ping если нет трафика
        socketsrv.setsockopt(zmq.HEARTBEAT_TIMEOUT, 20000) # если так и нет трафика или pong, то разрыв
        socketsrv.setsockopt(zmq.LINGER, 1000) # милисек. ждать при закрытии
        socketsrv.setsockopt(zmq.ROUTER_MANDATORY, 1)  # знать об отключениях
        socketsrv.setsockopt(zmq.ROUTER_HANDOVER, 1) # использовать одинаковые ID для переподплючения
        socketsrv.setsockopt(zmq.MAXMSGSIZE, -1)  # снимаем ограничение на размер одного сообщения
        socketsrv.setsockopt(zmq.SNDHWM, 3) # ограничить буфер на отправку
        socketsrv.bind("tcp://*:5555")
        logger.info("ROUTER bound to tcp://*:5555")
        return socketsrv
        
    def _get_client(self, name):
        socket1 = self.context.socket(zmq.DEALER)
        socket1.setsockopt(zmq.ROUTING_ID, name)
        socket1.setsockopt(zmq.SNDHWM, 3) # ограничить буфер на отправку
        socket1.setsockopt(zmq.SNDBUF, 65536) # системный буфер
        socket1.setsockopt(zmq.IMMEDIATE, 1) # не буферизовать для неготовых
        socket1.setsockopt(zmq.LINGER, 1000) # сброс через
        socket1.setsockopt(zmq.HEARTBEAT_IVL, 10000) # милисек. сделать ping если нет трафика
        socket1.setsockopt(zmq.HEARTBEAT_TIMEOUT, 20000) # если так и нет трафика или pong, то разрыв
        socket1.setsockopt(zmq.SNDTIMEO, 2000)  # милисек. если не удается отправить сообщение EAGAIN
        
        socket1.connect('tcp://127.0.0.1:5555')
        return socket1
    
    def test_case_1(self):
        print(f"zmq version: {zmq.__version__}")
        print(f"zmq.zmq_version(): {zmq.zmq_version()}")
        socketsrv = self._get_server()
        
        time.sleep(1)
        socket0 = self._get_client(b'client0')
        time.sleep(1)
        try:
            socket0.send_multipart([b'hello from server'], flags=zmq.NOBLOCK)
            socket0.send_multipart([ b'hello from server'], flags=zmq.NOBLOCK)
            socket0.send_multipart([ b'hello from server'], flags=zmq.NOBLOCK)
            socket0.send_multipart([ b'hello from server'], flags=zmq.NOBLOCK)
        except zmq.ZMQError as e:
            if zmq.EAGAIN == e.errno:
                print(f'client send {e} - {e.errno}')
        
        time.sleep(1)
        try:
            socketsrv.send_multipart([b'client0', b'', b'hello from server'], flags=zmq.NOBLOCK)
            socketsrv.send_multipart([b'client0', b'', b'hello from server'], flags=zmq.NOBLOCK)
            socketsrv.send_multipart([b'client0', b'', b'hello from server'], flags=zmq.NOBLOCK)
            socketsrv.send_multipart([ b'client0', b'', b'hello from server'], flags=zmq.NOBLOCK)
        except zmq.ZMQError as e:
            if zmq.EAGAIN == e.errno:
                print(f'server send {e} - {e.errno}')
        socketsrv.close()
        socket0.close()
        
        
        time.sleep(1)
        socketsrv = self._get_server()
        time.sleep(1)
        socket1 = self._get_client(b'client1')
        
        time.sleep(.1)
        logger.info("1. Сервер отправляет существующему клиенту client1")
        socketsrv.send_multipart([b'client1', b'', b'hello from server'], flags=zmq.NOBLOCK)
        msg = socket1.recv_multipart()
        logger.info("2. Сервер отправляет не существующему клиенту client2")
        try:
            socketsrv.send_multipart([b'client2', b'', b'hello from server'], flags=zmq.NOBLOCK)
        except zmq.ZMQError as e:
            if e.errno == zmq.EHOSTUNREACH:
                logger.info("---client2 нет")
        
        socketsrv.send_multipart([b'client1', b'', b'hello from server'], flags=zmq.NOBLOCK)
        socket1.close()
        logger.info("3. Сервер отправляет клиенту client1 с закрывшим соединением.")
        try:
            socketsrv.send_multipart([b'client1', b'', b'hello from server'], flags=zmq.NOBLOCK)
        except zmq.ZMQError as e:
            if e.errno == zmq.EHOSTUNREACH:
                logger.info("---client1 нет")
        
        logger.info("4. Добавляем клиента client1.")
        socket3 = self._get_client(b'client1')
        time.sleep(.1)
        socket3.send_multipart([b'hello from server'], flags=zmq.NOBLOCK)
        msg = socketsrv.recv_multipart()
        
        socketsrv.close()
        logger.info("6. Отправить сообщение остановленному серверу.")
        try:
            socket3.send_multipart([b'hello from server'], flags=zmq.NOBLOCK)
        except zmq.ZMQError as e:
            if e.errno == zmq.EAGAIN:
                logger.info("---Сервер закрыл соединение")
            
        socketsrv = self._get_server()
        time.sleep(1)
        socketsrv.send_multipart([b'client1', b'', b'hello from server'], flags=zmq.NOBLOCK)
        msg = socket3.recv_multipart()
        
        socket3.close()
        logger.info("7. Отправить сообщение с закрытым сокетом.")
        try:
            socket3.send_multipart([b'hello from server'], flags=zmq.NOBLOCK)
        except zmq.ZMQError as e:
            if e.errno == zmq.ENOTSOCK:
                logger.info("---Сокет закрыт")
        
        socketsrv.close()


if __name__ == "__main__":
    TestZMQ.start()