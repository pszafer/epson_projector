# Epson HTTP Protocol format

This is mostly reverse-engineered from `epson_projector/projector_http.py` in [epson-projector](https://github.com/pszafer/epson_projector) and observations of communication with LS11000 projector.

---

## Endpoints

The projector exposes an HTTP/CGI interface on port 80  

There are two endpoints of interest for the usage of ESC/VP21 commands.

| Endpoint              | Method | Purpose                              |
|-----------------------|--------|--------------------------------------|
| `/cgi-bin/json_query` | GET    | Query projector state (ESC/VP21 GET) |
| `/cgi-bin/directsend` | GET    | Send a command (ESC/VP21 SET)        |

Note that these are also offered on other endpoints like: `/cgi-bin/Remote/json_query`

---

## `GET /cgi-bin/json_query`

Executes an ESC/VP21 GET command and returns the result as JSON.

### Request

```text
GET /cgi-bin/json_query?jsoncallback=CMD?
```

The `jsoncallback` query parameter value is a literal ESC/VP21 GET command string, e.g. `PWR?`, `SOURCE?`, `VOL?` (note the ? at the end).

### Response

Generic format

```json
{
  "projector": {
    "feature": {
      "name": "esc/vp21",
      "query": "<command>",
      "reply": "<value>",
      "error": false
    }
  }
}
```

`query` is the original query command it is responding to.
`reply` is the raw ESC/VP21 response value.
`error` is set when there was an error.

Response from `PWR?` command

```json
{
  "projector": {
    "feature": {
      "name": "esc/vp21",
      "query": "PWR?",
      "reply": "04",
      "error": false
    }
  }
}
```

Error response (missing ? at the end)

```json
{
  "projector": {
    "feature": {
      "name": "esc/vp21",
      "query": "PWR",
      "reply": "ERR",
      "error": true
    }
  }
}
```

### Example

This is captured from the web interface

```text
GET /cgi-bin/json_query?jsoncallback=SOURCELIST?
→ {
  "projector": {
    "feature": {
      "name": "esc/vp21",
      "query": "SOURCELIST?",
      "reply": "30 HDMI1 A0 HDMI2",
      "error": false
    }
  }
}
```

---

## `GET /cgi-bin/directsend`

Sends an ESC/VP21 SET command.

### Request: ESC/VP21 SET

```text
GET /cgi-bin/directsend?CMD=VALUE
```

The query parameter key is the ESC/VP21 command name, the value is the operand.

```text
GET /cgi-bin/directsend?CMODE=15
GET /cgi-bin/directsend?ASPECT=00
```

### Response

HTTP 200. The response is empty based on captures from the web interface.

## Authentication

It seems like older models did not have (or require) authorization. Newer models (like LS11000) require it.

The used method is [Digest Authentication](https://en.wikipedia.org/wiki/Digest_access_authentication) which is a well-known standard.

The user is "EPSONWEB"

## CURL example

This seems to be the minimal required to have a command succeed.

Key points:

* Use referrer header
* Use digest authentication
* Quote the URL to avoid issues with the `?` at the end

```bash
curl --digest --user EPSONWEB:password -H 'Referer: http://192.168.178.46/cgi-bin/webconf' "http://192.168.178.46/cgi-bin/json_query?jsoncallback=PWR?"
```

## Web UI observations

Some observations from using the web interface and watching the requests in the devtools.

All requests seem to include an additional query parameter `_` which seems to be a timestamp. Might be linked to the authentication because the full URL is also in the `authorization` header.

On the remote webpage the commands are sent to a different URL (note the `Remote` part).

```text
http://192.168.178.46/cgi-bin/Remote/directsend?KEY=3E&_=1779026817393
```
