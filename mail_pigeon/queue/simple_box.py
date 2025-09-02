from typing import List
from mail_pigeon.queue import BaseQueue


class SimpleBox(BaseQueue):
    
    def __init__(self, timeout_processing: int = None):
        """
        Args:
            timeout_processing (int, optional): Количество секунд в течение которых нужно обработать сообщение,
                которое было полученно методом .get(), но не удаленно методом .done(key) из очереди. При запоздание 
                в обработке, сообщение снова окажется в очереди, где его смогут получить другие потоки.
                Если значение None, то из активного списка не будут происходить перемещения обратно.
        """
        super().__init__(timeout_processing)
        self._simple_box = {}

    def _init_live_queue(self) -> List[str]:
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