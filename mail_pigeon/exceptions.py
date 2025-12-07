from mail_pigeon.translate import _


class BaseException(Exception):
    
    def __str__(self):
        return f"[{self.__class__.__name__}] {self.args[0]}"
    
    def __repr__(self):
        return (f"{self.__class__.__name__}(message={self.args[0]!r})")


class CreateErrorFolderBox(BaseException):
    
    def __init__(self, folder: str):
        message = _("Ошибка при создание папки <{}> с очередью писем.").format(folder)
        super().__init__(message)


class PortAlreadyOccupied(BaseException):
    
    def __init__(self, port: int):
        message = _("Порт <{}> уже занят.").format(port)
        super().__init__(message)


class ServerNotRunning(BaseException):
    
    def __init__(self, port: int):
        message = _("Сервер не запущен по порту <{}>.").format(port)
        super().__init__(message)


class ParserNotFound(BaseException):
    
    def __init__(self, code: str):
        message = _("Парсер с кодом <{}> не найден.").format(code)
        super().__init__(message)


class CommandCodeNotFound(BaseException):
    
    def __init__(self, code: str):
        message = _("Команда с кодом <{}> не найдена.").format(code)
        super().__init__(message)


class ServerStopped(BaseException):
    
    def __init__(self):
        message = _("Сервер остановлен.")
        super().__init__(message)