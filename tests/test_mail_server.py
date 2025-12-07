from settings import logger, BaseTest
from mail_pigeon.mail_server import MailServer, MessageCommand, CommandsCode
from mail_pigeon.async_server.mail_server import AsyncMailServer
from mail_pigeon import logger as mail_logger
import asyncio
import time
import zmq
import zmq.asyncio

import logging
mail_logger.setLevel(logging.INFO)

class TestMailServer(BaseTest):
    
    @classmethod
    def filename_test(cls):
        return 'test_mail_server.log'
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.loop = asyncio.new_event_loop()
    
    @classmethod
    def tearDownClass(cls):
        ...
    
    def test_case_1(self):
        server = MailServer(5556)
        context = zmq.Context()
        socket1 = context.socket(zmq.DEALER)
        socket1.setsockopt_string(zmq.IDENTITY, 'my_client_identity1')
        socket1.connect('tcp://127.0.0.1:5556')
        
        socket2 = context.socket(zmq.DEALER)
        socket2.setsockopt_string(zmq.IDENTITY, 'my_client_identity2')
        socket2.connect('tcp://127.0.0.1:5556')
        
        socket3 = context.socket(zmq.DEALER)
        socket3.setsockopt_string(zmq.IDENTITY, 'my_client_identity3')
        socket3.connect('tcp://127.0.0.1:5556')
        
        logger.info('1. Подключение клиента к серверу.')
        logger.info('---- Клиента 1.')
        socket1.send_multipart([MailServer.SERVER_NAME.encode(), CommandsCode.CONNECT_CLIENT.encode()])
        data = socket1.recv_multipart()
        self.assertEqual(len(server.clients_wait_connect), 1)
        msg = MessageCommand.parse(data[1])
        self.assertEqual(len(msg.data), 0)
        socket1.send_multipart([MailServer.SERVER_NAME.encode(), CommandsCode.CONFIRM_CONNECT.encode()])
        time.sleep(.1)
        data = socket1.recv_multipart()
        self.assertEqual(len(server.clients_wait_connect), 0)
        self.assertEqual(len(server.clients), 1)
        
        logger.info('---- Клиента 2.')
        socket2.send_multipart([MailServer.SERVER_NAME.encode(), CommandsCode.CONNECT_CLIENT.encode()])
        time.sleep(.1)
        data = socket2.recv_multipart()
        msg = MessageCommand.parse(data[1])
        self.assertEqual(len(msg.data), 1)
        self.assertEqual(len(server.clients_wait_connect), 1)
        socket2.send_multipart([MailServer.SERVER_NAME.encode(), CommandsCode.CONFIRM_CONNECT.encode()])
        time.sleep(.1)
        data = socket2.recv_multipart()
        self.assertEqual(len(server.clients_wait_connect), 0)
        self.assertEqual(len(server.clients), 2)
        
        logger.info('---- Клиента 3.')
        socket3.send_multipart([MailServer.SERVER_NAME.encode(), CommandsCode.CONNECT_CLIENT.encode()])
        data = socket3.recv_multipart()
        msg = MessageCommand.parse(data[1])
        self.assertEqual(len(msg.data), 2)
        socket3.send_multipart([MailServer.SERVER_NAME.encode(), CommandsCode.CONFIRM_CONNECT.encode()])
        time.sleep(.1)
        msg1 = MessageCommand.parse(socket1.recv_multipart()[1])
        msg2 = MessageCommand.parse(socket1.recv_multipart()[1])
        msg3 = MessageCommand.parse(socket2.recv_multipart()[1])
        self.assertEqual('my_client_identity2', msg1.data)
        self.assertEqual('my_client_identity3', msg2.data)
        self.assertEqual('my_client_identity3', msg3.data)
        time.sleep(.1)
        self.assertEqual(len(server.clients_wait_connect), 0)
        self.assertEqual(len(server.clients), 3)
        # server.stop()
        socket1.close()
        socket2.close()
        socket3.close()
        context.term()
        logger.info("-------------------------------------------------------")
    
    def test_case_2(self):
        async def main():
            server = AsyncMailServer(5557)
            await asyncio.sleep(.1)
            context = zmq.asyncio.Context()
            socket1 = context.socket(zmq.DEALER)
            socket1.setsockopt_string(zmq.IDENTITY, 'my_client_identity1')
            socket1.connect('tcp://127.0.0.1:5557')
            
            socket2 = context.socket(zmq.DEALER)
            socket2.setsockopt_string(zmq.IDENTITY, 'my_client_identity2')
            socket2.connect('tcp://127.0.0.1:5557')
            
            socket3 = context.socket(zmq.DEALER)
            socket3.setsockopt_string(zmq.IDENTITY, 'my_client_identity3')
            socket3.connect('tcp://127.0.0.1:5557')
            
            logger.info('2. Подключение клиента к асинхронному серверу.')
            logger.info('---- Клиента 1.')
            await socket1.send_multipart([MailServer.SERVER_NAME.encode(), CommandsCode.CONNECT_CLIENT.encode()])
            data = await socket1.recv_multipart()
            res=await server.clients_wait_connect()
            self.assertEqual(len(res), 1)
            msg = MessageCommand.parse(data[1])
            self.assertEqual(len(msg.data), 0)
            await socket1.send_multipart([MailServer.SERVER_NAME.encode(), CommandsCode.CONFIRM_CONNECT.encode()])
            await asyncio.sleep(.1)
            data = await socket1.recv_multipart()
            res1=await server.clients_wait_connect()
            res2=await server.clients()
            self.assertEqual(len(res1), 0)
            self.assertEqual(len(res2), 1)
            
            logger.info('---- Клиента 2.')
            await socket2.send_multipart([MailServer.SERVER_NAME.encode(), CommandsCode.CONNECT_CLIENT.encode()])
            await asyncio.sleep(.1)
            data = await socket2.recv_multipart()
            msg = MessageCommand.parse(data[1])
            self.assertEqual(len(msg.data), 1)
            res1=await server.clients_wait_connect()
            self.assertEqual(len(res1), 1)
            await socket2.send_multipart([MailServer.SERVER_NAME.encode(), CommandsCode.CONFIRM_CONNECT.encode()])
            await asyncio.sleep(.1)
            data = await socket2.recv_multipart()
            res1=await server.clients_wait_connect()
            res2=await server.clients()
            self.assertEqual(len(res1), 0)
            self.assertEqual(len(res2), 2)
            
            logger.info('---- Клиента 3.')
            await socket3.send_multipart([MailServer.SERVER_NAME.encode(), CommandsCode.CONNECT_CLIENT.encode()])
            data = await socket3.recv_multipart()
            msg = MessageCommand.parse(data[1])
            self.assertEqual(len(msg.data), 2)
            await socket3.send_multipart([MailServer.SERVER_NAME.encode(), CommandsCode.CONFIRM_CONNECT.encode()])
            await asyncio.sleep(.1)
            res1 = await socket1.recv_multipart()
            res2 = await socket1.recv_multipart()
            res3 = await socket2.recv_multipart()
            msg1 = MessageCommand.parse(res1[1])
            msg2 = MessageCommand.parse(res2[1])
            msg3 = MessageCommand.parse(res3[1])
            self.assertEqual('my_client_identity2', msg1.data)
            self.assertEqual('my_client_identity3', msg2.data)
            self.assertEqual('my_client_identity3', msg3.data)
            await asyncio.sleep(.1)
            res1=await server.clients_wait_connect()
            res2=await server.clients()
            self.assertEqual(len(res1), 0)
            self.assertEqual(len(res2), 3)
            # server.stop()
            socket1.close()
            socket2.close()
            socket3.close()
            context.term()
            await server.stop()
            logger.info("-------------------------------------------------------")
        self.loop.run_until_complete(main())


if __name__ == "__main__":
    TestMailServer.start()