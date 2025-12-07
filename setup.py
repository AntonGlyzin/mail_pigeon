import os
from setuptools import setup, find_packages

# Для изменения версии программы 
# сообщение коммита должно содержать: "feat:" / "fix:".
VERSION_APP = os.getenv('VERSION_APP')

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name='mail_pigeon',
    version=VERSION_APP,
    packages=find_packages(),
    install_requires=[
        'pyzmq<=27.0.2',
        'psutil<=7.0.0',
        'cryptography<=46.0.1',
        'anyio<=4.12.0',
        'tornado>=6.1'
    ],
    package_data={
        'mail_pigeon': [
            'locale/*/*/*.mo',
            'locale/*/*/*.po'
        ]
    },
    include_package_data=True,
    python_requires=">=3.9",
    author='Антон Глызин',
    author_email='tosha.glyzin@mail.ru',
    description='Асинхронная клиент-серверная библиотека с файловой очередью на стороне клиента.',
    long_description=long_description,
    long_description_content_type="text/markdown",
    license='MIT',
    keywords='zmq files queue client server python',
    classifiers=[
        'Intended Audience :: Developers',
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Topic :: Software Development :: Libraries",
    ],
    project_urls={
        "Releases": "https://github.com/AntonGlyzin/mail_pigeon/releases",
        "Github": "https://github.com/AntonGlyzin/mail_pigeon",
        "Read the docs": "https://mail-pigeon.readthedocs.io/ru/stable"
    }
)