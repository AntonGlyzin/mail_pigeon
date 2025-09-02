from settings import logger, BaseTest
from mail_pigeon.translate import Translate

class TestTranslate(BaseTest):
    
    @classmethod
    def filename_test(cls):
        return 'test_translete.log'
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
    
    def test_case_1(self):
        logger.info('1. Проверка класса локализации.')
        Translate._get_local = lambda s: ['en', '']
        t1 = Translate().func_gettext()
        self.assertEqual(t1('{}: Ошибка в главном цикле блока zmq.ZMQError. '), '{}: Error in main ZMQError loop. ')
        self.assertEqual(t1('Текст которого нет.'), 'Текст которого нет.')
        
        Translate.instance = None
        Translate._get_local = lambda s: ['ru_RU', '']
        t2 = Translate().func_gettext()
        self.assertEqual(t2('{}: Ошибка в главном цикле блока zmq.ZMQError. '), '{}: Ошибка в главном цикле блока zmq.ZMQError. ')
        self.assertEqual(t2('Текст которого нет.'), 'Текст которого нет.')
        logger.info("-------------------------------------------------------")


if __name__ == "__main__":
    TestTranslate.start()