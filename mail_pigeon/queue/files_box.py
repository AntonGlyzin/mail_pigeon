import os
from pathlib import Path
from anyio import Path as AsyncPath, open_file
from typing import List
from mail_pigeon.exceptions import CreateErrorFolderBox
from mail_pigeon.queue.base_queue import BaseQueue
from mail_pigeon.queue.base_async_queue import BaseAsyncQueue
from mail_pigeon.translate import _
from mail_pigeon import logger


class FilesBox(BaseQueue):
    
    def __init__(self, folder="./queue"):
        """
        Args:
            folder (str, optional): Путь до директории с очерелью сообщений.

        Raises:
            CreateErrorFolderBox: Директория не может быть создана. Есть такой файл.
        """
        self._ext = '.q'
        self._folder = Path(folder).absolute()
        if not self._folder.exists():
            self._folder.mkdir(parents=True, exist_ok=True)
        elif not self._folder.is_dir():
            raise CreateErrorFolderBox(self._folder)
        super().__init__()

    def _init_queue(self) -> List[str]:
        """Инициализация очереди при создание экземпляра.

        Returns:
            List[str]: Список.
        """
        live_q = sorted(self._folder.iterdir(), key=lambda x: os.stat(x).st_birthtime)
        return [f.stem for f in live_q if f.suffix == self._ext]

    def _remove_data(self, key: str):
        """Удаляет данные одного элемента.

        Args:
            key (str): Ключ.
        """        
        file_path = self._folder / f'{key}{self._ext}'
        try:
            file_path.unlink()
        except Exception as e:
            logger.error(
                (_("Ошибка при удаление файла <{}> из очереди. ").format(key) +
                _("Контекст ошибки: <{}>").format(e)), 
                exc_info=True
            )

    def _read_data(self, key: str) -> str:
        """Чтение данных по ключу.

        Args:
            key (str): Название.

        Returns:
            str: Прочитанные данные.
        """        
        filename = f'{key}{self._ext}'
        path = self._folder / filename
        with open(path, 'rb') as file:
            content = file.read()
        return content.decode()

    def _save_data(self, key: str, value: str):
        """Сохраняет данные.

        Args:
            value (str): Ключ.
            value (str): Значение.
        """        
        filename = f'{key}{self._ext}'
        path = self._folder / filename
        with open(path, 'wb') as file:
            file.write(value.encode())


class AsyncFilesBox(BaseAsyncQueue):
    
    def __init__(self, folder="./queue"):
        """
        Args:
            folder (str, optional): Путь до директории с очерелью сообщений.

        Raises:
            CreateErrorFolderBox: Директория не может быть создана. Есть такой файл.
        """
        self._ext = '.q'
        self._path = folder
        self._folder: AsyncPath = None
        super().__init__()

    async def _init_queue(self) -> List[str]:
        """Инициализация очереди при создание экземпляра.

        Returns:
            List[str]: Список.
        """
        self._folder = await AsyncPath(self._path).absolute()
        exists = await self._folder.exists()
        is_dir = await self._folder.is_dir()
        if not exists:
            await self._folder.mkdir(parents=True, exist_ok=True)
        elif not is_dir:
            raise CreateErrorFolderBox(self._folder)
        files = []
        async for file_path in self._folder.iterdir():
            if file_path.suffix != self._ext:
                continue
            stat = await file_path.stat()
            files.append((file_path.stem, stat.st_birthtime))
        sorted_files = sorted(files, key=lambda x: x[1])
        return [i[0] for i in sorted_files]

    async def _remove_data(self, key: str):
        """Удаляет данные одного элемента.

        Args:
            key (str): Ключ.
        """        
        file_path = self._folder / f'{key}{self._ext}'
        try:
            await file_path.unlink()
        except Exception as e:
            logger.error(
                (_("Ошибка при удаление файла <{}> из очереди. ").format(key) +
                _("Контекст ошибки: <{}>").format(e)), 
                exc_info=True
            )

    async def _read_data(self, key: str) -> str:
        """Чтение данных по ключу.

        Args:
            key (str): Название.

        Returns:
            str: Прочитанные данные.
        """        
        filename = f'{key}{self._ext}'
        path = self._folder / filename
        async with await open_file(path, 'rb') as file:
            content = await file.read()
        return content.decode()

    async def _save_data(self, key: str, value: str):
        """Сохраняет данные.

        Args:
            value (str): Ключ.
            value (str): Значение.
        """        
        filename = f'{key}{self._ext}'
        path = self._folder / filename
        async with await open_file(path, 'wb') as file:
            await file.write(value.encode())