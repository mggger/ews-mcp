"""Custom NTLM adapter using pyspnego for cross-platform compatibility."""

import base64
import spnego
from requests.adapters import HTTPAdapter
from requests.auth import AuthBase
import logging

logger = logging.getLogger(__name__)


class PySpnegoNtlmAuth(AuthBase):
    """NTLM authentication using pyspnego for cross-platform compatibility.
    
    This implementation mimics requests-ntlm but uses pyspnego which has
    pure Python MD4 implementation, avoiding OpenSSL 3.x MD4 deprecation issues
    on macOS and providing more reliable NTLM authentication in Docker containers.
    """
    
    def __init__(self, username, password):
        self.username = username
        self.password = password
        
    def __call__(self, r):
        # Add response hook to handle NTLM authentication
        r.register_hook('response', self.response_hook)
        return r
    
    def response_hook(self, r, **kwargs):
        """Handle NTLM authentication on 401 responses."""
        if r.status_code != 401:
            return r
        
        # Check if server supports NTLM
        www_authenticate = r.headers.get('WWW-Authenticate', '')
        if 'NTLM' not in www_authenticate and 'Negotiate' not in www_authenticate:
            return r
        
        # Perform NTLM handshake
        return self.retry_with_ntlm_auth(r, kwargs)
    
    def retry_with_ntlm_auth(self, response, args):
        """Perform the NTLM authentication handshake."""
        # Create NTLM context
        context = spnego.client(
            self.username,
            self.password,
            hostname=response.url,
            service='HTTP',
            protocol='ntlm'
        )
        
        # Consume original response
        response.content
        response.raw.release_conn()
        
        # Step 1: Send negotiate message
        negotiate_token = context.step()
        request = response.request.copy()
        request.headers['Authorization'] = f'NTLM {base64.b64encode(negotiate_token).decode()}'
        
        # Send negotiate request
        response2 = response.connection.send(request, **args)
        response2.history.append(response)
        
        # Step 2: Handle challenge and send authenticate message
        if response2.status_code == 401:
            www_authenticate = response2.headers.get('WWW-Authenticate', '')
            if www_authenticate.startswith(('NTLM ', 'Negotiate ')):
                # Extract challenge token
                auth_type, challenge_b64 = www_authenticate.split(' ', 1)
                challenge_token = base64.b64decode(challenge_b64)
                
                # Generate authenticate message
                auth_token = context.step(challenge_token)
                
                # Consume challenge response
                response2.content
                response2.raw.release_conn()
                
                # Send authenticate request
                request2 = response2.request.copy()
                request2.headers['Authorization'] = f'NTLM {base64.b64encode(auth_token).decode()}'
                
                response3 = response2.connection.send(request2, **args)
                response3.history.append(response2)
                
                return response3
        
        return response2


class PySpnegoHTTPAdapter(HTTPAdapter):
    """HTTP Adapter that disables SSL verification for internal Exchange servers."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
    def init_poolmanager(self, *args, **kwargs):
        kwargs['assert_hostname'] = False
        kwargs['cert_reqs'] = 'CERT_NONE'
        return super().init_poolmanager(*args, **kwargs)
