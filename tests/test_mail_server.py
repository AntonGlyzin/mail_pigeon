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
        
    @classmethod
    def tearDownClass(cls):
        ...
    
    def test_case_1(self):
        self.server = MailServer(5556)
        self.context = zmq.Context()
        self.socket1 = self.context.socket(zmq.DEALER)
        self.socket1.setsockopt_string(zmq.IDENTITY, 'my_client_identity1')
        self.socket1.connect('tcp://127.0.0.1:5556')
        
        self.socket2 = self.context.socket(zmq.DEALER)
        self.socket2.setsockopt_string(zmq.IDENTITY, 'my_client_identity2')
        self.socket2.connect('tcp://127.0.0.1:5556')
        
        self.socket3 = self.context.socket(zmq.DEALER)
        self.socket3.setsockopt_string(zmq.IDENTITY, 'my_client_identity3')
        self.socket3.connect('tcp://127.0.0.1:5556')
        
        logger.info('1. Подключение клиента к серверу.')
        logger.info('---- Клиента 1.')
        self.socket1.send_multipart([MailServer.SERVER_NAME.encode(), CommandsCode.CONNECT_CLIENT.encode()])
        data = self.socket1.recv_multipart()
        self.assertEqual(len(self.server.clients_wait_connect), 1)
        msg = MessageCommand.parse(data[1])
        self.assertEqual(len(msg.data), 0)
        self.socket1.send_multipart([MailServer.SERVER_NAME.encode(), CommandsCode.CONFIRM_CONNECT.encode()])
        time.sleep(.1)
        data = self.socket1.recv_multipart()
        self.assertEqual(len(self.server.clients_wait_connect), 0)
        self.assertEqual(len(self.server.clients), 1)
        
        logger.info('---- Клиента 2.')
        self.socket2.send_multipart([MailServer.SERVER_NAME.encode(), CommandsCode.CONNECT_CLIENT.encode()])
        time.sleep(.1)
        data = self.socket2.recv_multipart()
        msg = MessageCommand.parse(data[1])
        self.assertEqual(len(msg.data), 1)
        self.assertEqual(len(self.server.clients_wait_connect), 1)
        self.socket2.send_multipart([MailServer.SERVER_NAME.encode(), CommandsCode.CONFIRM_CONNECT.encode()])
        time.sleep(.1)
        data = self.socket2.recv_multipart()
        self.assertEqual(len(self.server.clients_wait_connect), 0)
        self.assertEqual(len(self.server.clients), 2)
        
        logger.info('---- Клиента 3.')
        self.socket3.send_multipart([MailServer.SERVER_NAME.encode(), CommandsCode.CONNECT_CLIENT.encode()])
        data = self.socket3.recv_multipart()
        msg = MessageCommand.parse(data[1])
        self.assertEqual(len(msg.data), 2)
        self.socket3.send_multipart([MailServer.SERVER_NAME.encode(), CommandsCode.CONFIRM_CONNECT.encode()])
        time.sleep(.1)
        msg1 = MessageCommand.parse(self.socket1.recv_multipart()[1])
        msg2 = MessageCommand.parse(self.socket1.recv_multipart()[1])
        msg3 = MessageCommand.parse(self.socket2.recv_multipart()[1])
        self.assertEqual('my_client_identity2', msg1.data)
        self.assertEqual('my_client_identity3', msg2.data)
        self.assertEqual('my_client_identity3', msg3.data)
        time.sleep(.1)
        self.assertEqual(len(self.server.clients_wait_connect), 0)
        self.assertEqual(len(self.server.clients), 3)
        
        # self.server.stop()
        self.socket1.close()
        self.socket2.close()
        self.socket3.close()
        self.context.term()
        
        logger.info("-------------------------------------------------------")
        
if __name__ == "__main__":
    TestMailServer.start()