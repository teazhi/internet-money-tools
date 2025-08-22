"""
Application Configuration Module

Centralized configuration for different environments
"""

import os
from datetime import timedelta


class Config:
    """Base configuration class"""
    # Basic Flask config
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'development-key-change-in-production')
    
    # Session config
    SESSION_TYPE = 'filesystem'
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Database
    DATABASE_PATH = os.getenv('DATABASE_PATH', 'dashboard.db')
    DATABASE_BACKUP_PATH = 'dashboard_backup.db'
    
    # AWS S3
    AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
    AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')
    CONFIG_S3_BUCKET = os.getenv('CONFIG_S3_BUCKET', 'internet-money-tools-config')
    
    # Discord OAuth
    DISCORD_CLIENT_ID = os.getenv('DISCORD_CLIENT_ID')
    DISCORD_CLIENT_SECRET = os.getenv('DISCORD_CLIENT_SECRET')
    DISCORD_REDIRECT_URI = os.getenv('DISCORD_REDIRECT_URI')
    DISCORD_GUILD_ID = os.getenv('DISCORD_GUILD_ID')
    DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
    
    # Google OAuth
    GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
    
    # External APIs
    KEEPA_API_KEY = os.getenv('KEEPA_API_KEY')
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    
    # Application settings
    DEMO_MODE = os.getenv('DEMO_MODE', 'false').lower() == 'true'
    FORCE_UPDATE_MODE = os.getenv('FORCE_UPDATE_MODE', 'false').lower() == 'true'
    
    # Cache settings
    IMAGE_CACHE_EXPIRY_HOURS = 24
    ANALYTICS_CACHE_HOURS = 2
    
    # Email settings
    EMAIL_MONITOR_ADDRESS = os.getenv('DISCOUNT_MONITOR_EMAIL')
    EMAIL_SENDER_ADDRESS = os.getenv('DISCOUNT_SENDER_EMAIL')
    
    # Encryption
    ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY')
    if not ENCRYPTION_KEY:
        # Generate a key for development, but require it for production
        ENCRYPTION_KEY = 'development-encryption-key-32chr'


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False
    SESSION_COOKIE_SECURE = False  # Allow HTTP in development


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False
    
    # Require certain environment variables in production
    @classmethod
    def init_app(cls, app):
        # Verify required environment variables
        required_vars = [
            'FLASK_SECRET_KEY',
            'ENCRYPTION_KEY',
            'DISCORD_CLIENT_ID',
            'DISCORD_CLIENT_SECRET'
        ]
        
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            raise RuntimeError(f"Missing required environment variables: {', '.join(missing_vars)}")


class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    DATABASE_PATH = ':memory:'
    WTF_CSRF_ENABLED = False


# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}