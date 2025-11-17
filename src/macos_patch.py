"""macOS NTLM authentication patch - must be imported before exchangelib."""

import platform
import sys

# Only patch on macOS
if platform.system() == 'Darwin':
    # Patch requests_ntlm BEFORE any other imports
    from .ntlm_adapter import PySpnegoNtlmAuth
    from unittest.mock import MagicMock
    
    # Create mock module
    mock_ntlm = MagicMock()
    mock_ntlm.HttpNtlmAuth = PySpnegoNtlmAuth
    
    # Replace in sys.modules
    sys.modules['requests_ntlm'] = mock_ntlm
    
    print("✓ macOS NTLM patch applied (using pyspnego)")
