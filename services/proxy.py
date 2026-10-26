"""Small same-origin WebSocket proxy used to keep classroom networking simple."""
from __future__ import annotations

import base64
import hashlib
import select
import socket
import ssl
import urllib.parse


def proxy_websocket(client, client_headers, upstream_url: str) -> None:
    """Validate both upgrade handshakes, then copy opaque WebSocket bytes."""
    parsed = urllib.parse.urlsplit(upstream_url)
    if parsed.scheme not in ("ws", "wss") or not parsed.hostname:
        raise ValueError("Backend URL must use ws:// or wss://")
    port = parsed.port or (443 if parsed.scheme == "wss" else 80)
    upstream = socket.create_connection((parsed.hostname, port), timeout=10)
    if parsed.scheme == "wss":
        upstream = ssl.create_default_context().wrap_socket(upstream, server_hostname=parsed.hostname)
    try:
        upstream.settimeout(10)
        path = urllib.parse.urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
        key = base64.b64encode(__import__("os").urandom(16)).decode("ascii")
        host = parsed.hostname if parsed.port is None else f"{parsed.hostname}:{port}"
        subprotocol = client_headers.get("Sec-WebSocket-Protocol", "")
        protocol_header = f"Sec-WebSocket-Protocol: {subprotocol}\r\n" if subprotocol else ""
        request = (
            f"GET {path} HTTP/1.1\r\nHost: {host}\r\nUpgrade: websocket\r\n"
            f"Connection: Upgrade\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Key: {key}\r\n{protocol_header}\r\n"
        )
        upstream.sendall(request.encode("ascii"))
        response = bytearray()
        while b"\r\n\r\n" not in response:
            chunk = upstream.recv(1)
            if not chunk or len(response) > 16384:
                raise ConnectionError("Upstream did not complete a WebSocket handshake")
            response.extend(chunk)
        header, remainder = bytes(response).split(b"\r\n\r\n", 1)
        status = header.split(b"\r\n", 1)[0]
        if b" 101 " not in status:
            body = b"Realtime backend rejected the WebSocket handshake"
            client.sendall(b"HTTP/1.1 502 Bad Gateway\r\nConnection: close\r\nContent-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body)
            return
        response_headers = {}
        for line in header.split(b"\r\n")[1:]:
            if b":" in line:
                name, value = line.split(b":", 1)
                response_headers[name.lower()] = value.strip()
        # Each side has its own handshake key. Payload frames retain their
        # browser masking and order; this proxy does not normalize model events.
        expected_accept = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest())
        if response_headers.get(b"sec-websocket-accept") != expected_accept:
            raise ConnectionError("Invalid upstream WebSocket accept key")
        selected_protocol = response_headers.get(b"sec-websocket-protocol")
        if selected_protocol and selected_protocol.decode() not in [p.strip() for p in subprotocol.split(",")]:
            raise ConnectionError("Upstream selected an unrequested subprotocol")
        browser_protocol = b"Sec-WebSocket-Protocol: " + selected_protocol + b"\r\n" if selected_protocol else b""
        browser_key = client_headers.get("Sec-WebSocket-Key")
        accept = base64.b64encode(hashlib.sha1((browser_key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")).digest())
        client.sendall(b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: " + accept + b"\r\n" + browser_protocol + b"\r\n")
        # One bounded chunk is in flight; stalled sends release this proxy thread.
        client.settimeout(10)
        upstream.settimeout(10)
        if remainder:
            client.sendall(remainder)
        sockets = (client, upstream)
        while True:
            readable, _, _ = select.select(sockets, [], [])
            for source in readable:
                data = source.recv(65536)
                if not data:
                    return
                target = upstream if source is client else client
                target.sendall(data)
    finally:
        try:
            upstream.close()
        except OSError:
            pass
