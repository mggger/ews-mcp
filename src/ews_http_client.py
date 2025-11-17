"""Direct HTTP-based EWS client using pyspnego for NTLM authentication."""

import requests
import spnego
import base64
import urllib3
import logging
from typing import Optional
from xml.etree import ElementTree as ET

from .config import Settings
from .exceptions import ConnectionError, AuthenticationError

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class EWSHttpClient:
    """EWS client using direct HTTP requests with pyspnego NTLM authentication."""
    
    def __init__(self, config: Settings):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.session = requests.Session()
        self.session.verify = False
        
        # Create NTLM context
        self.ntlm_context = spnego.client(
            config.ews_username,
            config.ews_password,
            hostname=config.ews_server_url,
            service='HTTP',
            protocol='ntlm'
        )
        
    def _ntlm_auth_request(self, url: str, data: str, headers: dict) -> requests.Response:
        """Perform NTLM authenticated request."""
        # Step 1: Initial request to get 401
        response1 = self.session.post(url, data=data, headers=headers, verify=False)
        
        if response1.status_code == 401:
            # Step 2: Send NTLM negotiate message
            negotiate_token = self.ntlm_context.step()
            headers_with_auth = headers.copy()
            headers_with_auth['Authorization'] = f'NTLM {base64.b64encode(negotiate_token).decode()}'
            
            response2 = self.session.post(url, data=data, headers=headers_with_auth, verify=False)
            
            if response2.status_code == 401:
                # Step 3: Handle challenge and send authenticate message
                www_authenticate = response2.headers.get('WWW-Authenticate', '')
                if www_authenticate.startswith('NTLM '):
                    challenge_token = base64.b64decode(www_authenticate[5:])
                    
                    # Reset context for new authentication
                    self.ntlm_context = spnego.client(
                        self.config.ews_username,
                        self.config.ews_password,
                        hostname=self.config.ews_server_url,
                        service='HTTP',
                        protocol='ntlm'
                    )
                    # Re-do negotiate
                    negotiate_token = self.ntlm_context.step()
                    auth_token = self.ntlm_context.step(challenge_token)
                    
                    headers_with_auth['Authorization'] = f'NTLM {base64.b64encode(auth_token).decode()}'
                    
                    response3 = self.session.post(url, data=data, headers=headers_with_auth, verify=False)
                    return response3
            
            return response2
        
        return response1
    
    def test_connection(self) -> bool:
        """Test EWS connection by getting inbox folder."""
        try:
            soap_body = '''<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" 
               xmlns:t="http://schemas.microsoft.com/exchange/services/2006/types">
  <soap:Body>
    <GetFolder xmlns="http://schemas.microsoft.com/exchange/services/2006/messages">
      <FolderShape>
        <t:BaseShape>Default</t:BaseShape>
      </FolderShape>
      <FolderIds>
        <t:DistinguishedFolderId Id="inbox"/>
      </FolderIds>
    </GetFolder>
  </soap:Body>
</soap:Envelope>'''
            
            headers = {
                'Content-Type': 'text/xml; charset=utf-8',
            }
            
            response = self._ntlm_auth_request(
                self.config.ews_server_url,
                soap_body,
                headers
            )
            
            if response.status_code == 200:
                self.logger.info("✓ Successfully connected to Exchange")
                # Parse response to get inbox count
                if '<t:TotalCount>' in response.text:
                    import re
                    match = re.search(r'<t:TotalCount>(\d+)</t:TotalCount>', response.text)
                    if match:
                        self.logger.info(f"✓ Inbox count: {match.group(1)}")
                return True
            else:
                self.logger.error(f"Connection test failed with status {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"Connection test failed: {e}")
            return False
    
    def close(self) -> None:
        """Close session."""
        self.session.close()
