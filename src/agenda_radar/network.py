"""Bounded fetch with DNS validation and connection pinning on every redirect."""

import http.client
import ipaddress
import socket
import ssl
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

USER_AGENT = "AgendaRadar/0.1"
MAX_BYTES = 2 * 1024 * 1024


class FetchError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def public_addresses(url: str) -> tuple[str, int, list[str]]:
    parsed = urlsplit(url)
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        raise FetchError("invalid_url")
    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        if port not in (80, 443):
            raise FetchError("port_not_allowed")
        addresses = list(
            dict.fromkeys(
                str(row[4][0])
                for row in socket.getaddrinfo(parsed.hostname, port, type=socket.SOCK_STREAM)
            )
        )
    except (OSError, ValueError) as exc:
        raise FetchError("dns_failure") from exc
    if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise FetchError("ssrf_blocked")
    return parsed.hostname, port, addresses


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host, port, address):
        self.ssl_context = ssl.create_default_context()
        super().__init__(host, port, timeout=15, context=self.ssl_context)
        self.address = address

    def connect(self):
        sock = socket.create_connection((self.address, self.port), self.timeout)
        self.sock = self.ssl_context.wrap_socket(sock, server_hostname=self.host)


@dataclass
class FetchResult:
    url: str
    status: int
    body: bytes
    headers: dict[str, str]


def fetch(url: str, headers: dict | None = None) -> FetchResult:
    for _ in range(5):
        host, port, addresses = public_addresses(url)
        parsed = urlsplit(url)
        connection: http.client.HTTPConnection
        if parsed.scheme == "https":
            connection = PinnedHTTPSConnection(host, port, addresses[0])
        else:
            connection = http.client.HTTPConnection(addresses[0], port, timeout=15)
        try:
            path = (parsed.path or "/") + ("?" + parsed.query if parsed.query else "")
            connection.request(
                "GET",
                path,
                headers={
                    "Host": host,
                    "User-Agent": USER_AGENT,
                    "Accept-Encoding": "identity",
                    **(headers or {}),
                },
            )
            response = connection.getresponse()
            result_headers = {key.lower(): value for key, value in response.getheaders()}
            if response.status in (301, 302, 303, 307, 308):
                location = result_headers.get("location")
                if not location:
                    raise FetchError("redirect_without_location")
                url = urljoin(url, location)
                headers = None
                continue
            if response.status == 304:
                return FetchResult(url, 304, b"", result_headers)
            if response.status >= 400:
                raise FetchError(f"http_{response.status}")
            if result_headers.get("content-encoding", "identity") != "identity":
                raise FetchError("compressed_response_unsupported")
            body = response.read(MAX_BYTES + 1)
            if len(body) > MAX_BYTES:
                raise FetchError("response_too_large")
            return FetchResult(url, response.status, body, result_headers)
        except (OSError, http.client.HTTPException) as exc:
            raise FetchError("network_failure") from exc
        finally:
            connection.close()
    raise FetchError("too_many_redirects")


def check_robots(url: str):
    parsed = urlsplit(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    try:
        response = fetch(robots_url)
    except FetchError as exc:
        if exc.code == "http_404":
            return
        raise FetchError("robots_unavailable") from exc
    parser = RobotFileParser()
    parser.parse(response.body.decode("utf-8", errors="replace").splitlines())
    if not parser.can_fetch(USER_AGENT, url):
        raise FetchError("robots_denied")
