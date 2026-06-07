# Protocol

This document is intended to give a short overview/quickstart about the protocols supported.

## ESC/VP21

The commands that this library uses to control the projector are part of ESC/VP21 command set.
You can get the commands for your projector from the support page for your projector on the Epson website. The commands document is listed in the "Manuals & Documentation" section. The document seems to contain commands for most (all?) projectors.

The gist of it is that you send the command and end it with a CR like `COMMAND VALUE\r` to set a value or `COMMAND?\r` get a value. The projector executes the command and will respond with `:` (colon) for set or `COMMAND=VALUE\r:` for get.

## Connections

The ESC/VP21 is commandset is the same for many projectors (availability of commands varies, but format is the same). However the way to send them to the projector depends on how the projector is connected.

### HTTP

This connection method is implemented in `protocol_http.py`

Commands are sent by doing an HTTP `GET` on `/cgi-bin/<type>`. Where type can be "directsend" or "json_query".
The type "directsend" seems to be sending of plain ESC/VP21 commands. The type "json_query" results in a JSON reponse.

More details, see [HTTP_PROTOCOL.md](HTTP_PROTOCOL.md).

The serial number of the projector is obtained through another protocol, see [Serial number](#serial-number).

### ESC/VP.net

This connection method is implemented in `protocol_tcp.py`

ESC/VP.net is used with projectors connected over a network. It uses a TCP socket and after connecting does some handshaking and then it basically behaves like the Serial connection.

Searching for ESC/VP.net result in this specification <https://archive.org/details/manualzz-id-1050273/mode/2up>

### Serial

This connection method is implemented in `protocol_serial.py`

The projector is connected with a serial cable (see projector manual for wiring) and the commands are sent as plain text.

Example: [Epson EH-TW3200](https://www.epson.eu/en_EU/support/sc/epson-eh-tw3200/s/s944)

## Serial number protocol

This package uses an alternative command to obtain the serial number. It is sent on port 3620 and starts with "EEMP0100" (in binary). It is an alternative to using ESC/VP21 `SNO?` command.

This command is part of another protocol that is used by the iProjection and EasyMP apps.

There seems to be no official documentation about the protocol, but these places have some info.

* [Epson page mentioning the port number](https://download2.ebz.epson.net/sec_pubs_visual/projectors/EB-770F/useg/EN/Interactive/Reference/precautions_connection_netproj.html) and some others related to the protocol.
* Epson projector reverse engineering of the protocol. Has some captures, some analysis and a client. [Github repo](https://github.com/steamcircuit-ca/epson-projector)
* Java tool to project an image/picture on an Epson projector [Github repo](https://github.com/nospam2k/epson-wireless-projector).
* Epsonconnector is a tool that can connect and send images/video to the projector [SourceForge repo](https://sourceforge.net/projects/epsonconnector/)
