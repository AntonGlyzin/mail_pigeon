dir /s /b ..\*.py > files.txt
xgettext -d mail_pigeon -o ./en/LC_MESSAGES/mail_pigeon.po --files-from=files.txt --from-code=UTF-8 -j --no-location
del files.txt
pause