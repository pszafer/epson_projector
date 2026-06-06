# ESC/VP.net

A Python package for communicating with Epson projectors using ESC/VP.net.

This package exposes following features of ESC/VP.net protocol:

* Projector discovery with HELLO,
* Use CONNECT message to allow sending of ESC/VP21 commands
* Use PASSWORD message to check and change password

ESC/VP.net protocol implementation based on EPSON documentation found here:
https://www.epson.com.au/d/pub/epson/techtips/escvp.netmanual_e_f.pdf

## Usage

### Discovery

```python
from epson_projector.escvpnet.escvpnet import EscVpNet

discovered_projector_info_list = await EscVpNet.discover()
print(discovered_projector_info_list)
```

### Basic usage

Note that `connect()` returns an reader/writer pair similar to `asyncio.open_connection`.

```python
from epson_projector.escvpnet.escvpnet import EscvpNet

escvpnet_client = EscVpNet(host="192.168.1.123", password="password")
reader, writer await escvpnet_client.connect()

# Reader, writer can be used to send ESC/VP21 commands
command = "PWR?"

writer.write(command.encode("ascii"))
await writer.drain()

response = await self._reader.readuntil(b":")
print(response.decode("ascii"))
```

## Command-Line Usage

You can execute the module directly for manual experimentation. It allows to discover projectors, send commands and more. It will prompt for password when one is required. Use the `--help` commandline option for available commands and `command --help` for the command parameters.

Examples:

```bash
python -m epson_projector.escvpnet discover
python -m epson_projector.escvpnet send_commands 192.168.1.100 PWR?
python -m epson_projector.escvpnet send_commands 192.168.1.100 LAMP?:SOURCE 30
```
