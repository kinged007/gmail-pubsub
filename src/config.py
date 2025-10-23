"""Configuration management for Gmail Pub/Sub project."""

import os
import subprocess
import yaml
import inspect
from typing import Dict, Any, Optional
from pathlib import Path
import dotenv
from src.utils.logger import setup_logger

# Set up logging
logger = setup_logger(__name__)

def _is_called_from_scripts() -> bool:
    """Check if this module is being imported from the scripts folder."""
    frame = inspect.currentframe()
    try:
        # Walk up the call stack to find the original caller
        while frame:
            frame = frame.f_back
            if frame and frame.f_code.co_filename:
                filename = frame.f_code.co_filename
                path_parts = Path(filename).parts
                # Check if the caller is from the scripts folder
                if 'scripts' in path_parts:
                    logger.debug(f"Found scripts in call stack: {filename}")
                    return True
                logger.debug(f"Checking frame: {filename}")
        logger.debug("No scripts found in call stack")
        return False
    finally:
        del frame

env_var_map = {
    # Google Cloud Configuration
    "gcloud.project_id": "GOOGLE_CLOUD_PROJECT",
    "gcloud.region": "GOOGLE_CLOUD_REGION",

    # Cloud Run Configuration
    "cloudrun.service_name": "CLOUD_RUN_SERVICE_NAME",
    "cloudrun.url": "CLOUD_RUN_URL",

    # Pub/Sub Configuration
    "pubsub.topic_name": "PUBSUB_TOPIC_NAME",
    "pubsub.subscription_name": "PUBSUB_SUBSCRIPTION_NAME",

    # IAM & Service Account Configuration
    "iam.service_account_name": "SERVICE_ACCOUNT_NAME",
    "service_account.json": "GOOGLE_SERVICE_ACCOUNT_JSON",

    # Google Workspace Configuration (for domain delegation)
    "workspace.domain": "WORKSPACE_DOMAIN",
    "workspace.delegated_user_email": "DELEGATED_USER_EMAIL",

    # OAuth Configuration (for personal Gmail)
    "oauth.token_path": "GMAIL_OAUTH_TOKEN_PATH",
    "oauth.token_json": "GMAIL_OAUTH_TOKEN_JSON",
    "oauth.client_secret_json": "GMAIL_CLIENT_SECRET_JSON",

    # Gmail Account Type Configuration
    "gmail.account_type": "GMAIL_ACCOUNT_TYPE",

    # Gmail Watch Configuration
    "gmail.watch_labels": "GMAIL_WATCH_LABELS",
    "gmail.watch_label_ids": "GMAIL_WATCH_LABEL_IDS",

    # API Security
    "api.access_token": "API_ACCESS_TOKEN",

    # Database Configuration
    # "database.url": "DATABASE_URL",

    # Application Configuration
    # "app.log_level": "LOG_LEVEL",
    # "app.port": "PORT"
}

class Config:
    """Manages configuration with YAML file persistence and user prompts."""

    def __init__(self, config_file: str = "./config.yaml", auto_load: bool = None):
        self.config_file = Path(config_file)
        self.config: Dict[str, Any] = {}
        self.env_file = Path(".env")

        # Auto-detect if we should load config based on caller context
        if auto_load is None:
            auto_load = _is_called_from_scripts()

        if auto_load:
            self.load_config()
            logger.info("Config auto-loading enabled (called from scripts)")
        else:
            logger.info("Config auto-loading disabled (not called from scripts)")

        self.load_env_file()
        self.run_command = None
    
    def load_run_command(self, method: callable = None) -> None:
        """Load run_command method."""
        if method:
            self.run_command = method
    
    def load_config(self) -> None:
        """Load configuration from YAML file if it exists."""
        if self.config_file.exists():
            with open(self.config_file, 'r') as f:
                self.config = yaml.safe_load(f) or {}
                logger.info(f"Loaded configuration from {self.config_file}")

    def load_env_file(self) -> None:
        """Load environment variables from .env file if it exists."""
        if self.env_file.exists():
            dotenv.load_dotenv(self.env_file, override=True)
    
    def save_config(self) -> None:
        """Save current configuration to YAML file."""
        with open(self.config_file, 'w') as f:
            yaml.dump(self.config, f, default_flow_style=False, indent=2)
    
    def get(self, key: str, prompt: str = None, default: str = None, cmd:str = None, yaml_only:bool = False) -> str:
        """
        Get configuration value. If not exists, prompt user and save.
        
        Args:
            key: Configuration key (supports dot notation like 'gcloud.project_id')
            prompt: User prompt message
            default: Default value if user provides empty input
            
        Returns:
            Configuration value
        """
        global env_var_map

        # Navigate nested keys
        keys = key.split('.')
        current = self.config
        # print(current) # Debug
        # Check if value exists
        for k in keys[:-1]:
            if k not in current or not current[k]:
                current[k] = {}
            current = current[k]
        
        if keys[-1] in current and current[keys[-1]]:
            return current[keys[-1]]

        # Check for environment variable first
        env_var_name = env_var_map.get(key)
        if env_var_name and os.getenv(env_var_name) and not yaml_only:
            value = os.getenv(env_var_name)
            current[keys[-1]] = value
            self.save_config()
            return value

        if not yaml_only:
            # Attempt to get it from env. 
            if env_var_name and os.getenv(env_var_name):
                value = os.getenv(env_var_name)
                # current[keys[-1]] = value
                # self.save_config()
                return value
        
        # Value doesn't exist, prompt user
        if prompt:
            if cmd and self.run_command:
                output = self.run_command(cmd, False)
                # print(output) # debug
                if output and output.stdout:
                    print(output.stdout)
            value = input(f"{prompt}: ").strip()
            if not value and default:
                value = default
            
            # Save the value
            current[keys[-1]] = value
            self.save_config()
            return value
        
        return default or ""
    
    def set(self, key: str, value: str) -> None:
        """Set configuration value and save."""
        keys = key.split('.')
        current = self.config
        
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]
        
        current[keys[-1]] = value
        self.save_config()
    
    def get_project_id(self, yaml_only:bool = False) -> str:
        """Get Google Cloud project ID."""
        return self.get(
            'gcloud.project_id',
            'Enter your Google Cloud Project ID',
            None,
            'gcloud projects list --format="table(name, project_id, createTime.date(tz=LOCAL))"',
            yaml_only=yaml_only
        )
    
    def get_region(self, yaml_only:bool = False) -> str:
        """Get Google Cloud region."""
        # print("-> Available Regions: https://cloud.google.com/about/locations ")
        return self.get(
            'gcloud.region',
            'Enter your preferred Google Cloud region',
            'us-central1',
            'gcloud run regions list',
            yaml_only=yaml_only
        )
    
    def get_topic_name(self, yaml_only:bool = False) -> str:
        """Get Pub/Sub topic name (base name for all other resources)."""
        return self.get(
            'pubsub.topic_name',
            'Enter topic name (will be used for all resource names)',
            'gmail-incoming',
            yaml_only=yaml_only
        )

    def get_service_name(self, yaml_only:bool = False) -> str:
        """Get Cloud Run service name (derived from topic name)."""
        topic_name = self.get_topic_name(yaml_only=yaml_only)

        # Check if we already have a custom service name set
        existing_service_name = None
        if 'cloudrun' in self.config and 'service_name' in self.config['cloudrun']:
            existing_service_name = self.config['cloudrun']['service_name']

        # If no existing service name or it matches the old pattern, derive from topic
        if not existing_service_name or existing_service_name in ['gmail-push-api', f'{topic_name}']:
            derived_name = topic_name
            self.set('cloudrun.service_name', derived_name)
            return derived_name

        return existing_service_name

    def get_subscription_name(self, yaml_only:bool = False) -> str:
        """Get Pub/Sub subscription name (derived from topic name)."""
        topic_name = self.get_topic_name(yaml_only=yaml_only)

        # Check if we already have a custom subscription name set
        existing_subscription_name = None
        if 'pubsub' in self.config and 'subscription_name' in self.config['pubsub']:
            existing_subscription_name = self.config['pubsub']['subscription_name']

        # If no existing subscription name or it matches the old pattern, derive from topic
        if not existing_subscription_name or existing_subscription_name in ['gmail-incoming-sub', f'{topic_name}-sub']:
            derived_name = f'{topic_name}-sub'
            self.set('pubsub.subscription_name', derived_name)
            return derived_name

        return existing_subscription_name

    def get_service_account_name(self, yaml_only:bool = False) -> str:
        """Get service account name (derived from topic name)."""
        topic_name = self.get_topic_name(yaml_only=yaml_only)

        # Check if we already have a custom service account name set
        existing_sa_name = None
        if 'iam' in self.config and 'service_account_name' in self.config['iam']:
            existing_sa_name = self.config['iam']['service_account_name']

        # If no existing service account name or it matches the old pattern, derive from topic
        if not existing_sa_name or existing_sa_name in ['gmail-processor', f'{topic_name}']:
            derived_name = f'{topic_name}'
            self.set('iam.service_account_name', derived_name)
            return derived_name

        return existing_sa_name
    
    def get_service_account_email(self, yaml_only:bool = False) -> str:
        """Get full service account email."""
        sa_name = self.get_service_account_name(yaml_only)
        project_id = self.get_project_id(yaml_only)
        return f"{sa_name}@{project_id}.iam.gserviceaccount.com"

    def get_workspace_domain(self, yaml_only:bool = False) -> str:
        """Get Google Workspace domain for delegation (optional)."""
        return self.get(
            'workspace.domain',
            'Enter your Google Workspace domain (optional, press Enter if using personal Gmail)',
            '',
            yaml_only=yaml_only
        )

    def get_delegated_user_email(self, yaml_only:bool = False) -> str:
        """Get Gmail address to delegate access to (required for Workspace)."""
        return self.get(
            'workspace.delegated_user_email',
            'Enter the Gmail address to delegate access to (e.g., user@yourdomain.com)',
            '',
            yaml_only=yaml_only
        )

    def is_workspace_delegation_enabled(self) -> bool:
        """Check if workspace delegation is configured."""
        domain = self.get('workspace.domain')
        user_email = self.get('workspace.delegated_user_email')
        return bool(domain and user_email)

    def get_oauth_token_path(self, yaml_only:bool = False) -> str:
        """Get OAuth token file path."""
        return self.get(
            'oauth.token_path',
            'Enter path to OAuth token.json file',
            'token.json',
            yaml_only=yaml_only
        )

    def is_oauth_enabled(self) -> bool:
        """Check if OAuth authentication is configured."""
        # Only check environment variable for token JSON string (no file fallback)
        token_json = os.getenv('GMAIL_OAUTH_TOKEN_JSON')
        return bool(token_json)

    def get_gmail_account_type(self) -> str:
        """Determine Gmail account type based on configuration."""
        # Check environment variable first (most reliable)
        account_type = self.get(
            'gmail.account_type',
            default=None,
        )
        if account_type:
            return account_type
        
        # Fallback to detection logic
        if self.is_workspace_delegation_enabled():
            return "workspace"
        elif self.is_oauth_enabled():
            return "oauth"
        else:
            return "service_account"
    
    def get_cloud_run_url(self) -> Optional[str]:
        """Get Cloud Run service URL if available."""
        return self.config.get('cloudrun', {}).get('url')
    
    def set_cloud_run_url(self, url: str) -> None:
        """Set Cloud Run service URL."""
        self.set('cloudrun.url', url)
        
    def get_gmail_watch_labels(self, yaml_only:bool = False) -> list:
        """Get Gmail labels to watch for incoming emails."""
        gmail_labels_env = os.environ.get('GMAIL_WATCH_LABELS', 'INBOX')
        # Split by comma and strip whitespace
        gmail_labels = [label.strip() for label in gmail_labels_env.split(',') if label.strip()]

        return gmail_labels

    def get_gmail_watch_label_ids(self) -> list:
        """Get Gmail label IDs to watch for incoming emails."""
        label_ids_env = os.environ.get('GMAIL_WATCH_LABEL_IDS', '')
        if not label_ids_env:
            return []
        # Split by comma and strip whitespace
        label_ids = [label_id.strip() for label_id in label_ids_env.split(',') if label_id.strip()]
        return label_ids

    def set_gmail_watch_label_ids(self, label_ids: list) -> None:
        """Set Gmail label IDs environment variable."""
        label_ids_str = ','.join(label_ids)
        # Update .env file
        self._update_env_file('GMAIL_WATCH_LABEL_IDS', label_ids_str)

    def _update_env_file(self, key: str, value: str) -> None:
        """Update or add a key-value pair in the .env file."""
        env_file = Path('.env')
        lines = []
        key_found = False

        if env_file.exists():
            with open(env_file, 'r') as f:
                lines = f.readlines()

        # Update existing key or mark for addition
        for i, line in enumerate(lines):
            if line.strip().startswith(f'{key}='):
                lines[i] = f'{key}={value}\n'
                key_found = True
                break

        # Add new key if not found
        if not key_found:
            lines.append(f'{key}={value}\n')

        # Write back to file
        with open(env_file, 'w') as f:
            f.writelines(lines)


# Global config instance
config = Config()
