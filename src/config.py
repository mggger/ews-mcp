"""Configuration management for EWS MCP Server."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, model_validator
from typing import Literal, Optional


class Settings(BaseSettings):
    """Application settings with validation."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Exchange settings
    ews_server_url: Optional[str] = None
    ews_email: str
    ews_autodiscover: bool = True

    # Authentication
    ews_auth_type: Literal["oauth2", "basic", "ntlm"] = "oauth2"
    ews_client_id: Optional[str] = None
    ews_client_secret: Optional[str] = None
    ews_tenant_id: Optional[str] = None
    ews_username: Optional[str] = None
    ews_password: Optional[str] = None

    # Server configuration
    mcp_server_name: str = "ews-mcp-server"
    mcp_transport: Literal["stdio", "sse"] = "stdio"
    mcp_host: str = "0.0.0.0"
    mcp_port: int = 8000
    log_level: str = "INFO"

    # Performance
    enable_cache: bool = True
    cache_ttl: int = 300
    connection_pool_size: int = 10
    request_timeout: int = 30

    # Rate limiting
    rate_limit_enabled: bool = True
    rate_limit_requests_per_minute: int = 25

    # Features
    enable_email: bool = True
    enable_calendar: bool = True
    enable_contacts: bool = True
    enable_tasks: bool = True
    enable_folders: bool = True
    enable_attachments: bool = True

    # Security
    enable_audit_log: bool = True
    max_attachment_size: int = 157286400  # 150MB

    @model_validator(mode='after')
    def validate_auth_credentials(self) -> 'Settings':
        """Validate required credentials based on auth type."""
        if self.ews_auth_type == "oauth2":
            required = {
                "ews_client_id": self.ews_client_id,
                "ews_client_secret": self.ews_client_secret,
                "ews_tenant_id": self.ews_tenant_id
            }
            missing = [name for name, value in required.items() if not value]
            if missing:
                raise ValueError(f"OAuth2 auth requires: {', '.join(missing)}")
        elif self.ews_auth_type in ("basic", "ntlm"):
            if not self.ews_username or not self.ews_password:
                raise ValueError(f"{self.ews_auth_type.upper()} auth requires ews_username and ews_password")

        return self


# Singleton instance - lazy loading
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get or create settings instance (lazy loading)."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


# Backward compatibility - will only be evaluated when accessed
def __getattr__(name):
    """Lazy attribute access for backward compatibility."""
    if name == "settings":
        return get_settings()
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
