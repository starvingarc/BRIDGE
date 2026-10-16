"""Provider HTTP boundary: personal endpoints cannot choose private destinations."""
import ipaddress
import socket
import time
from urllib.parse import urlsplit

import httpcore
import httpx


def public_address(value):
    address = ipaddress.ip_address(value)
    if not address.is_global or address.is_multicast or address.is_reserved:
        return False
    if isinstance(address, ipaddress.IPv6Address):
        # Translation/tunnelling prefixes can hide a non-public IPv4 destination.
        if address.ipv4_mapped:
            return public_address(str(address.ipv4_mapped))
        if address.sixtofour or address.teredo:
            return False
        if address in ipaddress.ip_network("64:ff9b::/96") or address in ipaddress.ip_network("64:ff9b:1::/48"):
            return False
    return True


def validate_endpoint(base_url, allowlist=()):
    try:
        url = httpx.URL(base_url)
        parts = urlsplit(base_url)
        host = url.raw_host.decode("ascii")
        if not host or "%" in host or parts.username or parts.password or parts.query or parts.fragment or parts.port == 0:
            raise ValueError
        allowed = base_url.rstrip("/") in allowlist
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = None
        # Operator exceptions pin an exact IP endpoint, not a rebinding hostname.
        if allowed and (address is None or address.is_link_local or address.is_multicast or address.is_unspecified):
            raise ValueError
        if url.scheme != "https" and not (allowed and url.scheme == "http"):
            raise ValueError
        if address is not None and not (public_address(host) or allowed):
            raise ValueError
        return url, allowed
    except (ValueError, httpx.InvalidURL):
        raise ValueError("invalid_personal_model_endpoint") from None


class PinnedBackend(httpcore.NetworkBackend):
    def __init__(self, url, allowed):
        self.host = url.raw_host.decode("ascii")
        self.port = url.port or (443 if url.scheme == "https" else 80)
        self.allowed = allowed
        self.backend = httpcore.SyncBackend()

    def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        if host != self.host or port != self.port:
            raise httpcore.ConnectError("model_endpoint_denied")
        try:
            ipaddress.ip_address(host)
            addresses = [host]
        except ValueError:
            try:
                addresses = list(dict.fromkeys(item[4][0] for item in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)))
            except OSError:
                raise httpcore.ConnectError("model_endpoint_unavailable") from None
        if not addresses or len(addresses) > 16 or (not self.allowed and not all(public_address(ip) for ip in addresses)):
            raise httpcore.ConnectError("model_endpoint_denied")
        deadline = time.monotonic() + timeout if timeout is not None else None
        for address in addresses:
            remaining = max(0, deadline - time.monotonic()) if deadline is not None else None
            if remaining is not None and remaining <= 0:
                raise httpcore.ConnectTimeout("model_endpoint_timeout")
            try:
                # Only a numeric, checked address reaches the socket layer. The
                # connection pool retains the original Host and TLS server name.
                return self.backend.connect_tcp(address, port, timeout=remaining,
                                                local_address=local_address, socket_options=socket_options)
            except (httpcore.ConnectError, httpcore.ConnectTimeout):
                continue
        raise httpcore.ConnectError("model_endpoint_unavailable")


CORE_ERRORS = (httpcore.TimeoutException, httpcore.NetworkError, httpcore.ProtocolError,
               httpcore.ProxyError, httpcore.UnsupportedProtocol)


class ResponseStream(httpx.SyncByteStream):
    def __init__(self, response):
        self.response = response

    def __iter__(self):
        try:
            yield from self.response.stream
        except CORE_ERRORS:
            raise httpx.ReadError("provider_transport_failed") from None

    def close(self):
        self.response.close()


class PersonalTransport(httpx.BaseTransport):
    def __init__(self, base_url, allowlist):
        self.url, allowed = validate_endpoint(base_url, allowlist)
        self.pool = httpcore.ConnectionPool(network_backend=PinnedBackend(self.url, allowed),
                                            ssl_context=httpcore.default_ssl_context(),
                                            max_connections=2, max_keepalive_connections=1)

    def handle_request(self, request):
        if ((request.url.scheme, request.url.host, request.url.port) !=
                (self.url.scheme, self.url.host, self.url.port)
                or not request.url.path.startswith(self.url.path.rstrip("/") + "/")):
            raise httpx.ConnectError("model_endpoint_denied")
        core_request = httpcore.Request(
            method=request.method,
            url=httpcore.URL(scheme=request.url.raw_scheme, host=request.url.raw_host,
                             port=request.url.port, target=request.url.raw_path),
            headers=request.headers.raw, content=request.stream, extensions=request.extensions)
        try:
            response = self.pool.handle_request(core_request)
        except CORE_ERRORS:
            raise httpx.ConnectError("provider_transport_failed") from None
        return httpx.Response(response.status, headers=response.headers,
                              stream=ResponseStream(response), extensions=response.extensions)

    def close(self):
        self.pool.close()


def provider_client(settings, *, timeout, trust_env=True):
    options = {}
    if getattr(settings, "model_endpoint_restricted", False):
        trust_env = False
        options["transport"] = PersonalTransport(settings.model_base_url, settings.personal_model_allowlist)
    return httpx.Client(timeout=timeout, follow_redirects=False, trust_env=trust_env, **options)


_REASONING_OUTPUT_TOKEN_LIMIT = 32768


def apply_model_effort(settings, payload):
    """Apply one task-wide choice; None delegates to the provider's defaults.

    Return whether reasoning may be active, for request budget/timeout handling.
    """
    effort = getattr(settings, "model_effort", None)
    deepseek = (settings.model_action_protocol == "deepseek_tools"
                or urlsplit(settings.model_base_url).hostname == "api.deepseek.com")
    # No hidden per-workflow thinking policy survives an unspecified choice.
    payload.pop("thinking", None)
    payload.pop("reasoning_effort", None)
    if effort is not None:
        if deepseek:
            payload["thinking"] = {"type": "disabled" if effort == "none" else "enabled"}
        if not deepseek or effort != "none":
            payload["reasoning_effort"] = effort
    reasoning_possible = effort != "none" and (effort is not None or deepseek)
    if deepseek and effort != "none":
        # An undeclared provider default may enable thinking as well.
        payload.pop("tool_choice", None)
    if reasoning_possible:
        payload["max_tokens"] = max(payload.get("max_tokens", 0), _REASONING_OUTPUT_TOKEN_LIMIT)
    return reasoning_possible
