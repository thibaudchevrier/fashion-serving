"""Images downloaded from a URL, without letting users reach the server's own network.

Implements ``fashion_webapp.service.ImageFetcher``. The server fetches addresses chosen by users,
so each URL, and each redirect it leads to, is checked before any connection:

- ``http`` or ``https`` only, on the default ports;
- every address the host name resolves to must be public (no loopback, private, link-local or
  cloud metadata addresses);
- at most ``MAX_REDIRECTS`` redirects, an ``image/*`` content type, ``max_bytes`` at most, and a
  timeout.

The name is resolved again when connecting, so a DNS server answering differently the second time
could still point the request elsewhere (DNS rebinding); pinning the checked address would close
that gap at the cost of a custom transport.
"""

import ipaddress
import socket
from collections.abc import Callable
from urllib.parse import urljoin, urlsplit

import requests

from fashion_webapp.service import UrlRejected

MAX_REDIRECTS = 3
REDIRECT_STATUSES = {301, 302, 303, 307, 308}
DEFAULT_PORTS = {"http": 80, "https": 443}
# Many image hosts refuse anonymous clients: say who is downloading.
USER_AGENT = "fashion-serving/webapp (+https://github.com/thibaudchevrier/fashion-serving)"

Resolver = Callable[[str], list[str]]


def resolve(host: str) -> list[str]:
    """List the IP addresses a host name resolves to.

    Parameters
    ----------
    host : str
        Host name or IP address.

    Returns
    -------
    list[str]
        Its addresses (IPv4 and IPv6).

    Raises
    ------
    UrlRejected
        If the name does not resolve.
    """
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except (socket.gaierror, UnicodeError) as exc:
        raise UrlRejected(f"Unknown host: {host}") from exc
    return sorted({str(info[4][0]) for info in infos})


def check_url(url: str, resolver: Resolver = resolve) -> None:
    """Refuse URLs that are not plain web addresses of public hosts.

    Parameters
    ----------
    url : str
        URL to check (untrusted).
    resolver : Resolver
        Turns a host name into its IP addresses. By default ``resolve`` (DNS).

    Raises
    ------
    UrlRejected
        If the scheme, port or host is not allowed.

    Examples
    --------
    >>> check_url("http://127.0.0.1/admin")
    Traceback (most recent call last):
    ...
    fashion_webapp.service.UrlRejected: This address is not public: 127.0.0.1
    """
    parts = urlsplit(url)
    if parts.scheme not in DEFAULT_PORTS:
        raise UrlRejected("Only http and https URLs are allowed.")
    try:
        port = parts.port
    except ValueError as exc:
        raise UrlRejected("Invalid port.") from exc
    if port not in (None, DEFAULT_PORTS[parts.scheme]):
        raise UrlRejected("Only the default ports (80, 443) are allowed.")
    if not parts.hostname:
        raise UrlRejected("The URL has no host.")
    for address in resolver(parts.hostname):
        if not ipaddress.ip_address(address).is_global:
            raise UrlRejected(f"This address is not public: {parts.hostname}")


class UrlFetcher:
    """Downloads images over HTTP(S) from public hosts only.

    Parameters
    ----------
    max_bytes : int
        Largest download accepted.
    timeout : float
        Connection and read timeout, in seconds. By default 10.
    session : requests.Session | None
        HTTP session (tests pass a fake). By default a new session.
    resolver : Resolver
        Host name to IP addresses. By default ``resolve`` (DNS).

    Attributes
    ----------
    max_bytes : int
        Largest download accepted.
    timeout : float
        Connection and read timeout, in seconds.
    """

    max_bytes: int
    timeout: float

    def __init__(
        self,
        max_bytes: int,
        timeout: float = 10.0,
        session: requests.Session | None = None,
        resolver: Resolver = resolve,
    ):
        self.max_bytes = max_bytes
        self.timeout = timeout
        self._session = session or requests.Session()
        self._resolver = resolver

    def fetch(self, url: str) -> bytes:
        """Download an image, following a few checked redirects.

        Parameters
        ----------
        url : str
            Image URL (untrusted).

        Returns
        -------
        bytes
            The image file.

        Raises
        ------
        UrlRejected
            If a URL is refused, there are too many redirects, the download fails, or the
            answer is not an image of an acceptable size.
        """
        for _ in range(MAX_REDIRECTS + 1):
            check_url(url, self._resolver)
            try:
                response = self._session.get(
                    url,
                    stream=True,
                    allow_redirects=False,
                    timeout=self.timeout,
                    headers={"User-Agent": USER_AGENT, "Accept": "image/*"},
                )
            except requests.RequestException as exc:
                raise UrlRejected(f"Could not download the image: {exc}") from exc
            with response:
                if response.status_code in REDIRECT_STATUSES and "location" in response.headers:
                    url = urljoin(url, response.headers["location"])
                    continue
                return self._read_image(response)
        raise UrlRejected("Too many redirects.")

    def _read_image(self, response: requests.Response) -> bytes:
        """Read an image response, up to ``max_bytes``.

        Parameters
        ----------
        response : requests.Response
            A streamed, non-redirect response.

        Returns
        -------
        bytes
            The body.

        Raises
        ------
        UrlRejected
            If the status is an error, the content type is not an image, or the body is too
            big.
        """
        if not response.ok:
            raise UrlRejected(f"The server answered {response.status_code}.")
        content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
        if not content_type.startswith("image/"):
            raise UrlRejected(f"This URL is not an image ({content_type or 'no content type'}).")
        body = bytearray()
        for chunk in response.iter_content(chunk_size=64 * 1024):
            body.extend(chunk)
            if len(body) > self.max_bytes:
                raise UrlRejected(f"The image is larger than {self.max_bytes // 2**20} MB.")
        return bytes(body)
