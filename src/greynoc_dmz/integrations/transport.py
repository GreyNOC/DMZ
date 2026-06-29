from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass


class _NoFollowRedirect(urllib.request.HTTPRedirectHandler):
    """A redirect handler that never follows redirects.

    The endpoint safety gate validates only the URL it is given. If the
    transport silently followed a 3xx, the credential headers would be re-sent to
    an unvalidated host — defeating both the isolation gate and credential safety.
    Returning ``None`` makes urllib surface the redirect as an ``HTTPError``,
    which callers treat as a normal non-2xx response and reject.
    """

    def redirect_request(self, *args: object, **kwargs: object) -> None:
        return None


class TransportError(RuntimeError):
    """Raised when an HTTP request fails before a response is received.

    The message never contains request headers or credential material.
    """


@dataclass(frozen=True)
class HttpResponse:
    status: int
    body: str

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300


def post_json(
    url: str,
    payload: dict[str, object],
    *,
    headers: dict[str, str],
    timeout: int,
    verify_tls: bool = True,
) -> HttpResponse:
    """POST a JSON body and return the response.

    HTTP error responses (4xx/5xx) are returned, not raised, so adapters can
    interpret them. Connection-level failures raise ``TransportError`` with no
    credential material in the message.
    """
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, method="POST")
    request.add_header("Content-Type", "application/json")
    for key, value in headers.items():
        request.add_header(key, value)

    context: ssl.SSLContext | None = None
    if url.lower().startswith("https://"):
        context = ssl.create_default_context()
        if not verify_tls:
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

    # A per-request opener that refuses redirects (so credentials are never
    # re-sent to an unvalidated host) while preserving the chosen TLS context.
    handlers: list[urllib.request.BaseHandler] = [_NoFollowRedirect()]
    if context is not None:
        handlers.append(urllib.request.HTTPSHandler(context=context))
    opener = urllib.request.build_opener(*handlers)

    try:
        with opener.open(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
            return HttpResponse(status=response.status, body=body)
    except urllib.error.HTTPError as error:
        error_body = error.read().decode("utf-8", errors="replace")
        return HttpResponse(status=error.code, body=error_body)
    except urllib.error.URLError as error:
        raise TransportError(f"could not reach {url}: {error.reason}") from error
    except (TimeoutError, OSError) as error:
        raise TransportError(f"transport failure for {url}") from error
