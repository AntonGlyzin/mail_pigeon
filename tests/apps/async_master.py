import sys
from anyio import Path
path = Path(__file__)
tests_dir = path.parent
sys.path.insert(0, str(tests_dir.parent.parent))
from mail_pigeon import AsyncMailClient, logger
import asyncio

import logging
logger.setLevel(logging.DEBUG)

name = 'master'

start = asyncio.Event()
start.clear()

loop = asyncio.new_event_loop()

async def main():

    apps_cert = str(Path(__file__).parent.parent / 'apps_cert')

    client = AsyncMailClient(name, is_master=True, cert_dir=apps_cert)
    await client.wait_server()
    await start.wait()
            

loop.run_until_complete(main())