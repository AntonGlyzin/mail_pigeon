import uuid
import time
from typing import Optional, List, Tuple, Dict
from threading import Condition
from abc import ABC, abstractmethod


class IQueue(ABC):

    @abstractmethod
    def clear(self):
        """ Очищение файловой очереди. """
        ...
    
    @abstractmethod        
    def size(self) -> int:
        """Количество элементов во всей очереди.

        Returns:
            int: Размер очереди.
        """        
        ...

    @abstractmethod
    def put(self, value: str, key: str = None, use_get_key: bool = False) -> str:
        """Помещяет значение в очередь.

        Args:
            value (str): Значение в очередь.
            key (str): Помещает значение в очередь под этим ключом.
            use_get_key (bool): при получение `.get(key)` будем использовать ключ.

        Returns:
            str: Ключ значения.
        """        
        ...

    @abstractmethod
    def get(self, key: str = None, timeout: float = None) -> Optional[Tuple[str, str]]:
        """Получает ключ и значение из очереди.
        Когда очередь пуста, то метод блокируется, если не установлен timeout.
        
        Args:
            key (str, optional): Ждать значения по ключу. Нужно установить `use_get_key` в put.
            timeout (float, optional): Сколько в секундах ждать результата.

        Returns:
            res (Optional[(Tuple[str, str], optional)]): Ключ и значение, или пусто если есть timeout.
        """       
        ...

    @abstractmethod
    def done(self, key: str):
        """Завершает выполнение задачи, удаляя значение с файлом из любой очереди.

        Args:
            key (str): Ключ задачи.
        """        
        ...
    
    @abstractmethod
    def update(self):
        """ 
            Перемещает активные элементы снова 
            в живую очередь на выполнение _active_q -> _live_q, 
            потому как истекло время выполнения. Всегда выполняется перед `.get()`
        """
        ...
    
    @abstractmethod
    def move_active_to_live(self, key: str = '', startswith: bool = False):
        """
            Перемещает элемент снова в очередь на обработку.
            Если `key` пустая строка и активен `startswith`, то перемещает все. Если активен `startswith`
            и заполнен `key`, то перемещаются ключи в которых есть часть этого ключа.
            
            Args:
                key (str): Ключ.
                startswith (bool): Переместить ключи которые начинаются на key.
        """    
        ...
    
    @abstractmethod
    def move_live_to_active(self, key: str = '', startswith: bool = False):
        """
            Перемещает элемент в очередь на ожидание по ключу.
            Если `key` пустая строка и активен `startswith`, то перемещает все. Если активен `startswith`
            и заполнен `key`, то перемещаются ключи в которых есть часть этого ключа.
            
            Args:
                key (str): Ключ.
                startswith (bool): Переместить ключи которые начинаются на key.
        """ 
        ...
    
    @abstractmethod
    def gen_key(self) -> str:
        """Генерация ключа для очереди.

        Returns:
            str: Ключ.
        """
        ...


class BaseQueue(IQueue):
    
    def __init__(self, timeout_processing: int = None):
        """
        Args:
            timeout_processing (int, optional): Количество секунд в течение которых нужно обработать сообщение,
                которое было полученно методом .get(), но не удаленно методом .done(key) из очереди. При запоздание 
                в обработке, сообщение снова окажется в очереди, где его смогут получить другие потоки.
                Не относится к очереди, в которой ожидают значение по ключу.
                Если значение None, то из активного списка не будут происходить перемещения обратно.
        """
        self._timeout_processing = timeout_processing
        # очередь live_q содержит элементы которые еще будут обрабатываться
        self._live_q: List[str] = self._init_live_queue()
        # очередь active_q содержит элементы которые уже обрабатываются
        # {<название ключа>:<время когда помещен в очередь>}
        self._active_q: Dict[str, int] = {}
        self._cond = Condition()
    
    @property
    def active_keys(self) ->List[str]:
        """Активные ключи в обработки. От `.get()` до `.done()`

        Returns:
            List[str]: Список ключей в обработке.
        """        
        return [*self._active_q.keys()]
    
    @property
    def live_keys(self) ->List[str]:
        """Ожидают получения на обработку.

        Returns:
            List[str]: Список ключей в ожидающие получения из очереди.
        """        
        return [*self._live_q]

    def clear(self):
        """ Очищение файловой очереди. """        
        with self._cond:
            for key in self._live_q:
                self._remove_data(key)
            for key in self._active_q:
                self._remove_data(key)
            self._live_q.clear()
            self._active_q.clear()
            
    def size(self) -> int:
        """Количество элементов во всей очереди.

        Returns:
            int: Размер очереди.
        """        
        with self._cond:
            return len(self._live_q) + len(self._active_q)

    def put(self, value: str, key: str = None, use_get_key: bool = False) -> str:
        """Помещяет значение в очередь.

        Args:
            value (str): Значение в очередь.
            key (str): Помещает значение в очередь под этим ключом.
            use_get_key (bool): При получение `.get(key)` нужно использовать ключ.

        Returns:
            str: Ключ значения.
        """        
        with self._cond:
            key = key or self.gen_key()
            self._save_data(key, value)
            if use_get_key:
                self._active_q.update({key: int(time.time())})
            else:
                self._live_q.append(key)
            self._cond.notify_all()
        return key

    def get(self, key: str = None, timeout: float = None) -> Optional[Tuple[str, str]]:
        """Получает ключ и значение из очереди.
        Когда очередь пуста, то метод блокируется, если не установлен timeout.
        
        Args:
            key (str, optional): Ждать значения по ключу. Нужно установить `use_get_key` в put.
            timeout (float, optional): Сколько в секундах ждать результата.

        Returns:
            res (Optional[(Tuple[str, str], optional)]): Ключ и значение, или пусто если есть timeout.
        """
        self.update()
        with self._cond:
            if not key:
                while not self._live_q:
                    self._cond.wait(timeout=timeout)
                    if timeout and not self._live_q:
                        return None
                key = self._live_q.pop(0)
                self._active_q.update({key: int(time.time())})
            else:
                while key not in self._active_q:
                    self._cond.wait(timeout=timeout)
                    if (key not in self._active_q) and timeout:
                        return None
            content = self._read_data(key)
        return key, content

    def done(self, key: str):
        """Завершает выполнение задачи, удаляя значение с файлом из любой очереди.

        Args:
            key (str): Ключ задачи.
        """        
        with self._cond:
            if key in self._live_q:
                self._live_q.remove(key)
                self._remove_data(key)
            elif key in self._active_q:
                self._active_q.pop(key)
                self._remove_data(key)
            self._cond.notify_all()

    def update(self):
        """ 
            Перемещает активные элементы снова 
            в живую очередь на выполнение _active_q -> _live_q, 
            потому как истекло время выполнения. Всегда выполняется перед `.get()`
        """
        if not self._timeout_processing:
            return None
        old_keys = []
        current = int(time.time())
        with self._cond:
            for k, t in self._active_q.items():
                if (current - t) > self._timeout_processing:
                    old_keys.append(k)
            for old_key in old_keys:
                self._active_q.pop(old_key)
                self._live_q.append(old_key)

    def move_active_to_live(self, key: str = '', startswith: bool = False):
        """
            Перемещает элемент снова в очередь на обработку.
            Если `key` пустая строка и активен `startswith`, то перемещает все. Если активен `startswith`
            и заполнен `key`, то перемещаются ключи в которых есть часть этого ключа.
            
            Args:
                key (str): Ключ.
                startswith (bool): Переместить ключи которые начинаются на key.
        """        
        with self._cond:
            for active_key in self.active_keys:
                if startswith and active_key.startswith(key):
                    self._active_q.pop(active_key)
                    self._live_q.append(active_key)
                    continue
                if key == active_key:
                    self._active_q.pop(key)
                    self._live_q.append(key)
    
    def move_live_to_active(self, key: str = '', startswith: bool = False):
        """
            Перемещает элемент в очередь на ожидание по ключу.
            Если `key` пустая строка и активен `startswith`, то перемещает все. Если активен `startswith`
            и заполнен `key`, то перемещаются ключи в которых есть часть этого ключа.
            
            Args:
                key (str): Ключ.
                startswith (bool): Переместить ключи которые начинаются на key.
        """        
        with self._cond:
            for live_key in self.live_keys:
                if startswith and live_key.startswith(key):
                    self._live_q.remove(live_key)
                    self._active_q.update({ live_key: int(time.time()) })
                    continue
                if key == live_key:
                    self._live_q.remove(live_key)
                    self._active_q.update({ live_key: int(time.time()) })

    def gen_key(self) -> str:
        """Генерация ключа для очереди.

        Returns:
            str: Ключ.
        """        
        keys = [*self._live_q]
        keys.extend(list(self._active_q.keys()))
        while True:
            new_name = uuid.uuid4().hex
            if new_name not in keys:
                return new_name

    @abstractmethod
    def _init_live_queue(self) -> List[str]:
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