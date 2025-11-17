"""Tests for EWS client."""

import pytest
from unittest.mock import Mock, patch, MagicMock

from src.ews_client import EWSClient
from src.exceptions import ConnectionError


def test_ews_client_initialization(mock_settings, mock_auth_handler):
    """Test EWS client initialization."""
    client = EWSClient(mock_settings, mock_auth_handler)

    assert client.config == mock_settings
    assert client.auth_handler == mock_auth_handler
    assert client._account is None


def test_ews_client_lazy_account_loading(mock_settings, mock_auth_handler):
    """Test lazy loading of account."""
    with patch.object(EWSClient, '_create_account') as mock_create:
        mock_account = MagicMock()
        mock_create.return_value = mock_account

        client = EWSClient(mock_settings, mock_auth_handler)

        # Account should not be created yet
        assert client._account is None

        # Accessing account should trigger creation
        account = client.account

        assert account == mock_account
        mock_create.assert_called_once()


def test_ews_client_connection_test(mock_settings, mock_auth_handler):
    """Test connection testing."""
    with patch.object(EWSClient, '_create_account') as mock_create:
        mock_account = MagicMock()
        mock_account.inbox.total_count = 10
        mock_create.return_value = mock_account

        client = EWSClient(mock_settings, mock_auth_handler)

        result = client.test_connection()

        assert result is True


def test_ews_client_connection_failure(mock_settings, mock_auth_handler):
    """Test connection failure handling."""
    from unittest.mock import PropertyMock
    with patch.object(EWSClient, '_create_account') as mock_create:
        mock_account = MagicMock()
        type(mock_account.inbox).total_count = PropertyMock(side_effect=Exception("Connection failed"))
        mock_create.return_value = mock_account

        client = EWSClient(mock_settings, mock_auth_handler)

        result = client.test_connection()

        assert result is False


def test_normalize_server_url_domain_only(mock_settings, mock_auth_handler):
    """Test URL normalization with domain only."""
    client = EWSClient(mock_settings, mock_auth_handler)
    
    result = client._normalize_server_url("owa.example.com")
    assert result == "https://owa.example.com/ews/exchange.asmx"


def test_normalize_server_url_with_https(mock_settings, mock_auth_handler):
    """Test URL normalization with https prefix."""
    client = EWSClient(mock_settings, mock_auth_handler)
    
    result = client._normalize_server_url("https://owa.example.com")
    assert result == "https://owa.example.com/ews/exchange.asmx"


def test_normalize_server_url_full_url(mock_settings, mock_auth_handler):
    """Test URL normalization with full URL already provided."""
    client = EWSClient(mock_settings, mock_auth_handler)
    
    result = client._normalize_server_url("https://owa.example.com/ews/exchange.asmx")
    assert result == "https://owa.example.com/ews/exchange.asmx"


def test_normalize_server_url_with_trailing_slash(mock_settings, mock_auth_handler):
    """Test URL normalization with trailing slash."""
    client = EWSClient(mock_settings, mock_auth_handler)
    
    result = client._normalize_server_url("owa.example.com/")
    assert result == "https://owa.example.com/ews/exchange.asmx"


def test_normalize_server_url_case_insensitive(mock_settings, mock_auth_handler):
    """Test URL normalization is case insensitive for path."""
    client = EWSClient(mock_settings, mock_auth_handler)
    
    result = client._normalize_server_url("https://owa.example.com/EWS/Exchange.asmx")
    assert result == "https://owa.example.com/EWS/Exchange.asmx"


def test_normalize_server_url_with_whitespace(mock_settings, mock_auth_handler):
    """Test URL normalization strips whitespace."""
    client = EWSClient(mock_settings, mock_auth_handler)
    
    result = client._normalize_server_url("  owa.example.com  ")
    assert result == "https://owa.example.com/ews/exchange.asmx"


def test_create_account_uses_service_endpoint(mock_settings, mock_auth_handler):
    """Test that Configuration is created with service_endpoint parameter."""
    from exchangelib import Configuration, Account
    
    mock_settings.ews_autodiscover = False
    mock_settings.ews_server_url = "owa.example.com"
    
    client = EWSClient(mock_settings, mock_auth_handler)
    
    with patch('src.ews_client.Configuration') as mock_config_class, \
         patch('src.ews_client.Account') as mock_account_class, \
         patch('src.ews_client.EWSTimeZone') as mock_tz:
        
        mock_config = MagicMock()
        mock_config.protocol = MagicMock()
        mock_config_class.return_value = mock_config
        
        mock_account = MagicMock()
        mock_account.root.tree.return_value = None
        mock_account_class.return_value = mock_account
        
        mock_tz.return_value = MagicMock()
        
        # Call _create_account
        client._create_account()
        
        # Verify Configuration was called with service_endpoint
        mock_config_class.assert_called_once()
        call_kwargs = mock_config_class.call_args[1]
        
        assert 'service_endpoint' in call_kwargs
        assert call_kwargs['service_endpoint'] == 'https://owa.example.com/ews/exchange.asmx'
        assert 'server' not in call_kwargs
