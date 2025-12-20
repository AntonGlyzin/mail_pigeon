import uuid
from typing import Optional, List, Tuple
from threading import Condition
from abc import ABC, abstractmethod


class BaseQueue(ABC):
    
    def __init__(self):
        self._queue: List[str] = self._init_queue() or [] # на отправления
        self._wait_queue: List[str] = [] # ожидает по ключу
        self._send_queue: List[str] = [] # отправленные
        self._cond = Condition()

    @property
    def queue_mails(self) ->List[str]:
        """Сообщения на обработку.

        Returns:
            List[str]: Список ключей.
        """
        return list(self._queue)
    
    @property
    def wait_mails(self) ->List[str]:
        """Ожидающие сообщения по ключу.

        Returns:
            List[str]: Список ключей.
        """
        return list(self._wait_queue)
    
    @property
    def send_mails(self) ->List[str]:
        """Отправленые сообщения, но не подтвержденные.

        Returns:
            List[str]: Список ключей.
        """
        return list(self._send_queue)

    def clear(self):
        """ Очищение файловой очереди. """        
        with self._cond:
            for key in self._queue+self._wait_queue+self._send_queue:
                self._remove_data(key)
            self._queue.clear()
            self._wait_queue.clear()
            self._send_queue.clear()
    
    def size(self) -> int:
        """Количество элементов по всей очереди.

        Returns:
            int: Размер очереди.
        """        
        with self._cond:
            return (len(self._queue)
                    +len(self._wait_queue)
                    +len(self._send_queue))

    def put(self, value: str, key: str = None, use_get_key: bool = False) -> str:
        """Помещяет значение в очередь.

        Args:
            value (str): Значение в очередь.
            key (str): Помещает значение в очередь под этим ключом.
            use_get_key (bool): Элемент будет добавлен в ожидающую очередь по ключу `.get(key)`. 

        Returns:
            str: Ключ значения.
        """        
        with self._cond:
            local_key = key or self._gen_key()
            self._save_data(local_key, value)
            if use_get_key:
                self._wait_queue.append(local_key)
            else:
                self._queue.append(local_key)
            self._cond.notify_all()
        return local_key

    def get(self, key: str = None, timeout: float = None) -> Optional[Tuple[str, str]]:
        """Получает ключ и значение из очереди.
        Когда очередь пуста, то метод блокируется, если не установлен timeout.
        
        Args:
            key (str, optional): Ждать значение по ключу.
            timeout (float, optional): Сколько в секундах ждать результата.

        Returns:
            Optional[Tuple[str, str]]: Ключ и значение, или пусто если есть timeout.
        """
        with self._cond:
            if not key:
                while not self._queue:
                    self._cond.wait(timeout=timeout)
                    if timeout and not self._queue:
                        return None
                key = self._queue.pop(0)
                self._send_queue.append(key)
            else:
                while key not in self._wait_queue:
                    self._cond.wait(timeout=timeout)
                    if timeout and (key not in self._wait_queue):
                        return None
            content = self._read_data(key)
        return key, content

    def done(self, key: str):
        """Завершает выполнение задачи в ожидающей и отправленной очереди.

        Args:
            key (str): Ключ задачи.
        """        
        with self._cond:
            if key in self._wait_queue:
                self._wait_queue.remove(key)
                self._remove_data(key)
            if key in self._send_queue:
                self._send_queue.remove(key)
                self._remove_data(key)
            if key in self._queue:
                self._queue.remove(key)
                self._remove_data(key)
    
    def to_queue(self, key: str = ''):
        """Перемещает элемент снова на отправления.
        Можно переместить все ключи по части название в key.
            
            Args:
                key (str): Ключ.
        """        
        with self._cond:
            send_q = []
            for sendkey in self._send_queue:
                if sendkey.startswith(key):
                    send_q.append(sendkey)
            for i in send_q:
                self._send_queue.remove(i)
            self._queue = send_q + self._queue
            if send_q:
                self._cond.notify_all()
    
    def to_wait_queue(self, key: str = ''):
        """Перемещает элемент на ожидание в отправленные.
        Можно переместить все ключи по части название в key.
            
            Args:
                key (str): Ключ.
        """        
        with self._cond:
            send_q = []
            for sendkey in self._queue:
                if sendkey.startswith(key):
                    send_q.append(sendkey)
            for i in send_q:
                self._queue.remove(i)
                self._send_queue.append(i)

    def gen_key(self) -> str:
        """Генерация ключа для очереди.

        Returns:
            str: Ключ.
        """
        with self._cond:
            return self._gen_key()
    
    def _gen_key(self) -> str:
        """Генерация ключа для очереди.

        Returns:
            str: Ключ.
        """
        while True:
            new_name = uuid.uuid4().hex
            if new_name in self._wait_queue:
                continue
            if new_name in self._queue:
                continue
            if new_name in self._send_queue:
                continue
            return new_name

    @abstractmethod
    def _init_queue(self) -> List[str]:
        """Инициализация очереди при создание экземпляра.

        Returns:
            List[str]: Список.
        """        
        ...

    @abstractmethod
    def _remove_data(self, key: str):
        """Удаляет данные одного элемента.

        Args:
            key (str): Ключ.
        """        
        ...

    @abstractmethod
    def _read_data(self, key: str) -> str:
        """Чтение данных по ключу.

        Args:
            key (str): Название.

        Returns:
            str: Прочитанные данные.
        """        
        ...

    @abstractmethod
    def _save_data(self, key: str, value: str):
        """Сохраняет данные.

        Args:
            value (str): Ключ.
            value (str): Значение.
        """        
        ...