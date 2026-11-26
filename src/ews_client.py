"""Exchange Web Services client wrapper."""

import base64
import binascii
from collections import OrderedDict
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
import hashlib
import logging
import platform
import threading
from typing import Mapping, Optional, Tuple

from exchangelib import Account, Configuration, Credentials, DELEGATE, Version, EWSTimeZone
from exchangelib.errors import UnauthorizedError
from exchangelib.protocol import BaseProtocol, NoVerifyHTTPAdapter
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import pytz
import urllib3

from .config import Settings
from .auth import AuthHandler
from .exceptions import ConnectionError, AuthenticationError

# Suppress SSL warnings when using NoVerifyHTTPAdapter
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Per-request ContextVars for concurrent multi-user isolation
_request_account_var: ContextVar[Optional[Account]] = ContextVar("ews_request_account", default=None)
_request_email_var: ContextVar[Optional[str]] = ContextVar("ews_request_email", default=None)

MAX_CACHED_ACCOUNTS = 100


@dataclass(frozen=True)
class RequestCredentials:
    """Resolved per-request Exchange credentials."""

    email: str
    username: str
    password: str


def parse_credentials_from_headers(
    headers: Optional[Mapping[str, str]],
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Extract (email, username, password) from HTTP request headers.

    Supported headers (case-insensitive):
    - Email: X-EWS-Email (preferred) > X-OpenWebUI-User-Email > Basic Auth user (if contains '@')
    - Username: X-EWS-Username (optional, e.g. DOMAIN\\user) > Basic Auth user
    - Password: X-EWS-Password > Authorization: Basic > Authorization: Bearer
    """
    if not headers:
        return None, None, None

    normalized = {k.lower(): v for k, v in headers.items() if isinstance(k, str) and v is not None}

    email = (
        normalized.get("x-ews-email", "").strip()
        or normalized.get("x-openwebui-user-email", "").strip()
        or None
    )
    username = normalized.get("x-ews-username", "").strip() or None

    raw_password = normalized.get("x-ews-password")
    password: Optional[str] = raw_password if (raw_password is not None and raw_password != "") else None

    auth_header = normalized.get("authorization", "").strip()
    if auth_header:
        lower_auth = auth_header.lower()
        if lower_auth.startswith("basic "):
            encoded = auth_header[6:].strip()
            try:
                decoded = base64.b64decode(encoded, validate=True).decode("utf-8")
            except (binascii.Error, UnicodeDecodeError, ValueError):
                raise AuthenticationError("Invalid Authorization Basic header encoding")

            basic_user, sep, basic_pass = decoded.partition(":")
            if sep != ":":
                raise AuthenticationError("Invalid Authorization Basic header format (expected username:password)")

            basic_user = basic_user.strip()
            if basic_user:
                if not username:
                    username = basic_user
                if not email and "@" in basic_user:
                    email = basic_user
            if not password and basic_pass != "":
                password = basic_pass
        elif lower_auth.startswith("bearer "):
            bearer_token = auth_header[7:].strip()
            if not password and bearer_token:
                password = bearer_token

    return email, username, password


class EWSClient:
    """Exchange Web Services client wrapper with multi-user connection management."""

    def __init__(self, config: Settings, auth_handler: AuthHandler, max_cached_accounts: int = MAX_CACHED_ACCOUNTS):
        self.config = config
        self.auth_handler = auth_handler
        self.logger = logging.getLogger(__name__)
        self._account: Optional[Account] = None
        self._accounts_cache: "OrderedDict[str, Account]" = OrderedDict()
        self._cache_lock = threading.Lock()
        self._max_cached_accounts = max_cached_accounts

        # Configure exchangelib
        BaseProtocol.HTTP_ADAPTER_CLS = NoVerifyHTTPAdapter

        if self.config.ews_auth_type == 'ntlm':
            self.logger.info(f"Using pyspnego for NTLM authentication ({platform.system()})")

    @property
    def account(self) -> Account:
        """Return per-request account when bound, otherwise lazy-load default account."""
        req_account = _request_account_var.get()
        if req_account is not None:
            return req_account
        if self._account is None:
            self._account = self._create_account()
        return self._account

    @property
    def current_email(self) -> str:
        """Return active request email if bound, otherwise configured default email."""
        return _request_email_var.get() or self.config.ews_email or "unknown"

    def resolve_request_credentials(
        self, headers: Optional[Mapping[str, str]]
    ) -> Optional[RequestCredentials]:
        """Resolve per-request Exchange credentials from HTTP headers and config fallback.

        Returns:
            RequestCredentials if dynamic per-request auth should be used,
            or None to fall back to the default static .env account.
        Raises:
            AuthenticationError: If headers are malformed or required credentials are missing.
        """
        header_email, header_username, header_password = parse_credentials_from_headers(headers)
        has_header_creds = any(v is not None for v in (header_email, header_username, header_password))

        if self.config.ews_auth_type == "oauth2" and not header_password:
            return None

        if not has_header_creds:
            # Allow default .env credentials if fully configured or when not in HTTP request context
            if self.config.ews_email and self.config.ews_password:
                return None
            if headers is None:
                return None
            raise AuthenticationError(
                "Missing EWS credentials. Provide X-EWS-Email and X-EWS-Password (or Authorization: Bearer <password>), "
                "or Authorization: Basic <base64(email:password)>."
            )

        email = header_email or self.config.ews_email
        if not email:
            raise AuthenticationError(
                "Missing EWS email. Provide X-EWS-Email, X-OpenWebUI-User-Email, or "
                "Authorization: Basic <base64(email:password)>, or set EWS_EMAIL in .env."
            )

        if header_username:
            username = header_username
        elif header_email:
            username = header_email
        else:
            username = self.config.ews_username or email

        if header_password is not None:
            password = header_password
        else:
            # Never reuse .env EWS_PASSWORD for a different user's email
            same_as_default_user = (
                self.config.ews_email is not None
                and email.lower() == self.config.ews_email.lower()
            )
            if same_as_default_user and self.config.ews_password:
                password = self.config.ews_password
            else:
                raise AuthenticationError(
                    f"Missing EWS password for {email}. Provide X-EWS-Password, "
                    "Authorization: Bearer <password>, or Authorization: Basic <base64(email:password)>."
                )

        return RequestCredentials(email=email, username=username, password=password)

    @staticmethod
    def _make_cache_key(email: str, username: str, password: str) -> str:
        """Build a collision-resistant cache key without storing raw passwords."""
        pw_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
        return f"{email.lower()}|{username.lower()}|{pw_hash}"

    def _get_timezone(self) -> EWSTimeZone:
        """Load configured EWSTimeZone with UTC fallback."""
        try:
            return EWSTimeZone(self.config.timezone)
        except Exception as e:
            self.logger.warning(f"时区加载失败 {self.config.timezone}, 使用UTC: {e}")
            return EWSTimeZone('UTC')

    def get_or_create_account(
        self,
        email: str,
        password: str,
        username: Optional[str] = None,
    ) -> Account:
        """Get a cached Exchange Account or create a new one for (email, username, password)."""
        effective_username = username or email
        cache_key = self._make_cache_key(email, effective_username, password)

        with self._cache_lock:
            cached = self._accounts_cache.get(cache_key)
            if cached is not None:
                self._accounts_cache.move_to_end(cache_key)
                self.logger.info(f"使用缓存的 Exchange 连接: {email}")
                return cached

        # Create Exchange connection outside lock to avoid blocking other users
        account = self._create_account_with_credentials(
            email=email,
            password=password,
            username=effective_username,
        )

        evicted_account: Optional[Account] = None
        duplicate_account: Optional[Account] = None
        with self._cache_lock:
            existing = self._accounts_cache.get(cache_key)
            if existing is not None:
                self._accounts_cache.move_to_end(cache_key)
                duplicate_account = account
                account = existing
            else:
                self._accounts_cache[cache_key] = account
                if len(self._accounts_cache) > self._max_cached_accounts:
                    _, evicted_account = self._accounts_cache.popitem(last=False)

        for to_close in (duplicate_account, evicted_account):
            if to_close is not None:
                try:
                    to_close.protocol.close()
                except Exception:
                    pass

        self.logger.info(f"创建新的 Exchange 连接: {email}")
        return account

    @contextmanager
    def bind_request_account(self, account: Account, email: str):
        """Bind an Exchange Account and email to the current async/thread request context."""
        account_token = _request_account_var.set(account)
        email_token = _request_email_var.set(email)
        try:
            yield account
        finally:
            _request_account_var.reset(account_token)
            _request_email_var.reset(email_token)

    @contextmanager
    def use_credentials(
        self,
        email: str,
        password: str,
        username: Optional[str] = None,
    ):
        """Acquire an Account for credentials and bind it to the current request context."""
        account = self.get_or_create_account(email=email, password=password, username=username)
        with self.bind_request_account(account, email):
            yield account

    def set_bearer_password(
        self,
        password: str,
        email: Optional[str] = None,
        username: Optional[str] = None,
    ):
        """Backward-compatible helper to set default account using dynamic credentials."""
        target_email = email or self.config.ews_email
        if not target_email:
            raise AuthenticationError("Missing EWS email for Bearer authentication")
        target_username = username or (email if email else (self.config.ews_username or target_email))
        self._account = self.get_or_create_account(
            email=target_email,
            password=password,
            username=target_username,
        )

    def _create_account_with_credentials(
        self,
        email: str,
        password: str,
        username: Optional[str] = None,
    ) -> Account:
        """Create an Exchange Account for specific email/username/password credentials."""
        effective_username = username or email
        try:
            self.logger.info(f"动态认证连接到 Exchange: {email}")

            credentials = Credentials(
                username=effective_username,
                password=password
            )

            tz = self._get_timezone()
            BaseProtocol.TIMEOUT = self.config.request_timeout

            if self.config.ews_autodiscover:
                account = Account(
                    primary_smtp_address=email,
                    credentials=credentials,
                    autodiscover=True,
                    access_type=DELEGATE,
                    default_timezone=tz
                )
            else:
                if not self.config.ews_server_url:
                    raise ConnectionError("禁用自动发现时需要 EWS_SERVER_URL")

                config = Configuration(
                    service_endpoint=self.config.ews_server_url,
                    credentials=credentials
                )

                account = Account(
                    primary_smtp_address=email,
                    config=config,
                    autodiscover=False,
                    access_type=DELEGATE,
                    default_timezone=tz
                )

            # 测试连接
            _ = account.root.tree()
            self.logger.info(f"Exchange 认证成功: {email}")

            return account

        except UnauthorizedError as e:
            self.logger.error(f"Exchange 认证失败（邮箱或密码错误）: {email}")
            raise AuthenticationError(f"Exchange 认证失败（请检查邮箱和密码）: {email}") from e
        except AuthenticationError:
            raise
        except Exception as e:
            self.logger.error(f"动态认证连接 Exchange 失败 ({email}): {e}")
            raise ConnectionError(f"连接 Exchange 失败 ({email}): {e}")

    def _create_account_with_password(self, password: str) -> Account:
        """Backward-compatible alias for creating an account with the default configured email."""
        if not self.config.ews_email:
            raise AuthenticationError("Missing EWS email in configuration")
        return self._create_account_with_credentials(
            email=self.config.ews_email,
            password=password,
            username=self.config.ews_username or self.config.ews_email,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((ConnectionError, Exception))
    )
    def _create_account(self) -> Account:
        """Create Exchange account with retry logic."""
        try:
            self.logger.info(f"Connecting to Exchange for {self.config.ews_email}")
            self.logger.info(f"Using timezone: {self.config.timezone}")

            # Get credentials
            credentials = self.auth_handler.get_credentials()

            # Get timezone - use EWSTimeZone from exchangelib
            try:
                tz = EWSTimeZone(self.config.timezone)
                self.logger.info(f"Successfully loaded timezone: {self.config.timezone}")
            except Exception as e:
                self.logger.warning(f"Failed to load timezone {self.config.timezone}, falling back to UTC: {e}")
                tz = EWSTimeZone('UTC')

            # Use autodiscovery or manual configuration
            if self.config.ews_autodiscover:
                self.logger.info("Using autodiscovery")

                # Set timeout for autodiscovery
                BaseProtocol.TIMEOUT = self.config.request_timeout

                account = Account(
                    primary_smtp_address=self.config.ews_email,
                    credentials=credentials,
                    autodiscover=True,
                    access_type=DELEGATE,
                    default_timezone=tz
                )
            else:
                if not self.config.ews_server_url:
                    raise ConnectionError("EWS_SERVER_URL required when autodiscover is disabled")

                self.logger.info(f"Using manual configuration: {self.config.ews_server_url}")

                # Set timeout globally before creating configuration
                BaseProtocol.TIMEOUT = self.config.request_timeout

                # Create configuration using service_endpoint parameter
                # Use the exact same approach as the working test.py
                config = Configuration(
                    service_endpoint=self.config.ews_server_url,
                    credentials=credentials
                )

                account = Account(
                    primary_smtp_address=self.config.ews_email,
                    config=config,
                    autodiscover=False,
                    access_type=DELEGATE,
                    default_timezone=tz
                )

            # Test the connection
            _ = account.root.tree()
            self.logger.info("Successfully connected to Exchange")

            return account

        except AuthenticationError:
            raise
        except Exception as e:
            self.logger.error(f"Failed to create account: {e}")
            raise ConnectionError(f"Failed to connect to Exchange: {e}")

    def test_connection(self) -> bool:
        """Test EWS connection."""
        try:
            # Try a simple operation
            _ = self.account.inbox.total_count
            self.logger.info("Connection test successful")
            return True
        except Exception as e:
            self.logger.error(f"Connection test failed: {e}")
            return False

    def close(self) -> None:
        """Close default and cached connections and cleanup."""
        closed_ids = set()

        if self._account:
            self.logger.info("Closing EWS connection")
            try:
                self._account.protocol.close()
            except Exception as e:
                self.logger.warning(f"Error closing default EWS connection: {e}")
            closed_ids.add(id(self._account))
            self._account = None

        with self._cache_lock:
            cached_accounts = list(self._accounts_cache.values())
            self._accounts_cache.clear()

        for account in cached_accounts:
            if id(account) in closed_ids:
                continue
            try:
                account.protocol.close()
            except Exception as e:
                self.logger.warning(f"Error closing cached EWS connection: {e}")
            closed_ids.add(id(account))
