# Epson-projector module

## Asynchronous library to control Epson projectors

Requires Python 3.11 or higher.

Created mostly to use with Home Assistant.

### Usage

Check out the test_*.py files and const.py to see all posibilities to send to projector.

```python
"""Test and example of usage of Epson module."""
import epson_projector as epson
from epson_projector.const import (POWER)

import asyncio
import aiohttp


async def main():
    """Run main with aiohttp ClientSession."""
    async with aiohttp.ClientSession() as session:
        await run(session)

    # With a password
    digest_auth = aiohttp.DigestAuthMiddleware(
        login="EPSONWEB", password="YOUR_PASSWORD"
    )
    async with aiohttp.ClientSession(middlewares=[digest_auth]) as session:
        await run(session)



async def run(websession):
    """Use Projector class of epson module and check if it is turned on."""
    projector = epson.Projector(
        host='HOSTNAME',
        websession=websession)
    data = await projector.get_property(POWER)
    print(data)

asyncio.run(main())
```
