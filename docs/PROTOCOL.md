# Protocol

This document is intended to give a short overview/quickstart about the protocols supported.

## ESC/VP21

The commands that this library uses to control the projector are part of ESC/VP21 command set.
You can get the commands for your projector from the support page for your projector on the Epson website. The commands document is listed in the "Manuals & Documentation" section. The document seems to contain commands for most (all?) projectors.

The gist of it is that you send the command (close it with a CR), the projector executes the command and will respond with : (colon).

## Connections

The ESC/VP21 is commandset is the same for many projectors (availability of commands varies, but format is the same). However the way to send them to the projector depends on how the projector is connected.

### HTTP

This connection method is implemented in `protocol_http.py`

Commands are sent by doing an HTTP `GET` on `/cgi-bin/<type>`. Where type can be "directsend" or "json_query".
The type "directsend" seems to be sending of plain ESC/VP21 commands. The type "json_query" results in a JSON reponse.

The serial number of the projector seems to be obtained through the same way as done with `projector_tcp.py`.

More details, see [HTTP_PROTOCOL.md](HTTP_PROTOCOL.md).

### ESC/VP.net

This connection method is implemented in `protocol_tcp.py`

ESC/VP.net is used with projectors connected over a network. It uses a TCP socket and after connecting does some handshaking and then it basically behaves like the Serial connection.

Searching for ESC/VP.net result in this specification <https://archive.org/details/manualzz-id-1050273/mode/2up>

### Serial

This connection method is implemented in `protocol_serial.py`

The projector is connected with a serial cable (see projector manual for wiring) and the commands are sent as plain text.

Example: [Epson EH-TW3200](https://www.epson.eu/en_EU/support/sc/epson-eh-tw3200/s/s944)
