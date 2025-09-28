import json
from settings import logger, BaseTest
from mail_pigeon.security import TypesEncryptors

class TestEncryptors(BaseTest):
    
    @classmethod
    def filename_test(cls):
        return 'test_encryptors.log'
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
    def _check(self, cipher, cipher2, cipher3):
        data1 = {'id': 1, 'name': 'Leanne Graham', 'username': 'Bret', 'email': 'Sincere@april.biz', 'address': {'street': 'Kulas Light', 'suite': 'Apt. 556', 'city': 'Gwenborough', 'zipcode': '92998-3874', 'geo': {'lat': '-37.3159', 'lng': '81.1496'}}, 'phone': '1-770-736-8031 x56442', 'website': 'hildegard.org', 'company': {'name': 'Romaguera-Crona', 'catchPhrase': 'Multi-layered client-server neural-net', 'bs': 'harness real-time e-markets'}}
        aes_encrypt = cipher.encrypt(json.dumps(data1).encode())
        self.assertEqual(cipher.decrypt(aes_encrypt).decode(), json.dumps(data1))
        self.assertEqual(cipher3.decrypt(aes_encrypt).decode(), json.dumps(data1))
        with self.assertRaises(Exception):
            cipher2.decrypt(aes_encrypt).decode()
    
    def test_case_1(self):
        logger.info('1. Проверка классов для шифрования сообщений.')
        word = 'admin'
        word2 = 'admin2'
        
        logger.info('--- Проверка HMAC.')
        cipher = TypesEncryptors.HMAC(word)
        cipher2 = TypesEncryptors.HMAC(word2)
        cipher3 = TypesEncryptors.HMAC(word)
        self._check(cipher, cipher2, cipher3)
        logger.info("-------------------------------------------------------")


if __name__ == "__main__":
    TestEncryptors.start()