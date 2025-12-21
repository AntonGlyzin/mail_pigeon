@echo off
REM Запуск каждого app.py в отдельном окне с ожиданием 1 секунда
echo Starting applications in separate windows...

@REM start "Async master" cmd /k "python async_master.py"
@REM timeout /t 2 /nobreak > nul

@REM start "App 1" cmd /k "mode con: cols=70 lines=30 && python app1.py"

start "App 2" cmd /k "mode con: cols=70 lines=30 && python app2.py"

@REM start "App 3" cmd /k "mode con: cols=70 lines=30 && python app3.py"

@REM start "App 4" cmd /k "mode con: cols=70 lines=30 && python app4.py"

echo All applications started in separate windows!