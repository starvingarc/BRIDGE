import socket
import ssl
from dataclasses import replace

import httpcore
import httpx
import pytest

from bridge.web.model_transport import provider_client
from bridge.web.runtime import Settings


def settings(tmp_path, **kwargs):
    return Settings(storage_root=tmp_path, model="test", model_api_key="secret",
                    model_base_url="https://model.example/v1", model_endpoint_restricted=True, **kwargs)


def dns(addresses):
    return [(socket.AF_INET6 if ":" in address else socket.AF_INET, socket.SOCK_STREAM, 6, "",
             (address, 443, 0, 0) if ":" in address else (address, 443)) for address in addresses]


@pytest.mark.parametrize("addresses", [
    ["127.0.0.1"], ["10.0.0.1"], ["169.254.169.254"], ["::1"], ["::ffff:127.0.0.1"],
    ["224.0.0.1"], ["64:ff9b::7f00:1"], ["8.8.8.8", "192.168.1.1"],
])
def test_private_targets_and_mixed_dns_are_blocked(tmp_path, monkeypatch, addresses):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: dns(addresses))
    def forbidden(*a, **k):
        pytest.fail("a disallowed address reached TCP")
    monkeypatch.setattr(httpcore.SyncBackend, "connect_tcp", forbidden)
    with provider_client(settings(tmp_path), timeout=1) as client:
        with pytest.raises(httpx.HTTPError):
            client.post("https://model.example/v1/chat/completions", json={})


def test_dns_is_resolved_once_and_tls_keeps_original_host(tmp_path, monkeypatch):
    calls, connected, tls = [], [], []
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9999")
    def resolve(host, port, **kwargs):
        calls.append(host)
        return dns(["8.8.8.8"] if len(calls) == 1 else ["127.0.0.1"])
    monkeypatch.setattr(socket, "getaddrinfo", resolve)
    class Stream(httpcore.MockStream):
        def start_tls(self, ssl_context, server_hostname=None, timeout=None):
            tls.append((server_hostname, ssl_context.check_hostname, ssl_context.verify_mode))
            return self
    def connect(self, host, port, **kwargs):
        connected.append((host, port))
        return Stream([b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nOK"])
    monkeypatch.setattr(httpcore.SyncBackend, "connect_tcp", connect)
    with provider_client(settings(tmp_path), timeout=1) as client:
        result = client.post("https://model.example/v1/chat/completions", json={})
    assert result.text == "OK"
    assert calls == ["model.example"]
    assert connected == [("8.8.8.8", 443)]
    assert tls == [("model.example", True, ssl.CERT_REQUIRED)]


def test_redirects_do_not_forward_credentials(tmp_path, monkeypatch):
    connected = []
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: dns(["8.8.8.8"]))
    def connect(self, host, port, **kwargs):
        connected.append(host)
        return httpcore.MockStream([b"HTTP/1.1 302 Found\r\nLocation: https://127.0.0.1/secret\r\nContent-Length: 0\r\n\r\n"])
    monkeypatch.setattr(httpcore.SyncBackend, "connect_tcp", connect)
    with provider_client(settings(tmp_path), timeout=1) as client:
        result = client.post("https://model.example/v1/chat/completions", headers={"Authorization": "Bearer secret"})
    assert result.status_code == 302
    assert connected == ["8.8.8.8"]


def test_operator_allowed_endpoint_is_pinned(tmp_path, monkeypatch):
    target = "http://10.20.30.40:8080/v1"
    config = replace(settings(tmp_path, personal_model_allowlist=(target,)), model_base_url=target)
    connected = []
    def connect(self, host, port, **kwargs):
        connected.append((host, port))
        return httpcore.MockStream([b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nOK"])
    monkeypatch.setattr(httpcore.SyncBackend, "connect_tcp", connect)
    with provider_client(config, timeout=1) as client:
        assert client.post(target + "/chat/completions").text == "OK"
        with pytest.raises(httpx.HTTPError):
            client.post("http://10.20.30.41:8080/v1/chat/completions")
        with pytest.raises(httpx.HTTPError):
            client.post("http://10.20.30.40:8080/admin")
    assert connected == [("10.20.30.40", 8080)]
