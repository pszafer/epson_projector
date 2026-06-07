# Epson-projector module

## Asynchronous library to control Epson projectors

Requires Python 3.11 or higher.

Created mostly to use with Home Assistant.

### Usage

Check out the test_*.py files and const.py to see all posibilities to send to projector.

```python
"""Test and example of usage of Epson module."""
import epson_projector as epson
from epson_projector.const import POWER

import asyncio

async def main():
    """Use Projector class of epson module and check if it is turned on."""
    projector = epson.Projector.create_http(
        host='HOSTNAME',
        password='PASSWORD_IF_NEEDED'
    )
    data = await projector.get_property(POWER)
    print(data)

    await projector.close()

asyncio.run(main())
```
