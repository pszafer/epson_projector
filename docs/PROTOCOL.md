# Protocol

This document is intended to give a short overview/quickstart about the protocols supported.

## ESC/VP21

The commands that this library uses to control the projector are part of ESC/VP21 command set.

The gist of it is that you send the command and end it with a CR like `COMMAND VALUE\r` to set a value or `COMMAND?\r` get a value. The projector executes the command and will respond with `:` (colon) for set or `COMMAND=VALUE\r:` for get. Or if a value was out of range, command not supported, or not available because projector is not On you get `ERR\r:` as response.

There is at least one command that does not follow the common get format of `COMMAND=VALUE`. This is command is `AXESADJ`, there might be more.

```txt
Sending: b'AXESADJ?\r'
Received: b'R=126 126 126\rG=126 126 126\rB=126 126 126\rC=126 126 126\rM=126 126 126\rY=126 126 126\r:' 
```

The list of commands supported for a projector can usually be found in the "Manuals & Documentation" section on the support page for the projector model on the Epson website. For some projectors it only lists commands for the specific model or a small set. For others it is an Excel sheet with lots of models.

ESC/VP21 specs can also be found on the EPSON website by searching for ["ESC/VP21" in the search](https://epson.com/search/?text=esc%2Fvp21&keyword=esc%2Fvp21#support) and selecting the support tab (it defaults to products)

This is [a direct link](https://epson.com/support/esc-vp21-command-codes-license-agreement) that has a zip with `ESCVP21_command_guide(E)RevC.pdf` and `ESCVP21_command_list(E)RevS.xlsx` which was updated on May 27th 2025 and seems to be the most recent one.

## Connections

The ESC/VP21 is commandset is the same for many projectors (availability of commands varies, but format is the same). However the way to send them to the projector depends on how the projector is connected.

### HTTP

This connection method is implemented in `protocol_http.py`

Commands are sent by doing an HTTP `GET` on `/cgi-bin/<type>`. Where type can be "directsend" or "json_query".
The type "directsend" seems to be sending of plain ESC/VP21 commands. The type "json_query" results in a JSON reponse.

More details, see [HTTP_PROTOCOL.md](HTTP_PROTOCOL.md).

The serial number of the projector is obtained through another protocol, see [Serial number protocol](#serial-number-protocol).

### ESC/VP.net

This connection method is implemented in `protocol_tcp.py`

ESC/VP.net is used with projectors connected over a network. It uses a TCP socket and after connecting does some handshaking and then it basically behaves like the Serial connection.

Searching for ESC/VP.net results in this specification <https://archive.org/details/manualzz-id-1050273/mode/2up>

ESC/VP.net adds a number of additional commands to the ESC/VP21 command set. These are mostly commands to set/get network related configuration. Check the specification for the full list. Not every command is implemented on all projectors.

ESC/VP.net can push status updates with the `IMEVENT` message. This message can be sent at _any_ time, so also in between request and its response. The `IMEVENT` message contains info about the power status, warnings and alarms. It seems like a message gets pushed when there is a change in any of those. The format is the same as the response to the `PWSTATUS?` command. Check the specification for details on the formatting.

The serial number of the projector is obtained through another protocol, see [Serial number protocol](#serial-number-protocol).

### Serial

This connection method is implemented in `protocol_serial.py`

The projector is connected with a serial cable (see projector manual for wiring) and the commands are sent as plain text.

Example: [Epson EH-TW3200](https://www.epson.eu/en_EU/support/sc/epson-eh-tw3200/s/s944)

The serial number is retrieved by using the `SNO?` command.

## Serial number protocol

This package uses an alternative protocol to obtain the serial number. It is sent on port 3620 and starts with "EEMP0100". This is part of the protocol used by EasyMP and iProjection apps (maybe EEMP is EPSON Easy MP?).

There seems to be no official documentation about the protocol, but these places have some info.

* [Epson page mentioning the port number](https://download2.ebz.epson.net/sec_pubs_visual/projectors/EB-770F/useg/EN/Interactive/Reference/precautions_connection_netproj.html) and some others related to the protocol.
* Epson projector reverse engineering of the protocol. Has some Wireshark captures, some analysis and a client. [Github repo](https://github.com/steamcircuit-ca/epson-projector)
* Java tool to project an image/picture on an Epson projector [Github repo](https://github.com/nospam2k/epson-wireless-projector).
* Epsonconnector is a tool that can connect and send images/video to the projector [SourceForge repo](https://sourceforge.net/projects/epsonconnector/)

Note that the value of the serial number is different from the `SNO?` command. The implementation takes 8 bytes while SNO responds with more (11 characters seems common). Next to that some of the reverse engineering efforts refer to those bytes as PROJECTOR_NAME and looks like this in captures "EBAF67AA".
