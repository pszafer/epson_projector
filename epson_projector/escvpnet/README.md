# escvpnet

A Python package for communicating with Epson projectors using the ESC/VP21 protocol over TCP/IP networks.

This package exposes all features of ESC/VP.net protocol like:

* Projector discovery with HELLO,
* Use CONNECT message allow sending of ESC/VP21 commands
* Use PASSWORD message to check and change password

## Usage

### Discovery

```python
from epson_projector.escvpnet.escvpnet import EscvpNet

discovered_projector_info_list = await EscVpNet.discover()
print(discovered_projector_info_list)
```

### Basic usage

```python
from epson_projector.escvpnet.escvpnet import EscvpNet

client = EscVpNet(host="192.168.1.123", password="password")
await client.connect()

print(await escvp21.get("LAMP"))
await escvp21.set("PWR", "ON")
```

### Using contextmanager

```python
from epson_projector.escvpnet.escvpnet import EscvpNet

async with EscVpNet(host="192.168.1.123", password="password") as client:
    print(await escvp21.get("LAMP"))
    await escvp21.set("PWR", "ON")
```


## Command-Line Usage

You can execute the module directly for manual experimentation. It allows to discover projectors, send commands and more. It will prompt for password when one is required. Use the `--help` commandline option for available commands and `command --help` for the command parameters.

Examples:

```bash
python -m epson_projector.escvpnet discover
python -m epson_projector.escvpnet send_commands 192.168.1.100 PWR?:SOURCE 30:LAMP?
```
