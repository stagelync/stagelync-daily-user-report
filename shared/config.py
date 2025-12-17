"""
Configuration loader for StageLync Reports.
Loads from .env file locally or Secret Manager in production.
"""

import os
from functools import lru_cache


def load_env_file(env_path: str = None) -> None:
    """Load environment variables from .env file."""
    if env_path is None:
        # Look for .env in project root
        current_dir = os.path.dirname(os.path.abspath(__file__))
        env_path = os.path.join(current_dir, '..', '.env')
    
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    # Remove quotes from value
                    value = value.strip().strip('"').strip("'")
                    os.environ.setdefault(key.strip(), value)


def is_cloud_environment() -> bool:
    """Check if running in Google Cloud."""
    return os.getenv('K_SERVICE') is not None or os.getenv('CLOUD_RUN_JOB') is not None


@lru_cache(maxsize=32)
def get_secret(secret_id: str) -> str:
    """
    Get secret from Secret Manager (production) or environment (local).
    Results are cached to minimize API calls.
    """
    # First check environment variable
    env_value = os.getenv(secret_id.upper().replace('-', '_'))
    if env_value:
        return env_value
    
    # In cloud, try Secret Manager
    if is_cloud_environment():
        try:
            from google.cloud import secretmanager
            project_id = os.getenv('GCP_PROJECT_ID', 'stagelync-daily-user-reports')
            client = secretmanager.SecretManagerServiceClient()
            name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
            response = client.access_secret_version(request={"name": name})
            return response.payload.data.decode("UTF-8")
        except Exception as e:
            raise ValueError(f"Failed to get secret '{secret_id}': {e}")
    
    raise ValueError(f"Secret '{secret_id}' not found in environment")


class Config:
    """Configuration container with lazy loading."""
    
    def __init__(self):
        # Try to load .env file
        load_env_file()
    
    # GCP
    @property
    def gcp_project_id(self) -> str:
        return os.getenv('GCP_PROJECT_ID', 'stagelync-daily-user-reports')
    
    @property
    def gcp_region(self) -> str:
        return os.getenv('GCP_REGION', 'asia-northeast1')
    
    # MySQL
    @property
    def mysql_host(self) -> str:
        return os.getenv('MYSQL_HOST') or get_secret('mysql-host')
    
    @property
    def mysql_port(self) -> int:
        return int(os.getenv('MYSQL_PORT', '3306'))
    
    @property
    def mysql_user(self) -> str:
        return os.getenv('MYSQL_USER') or get_secret('mysql-user')
    
    @property
    def mysql_password(self) -> str:
        return os.getenv('MYSQL_PASSWORD') or get_secret('mysql-password')
    
    @property
    def mysql_database(self) -> str:
        return os.getenv('MYSQL_DATABASE') or get_secret('mysql-database')
    
    # SMTP
    @property
    def smtp_host(self) -> str:
        return os.getenv('SMTP_HOST', 'smtp.gmail.com')
    
    @property
    def smtp_port(self) -> int:
        return int(os.getenv('SMTP_PORT', '587'))
    
    @property
    def smtp_user(self) -> str:
        return os.getenv('SMTP_USER') or get_secret('smtp-user')
    
    @property
    def smtp_password(self) -> str:
        return os.getenv('SMTP_PASSWORD') or get_secret('smtp-password')
    
    @property
    def email_to(self) -> str:
        return os.getenv('EMAIL_TO', 'laci@stagelync.com')
    
    # Sheets
    @property
    def sheet_new_users(self) -> str:
        return os.getenv('SHEET_NEW_USERS', 'StageLync - New Users Report')
    
    @property
    def sheet_subscriptions(self) -> str:
        return os.getenv('SHEET_SUBSCRIPTIONS', 'StageLync - Subscriptions Report')
    
    # Logging
    @property
    def log_level(self) -> str:
        return os.getenv('LOG_LEVEL', 'INFO')


# Global config instance
config = Config()
