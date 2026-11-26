"""Tests for multi-user per-request dynamic credentials and HTTP header auth."""

import asyncio
import base64
import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.auth import AuthHandler
from src.config import Settings
from src.ews_client import (
    EWSClient,
    RequestCredentials,
    parse_credentials_from_headers,
)
from src.exceptions import AuthenticationError
from src.main import EWSMCPServer
from src.tools.base import BaseTool


def _make_settings(**overrides) -> Settings:
    defaults = dict(
        ews_server_url="https://mail.example.com/EWS/Exchange.asmx",
        ews_email=None,
        ews_username=None,
        ews_password=None,
        ews_autodiscover=False,
        ews_auth_type="ntlm",
        mcp_transport="streamable_http",
        rate_limit_enabled=False,
        enable_audit_log=False,
    )
    defaults.update(overrides)
    return Settings(_env_file=None, **defaults)


class TestHeaderParsing:
    """Verify extraction of email, username, and password from HTTP headers."""

    def test_x_ews_email_and_bearer(self):
        email, username, password = parse_credentials_from_headers({
            "X-EWS-Email": "alice@company.com",
            "Authorization": "Bearer secret-pw",
        })
        assert email == "alice@company.com"
        assert username is None
        assert password == "secret-pw"

    def test_openwebui_email_and_x_ews_password(self):
        email, username, password = parse_credentials_from_headers({
            "X-OpenWebUI-User-Email": "bob@company.com",
            "X-EWS-Password": "bob-secret:with:colons",
        })
        assert email == "bob@company.com"
        assert username is None
        assert password == "bob-secret:with:colons"

    def test_x_ews_email_takes_precedence_over_openwebui_email(self):
        email, _, _ = parse_credentials_from_headers({
            "X-EWS-Email": "override@company.com",
            "X-OpenWebUI-User-Email": "webui@company.com",
            "Authorization": "Bearer pw",
        })
        assert email == "override@company.com"

    def test_basic_auth_with_email_and_password_containing_colon(self):
        raw = base64.b64encode(b"carol@company.com:p@ss:word:123").decode()
        email, username, password = parse_credentials_from_headers({
            "Authorization": f"Basic {raw}",
        })
        assert email == "carol@company.com"
        assert username == "carol@company.com"
        assert password == "p@ss:word:123"

    def test_basic_auth_with_domain_username_and_x_ews_email(self):
        raw = base64.b64encode(br"CORP\dave:dave-pw").decode()
        email, username, password = parse_credentials_from_headers({
            "X-EWS-Email": "dave@company.com",
            "Authorization": f"Basic {raw}",
        })
        assert email == "dave@company.com"
        assert username == r"CORP\dave"
        assert password == "dave-pw"

    def test_x_ews_username_override(self):
        email, username, password = parse_credentials_from_headers({
            "X-EWS-Email": "erin@company.com",
            "X-EWS-Username": r"CORP\erin",
            "X-EWS-Password": "erin-pw",
        })
        assert email == "erin@company.com"
        assert username == r"CORP\erin"
        assert password == "erin-pw"

    def test_invalid_basic_auth_raises(self):
        with pytest.raises(AuthenticationError):
            parse_credentials_from_headers({"Authorization": "Basic not-valid-base64!!!"})

        no_colon = base64.b64encode(b"onlyuser").decode()
        with pytest.raises(AuthenticationError):
            parse_credentials_from_headers({"Authorization": f"Basic {no_colon}"})


class TestCredentialResolution:
    """Verify fallback rules and cross-user password protection."""

    def test_pure_multi_user_mode_without_default_email(self):
        settings = _make_settings()
        client = EWSClient(settings, AuthHandler(settings))

        creds = client.resolve_request_credentials({
            "X-EWS-Email": "alice@company.com",
            "Authorization": "Bearer alice-pw",
        })
        assert creds == RequestCredentials(
            email="alice@company.com",
            username="alice@company.com",
            password="alice-pw",
        )

    def test_bearer_only_falls_back_to_default_env_email(self):
        settings = _make_settings(ews_email="default@company.com", ews_username=r"CORP\default")
        client = EWSClient(settings, AuthHandler(settings))

        creds = client.resolve_request_credentials({
            "Authorization": "Bearer default-pw",
        })
        assert creds == RequestCredentials(
            email="default@company.com",
            username=r"CORP\default",
            password="default-pw",
        )

    def test_dynamic_email_does_not_inherit_default_env_username_or_password(self):
        settings = _make_settings(
            ews_email="admin@company.com",
            ews_username=r"CORP\admin",
            ews_password="admin-secret-password",
        )
        client = EWSClient(settings, AuthHandler(settings))

        # Different user without password MUST NOT reuse admin's .env password
        with pytest.raises(AuthenticationError, match="Missing EWS password"):
            client.resolve_request_credentials({"X-EWS-Email": "bob@company.com"})

        # Different user with their own password uses their own email as username, not CORP\admin
        creds = client.resolve_request_credentials({
            "X-EWS-Email": "bob@company.com",
            "Authorization": "Bearer bob-pw",
        })
        assert creds == RequestCredentials(
            email="bob@company.com",
            username="bob@company.com",
            password="bob-pw",
        )

    def test_missing_email_without_default_raises(self):
        settings = _make_settings()
        client = EWSClient(settings, AuthHandler(settings))

        with pytest.raises(AuthenticationError, match="Missing EWS email"):
            client.resolve_request_credentials({"Authorization": "Bearer some-pw"})

    def test_empty_headers_without_env_password_raises(self):
        settings = _make_settings(ews_email="default@company.com", ews_password=None)
        client = EWSClient(settings, AuthHandler(settings))

        with pytest.raises(AuthenticationError, match="Missing EWS credentials"):
            client.resolve_request_credentials({})

    def test_stdio_mode_still_requires_email_in_config(self):
        with pytest.raises(ValueError, match="stdio mode requires"):
            _make_settings(mcp_transport="stdio", ews_email=None, ews_username=None)


class TestMultiUserConcurrencyAndCaching:
    """Verify per-request ContextVar isolation, LRU caching, and close cleanup."""

    @pytest.mark.asyncio
    async def test_concurrent_requests_do_not_cross_accounts(self):
        settings = _make_settings()
        client = EWSClient(settings, AuthHandler(settings))

        def fake_create(email, password, username=None):
            acc = MagicMock()
            acc.primary_smtp_address = email
            acc.password_marker = password
            acc.protocol = MagicMock()
            return acc

        with patch.object(client, "_create_account_with_credentials", side_effect=fake_create):
            async def simulate_user_request(email: str, password: str, delay: float):
                account = await asyncio.to_thread(client.get_or_create_account, email, password, email)
                with client.bind_request_account(account, email):
                    seen_before = (client.account.primary_smtp_address, client.current_email)
                    await asyncio.sleep(delay)
                    seen_after = (client.account.primary_smtp_address, client.current_email)
                    return seen_before, seen_after

            res_a, res_b = await asyncio.gather(
                simulate_user_request("alice@company.com", "pw-a", 0.05),
                simulate_user_request("bob@company.com", "pw-b", 0.01),
            )

        assert res_a == (("alice@company.com", "alice@company.com"), ("alice@company.com", "alice@company.com"))
        assert res_b == (("bob@company.com", "bob@company.com"), ("bob@company.com", "bob@company.com"))
        # Context must be reset outside the with block
        assert client.current_email == "unknown"

    def test_lru_cache_eviction_and_close_cleanup(self):
        settings = _make_settings()
        client = EWSClient(settings, AuthHandler(settings), max_cached_accounts=2)

        created = {}

        def fake_create(email, password, username=None):
            acc = MagicMock()
            acc.primary_smtp_address = email
            acc.protocol = MagicMock()
            created[email] = acc
            return acc

        with patch.object(client, "_create_account_with_credentials", side_effect=fake_create) as mock_create:
            a1 = client.get_or_create_account("a@company.com", "pw1")
            a2 = client.get_or_create_account("a@company.com", "pw1")
            assert a1 is a2
            assert mock_create.call_count == 1

            b1 = client.get_or_create_account("b@company.com", "pw2")
            assert b1 is not a1
            # Access a@ again so b@ becomes LRU
            assert client.get_or_create_account("a@company.com", "pw1") is a1

            # Adding c@ evicts b@
            c1 = client.get_or_create_account("c@company.com", "pw3")
            assert c1 is not None
            created["b@company.com"].protocol.close.assert_called_once()
            created["a@company.com"].protocol.close.assert_not_called()

            # Closing client closes remaining cached accounts (a@ and c@)
            client.close()
            created["a@company.com"].protocol.close.assert_called_once()
            created["c@company.com"].protocol.close.assert_called_once()
            assert len(client._accounts_cache) == 0


class _WhoAmITool(BaseTool):
    """Test tool returning the active Exchange account bound to this request."""

    def get_schema(self):
        return {
            "name": "whoami",
            "description": "Return bound Exchange mailbox email",
            "inputSchema": {"type": "object", "properties": {}},
        }

    async def execute(self, **kwargs):
        await asyncio.sleep(0.02)
        return {
            "success": True,
            "smtp": self.ews_client.account.primary_smtp_address,
            "current_email": self.ews_client.current_email,
        }


def _parse_sse_json(text: str) -> dict:
    for line in text.splitlines():
        if line.startswith("data: "):
            return json.loads(line[6:])
    return json.loads(text)


@pytest.mark.asyncio
async def test_streamable_http_end_to_end_multi_user_headers():
    """End-to-end ASGI test through StreamableHTTPSessionManager verifying per-request headers."""
    settings = _make_settings()

    with patch("src.main.get_settings", return_value=settings):
        mcp_server = EWSMCPServer()

    mcp_server.tools = {"whoami": _WhoAmITool(mcp_server.ews_client)}

    def fake_create(email, password, username=None):
        acc = MagicMock()
        acc.primary_smtp_address = f"{email}|{username}|{password}"
        acc.protocol = MagicMock()
        return acc

    app = mcp_server.create_streamable_http_app()

    # Drive Starlette lifespan so StreamableHTTPSessionManager initializes its task group
    starlette_app = app.app
    async with starlette_app.router.lifespan_context(starlette_app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as http_client:
            # 1. Initialize & tools/list succeed WITHOUT Exchange credentials
            init_resp = await http_client.post(
                "/mcp/",
                headers={
                    "Accept": "application/json, text/event-stream",
                    "Content-Type": "application/json",
                },
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-03-26",
                        "capabilities": {},
                        "clientInfo": {"name": "open-webui-test", "version": "1.0"},
                    },
                },
            )
            assert init_resp.status_code == 200
            session_id = init_resp.headers["mcp-session-id"]

            await http_client.post(
                "/mcp/",
                headers={
                    "Accept": "application/json, text/event-stream",
                    "Content-Type": "application/json",
                    "mcp-session-id": session_id,
                },
                json={"jsonrpc": "2.0", "method": "notifications/initialized"},
            )

            list_resp = await http_client.post(
                "/mcp/",
                headers={
                    "Accept": "application/json, text/event-stream",
                    "Content-Type": "application/json",
                    "mcp-session-id": session_id,
                },
                json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            )
            assert list_resp.status_code == 200
            list_payload = _parse_sse_json(list_resp.text)
            assert [t["name"] for t in list_payload["result"]["tools"]] == ["whoami"]

            # 2. Concurrent tool calls with different users' headers on the same server
            with patch.object(mcp_server.ews_client, "_create_account_with_credentials", side_effect=fake_create):
                alice_call = http_client.post(
                    "/mcp/",
                    headers={
                        "Accept": "application/json, text/event-stream",
                        "Content-Type": "application/json",
                        "mcp-session-id": session_id,
                        "X-EWS-Email": "alice@company.com",
                        "Authorization": "Bearer alice-pass",
                    },
                    json={
                        "jsonrpc": "2.0",
                        "id": 3,
                        "method": "tools/call",
                        "params": {"name": "whoami", "arguments": {}},
                    },
                )
                bob_basic = base64.b64encode(b"bob@company.com:bob-pass").decode()
                bob_call = http_client.post(
                    "/mcp/",
                    headers={
                        "Accept": "application/json, text/event-stream",
                        "Content-Type": "application/json",
                        "mcp-session-id": session_id,
                        "Authorization": f"Basic {bob_basic}",
                    },
                    json={
                        "jsonrpc": "2.0",
                        "id": 4,
                        "method": "tools/call",
                        "params": {"name": "whoami", "arguments": {}},
                    },
                )
                carol_call = http_client.post(
                    "/mcp/",
                    headers={
                        "Accept": "application/json, text/event-stream",
                        "Content-Type": "application/json",
                        "mcp-session-id": session_id,
                        "X-OpenWebUI-User-Email": "carol@company.com",
                        "X-EWS-Password": "carol-pass",
                    },
                    json={
                        "jsonrpc": "2.0",
                        "id": 5,
                        "method": "tools/call",
                        "params": {"name": "whoami", "arguments": {}},
                    },
                )

                alice_resp, bob_resp, carol_resp = await asyncio.gather(alice_call, bob_call, carol_call)

            alice_text = _parse_sse_json(alice_resp.text)["result"]["content"][0]["text"]
            bob_text = _parse_sse_json(bob_resp.text)["result"]["content"][0]["text"]
            carol_text = _parse_sse_json(carol_resp.text)["result"]["content"][0]["text"]

            assert "alice@company.com|alice@company.com|alice-pass" in alice_text
            assert "bob@company.com|bob@company.com|bob-pass" in bob_text
            assert "carol@company.com|carol@company.com|carol-pass" in carol_text
