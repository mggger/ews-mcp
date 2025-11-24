"""多账户管理器 - 支持通过API key选择不同的EWS账户"""

import json
import logging
from pathlib import Path
from typing import Dict, Optional, List
from dataclasses import dataclass


@dataclass
class AccountConfig:
    """单个账户配置"""
    api_key: str
    name: str
    ews_email: str
    ews_server_url: Optional[str]
    ews_autodiscover: bool
    ews_auth_type: str
    ews_username: Optional[str] = None
    ews_password: Optional[str] = None
    ews_client_id: Optional[str] = None
    ews_client_secret: Optional[str] = None
    ews_tenant_id: Optional[str] = None
    timezone: str = "UTC"

    @classmethod
    def from_dict(cls, data: dict) -> 'AccountConfig':
        """从字典创建账户配置"""
        return cls(
            api_key=data['api_key'],
            name=data['name'],
            ews_email=data['ews_email'],
            ews_server_url=data.get('ews_server_url'),
            ews_autodiscover=data.get('ews_autodiscover', True),
            ews_auth_type=data['ews_auth_type'],
            ews_username=data.get('ews_username'),
            ews_password=data.get('ews_password'),
            ews_client_id=data.get('ews_client_id'),
            ews_client_secret=data.get('ews_client_secret'),
            ews_tenant_id=data.get('ews_tenant_id'),
            timezone=data.get('timezone', 'UTC')
        )


class AccountManager:
    """管理多个EWS账户配置"""

    def __init__(self, config_file: str = "accounts.json"):
        self.logger = logging.getLogger(__name__)
        self.config_file = Path(config_file)
        self.accounts: Dict[str, AccountConfig] = {}
        self._load_accounts()

    def _load_accounts(self):
        """从配置文件加载账户"""
        if not self.config_file.exists():
            self.logger.warning(f"账户配置文件不存在: {self.config_file}")
            self.logger.info("将使用环境变量中的默认配置")
            return

        try:
            self.logger.info(f"正在从配置文件加载账户: {self.config_file.absolute()}")
            with open(self.config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            accounts_data = data.get('accounts', [])
            self.logger.info(f"配置文件中找到 {len(accounts_data)} 个账户定义")
            
            for account_data in accounts_data:
                account = AccountConfig.from_dict(account_data)
                self.accounts[account.api_key] = account
                self.logger.info(f"加载账户: {account.name} ({account.ews_email})")

            self.logger.info(f"成功加载 {len(self.accounts)} 个账户配置")

        except Exception as e:
            self.logger.error(f"加载账户配置失败: {e}")
            raise

    def get_account(self, api_key: str) -> Optional[AccountConfig]:
        """根据API key获取账户配置"""
        account = self.accounts.get(api_key)
        if account:
            self.logger.info(f"使用账户: {account.name} ({account.ews_email})")
        else:
            self.logger.warning(f"未找到API key对应的账户: {api_key}")
        return account

    def list_accounts(self) -> List[Dict[str, str]]:
        """列出所有账户（不包含敏感信息）"""
        return [
            {
                "api_key": account.api_key,
                "name": account.name,
                "email": account.ews_email,
                "auth_type": account.ews_auth_type
            }
            for account in self.accounts.values()
        ]

    def has_accounts(self) -> bool:
        """检查是否有配置的账户"""
        return len(self.accounts) > 0
