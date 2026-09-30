"""URL fetcher tests: which addresses are refused, and how downloads are checked (no network)."""

import pytest
import requests

from fashion_webapp.fetching import UrlFetcher, check_url
from fashion_webapp.service import UrlRejected

PUBLIC = {"shop.example": ["93.184.216.34"], "cdn.example": ["2606:4700::6810:84e5"]}
PRIVATE = {
    "localhost": ["127.0.0.1"],
    "intranet.example": ["10.0.0.7"],
    "metadata.example": ["169.254.169.254"],
    "v6-loopback.example": ["::1"],
    "mixed.example": ["93.184.216.34", "192.168.1.10"],
}


def resolver(host):
    """Resolve the test host names."""
    return {**PUBLIC, **PRIVATE}.get(host, [host])


@pytest.mark.parametrize(
    "url",
    [
        "ftp://shop.example/a.jpg",
        "file:///etc/passwd",
        "http://shop.example:8080/a.jpg",
        "https:///a.jpg",
        *(f"http://{host}/a.jpg" for host in PRIVATE),
        "http://127.0.0.1/a.jpg",
        "http://[::1]/a.jpg",
    ],
)
def test_non_public_urls_are_refused(url):
    """Other schemes, other ports, missing hosts and non-public addresses are refused."""
    with pytest.raises(UrlRejected):
        check_url(url, resolver)


@pytest.mark.parametrize(
    "url",
    ["https://shop.example/a.jpg", "http://cdn.example:80/a.jpg", "https://shop.example:443/"],
)
def test_public_urls_are_allowed(url):
    """Public hosts on the default ports pass."""
    check_url(url, resolver)


class FakeResponse:
    """A streamed HTTP response."""

    def __init__(self, status=200, headers=None, body=b""):
        """Build the response."""
        self.status_code = status
        self.headers = {k.lower(): v for k, v in (headers or {}).items()}
        self.body = body

    @property
    def ok(self):
        """Whether the status is a success."""
        return self.status_code < 400

    def iter_content(self, chunk_size):
        """Yield the body in chunks."""
        for i in range(0, len(self.body), chunk_size):
            yield self.body[i : i + chunk_size]

    def __enter__(self):
        """Use as a context manager."""
        return self

    def __exit__(self, *exc):
        """Nothing to close."""


class FakeSession:
    """Answers GETs from a dictionary of URLs, recording them."""

    def __init__(self, responses):
        """Serve these responses (a response, or an exception to raise)."""
        self.responses = responses
        self.requested = []

    def get(self, url, **kwargs):
        """Return (or raise) the response for a URL; redirects must not be followed here."""
        assert kwargs["allow_redirects"] is False and kwargs["stream"] is True
        assert kwargs["headers"]["User-Agent"].startswith("fashion-serving")
        self.requested.append(url)
        answer = self.responses[url]
        if isinstance(answer, Exception):
            raise answer
        return answer


def _fetcher(responses, max_bytes=1000):
    """Build a fetcher over a fake session and the test resolver."""
    session = FakeSession(responses)
    return UrlFetcher(max_bytes, session=session, resolver=resolver), session


IMAGE = FakeResponse(headers={"Content-Type": "image/jpeg"}, body=b"\xff\xd8jpeg")


def test_an_image_is_downloaded():
    """A public image URL gives its bytes."""
    fetcher, _ = _fetcher({"https://shop.example/a.jpg": IMAGE})
    assert fetcher.fetch("https://shop.example/a.jpg") == b"\xff\xd8jpeg"


def test_redirects_are_followed_and_checked():
    """Redirects are followed, each target checked: one to a private address is refused."""
    fetcher, session = _fetcher(
        {
            "https://shop.example/a": FakeResponse(301, {"Location": "/b.jpg"}),
            "https://shop.example/b.jpg": IMAGE,
            "https://shop.example/evil": FakeResponse(302, {"Location": "http://10.0.0.7/x"}),
        }
    )
    assert fetcher.fetch("https://shop.example/a") == IMAGE.body
    with pytest.raises(UrlRejected, match="not public"):
        fetcher.fetch("https://shop.example/evil")
    assert "http://10.0.0.7/x" not in session.requested  # refused before any connection


def test_too_many_redirects():
    """A redirect loop stops after a few hops."""
    loop = FakeResponse(302, {"Location": "https://shop.example/loop"})
    fetcher, _ = _fetcher({"https://shop.example/loop": loop})
    with pytest.raises(UrlRejected, match="Too many redirects"):
        fetcher.fetch("https://shop.example/loop")


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (FakeResponse(404), "answered 404"),
        (FakeResponse(headers={"Content-Type": "text/html"}, body=b"<html>"), "not an image"),
        (FakeResponse(headers={"Content-Type": "image/png"}, body=b"x" * 2000), "larger than"),
        (requests.ConnectionError("refused"), "Could not download"),
    ],
)
def test_bad_answers_are_refused(response, message):
    """Error statuses, non-images, oversized bodies and network errors are refused."""
    fetcher, _ = _fetcher({"https://shop.example/a.jpg": response})
    with pytest.raises(UrlRejected, match=message):
        fetcher.fetch("https://shop.example/a.jpg")
