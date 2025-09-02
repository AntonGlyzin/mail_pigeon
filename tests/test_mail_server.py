from settings import logger, BaseTest
from mail_pigeon.mail_server import MailServer, MessageCommand, CommandsCode
from mail_pigeon import logger as mail_logger
import time
import zmq

import logging
mail_logger.setLevel(logging.INFO)

class TestMailServer(BaseTest):
    
    @classmethod
    def filename_test(cls):
        return 'test_mail_server.log'
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server = MailServer(5556)
        cls.context = zmq.Context()
        cls.socket1 = cls.context.socket(zmq.DEALER)
        cls.socket1.setsockopt_string(zmq.IDENTITY, 'my_client_identity1')
        cls.socket1.connect('tcp://127.0.0.1:5556')
        
        cls.socket2 = cls.context.socket(zmq.DEALER)
        cls.socket2.setsockopt_string(zmq.IDENTITY, 'my_client_identity2')
        cls.socket2.connect('tcp://127.0.0.1:5556')
        
        cls.socket3 = cls.context.socket(zmq.DEALER)
        cls.socket3.setsockopt_string(zmq.IDENTITY, 'my_client_identity3')
        cls.socket3.connect('tcp://127.0.0.1:5556')
        
    @classmethod
    def tearDownClass(cls):
        cls.server.stop()
    
    def test_case_1(self):
        logger.info('1. Подключение клиента к серверу.')
        logger.info('---- Клиента 1.')
        self.socket1.send_multipart([MailServer.SERVER_NAME, CommandsCode.CONNECT_CLIENT])
        data = self.socket1.recv_multipart()
        self.assertEqual(len(self.server.clients_wait_connect), 1)
        msg = MessageCommand.parse(data[1])
        self.assertEqual(len(eval(msg.data)), 0)
        self.socket1.send_multipart([MailServer.SERVER_NAME, CommandsCode.CONFIRM_CONNECT])
        time.sleep(.01)
        self.assertEqual(len(self.server.clients_wait_connect), 0)
        self.assertEqual(len(self.server.clients), 1)
        data = self.socket1.recv_multipart()
        self.assertEqual(b'confirm:', data[1])
        
        logger.info('---- Клиента 2.')
        self.socket2.send_multipart([MailServer.SERVER_NAME, CommandsCode.CONNECT_CLIENT])
        time.sleep(.01)
        data = self.socket2.recv_multipart()
        msg = MessageCommand.parse(data[1])
        self.assertEqual(len(eval(msg.data)), 1)
        self.assertEqual(len(self.server.clients_wait_connect), 1)
        time.sleep(.01)
        self.socket2.send_multipart([MailServer.SERVER_NAME, CommandsCode.CONFIRM_CONNECT])
        data = self.socket2.recv_multipart()
        self.assertEqual(b'confirm:', data[1])
        self.assertEqual(len(self.server.clients_wait_connect), 0)
        self.assertEqual(len(self.server.clients), 2)
        data = self.socket1.recv_multipart()
        self.assertEqual(b'new_client:my_client_identity2', data[1])
        
        logger.info('---- Клиента 3.')
        self.socket3.send_multipart([MailServer.SERVER_NAME, CommandsCode.CONNECT_CLIENT])
        data = self.socket3.recv_multipart()
        msg = MessageCommand.parse(data[1])
        self.assertEqual(len(eval(msg.data)), 2)
        self.socket3.send_multipart([MailServer.SERVER_NAME, CommandsCode.CONFIRM_CONNECT])
        data1 = self.socket1.recv_multipart()
        data2 = self.socket2.recv_multipart()
        self.assertEqual(b'new_client:my_client_identity3', data1[1])
        self.assertEqual(b'new_client:my_client_identity3', data2[1])
        time.sleep(.01)
        self.assertEqual(len(self.server.clients_wait_connect), 0)
        self.assertEqual(len(self.server.clients), 3)
        
        logger.info("-------------------------------------------------------")
        
if __name__ == "__main__":
    TestMailServer.start()