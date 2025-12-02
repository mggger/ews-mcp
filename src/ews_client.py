"""Exchange Web Services client wrapper."""

import platform
from exchangelib import Account, Configuration, DELEGATE, Version, EWSTimeZone
from exchangelib.protocol import BaseProtocol, NoVerifyHTTPAdapter
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import logging
import pytz
from typing import Optional, Dict
import urllib3

from .config import Settings
from .auth import AuthHandler
from .exceptions import ConnectionError, AuthenticationError

# Suppress SSL warnings when using NoVerifyHTTPAdapter
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class EWSClient:
    """Exchange Web Services client wrapper with connection management."""

    def __init__(self, config: Settings, auth_handler: AuthHandler):
        self.config = config
        self.auth_handler = auth_handler
        self.logger = logging.getLogger(__name__)
        self._account: Optional[Account] = None
        self._accounts_cache: Dict[str, Account] = {}  # 缓存连接

        # Configure exchangelib
        BaseProtocol.HTTP_ADAPTER_CLS = NoVerifyHTTPAdapter
        
        if self.config.ews_auth_type == 'ntlm':
            self.logger.info(f"Using pyspnego for NTLM authentication ({platform.system()})")

    @property
    def account(self) -> Account:
        """Lazy load account connection."""
        if self._account is None:
            self._account = self._create_account()
        return self._account

    def set_bearer_password(self, password: str):
        """设置 Bearer 认证的密码（密码通过 Bearer token 传递）"""
        # 使用密码的哈希作为缓存 key
        import hashlib
        cache_key = f"bearer_{hashlib.sha256(password.encode()).hexdigest()[:16]}"
        
        if cache_key in self._accounts_cache:
            self._account = self._accounts_cache[cache_key]
            self.logger.info(f"使用缓存的 Bearer 认证连接: {self.config.ews_email}")
        else:
            # 创建新连接
            self._account = self._create_account_with_password(password)
            self._accounts_cache[cache_key] = self._account
            self.logger.info(f"创建新的 Bearer 认证连接: {self.config.ews_email}")

    def _create_account_with_password(self, password: str) -> Account:
        """使用指定密码创建 Exchange 账户连接（用于 Bearer 认证）"""
        try:
            self.logger.info(f"Bearer 认证连接到 Exchange: {self.config.ews_email}")
            
            # 创建凭据 - 使用 NTLM 或 Basic 认证
            from exchangelib import Credentials
            credentials = Credentials(
                username=self.config.ews_username or self.config.ews_email,
                password=password
            )

            # 获取时区
            try:
                tz = EWSTimeZone(self.config.timezone)
            except Exception as e:
                self.logger.warning(f"时区加载失败 {self.config.timezone}, 使用UTC: {e}")
                tz = EWSTimeZone('UTC')

            BaseProtocol.TIMEOUT = self.config.request_timeout

            if self.config.ews_autodiscover:
                account = Account(
                    primary_smtp_address=self.config.ews_email,
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
                    primary_smtp_address=self.config.ews_email,
                    config=config,
                    autodiscover=False,
                    access_type=DELEGATE,
                    default_timezone=tz
                )

            # 测试连接
            _ = account.root.tree()
            self.logger.info(f"Bearer 认证成功: {self.config.ews_email}")

            return account

        except Exception as e:
            self.logger.error(f"Bearer 认证连接失败: {e}")
            raise ConnectionError(f"Bearer 认证连接 Exchange 失败: {e}")

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
        """Close connection and cleanup."""
        if self._account:
            self.logger.info("Closing EWS connection")
            self._account.protocol.close()
            self._account = None
