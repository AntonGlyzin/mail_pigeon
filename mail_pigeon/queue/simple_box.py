from typing import List
from mail_pigeon.queue.base_queue import BaseQueue
from mail_pigeon.queue.base_async_queue import BaseAsyncQueue


class SimpleBox(BaseQueue):
    
    def __init__(self):
        super().__init__()
        self._simple_box = {}

    def _init_queue(self) -> List[str]:
        """Инициализация очереди при создание экземпляра.

        Returns:
            List[str]: Список.
        """
        return []
            
    def _remove_data(self, key: str):
        """Удаляет данные одного элемента.

        Args:
            key (str): Ключ.
        """
        if key in self._simple_box:
            del self._simple_box[key]

    def _read_data(self, key: str) -> str:
        """Чтение данных по ключу.

        Args:
            key (str): Название.

        Returns:
            str: Прочитанные данные.
        """
        return self._simple_box[key]

    def _save_data(self, key: str, value: str):
        """Сохраняет данные.

        Args:
            value (str): Ключ.
            value (str): Значение.
        """
        self._simple_box[key] = value


class AsyncSimpleBox(BaseAsyncQueue):
    
    def __init__(self):
        super().__init__()
        self._simple_box = {}

    async def _init_queue(self) -> List[str]:
        """Инициализация очереди при создание экземпляра.

        Returns:
            List[str]: Список.
        """
        return []
    
    async def _remove_data(self, key: str):
        """Удаляет данные одного элемента.

        Args:
            key (str): Ключ.
        """
        if key in self._simple_box:
            del self._simple_box[key]

    async def _read_data(self, key: str) -> str:
        """Чтение данных по ключу.

        Args:
            key (str): Название.

        Returns:
            str: Прочитанные данные.
        """
        return self._simple_box[key]
    
    async def _save_data(self, key: str, value: str):
        """Сохраняет данные.

        Args:
            value (str): Ключ.
            value (str): Значение.
        """
        self._simple_box[key] = value