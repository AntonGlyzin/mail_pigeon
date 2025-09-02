import os
from pathlib import Path
from typing import List
from mail_pigeon.exceptions import CreateErrorFolderBox
from mail_pigeon.queue import BaseQueue
from mail_pigeon.translate import _
from mail_pigeon import logger


class FilesBox(BaseQueue):
    
    def __init__(
        self, folder="./queue", timeout_processing: int = None
    ):
        """
        Args:
            folder (str, optional): Путь до директории с очерелью сообщений.
            timeout_processing (int, optional): Количество секунд в течение которых нужно обработать сообщение,
                которое было полученно методом .get(), но не удаленно методом .done(key) из очереди. При запоздание 
                в обработке, сообщение снова окажется в очереди, где его смогут получить другие потоки.
                Если значение None, то из активного списка не будут происходить перемещения обратно.

        Raises:
            CreateErrorFolderBox: Директория не может быть создана. Есть такой файл.
        """
        self._ext = '.q'
        self._folder = Path(folder).absolute()
        if not self._folder.exists():
            self._folder.mkdir(parents=True, exist_ok=True)
        elif not self._folder.is_dir():
            raise CreateErrorFolderBox(self._folder)
        super().__init__(timeout_processing)

    def _init_live_queue(self) -> List[str]:
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
                (_("Ошибка при удаление файла '{}' из очереди. ").format(key) +
                _("Контекст ошибки: {}").format(e)), 
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