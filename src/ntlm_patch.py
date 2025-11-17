"""NTLM authentication patch using pyspnego - must be imported before exchangelib."""

import platform
import sys

# Apply patch on all platforms for consistent NTLM behavior
# This fixes issues with both macOS OpenSSL 3.x and Docker containers
from .ntlm_adapter import PySpnegoNtlmAuth
from unittest.mock import MagicMock

# Create mock module
mock_ntlm = MagicMock()
mock_ntlm.HttpNtlmAuth = PySpnegoNtlmAuth

# Replace in sys.modules
sys.modules['requests_ntlm'] = mock_ntlm

print(f"✓ NTLM patch applied (using pyspnego on {platform.system()})")
