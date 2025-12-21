import uuid
from typing import Optional, List, Tuple
import asyncio
from asyncio import Condition
from abc import ABC, abstractmethod


class BaseAsyncQueue(ABC):
    
    def __init__(self) -> None:
        self._queue: List[str] = [] # на отправление
        self._wait_keys_queue: List[str] = [] # ключи, которые могут ожитаться из разных потоков
        self._wait_queue: List[str] = [] # приходят письма, которые ожидают по ключу
        self._send_queue: List[str] = [] # отправленные или те, которые не должны отправиться
        self._cond = Condition()
        asyncio.create_task(self._init())

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

    async def clear(self):
        """ Очищение файловой очереди. """        
        async with self._cond:
            for key in self._queue+self._wait_queue+self._send_queue:
                await self._remove_data(key)
            self._queue.clear()
            self._wait_queue.clear()
            self._send_queue.clear()
    
    async def size(self) -> int:
        """Количество элементов по всей очереди.

        Returns:
            int: Размер очереди.
        """        
        async with self._cond:
            return (len(self._queue)
                    +len(self._wait_queue)
                    +len(self._send_queue))

    async def put(self, value: str, key: Optional[str] = None, use_get_key: bool = False) -> str:
        """Помещяет значение в очередь.

        Args:
            value (str): Значение в очередь.
            key (str): Помещает значение в очередь под этим ключом.
            use_get_key (bool): Элемент будет добавлен в ожидающую очередь по ключу `.get(key)`. 

        Returns:
            str: Ключ значения.
        """        
        async with self._cond:
            local_key = key or self._gen_key()
            await self._save_data(local_key, value)
            if use_get_key:
                self._wait_queue.append(local_key)
            else:
                self._queue.append(local_key)
            self._cond.notify_all()
        return local_key

    async def get(self, key: Optional[str] = None, timeout: Optional[float] = None) -> Optional[Tuple[str, str]]:
        """Получает ключ и значение из очереди.
        Когда очередь пуста, то метод блокируется, если не установлен timeout.
        
        Args:
            key (str, optional): Ждать значение по ключу.
            timeout (float, optional): Сколько в секундах ждать результата.

        Returns:
            Optional[Tuple[str, str]]: Ключ и значение, или пусто если есть timeout.
        """
        async with self._cond:
            if not key:
                while not self._queue:
                    try:
                        await asyncio.wait_for(self._cond.wait(), timeout=timeout)
                    except asyncio.TimeoutError:
                        pass
                    if timeout and not self._queue:
                        return None
                key = self._queue.pop(0)
                self._send_queue.append(key)
            else:
                self._wait_keys_queue.append(key)
                while key not in self._wait_queue:
                    try:
                        await asyncio.wait_for(self._cond.wait(), timeout=timeout)
                    except asyncio.TimeoutError:
                        pass
                    if key not in self._wait_keys_queue:
                        return None
                    if timeout and (key not in self._wait_queue):
                        self._wait_keys_queue.remove(key)
                        return None
                self._wait_keys_queue.remove(key)
            if key is None:
                return None
            content = await self._read_data(key)
        return key, content

    async def done(self, key: str):
        """Завершает выполнение задачи в ожидающей и отправленной очереди.

        Args:
            key (str): Ключ задачи.
        """        
        async with self._cond:
            if key in self._wait_queue:
                self._wait_queue.remove(key)
                await self._remove_data(key)
            if key in self._send_queue:
                self._send_queue.remove(key)
                await self._remove_data(key)
            if key in self._queue:
                self._queue.remove(key)
                await self._remove_data(key)
    
    async def to_queue(self, key: str = ''):
        """Перемещает элемент снова на отправления в начало очереди.
        Можно переместить все ключи по части название key.
            
            Args:
                key (str): Часть ключа.
        """        
        async with self._cond:
            send_q = []
            for sendkey in self._send_queue:
                if sendkey.startswith(key):
                    send_q.append(sendkey)
            for i in send_q:
                self._send_queue.remove(i)
            self._queue = send_q + self._queue
            if send_q:
                self._cond.notify_all()
    
    async  def to_send_queue(self, key: str = ''):
        """Перемещает элемент на ожидание в отправленные.
        Можно переместить все ключи по части название key.
            
            Args:
                key (str): Часть ключа.
        """        
        async with self._cond:
            send_q = []
            for sendkey in self._queue:
                if sendkey.startswith(key):
                    send_q.append(sendkey)
            for i in send_q:
                self._queue.remove(i)
                self._send_queue.append(i)
    
    async def del_wait_key(self, key: str = ''):
        """Удалить ключи из ожиданий, чтобы вывести потоки из блока.
            
            Args:
                key (str): Часть ключа.
        """        
        async with self._cond:
            del_items = []
            for k in self._wait_keys_queue:
                if k.startswith(key):
                    del_items.append(k)
            for item in del_items:
                self._wait_keys_queue.remove(item)

    async def gen_key(self) -> str:
        """Генерация ключа для очереди.

        Returns:
            str: Ключ.
        """
        async with self._cond:
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
    
    async def _init(self) -> None:
        """ Инициализация очереди при создание экземпляра. """
        async with self._cond:
            self._queue = await self._init_queue()

    @abstractmethod
    async def _init_queue(self) -> List[str]:
        """Инициализация очереди при создание экземпляра.

        Returns:
            List[str]: Список.
        """        
        ...

    @abstractmethod
    async def _remove_data(self, key: str):
        """Удаляет данные одного элемента.

        Args:
            key (str): Ключ.
        """        
        ...

    @abstractmethod
    async def _read_data(self, key: str) -> str:
        """Чтение данных по ключу.

        Args:
            key (str): Название.

        Returns:
            str: Прочитанные данные.
        """        
        ...

    @abstractmethod
    async def _save_data(self, key: str, value: str):
        """Сохраняет данные.

        Args:
            value (str): Ключ.
            value (str): Значение.
        """        
        ...