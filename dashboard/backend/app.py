from flask import Flask, request, jsonify, session, redirect, url_for, send_from_directory, make_response
from flask_cors import CORS
from typing import Optional, Dict, List
import os
import json
import requests
import boto3
from botocore.exceptions import ClientError
from datetime import datetime, timedelta, date
import pytz
import uuid
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import pandas as pd
from io import StringIO, BytesIO
import sqlite3
from functools import wraps
import urllib.parse
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
import base64
import secrets
from cryptography.fernet import Fernet
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from inventory_age_analysis import InventoryAgeAnalyzer
import atexit
from email_monitor import EmailMonitor, CHECK_INTERVAL
from email_monitor_s3_general import EmailMonitorS3
from email_monitoring_s3 import email_monitoring_manager

def sanitize_for_json(obj):
    """
    Recursively sanitize a data structure to ensure all values are JSON-serializable.
    This prevents issues with pandas/numpy types that can cause unexpected serialization behavior.
    """
    import pandas as pd
    import numpy as np
    from datetime import datetime, date
    
    # Handle pandas NA/null values first (works with all pandas versions)
    try:
        if pd.isna(obj):
            return None
    except:
        # If pd.isna fails, try alternative null checks
        if obj is None or (hasattr(obj, '__class__') and obj.__class__.__name__ == 'NaTType'):
            return None
        if str(obj) == '<NA>' or str(obj) == 'NaT' or str(obj) == 'nan':
            return None
    
    if isinstance(obj, dict):
        return {key: sanitize_for_json(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_for_json(item) for item in obj]
    elif isinstance(obj, tuple):
        return [sanitize_for_json(item) for item in obj]
    elif isinstance(obj, (pd.DataFrame, pd.Series)):
        raise ValueError(f"Found pandas object in response data: {type(obj)}. This should not be serialized.")
    elif hasattr(obj, 'item'):  # numpy scalar types
        return obj.item()
    elif hasattr(obj, 'to_pydatetime'):  # pandas timestamp
        return obj.to_pydatetime().isoformat()
    elif isinstance(obj, (datetime, date)):
        return obj.isoformat()
    elif str(type(obj)).startswith('<class \'pandas.'):
        # Handle pandas-specific types including NA
        if str(obj) == '<NA>':
            return None
        return str(obj)
    elif str(type(obj)).startswith('<class \'numpy.'):
        # Handle numpy types
        if hasattr(obj, 'item'):
            return obj.item()
        else:
            return str(obj)
    elif isinstance(obj, (int, float, str, bool)) or obj is None:
        return obj
    else:
        # Fallback for any other type
        return str(obj)

# Load environment variables
try:
    load_dotenv()
    pass  # Environment variables loaded
except Exception as e:
    pass  # Failed to load .env file

# Demo mode flag - set to True to use dummy data for demos
DEMO_MODE = os.getenv('DEMO_MODE', 'false').lower() == 'true'

# Simple in-memory cache for analytics data (expires after 24 hours for daily use)
analytics_cache = {}
CACHE_EXPIRY_HOURS = 24

# In-memory cache for S3 config data to reduce repeated reads
config_cache = {}
CONFIG_CACHE_EXPIRY_MINUTES = 30  # Cache configs for 30 minutes

# Session-based user config cache to reduce S3 fetches during user sessions
user_session_cache = {}
USER_SESSION_CACHE_EXPIRY_MINUTES = 15  # Cache user config for 15 minutes per session

# Cache for file listings to reduce S3 list operations
file_listing_cache = {}
FILE_LISTING_CACHE_EXPIRY_MINUTES = 15  # Cache file listings for 15 minutes

def get_cached_user_config(user_id):
    """Get user config from session cache if available"""
    if not user_id:
        return None
    
    cache_key = f"user_{user_id}"
    if cache_key in user_session_cache:
        cached_data, cached_time = user_session_cache[cache_key]
        if (datetime.now() - cached_time).total_seconds() < USER_SESSION_CACHE_EXPIRY_MINUTES * 60:
            return cached_data
    return None

def cache_user_config(user_id, user_data):
    """Cache user config in session cache"""
    if user_id and user_data:
        cache_key = f"user_{user_id}"
        user_session_cache[cache_key] = (user_data, datetime.now())

def invalidate_user_cache(user_id):
    """Invalidate cached user config when user data changes"""
    if user_id:
        cache_key = f"user_{user_id}"
        if cache_key in user_session_cache:
            del user_session_cache[cache_key]

def get_cached_s3_list(bucket, prefix=""):
    """Get S3 object list with caching to reduce list_objects calls"""
    cache_key = f"s3_list_{bucket}_{prefix}"
    
    if cache_key in file_listing_cache:
        cached_data, cached_time = file_listing_cache[cache_key]
        if (datetime.now() - cached_time).total_seconds() < FILE_LISTING_CACHE_EXPIRY_MINUTES * 60:
            return cached_data
    
    try:
        s3_client = get_s3_client()
        if prefix:
            response = s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)
        else:
            response = s3_client.list_objects_v2(Bucket=bucket)
        
        objects = response.get('Contents', [])
        file_listing_cache[cache_key] = (objects, datetime.now())
        return objects
    except Exception as e:
        return []

def invalidate_file_listing_cache(bucket, prefix=""):
    """Invalidate file listing cache when files are added/removed"""
    cache_key = f"s3_list_{bucket}_{prefix}"
    if cache_key in file_listing_cache:
        del file_listing_cache[cache_key]

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'development-key-change-in-production')

# Initialize encryption key for email credentials
ENCRYPTION_KEY = os.getenv('EMAIL_ENCRYPTION_KEY')
if not ENCRYPTION_KEY:
    ENCRYPTION_KEY = Fernet.generate_key()
    print("⚠️  Warning: Using auto-generated encryption key. Set EMAIL_ENCRYPTION_KEY environment variable for production.")

email_cipher = Fernet(ENCRYPTION_KEY)

# Flask app initialized

# Start Email Monitoring Service in Background
email_monitor_thread = None
email_monitor_instance = None

def start_email_monitoring():
    """Start the refund email monitoring service in a background thread"""
    global email_monitor_thread, email_monitor_instance
    
    try:
        print("🚀 Starting Email Monitoring Service in background...")
        email_monitor_instance = EmailMonitorS3()
        
        # Create and start the background thread
        email_monitor_thread = threading.Thread(target=email_monitor_instance.start, daemon=True)
        email_monitor_thread.start()
        print("✅ Email Monitoring Service started successfully")
    except Exception as e:
        print(f"❌ Failed to start Email Monitoring Service: {e}")

def stop_email_monitoring():
    """Stop the email monitoring service"""
    global email_monitor_instance
    
    if email_monitor_instance:
        print("🛑 Stopping Email Monitoring Service...")
        email_monitor_instance.stop()

# Register cleanup function
atexit.register(stop_email_monitoring)

# Start email monitoring when app starts
start_email_monitoring()

# Configure session for cookies to work properly with cross-domain
app.config['SESSION_COOKIE_SECURE'] = True  # Required for HTTPS cross-domain
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'None'  # Required for cross-domain
app.config['SESSION_COOKIE_DOMAIN'] = None  # Allow cross-domain

# Configure file uploads
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = '/tmp'

# CORS configuration for development and production
allowed_origins = [
    "http://localhost:3000",
    "https://dms-amazon.vercel.app",  # Add Vercel frontend
    "https://internet-money-tools-git-main-teazhis-projects.vercel.app",  # Vercel preview URLs
    "https://internet-money-tools-dfqzt1xy0-teazhis-projects.vercel.app"  # Vercel deployment URLs
]
if os.environ.get('FRONTEND_URL'):
    allowed_origins.append(os.environ.get('FRONTEND_URL'))
if os.environ.get('RAILWAY_STATIC_URL'):
    allowed_origins.append(f"https://{os.environ.get('RAILWAY_STATIC_URL')}")

# Database setup
DATABASE_FILE = 'app_data.db'
conn = sqlite3.connect(DATABASE_FILE, check_same_thread=False)
conn.execute('PRAGMA journal_mode=WAL')
conn.execute('PRAGMA synchronous=NORMAL')
cursor = conn.cursor()

try:
    CORS(app, supports_credentials=True, origins=allowed_origins)
    pass  # CORS configured
except Exception as e:
    pass  # CORS configuration failed
    # Try basic CORS as fallback
    CORS(app)

# Discord OAuth Configuration
DISCORD_CLIENT_ID = os.getenv('DISCORD_CLIENT_ID')
DISCORD_CLIENT_SECRET = os.getenv('DISCORD_CLIENT_SECRET')
# Dynamic Discord redirect URI for development and production
# Force production Railway URL since we know it
default_redirect = 'https://internet-money-tools-production.up.railway.app/auth/discord/callback'
    
DISCORD_REDIRECT_URI = os.getenv('DISCORD_REDIRECT_URI', default_redirect)

# AWS Configuration
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
CONFIG_S3_BUCKET = os.getenv("CONFIG_S3_BUCKET")
USERS_CONFIG_KEY = "users.json"
INVITATIONS_CONFIG_KEY = "invitations.json"
DISCOUNT_MONITORING_CONFIG_KEY = "discount_monitoring.json"
PURCHASES_CONFIG_KEY = "purchases.json"

# Email Configuration (for invitations)
SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
SMTP_EMAIL = os.getenv('SMTP_EMAIL')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')

# Alternative HTTP-based email service (Resend)
RESEND_API_KEY = os.getenv('RESEND_API_KEY')
RESEND_FROM_DOMAIN = os.getenv('RESEND_FROM_DOMAIN', 'onboarding@resend.dev')

# Google OAuth Configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")

# Amazon SP-API OAuth Configuration
SP_API_LWA_APP_ID = os.getenv('SP_API_LWA_APP_ID')
SP_API_LWA_CLIENT_SECRET = os.getenv('SP_API_LWA_CLIENT_SECRET')
# Dynamic Amazon redirect URI for development and production
default_amazon_redirect = 'https://internet-money-tools-production.up.railway.app/auth/amazon-seller/callback'
AMAZON_SELLER_REDIRECT_URI = os.getenv('AMAZON_SELLER_REDIRECT_URI', default_amazon_redirect)

# Discount Monitoring Configuration (Admin Only)
DISCOUNT_MONITOR_EMAIL = os.getenv('DISCOUNT_MONITOR_EMAIL')  # Admin email for discount monitoring
DISCOUNT_SENDER_EMAIL = 'alert@distill.io'  # Only monitor emails from this sender
DISCOUNT_EMAIL_DAYS_BACK = int(os.getenv('DISCOUNT_EMAIL_DAYS_BACK', '7'))  # How many days back to check emails (default: 7)

# Encryption key for sensitive data (SP-API tokens)
ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY', Fernet.generate_key().decode())
cipher_suite = Fernet(ENCRYPTION_KEY.encode())

def is_date_yesterday(target_date, user_timezone):
    """Helper function to determine if target_date is yesterday in the user's timezone"""
    if user_timezone:
        try:
            tz = pytz.timezone(user_timezone)
            current_date_in_user_tz = datetime.now(tz).date()
        except pytz.UnknownTimeZoneError:
            current_date_in_user_tz = date.today()
    else:
        current_date_in_user_tz = date.today()
    
    return target_date == (current_date_in_user_tz - timedelta(days=1))

def get_config_user_for_subuser(user_record):
    """Get the user record to use for configuration (parent for subusers, self for main users)"""
    if not user_record:
        return None
        
    if get_user_field(user_record, 'account.user_type') == 'subuser':
        parent_user_id = get_user_field(user_record, 'account.parent_user_id')
        if parent_user_id:
            parent_record = get_user_record(parent_user_id)
            if parent_record:
                return parent_record
        # If parent not found, fallback to subuser record
        return user_record
    
    return user_record

def update_user_last_activity(discord_id):
    """Update user's last activity timestamp consistently"""
    try:
        users = get_users_config()
        for user in users:
            if get_user_field(user, 'identity.discord_id') == discord_id:
                # Always update in profile.last_activity for consistency
                set_user_field(user, 'profile.last_activity', datetime.now().isoformat())
                break
        update_users_config(users)
    except Exception as e:
        print(f"[ERROR] Failed to update last activity: {e}")

def get_s3_client():
    return boto3.client(
        's3',
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    )

def encrypt_token(token):
    """Encrypt sensitive tokens for storage"""
    try:
        if not token:
            return None
        encrypted_token = cipher_suite.encrypt(token.encode())
        return base64.b64encode(encrypted_token).decode()
    except Exception as e:
        pass  # Error encrypting token
        return None

def decrypt_token(encrypted_token):
    """Decrypt stored tokens"""
    try:
        if not encrypted_token:
            return None
        encrypted_data = base64.b64decode(encrypted_token.encode())
        decrypted_token = cipher_suite.decrypt(encrypted_data)
        return decrypted_token.decode()
    except Exception as e:
        pass  # Error decrypting token
        return None

def exchange_amazon_auth_code(auth_code):
    """Exchange Amazon authorization code for refresh token"""
    try:
        token_url = "https://api.amazon.com/auth/o2/token"
        
        data = {
            'grant_type': 'authorization_code',
            'code': auth_code,
            'client_id': SP_API_LWA_APP_ID,
            'client_secret': SP_API_LWA_CLIENT_SECRET
        }
        
        response = requests.post(token_url, data=data)
        
        if response.status_code == 200:
            token_data = response.json()
            return token_data.get('refresh_token')
        else:
            pass  # Token exchange failed
            return None
            
    except Exception as e:
        pass  # Error exchanging auth code
        return None

def get_dummy_users():
    """Generate dummy users for demo purposes with new organized schema"""
    import uuid
    
    return [
        {
            "id": str(uuid.uuid4()),
            "identity": {
                "discord_id": "123456789012345678",
                "discord_username": "DemoUser#1234",
                "email": "demo@example.com",
                "va_name": "Demo VA"
            },
            "account": {
                "user_type": "main",
                "parent_user_id": None,
                "permissions": ["all"],
                "status": "active",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": (datetime.utcnow() - timedelta(days=1)).isoformat(),
                "last_activity": (datetime.utcnow() - timedelta(hours=2)).isoformat()
            },
            "profile": {
                "configured": True,
                "setup_step": "completed"
            },
            "integrations": {
                "google": {
                    "linked": True,
                    "tokens": {
                        "access_token": "dummy_access_token",
                        "refresh_token": "dummy_refresh_token",
                        "expires_at": None,
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "client_id": "dummy_client_id",
                        "client_secret": "dummy_client_secret"
                    },
                    "sheet_id": "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms",
                    "worksheet_title": "Demo Sheet",
                    "column_mapping": {}
                },
                "sellerboard": {
                    "configured": True,
                    "orders_url": "https://demo.sellerboard.com/orders",
                    "stock_url": "https://demo.sellerboard.com/stock",
                    "file_key": "demo_sellerboard.xlsx"
                },
                "amazon": {
                    "configured": True,
                    "listing_loader_key": "demo_listing.xlsm",
                    "sp_api_connected": False
                }
            },
            "files": {
                "uploaded_count": 2,
                "storage_used_bytes": 3072000,
                "recent_uploads": [
                    {
                        "filename": "orders_2024_01.csv",
                        "upload_date": "2024-01-15T10:30:00Z",
                        "file_size": 2048000,
                        "s3_key": "demo/orders_2024_01.csv"
                    }
                ]
            }
        },
        {
            "id": str(uuid.uuid4()),
            "identity": {
                "discord_id": "234567890123456789",
                "discord_username": "AdminDemo#5678",
                "email": "admin@example.com",
                "va_name": None
            },
            "account": {
                "user_type": "admin", 
                "parent_user_id": None,
                "permissions": ["all"],
                "status": "active",
                "created_at": "2023-12-01T00:00:00Z",
                "updated_at": datetime.utcnow().isoformat(),
                "last_activity": (datetime.utcnow() - timedelta(minutes=30)).isoformat()
            },
            "profile": {
                "configured": True,
                "setup_step": "completed"
            },
            "integrations": {
                "google": {
                    "linked": True,
                    "tokens": {},
                    "sheet_id": "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms",
                    "worksheet_title": "Admin Sheet",
                    "column_mapping": {}
                },
                "sellerboard": {
                    "configured": True,
                    "orders_url": "https://demo.sellerboard.com/admin/orders",
                    "stock_url": "https://demo.sellerboard.com/admin/stock",
                    "file_key": "admin_sellerboard.xlsx"
                },
                "amazon": {
                    "configured": False,
                    "listing_loader_key": None,
                    "sp_api_connected": False
                }
            },
            "files": {
                "uploaded_count": 0,
                "storage_used_bytes": 0,
                "recent_uploads": []
            }
        },
        {
            "id": str(uuid.uuid4()),
            "identity": {
                "discord_id": "345678901234567890",
                "discord_username": "VAUser#9012",
                "email": "va@example.com",
                "va_name": "Virtual Assistant"
            },
            "account": {
                "user_type": "subuser",
                "parent_user_id": "123456789012345678",
                "permissions": ["reimbursements_analysis"],
                "status": "active",
                "created_at": "2024-01-05T00:00:00Z",
                "updated_at": (datetime.utcnow() - timedelta(hours=6)).isoformat(),
                "last_activity": (datetime.utcnow() - timedelta(hours=1)).isoformat()
            },
            "profile": {
                "configured": True,
                "setup_step": "completed"
            },
            "integrations": {
                "google": {
                    "linked": False,
                    "tokens": {},
                    "sheet_id": None,
                    "worksheet_title": None,
                    "column_mapping": {}
                },
                "sellerboard": {
                    "configured": False,
                    "orders_url": None,
                    "stock_url": None,
                    "file_key": None
                },
                "amazon": {
                    "configured": False,
                    "listing_loader_key": None,
                    "sp_api_connected": False
                }
            },
            "files": {
                "uploaded_count": 0,
                "storage_used_bytes": 0,
                "recent_uploads": []
            }
        }
    ]

def migrate_user_to_new_schema(old_user):
    """Migrate a user from old flat schema to new organized schema"""
    import uuid
    
    # Generate UUID if not exists
    user_id = old_user.get('id', str(uuid.uuid4()))
    
    # Organize into new schema with ALL user data
    new_user = {
        "id": user_id,
        "identity": {
            "discord_id": str(old_user.get("discord_id", "")),
            "discord_username": old_user.get("discord_username"),
            "email": old_user.get("email"),
            "va_name": old_user.get("va_name")
        },
        "account": {
            "user_type": old_user.get("user_type", "main"),
            "parent_user_id": old_user.get("parent_user_id"),
            "permissions": old_user.get("permissions", []),
            "status": old_user.get("status", "active"),
            "created_at": old_user.get("created_at", datetime.utcnow().isoformat()),
            "updated_at": old_user.get("updated_at", datetime.utcnow().isoformat()),
            "last_activity": old_user.get("last_activity", datetime.utcnow().isoformat()),
            "feature_permissions": old_user.get("feature_permissions", {})
        },
        "profile": {
            "configured": old_user.get("profile_configured", False) or bool(
                old_user.get("email") and 
                (old_user.get("sellerboard_orders_url") or old_user.get("sheet_id"))
            ),
            "setup_step": "completed" if (old_user.get("profile_configured") or bool(
                old_user.get("email") and 
                (old_user.get("sellerboard_orders_url") or old_user.get("sheet_id"))
            )) else "initial",
            "timezone": old_user.get("timezone")
        },
        "integrations": {
            "google": {
                "linked": old_user.get("google_linked", False),
                "tokens": old_user.get("google_tokens", {}),
                "sheet_id": old_user.get("sheet_id"),
                "worksheet_title": old_user.get("worksheet_title"),
                "column_mapping": old_user.get("column_mapping", {}),
                "sheet_configured": old_user.get("sheet_configured", False),
                "search_all_worksheets": old_user.get("search_all_worksheets", False),
                "discount_gmail_tokens": old_user.get("discount_gmail_tokens", {})
            },
            "sellerboard": {
                "configured": bool(old_user.get("sellerboard_orders_url") or old_user.get("sb_file_key")),
                "orders_url": old_user.get("sellerboard_orders_url"),
                "stock_url": old_user.get("sellerboard_stock_url"),
                "cogs_url": old_user.get("sellerboard_cogs_url"),
                "file_key": old_user.get("sb_file_key")
            },
            "amazon": {
                "configured": bool(old_user.get("listing_loader_key") or old_user.get("amazon_refresh_token")),
                "listing_loader_key": old_user.get("listing_loader_key"),
                "sp_api_connected": old_user.get("sp_api_connected", False),
                "refresh_token": old_user.get("amazon_refresh_token"),
                "selling_partner_id": old_user.get("amazon_selling_partner_id"),
                "connected_at": old_user.get("amazon_connected_at"),
                "marketplace_id": old_user.get("marketplace_id"),
                "disable_sp_api": old_user.get("disable_sp_api", False),
                "lead_time_days": old_user.get("amazon_lead_time_days")
            }
        },
        "settings": {
            "enable_source_links": old_user.get("enable_source_links", False)
        },
        "files": {
            "uploaded_count": len(old_user.get("uploaded_files", [])),
            "storage_used_bytes": sum(f.get("file_size", 0) for f in old_user.get("uploaded_files", [])),
            "uploaded_files": old_user.get("uploaded_files", []),  # Keep all uploaded files
            "recent_uploads": old_user.get("uploaded_files", [])[-5:]  # Keep last 5
        }
    }
    
    return new_user

def is_new_schema(user):
    """Check if user data is in new organized schema"""
    return "identity" in user and "account" in user and "integrations" in user

def normalize_user(user):
    """Ensure user is in new schema format"""
    if is_new_schema(user):
        return user
    return migrate_user_to_new_schema(user)

def get_user_field(user, field_path):
    """Get field from user using dot notation (e.g., 'identity.discord_id')"""
    # Note: User should already be normalized when passed to this function
    # Normalize here only as safety fallback, but avoid for performance
    if not is_new_schema(user):
        user = normalize_user(user)
    
    parts = field_path.split('.')
    current = user
    
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    
    return current

def set_user_field(user, field_path, value):
    """Set field in user using dot notation"""
    user = normalize_user(user)
    
    parts = field_path.split('.')
    current = user
    
    for part in parts[:-1]:
        if part not in current:
            current[part] = {}
        current = current[part]
    
    current[parts[-1]] = value
    return user

def migrate_all_users_to_new_schema():
    """Migrate all users from old schema to new organized schema"""
    if DEMO_MODE:
        return True, "Demo mode - no migration needed"
    
    try:
        # Load raw users data without schema normalization
        s3_client = get_s3_client()
        response = s3_client.get_object(Bucket=CONFIG_S3_BUCKET, Key=USERS_CONFIG_KEY)
        config_data = json.loads(response['Body'].read().decode('utf-8'))
        users = config_data.get("users", [])
        
        # Check if migration is needed
        needs_migration = any(not is_new_schema(user) for user in users)
        if not needs_migration:
            return True, "All users already in new schema format"
        
        # Migrate users
        migrated_users = []
        for user in users:
            if is_new_schema(user):
                migrated_users.append(user)
            else:
                migrated_users.append(migrate_user_to_new_schema(user))
        
        # Create backup of old data
        backup_key = f"{USERS_CONFIG_KEY}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        s3_client.put_object(
            Bucket=CONFIG_S3_BUCKET,
            Key=backup_key,
            Body=json.dumps({"users": users}, indent=2),
            ContentType='application/json'
        )
        
        # Save migrated data
        new_config = {
            "version": "2.0",
            "migrated_at": datetime.utcnow().isoformat(),
            "users": migrated_users
        }
        
        s3_client.put_object(
            Bucket=CONFIG_S3_BUCKET,
            Key=USERS_CONFIG_KEY,
            Body=json.dumps(new_config, indent=2),
            ContentType='application/json'
        )
        
        # Clear cache to force reload
        cache_key = f"config_{USERS_CONFIG_KEY}"
        if cache_key in config_cache:
            del config_cache[cache_key]
        
        # Clear user session caches
        user_session_cache.clear()
        
        return True, f"Successfully migrated {len(migrated_users)} users to new schema. Backup saved as {backup_key}"
        
    except Exception as e:
        return False, f"Migration failed: {str(e)}"

# Convenience functions for common user field access patterns
def get_user_discord_id(user):
    """Get user's discord ID from any schema"""
    return get_user_field(user, 'identity.discord_id') or user.get('discord_id')

def get_user_email(user):
    """Get user's email from any schema"""
    return get_user_field(user, 'identity.email') or user.get('email')

def get_user_type(user):
    """Get user's type from any schema"""
    return get_user_field(user, 'account.user_type') or user.get('user_type', 'main')

def get_user_permissions(user):
    """Get user's permissions from any schema"""
    return get_user_field(user, 'account.permissions') or user.get('permissions', [])

def get_user_google_tokens(user):
    """Get user's Google tokens from any schema - returns tokens dict or None if no valid tokens"""
    tokens = get_user_field(user, 'integrations.google.tokens') or user.get('google_tokens', {})
    # Return None if tokens dict is empty or doesn't have access_token
    if not tokens or not tokens.get('access_token'):
        return None
    return tokens

def get_user_sheet_id(user):
    """Get user's Google Sheet ID from any schema"""
    return get_user_field(user, 'files.sheet_id') or user.get('sheet_id')

def get_user_parent_id(user):
    """Get user's parent ID from any schema"""
    return get_user_field(user, 'account.parent_user_id') or user.get('parent_user_id')

def get_user_timezone(user):
    """Get user's timezone from any schema"""
    return get_user_field(user, 'profile.timezone') or user.get('timezone')

def get_user_amazon_refresh_token(user):
    """Get user's Amazon refresh token from any schema"""
    return get_user_field(user, 'integrations.amazon.refresh_token') or user.get('amazon_refresh_token')

def get_user_amazon_selling_partner_id(user):
    """Get user's Amazon selling partner ID from any schema"""
    return get_user_field(user, 'integrations.amazon.selling_partner_id') or user.get('amazon_selling_partner_id')

def get_user_amazon_connected_at(user):
    """Get user's Amazon connection timestamp from any schema"""
    return get_user_field(user, 'integrations.amazon.connected_at') or user.get('amazon_connected_at')

def get_user_sellerboard_orders_url(user):
    """Get user's Sellerboard orders URL from any schema"""
    return get_user_field(user, 'integrations.sellerboard.orders_url') or user.get('sellerboard_orders_url')

def get_user_sellerboard_stock_url(user):
    """Get user's Sellerboard stock URL from any schema"""
    return get_user_field(user, 'integrations.sellerboard.stock_url') or user.get('sellerboard_stock_url')

def get_user_sellerboard_cogs_url(user):
    """Get user's Sellerboard COGS URL from any schema"""
    return get_user_field(user, 'integrations.sellerboard.cogs_url') or user.get('sellerboard_cogs_url')

def get_user_column_mapping(user):
    """Get user's column mapping from any schema"""
    return get_user_field(user, 'integrations.google.column_mapping') or user.get('column_mapping', {})

def get_user_worksheet_title(user):
    """Get user's worksheet title from any schema"""
    return get_user_field(user, 'integrations.google.worksheet_title') or user.get('worksheet_title')

def get_user_feature_permissions(user):
    """Get user's feature permissions from any schema"""
    return get_user_field(user, 'account.feature_permissions') or user.get('feature_permissions', {})

def get_user_marketplace_id(user):
    """Get user's marketplace ID from any schema"""
    return get_user_field(user, 'integrations.amazon.marketplace_id') or user.get('marketplace_id')

def get_user_enable_source_links(user):
    """Get user's enable source links setting from any schema"""
    return get_user_field(user, 'settings.enable_source_links') or user.get('enable_source_links', False)

def is_user_configured(user):
    """Check if user profile is configured"""
    # First check the explicit configured flag
    explicit_configured = get_user_field(user, 'profile.configured') or user.get('profile_configured', False)
    if explicit_configured:
        return True
    
    # If not explicitly set, check if user has essential configuration
    has_email = bool(get_user_email(user))
    has_integrations = bool(get_user_sheet_id(user) or get_user_sellerboard_orders_url(user))
    
    return has_email and has_integrations

# Update user field convenience functions
def set_user_google_tokens(user, tokens):
    """Set user's Google tokens in correct schema location"""
    return set_user_field(user, 'integrations.google.tokens', tokens)

def set_user_sheet_config(user, sheet_id, worksheet_title=None, column_mapping=None):
    """Set user's Google Sheet configuration"""
    user = set_user_field(user, 'integrations.google.sheet_id', sheet_id)
    if worksheet_title:
        user = set_user_field(user, 'integrations.google.worksheet_title', worksheet_title)
    if column_mapping:
        user = set_user_field(user, 'integrations.google.column_mapping', column_mapping)
    return user

def mark_user_configured(user, configured=True):
    """Mark user as configured or not"""
    user = set_user_field(user, 'profile.configured', configured)
    if configured:
        user = set_user_field(user, 'profile.setup_step', 'completed')
    return user

def get_dummy_analytics_data(target_date):
    """Generate dummy analytics data for demo purposes"""
    base_date = target_date
    yesterday = base_date - timedelta(days=1)
    
    return {
        'success': True,
        'report_date': target_date.strftime('%Y-%m-%d'),
        'user_timezone': 'America/New_York',
        'total_revenue': 4235.67,
        'total_orders': 89,
        'avg_order_value': 47.60,
        'units_sold': 134,
        'today_sales': {
            'B08N5WRWNW': 18,
            'B07XJ8C8F7': 22,
            'B09KMXJQ9R': 15
        },
        'sellerboard_orders': [
            {
                'date': yesterday.strftime('%Y-%m-%d'),
                'asin': 'B08N5WRWNW',
                'product_name': 'Demo Wireless Bluetooth Headphones',
                'quantity': 5,
                'revenue': 399.95,
                'price': 79.99
            },
            {
                'date': yesterday.strftime('%Y-%m-%d'),
                'asin': 'B07XJ8C8F7',
                'product_name': 'Premium Phone Case - Clear',
                'quantity': 8,
                'revenue': 199.92,
                'price': 24.99
            },
            {
                'date': yesterday.strftime('%Y-%m-%d'),
                'asin': 'B09KMXJQ9R',
                'product_name': 'Wireless Charging Pad',
                'quantity': 6,
                'revenue': 389.94,
                'price': 64.99
            }
        ],
        'enhanced_analytics': {
            'B08N5WRWNW': {
                'product_name': 'Demo Wireless Bluetooth Headphones',
                'current_stock': 8,
                'days_remaining': 3.2,
                'daily_velocity': 2.5,
                'alert_type': 'low_stock',
                'restock_priority': 'urgent',
                'velocity': {
                    'weighted_velocity': 2.5,
                    'trend': 'accelerating'
                },
                'restock': {
                    'current_stock': 8,
                    'suggested_quantity': 150,
                    'monthly_purchase_adjustment': 0
                },
                'priority': {
                    'category': 'critical_high_velocity',
                    'score': 95.5
                },
                'cogs_data': {
                    'cogs': 45.00,
                    'last_purchase_date': (datetime.now() - timedelta(days=21)).strftime('%Y-%m-%d'),
                    'source_link': 'https://supplier.example.com/products/B08N5WRWNW'
                },
                'stock_info': {
                    'Source': 'https://supplier.example.com/products/B08N5WRWNW'
                }
            },
            'B07XJ8C8F7': {
                'product_name': 'Premium Phone Case - Clear',
                'current_stock': 15,
                'days_remaining': 6.8,
                'daily_velocity': 2.2,
                'alert_type': 'medium_stock',
                'restock_priority': 'high',
                'velocity': {
                    'weighted_velocity': 2.2,
                    'trend': 'stable'
                },
                'restock': {
                    'current_stock': 15,
                    'suggested_quantity': 100,
                    'monthly_purchase_adjustment': 0
                },
                'priority': {
                    'category': 'warning_high_velocity',
                    'score': 78.3
                },
                'cogs_data': {
                    'cogs': 18.00,
                    'last_purchase_date': (datetime.now() - timedelta(days=15)).strftime('%Y-%m-%d'),
                    'source_link': 'https://supplier.example.com/products/B07XJ8C8F7'
                },
                'stock_info': {
                    'Source': 'https://supplier.example.com/products/B07XJ8C8F7'
                }
            },
            'B09KMXJQ9R': {
                'product_name': 'Wireless Charging Pad',
                'current_stock': 45,
                'days_remaining': 15.0,
                'daily_velocity': 3.0,
                'alert_type': 'good_stock',
                'restock_priority': 'medium',
                'velocity': {
                    'weighted_velocity': 3.0,
                    'trend': 'declining'
                },
                'restock': {
                    'current_stock': 45,
                    'suggested_quantity': 75,
                    'monthly_purchase_adjustment': 25
                },
                'priority': {
                    'category': 'warning_moderate',
                    'score': 62.1
                },
                'cogs_data': {
                    'cogs': 35.00,
                    'last_purchase_date': (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'),
                    'source_link': 'https://supplier.example.com/products/B09KMXJQ9R'
                },
                'stock_info': {
                    'Source': 'https://supplier.example.com/products/B09KMXJQ9R'
                }
            }
        },
        'top_products': [
            {
                'asin': 'B08N5WRWNW',
                'title': 'Demo Wireless Bluetooth Headphones',
                'units_sold': 18,
                'revenue': 1439.10,
                'avg_price': 79.95
            },
            {
                'asin': 'B07XJ8C8F7',
                'title': 'Premium Phone Case - Clear',
                'units_sold': 22,
                'revenue': 549.78,
                'avg_price': 24.99
            },
            {
                'asin': 'B09KMXJQ9R',
                'title': 'Wireless Charging Pad',
                'units_sold': 15,
                'revenue': 974.85,
                'avg_price': 64.99
            }
        ],
        'hourly_sales': [
            {'hour': '00:00', 'revenue': 125.30, 'orders': 2},
            {'hour': '01:00', 'revenue': 89.45, 'orders': 1},
            {'hour': '02:00', 'revenue': 156.78, 'orders': 3},
            {'hour': '03:00', 'revenue': 203.89, 'orders': 4},
            {'hour': '04:00', 'revenue': 178.20, 'orders': 3},
            {'hour': '05:00', 'revenue': 267.90, 'orders': 5},
            {'hour': '06:00', 'revenue': 312.45, 'orders': 6},
            {'hour': '07:00', 'revenue': 389.34, 'orders': 8},
            {'hour': '08:00', 'revenue': 445.67, 'orders': 9},
            {'hour': '09:00', 'revenue': 534.78, 'orders': 11},
            {'hour': '10:00', 'revenue': 623.90, 'orders': 13},
            {'hour': '11:00', 'revenue': 712.12, 'orders': 15},
            {'hour': '12:00', 'revenue': 789.34, 'orders': 16},
            {'hour': '13:00', 'revenue': 734.65, 'orders': 15},
            {'hour': '14:00', 'revenue': 656.43, 'orders': 14},
            {'hour': '15:00', 'revenue': 578.21, 'orders': 12},
            {'hour': '16:00', 'revenue': 489.09, 'orders': 10},
            {'hour': '17:00', 'revenue': 423.87, 'orders': 9},
            {'hour': '18:00', 'revenue': 367.65, 'orders': 7},
            {'hour': '19:00', 'revenue': 334.54, 'orders': 6},
            {'hour': '20:00', 'revenue': 289.43, 'orders': 5},
            {'hour': '21:00', 'revenue': 234.32, 'orders': 4},
            {'hour': '22:00', 'revenue': 189.21, 'orders': 3},
            {'hour': '23:00', 'revenue': 145.10, 'orders': 2}
        ],
        'comparison': {
            'yesterday_revenue': 3842.33,
            'yesterday_orders': 82,
            'revenue_change': 10.2,
            'orders_change': 8.5
        },
        'purchase_investment': {
            'total_investment': 52750.00,
            'monthly_investment': 8950.00,
            'roi_percentage': 24.3,
            'break_even_days': 18
        },
        'purchase_insights': {
            'summary_metrics': {
                'total_investment': 52750.00,  # Total across all worksheets
                'current_month_investment': 8950.00,  # Current month only (for Purchase Investment box)
                'current_month_asins': 12,
                'current_month_units': 145,
                'total_asins_tracked': 35,
                'total_units_purchased': 1250,
                'analysis_date_range': {
                    'start': '2024-01-01',
                    'end': datetime.now().strftime('%Y-%m-%d')
                }
            }
        },
        'inventory_alerts': [
            {
                'asin': 'B08N5WRWNW',
                'title': 'Demo Wireless Bluetooth Headphones',
                'current_stock': 8,
                'days_remaining': 3.2,
                'daily_velocity': 2.5,
                'alert_type': 'low_stock'
            },
            {
                'asin': 'B07XJ8C8F7',
                'title': 'Premium Phone Case - Clear',
                'current_stock': 15,
                'days_remaining': 6.8,
                'daily_velocity': 2.2,
                'alert_type': 'medium_stock'
            }
        ],
        'restock_recommendations': [
            {
                'asin': 'B08N5WRWNW',
                'title': 'Demo Wireless Bluetooth Headphones',
                'recommended_quantity': 120,
                'lead_time_days': 14,
                'order_by_date': (datetime.now() + timedelta(days=2)).strftime('%Y-%m-%d'),
                'priority': 'high'
            }
        ],
        'restock_alerts': {
            'B08N5WRWNW': {
                'asin': 'B08N5WRWNW',
                'product_name': 'Demo Wireless Bluetooth Headphones',
                'priority_score': 95.5,
                'category': 'critical_high_velocity',
                'emoji': '🔥',
                'suggested_quantity': 150,
                'current_stock': 8,
                'days_left': 3.2,
                'velocity': 2.5,
                'trend': 'accelerating',
                'cogs': 45.00,
                'last_purchase_date': (datetime.now() - timedelta(days=21)).strftime('%Y-%m-%d')
            },
            'B07XJ8C8F7': {
                'asin': 'B07XJ8C8F7', 
                'product_name': 'Premium Phone Case - Clear',
                'priority_score': 78.3,
                'category': 'warning_high_velocity',
                'emoji': '⚠️',
                'suggested_quantity': 100,
                'current_stock': 15,
                'days_left': 6.8,
                'velocity': 2.2,
                'trend': 'stable',
                'cogs': 18.00,
                'last_purchase_date': (datetime.now() - timedelta(days=15)).strftime('%Y-%m-%d')
            },
            'B09KMXJQ9R': {
                'asin': 'B09KMXJQ9R',
                'product_name': 'Wireless Charging Pad',
                'priority_score': 62.1,
                'category': 'warning_moderate',
                'emoji': '⏰',
                'suggested_quantity': 75,
                'current_stock': 45,
                'days_left': 15.0,
                'velocity': 3.0,
                'trend': 'declining',
                'cogs': 35.00,
                'last_purchase_date': (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            }
        },
        'critical_alerts': ['B08N5WRWNW'],
        'total_products_analyzed': 3,
        'high_priority_count': 2,
        'stockout_30d': {
            'B08N5WRWNW': {
                'title': 'Demo Wireless Bluetooth Headphones',
                'sold_today': 18,
                'current_stock': 8,
                'days_left': 3,
                'suggested_reorder': 150
            },
            'B07XJ8C8F7': {
                'title': 'Premium Phone Case - Clear',
                'sold_today': 22,
                'current_stock': 15,
                'days_left': 7,
                'suggested_reorder': 100
            }
        },
        'date': target_date.strftime('%Y-%m-%d'),
        'generated_at': datetime.utcnow().isoformat()
    }

def get_dummy_reimbursements_data():
    """Generate dummy reimbursements data for demo purposes"""
    return {
        'success': True,
        'underpaid_reimbursements': [
            {
                'reimbursement_id': 'REIMB-2024-001',
                'asin': 'B08N5WRWNW',
                'fnsku': 'X001ABC123',
                'product_name': 'Demo Wireless Bluetooth Headphones',
                'reimbursed_quantity': 2,
                'amount_per_unit': 35.50,
                'amount_total': 71.00,
                'max_cogs': 45.00,
                'difference_per_unit': 9.50,
                'total_underpaid': 19.00,
                'reason': 'Customer Return'
            },
            {
                'reimbursement_id': 'REIMB-2024-002',
                'asin': 'B07XJ8C8F7',
                'fnsku': 'X001DEF456',
                'product_name': 'Premium Phone Case - Clear',
                'reimbursed_quantity': 5,
                'amount_per_unit': 12.00,
                'amount_total': 60.00,
                'max_cogs': 18.00,
                'difference_per_unit': 6.00,
                'total_underpaid': 30.00,
                'reason': 'Lost in Warehouse'
            },
            {
                'reimbursement_id': 'REIMB-2024-003',
                'asin': 'B09KMXJQ9R',
                'fnsku': 'X001GHI789',
                'product_name': 'Wireless Charging Pad',
                'reimbursed_quantity': 3,
                'amount_per_unit': 22.00,
                'amount_total': 66.00,
                'max_cogs': 35.00,
                'difference_per_unit': 13.00,
                'total_underpaid': 39.00,
                'reason': 'Damaged by Amazon'
            }
        ],
        'summary': {
            'total_underpaid_amount': 88.00,
            'total_cases': 3,
            'total_units_affected': 10,
            'average_underpayment': 29.33,
            'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    }

def get_dummy_expected_arrivals_data():
    """Generate dummy expected arrivals data for demo purposes"""
    return {
        'success': True,
        'expected_arrivals': [
            {
                'expected_date': (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d'),
                'asin': 'B08N5WRWNW',
                'product_name': 'Demo Wireless Bluetooth Headphones',
                'expected_quantity': 150,
                'current_stock': 8,
                'days_of_stock': 3.2,
                'daily_velocity': 2.5,
                'status': 'on_time'
            },
            {
                'expected_date': (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d'),
                'asin': 'B07XJ8C8F7',
                'product_name': 'Premium Phone Case - Clear',
                'expected_quantity': 200,
                'current_stock': 15,
                'days_of_stock': 6.8,
                'daily_velocity': 2.2,
                'status': 'on_time'
            },
            {
                'expected_date': (datetime.now() + timedelta(days=14)).strftime('%Y-%m-%d'),
                'asin': 'B09KMXJQ9R',
                'product_name': 'Wireless Charging Pad',
                'expected_quantity': 100,
                'current_stock': 45,
                'days_of_stock': 15.0,
                'daily_velocity': 3.0,
                'status': 'delayed'
            }
        ],
        'missing_listings': [
            {
                'asin': 'B09ABC123',
                'product_name': 'Smart Watch Band - Black',
                'quantity_purchased': 50,
                'purchase_count': 3,
                'last_purchase_date': (datetime.now() - timedelta(days=21)).strftime('%Y-%m-%d'),
                'avg_cogs': 12.50,
                'total_cost': 625.00,
                'source_worksheets': ['Q1 2024 Purchases', 'February Orders'],
                'status': 'No Amazon listing created'
            },
            {
                'asin': 'B09DEF456',
                'product_name': 'USB-C Cable 6ft - Premium Quality',
                'quantity_purchased': 100,
                'purchase_count': 2,
                'last_purchase_date': (datetime.now() - timedelta(days=35)).strftime('%Y-%m-%d'),
                'avg_cogs': 8.75,
                'total_cost': 875.00,
                'source_worksheets': ['January Inventory'],
                'status': 'No Amazon listing created'
            },
            {
                'asin': 'B09GHI789',
                'product_name': 'Wireless Mouse - Ergonomic Design',
                'quantity_purchased': 25,
                'purchase_count': 1,
                'last_purchase_date': (datetime.now() - timedelta(days=14)).strftime('%Y-%m-%d'),
                'avg_cogs': 22.00,
                'total_cost': 550.00,
                'source_worksheets': ['March Electronics'],
                'status': 'No Amazon listing created'
            }
        ],
        'summary': {
            'total_expected_arrivals': 3,
            'arrivals_on_time': 2,
            'arrivals_delayed': 1,
            'total_items': 3,
            'total_quantity': 175,
            'total_cost': 2050.00
        },
        'analyzed_at': datetime.now().isoformat()
    }

def get_dummy_smart_restock_data():
    """Generate dummy smart restock recommendations for demo purposes"""
    return {
        'success': True,
        'recommendations': [
            {
                'asin': 'B08N5WRWNW',
                'product_name': 'Demo Wireless Bluetooth Headphones',
                'current_stock': 8,
                'daily_velocity': 2.5,
                'days_remaining': 3.2,
                'lead_time': 90,
                'recommended_quantity': 300,
                'reorder_date': (datetime.now() + timedelta(days=2)).strftime('%Y-%m-%d'),
                'priority': 'urgent',
                'confidence_score': 0.92,
                'seasonality_factor': 1.2,
                'trend': 'increasing'
            },
            {
                'asin': 'B07XJ8C8F7',
                'product_name': 'Premium Phone Case - Clear',
                'current_stock': 15,
                'daily_velocity': 2.2,
                'days_remaining': 6.8,
                'lead_time': 90,
                'recommended_quantity': 250,
                'reorder_date': (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d'),
                'priority': 'high',
                'confidence_score': 0.88,
                'seasonality_factor': 1.0,
                'trend': 'stable'
            },
            {
                'asin': 'B09KMXJQ9R',
                'product_name': 'Wireless Charging Pad',
                'current_stock': 45,
                'daily_velocity': 3.0,
                'days_remaining': 15.0,
                'lead_time': 90,
                'recommended_quantity': 350,
                'reorder_date': (datetime.now() + timedelta(days=15)).strftime('%Y-%m-%d'),
                'priority': 'medium',
                'confidence_score': 0.85,
                'seasonality_factor': 0.9,
                'trend': 'decreasing'
            }
        ],
        'alerts': [
            {
                'type': 'urgent_restock',
                'message': '1 product needs immediate reorder (less than 5 days of stock)',
                'affected_asins': ['B08N5WRWNW']
            },
            {
                'type': 'velocity_spike',
                'message': 'Sales velocity increased by 30% for 2 products',
                'affected_asins': ['B08N5WRWNW', 'B07XJ8C8F7']
            }
        ],
        'summary': {
            'total_products': 3,
            'urgent_reorders': 1,
            'high_priority': 1,
            'medium_priority': 1,
            'total_recommended_units': 900,
            'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    }

def get_dummy_discount_opportunities():
    """Generate dummy discount opportunities data for demo purposes"""
    return {
        'success': True,
        'opportunities': [
            {
                'asin': 'B00F3DCZ6Q',
                'product_name': 'Demo Wireless Bluetooth Headphones',
                'retailer': 'Walmart',
                'current_stock': 8,
                'recent_purchases': 25,
                'suggested_quantity': 120,
                'days_left': 3.2,
                'velocity': 2.5,
                'source_link': 'https://www.walmart.com/search?query=B00F3DCZ6Q',
                'promo_message': None,
                'note': 'Locally',
                'alert_time': (datetime.now() - timedelta(hours=4)).isoformat(),
                'priority_score': 95,
                'restock_priority': 'critical_high_velocity',
                'status': 'Restock Needed',
                'needs_restock': True
            },
            {
                'asin': 'B07XJ8C8F7',
                'product_name': 'Premium Phone Case - Clear',
                'retailer': 'Target',
                'current_stock': 15,
                'recent_purchases': 50,
                'suggested_quantity': 75,
                'days_left': 6.8,
                'velocity': 2.2,
                'source_link': 'https://www.target.com/s?searchTerm=B07XJ8C8F7',
                'promo_message': None,
                'note': 'Flash sale - 20% off',
                'alert_time': (datetime.now() - timedelta(hours=8)).isoformat(),
                'priority_score': 85,
                'restock_priority': 'warning_high_velocity',
                'status': 'Restock Needed',
                'needs_restock': True
            },
            {
                'asin': 'B00TW2XZ04',
                'product_name': 'Wireless Charging Pad',
                'retailer': 'Lowes',
                'current_stock': 25,
                'recent_purchases': 0,
                'suggested_quantity': 0,
                'days_left': None,
                'velocity': 3.0,
                'source_link': 'https://www.lowes.com/search?searchTerm=B00TW2XZ04',
                'promo_message': None,
                'note': 'Good stock level',
                'alert_time': (datetime.now() - timedelta(hours=12)).isoformat(),
                'priority_score': 0,
                'restock_priority': 'normal',
                'status': 'Not Needed',
                'needs_restock': False
            },
            {
                'asin': 'B09ABCD123',
                'product_name': 'Product not tracked',
                'retailer': 'Home Depot',
                'current_stock': 0,
                'recent_purchases': 0,
                'suggested_quantity': 0,
                'days_left': None,
                'velocity': 0,
                'source_link': None,
                'promo_message': None,
                'note': 'Price drop alert',
                'alert_time': (datetime.now() - timedelta(hours=16)).isoformat(),
                'priority_score': 0,
                'restock_priority': 'not_tracked',
                'status': 'Not Tracked',
                'needs_restock': False
            }
        ],
        'total_alerts_processed': 4,
        'matched_products': 4,
        'restock_needed_count': 2,
        'not_needed_count': 1,
        'not_tracked_count': 1,
        'retailer_filter': '',
        'analyzed_at': datetime.now().isoformat(),
        'message': 'Found 4 discount leads (2 need restocking, 1 not needed, 1 not tracked)'
    }

def get_dummy_sheet_data():
    """Generate dummy Google Sheets data for demo purposes"""
    return {
        'spreadsheets': [
            {
                'id': '1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms',
                'name': 'Demo Product Catalog 2024',
                'url': 'https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms',
                'created_time': '2024-01-01T00:00:00Z',
                'modified_time': (datetime.now() - timedelta(hours=2)).isoformat() + 'Z'
            },
            {
                'id': '1AbCdEfGhIjKlMnOpQrStUvWxYz1234567890',
                'name': 'Demo Inventory Tracking',
                'url': 'https://docs.google.com/spreadsheets/d/1AbCdEfGhIjKlMnOpQrStUvWxYz1234567890',
                'created_time': '2024-01-15T00:00:00Z',
                'modified_time': (datetime.now() - timedelta(days=1)).isoformat() + 'Z'
            }
        ],
        'worksheets': {
            '1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms': [
                {'title': 'Products', 'id': '0'},
                {'title': 'COGS Data', 'id': '1'},
                {'title': 'Archive', 'id': '2'}
            ]
        },
        'headers': {
            'Products': ['ASIN', 'Product Name', 'COGS', 'Supplier', 'Last Updated'],
            'COGS Data': ['ASIN', 'Max COGS', 'Current COGS', 'Effective Date']
        }
    }

def get_cache_key(discord_id, target_date, endpoint_type='analytics'):
    """Generate cache key for user data"""
    return f"{endpoint_type}_{discord_id}_{target_date.strftime('%Y-%m-%d')}"

def is_cache_valid(cache_entry):
    """Check if cache entry is still valid"""
    if not cache_entry:
        return False
    
    cached_time = cache_entry.get('timestamp')
    if not cached_time:
        return False
    
    # Check if cache is older than CACHE_EXPIRY_HOURS
    cache_age = datetime.utcnow() - cached_time
    return cache_age.total_seconds() < (CACHE_EXPIRY_HOURS * 3600)

def get_cached_data(cache_key):
    """Get cached data if valid, otherwise return None"""
    cache_entry = analytics_cache.get(cache_key)
    if is_cache_valid(cache_entry):
        return cache_entry.get('data')
    return None

def set_cached_data(cache_key, data):
    """Store data in cache with timestamp"""
    analytics_cache[cache_key] = {
        'data': data,
        'timestamp': datetime.utcnow()
    }
    
    # Clean old cache entries (simple cleanup)
    current_time = datetime.utcnow()
    keys_to_remove = []
    for key, entry in analytics_cache.items():
        if not is_cache_valid(entry):
            keys_to_remove.append(key)
    
    for key in keys_to_remove:
        del analytics_cache[key]

def get_users_config():
    if DEMO_MODE:
        return get_dummy_users()
    
    # Check cache first to reduce S3 reads
    cache_key = f"config_{USERS_CONFIG_KEY}"
    if cache_key in config_cache:
        cached_data, cached_time = config_cache[cache_key]
        if (datetime.now() - cached_time).total_seconds() < CONFIG_CACHE_EXPIRY_MINUTES * 60:
            return cached_data
    
    s3_client = get_s3_client()
    try:
        response = s3_client.get_object(Bucket=CONFIG_S3_BUCKET, Key=USERS_CONFIG_KEY)
        config_data = json.loads(response['Body'].read().decode('utf-8'))
        users = config_data.get("users", [])
        
        # Normalize all users to new schema and validate tokens
        normalized_users = []
        for user in users:
            normalized_user = normalize_user(user)
            
            # Validate and fix token data in new schema location
            google_tokens = get_user_field(normalized_user, 'integrations.google.tokens')
            if google_tokens:
                fixed_tokens = validate_and_fix_token_data(google_tokens)
                set_user_field(normalized_user, 'integrations.google.tokens', fixed_tokens)
            
            normalized_users.append(normalized_user)
        
        # Cache the result to reduce future S3 reads
        config_cache[cache_key] = (normalized_users, datetime.now())
        return normalized_users
    except Exception as e:
        pass  # Error fetching users config
        return []

def get_user_config(user_id):
    """Get config for a specific user with session-based caching"""
    if DEMO_MODE:
        users = get_dummy_users()
        return next((u for u in users if u.get("id") == user_id), None)
    
    # Check session cache first
    cached_user = get_cached_user_config(user_id)
    if cached_user:
        return cached_user
    
    # Fallback to loading all users and finding the specific one
    users = get_users_config()
    user = next((u for u in users if u.get("id") == user_id), None)
    
    # Cache the user data for future requests in this session
    if user:
        cache_user_config(user_id, user)
    
    return user

def update_users_config(users):
    s3_client = get_s3_client()
    
    # Ensure all users are in new schema format
    normalized_users = []
    for user in users:
        normalized_users.append(normalize_user(user))
    
    # Save in new organized format with version info
    config_data = {
        "version": "2.0",
        "last_updated": datetime.utcnow().isoformat(),
        "users": normalized_users
    }
    
    # About to save users to S3
    
    try:
        result = s3_client.put_object(
            Bucket=CONFIG_S3_BUCKET, 
            Key=USERS_CONFIG_KEY, 
            Body=json.dumps(config_data, indent=2),
            ContentType='application/json'
        )
        # Users configuration updated successfully
        
        # Invalidate global cache after successful update to ensure consistency
        cache_key = f"config_{USERS_CONFIG_KEY}"
        if cache_key in config_cache:
            del config_cache[cache_key]
        
        # Invalidate user session caches for all affected users
        for user in normalized_users:
            user_id = get_user_field(user, 'id')
            discord_id = get_user_field(user, 'identity.discord_id')
            if user_id:
                invalidate_user_cache(user_id)
            if discord_id:
                invalidate_user_cache(discord_id)
        
        # Skip verification read to reduce S3 costs - put_object is reliable
        # Previous verification step removed to reduce S3 GET requests
        pass  # Update completed successfully
        
        return True
    except Exception as e:
        pass  # Error updating users config
        import traceback
        traceback.print_exc()
        return False

def get_invitations_config():
    """Get invitations configuration from S3 with caching"""
    # Check cache first to reduce S3 reads
    cache_key = f"config_{INVITATIONS_CONFIG_KEY}"
    if cache_key in config_cache:
        cached_data, cached_time = config_cache[cache_key]
        if (datetime.now() - cached_time).total_seconds() < CONFIG_CACHE_EXPIRY_MINUTES * 60:
            return cached_data
    
    try:
        s3_client = get_s3_client()
        response = s3_client.get_object(Bucket=CONFIG_S3_BUCKET, Key=INVITATIONS_CONFIG_KEY)
        data = json.loads(response['Body'].read().decode('utf-8'))
        
        # Cache the result
        config_cache[cache_key] = (data, datetime.now())
        return data
    except s3_client.exceptions.NoSuchKey:
        # Cache empty result too
        config_cache[cache_key] = ([], datetime.now())
        return []
    except Exception as e:
        pass  # Error reading invitations config
        return []

def update_invitations_config(invitations):
    """Update invitations configuration in S3"""
    try:
        s3_client = get_s3_client()
        s3_client.put_object(
            Bucket=CONFIG_S3_BUCKET,
            Key=INVITATIONS_CONFIG_KEY,
            Body=json.dumps(invitations, indent=2),
            ContentType='application/json'
        )
        
        # Invalidate cache after successful update
        cache_key = f"config_{INVITATIONS_CONFIG_KEY}"
        if cache_key in config_cache:
            del config_cache[cache_key]
        
        return True
    except Exception as e:
        pass  # Error updating invitations config
        return False

def get_discount_monitoring_config():
    """Get discount monitoring configuration from S3 with caching"""
    # Check cache first to reduce S3 reads
    cache_key = f"config_{DISCOUNT_MONITORING_CONFIG_KEY}"
    if cache_key in config_cache:
        cached_data, cached_time = config_cache[cache_key]
        if (datetime.now() - cached_time).total_seconds() < CONFIG_CACHE_EXPIRY_MINUTES * 60:
            return cached_data
    
    s3_client = get_s3_client()
    try:
        response = s3_client.get_object(Bucket=CONFIG_S3_BUCKET, Key=DISCOUNT_MONITORING_CONFIG_KEY)
        config_data = json.loads(response['Body'].read().decode('utf-8'))
        
        # Cache the result
        config_cache[cache_key] = (config_data, datetime.now())
        return config_data
    except Exception as e:
        # Return default config if not found and cache it
        default_config = {
            'days_back': 7,  # Default to 7 days
            'enabled': bool(DISCOUNT_MONITOR_EMAIL),
            'last_updated': None
        }
        config_cache[cache_key] = (default_config, datetime.now())
        return default_config

def update_discount_monitoring_config(config):
    """Update discount monitoring configuration in S3"""
    try:
        from datetime import datetime
        import pytz
        
        # Add timestamp
        config['last_updated'] = datetime.now(pytz.UTC).isoformat()
        
        s3_client = get_s3_client()
        s3_client.put_object(
            Bucket=CONFIG_S3_BUCKET,
            Key=DISCOUNT_MONITORING_CONFIG_KEY,
            Body=json.dumps(config, indent=2),
            ContentType='application/json'
        )
        
        # Invalidate cache after successful update
        cache_key = f"config_{DISCOUNT_MONITORING_CONFIG_KEY}"
        if cache_key in config_cache:
            del config_cache[cache_key]
            
        return True
    except Exception as e:
        print(f"Error updating discount monitoring config: {e}")
        return False

def get_discount_email_days_back():
    """Get the current days back setting for discount email checking"""
    config = get_discount_monitoring_config()
    env_days = int(os.getenv('DISCOUNT_EMAIL_DAYS_BACK', '14'))
    
    # Prefer config over environment variable, but fallback to env if not set
    days_back = config.get('days_back', env_days)
    
    # Debug logging to see what date range we're using
    
    return days_back

def get_purchases_config():
    """Get purchases configuration from S3 with caching"""
    if DEMO_MODE:
        return []
    
    # Check cache first to reduce S3 reads
    cache_key = f"config_{PURCHASES_CONFIG_KEY}"
    if cache_key in config_cache:
        cached_data, cached_time = config_cache[cache_key]
        if (datetime.now() - cached_time).total_seconds() < CONFIG_CACHE_EXPIRY_MINUTES * 60:
            return cached_data
    
    s3_client = get_s3_client()
    try:
        response = s3_client.get_object(Bucket=CONFIG_S3_BUCKET, Key=PURCHASES_CONFIG_KEY)
        data = json.loads(response['Body'].read().decode('utf-8'))
        purchases = data.get('purchases', [])
        
        # Cache the result
        config_cache[cache_key] = (purchases, datetime.now())
        return purchases
    except s3_client.exceptions.NoSuchKey:
        # Cache empty result too
        config_cache[cache_key] = ([], datetime.now())
        return []
    except Exception as e:
        print(f"Error fetching purchases config: {e}")
        # Cache empty result for error cases to reduce repeated failed requests
        config_cache[cache_key] = ([], datetime.now())
        return []

def update_purchases_config(purchases):
    """Update purchases configuration in S3"""
    if DEMO_MODE:
        return True
    
    try:
        s3_client = get_s3_client()
        config_data = json.dumps({"purchases": purchases}, indent=2)
        s3_client.put_object(
            Bucket=CONFIG_S3_BUCKET,
            Key=PURCHASES_CONFIG_KEY,
            Body=config_data,
            ContentType='application/json'
        )
        
        # Invalidate cache after successful update
        cache_key = f"config_{PURCHASES_CONFIG_KEY}"
        if cache_key in config_cache:
            del config_cache[cache_key]
            
        return True
    except Exception as e:
        print(f"Error updating purchases config: {e}")
        return False

def send_invitation_email_via_resend(email, invitation_token, invited_by):
    """Send invitation email using Resend API"""
    if not RESEND_API_KEY:
        print("Warning: Resend API key not configured")
        return False
        
    try:
        invitation_url = f"https://dms-amazon.vercel.app/login?invitation={invitation_token}"
        
        html_body = f"""
        <html>
        <body>
            <h2>You're invited to DMS Dashboard!</h2>
            <p>Hi there!</p>
            <p>{invited_by} has invited you to join the DMS Amazon Seller Dashboard.</p>
            <p>This platform provides:</p>
            <ul>
                <li>Advanced analytics for your Amazon business</li>
                <li>Smart restock recommendations</li>
                <li>Inventory tracking and insights</li>
            </ul>
            <p><strong><a href="{invitation_url}" style="background-color: #3B82F6; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px;">Accept Invitation</a></strong></p>
            <p>Or copy and paste this link: {invitation_url}</p>
            <p>This invitation will expire in 7 days.</p>
            <br>
            <p>Best regards,<br>DMS Team</p>
        </body>
        </html>
        """
        
        from_email = f'DMS Dashboard <{RESEND_FROM_DOMAIN}>'
        
        response = requests.post(
            'https://api.resend.com/emails',
            headers={
                'Authorization': f'Bearer {RESEND_API_KEY}',
                'Content-Type': 'application/json'
            },
            json={
                'from': from_email,
                'to': [email],
                'subject': "You're invited to DMS Dashboard",
                'html': html_body
            }
        )
        
        if response.status_code == 200:
            print(f"[RESEND] Email sent successfully to {email}")
            return True
        else:
            print(f"[RESEND] Failed to send email. Status: {response.status_code}, Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"[RESEND] Error sending email to {email}: {str(e)}")
        return False

def send_invitation_email(email, invitation_token, invited_by):
    """Send invitation email to user via Resend API"""
    if not RESEND_API_KEY:
        print(f"Warning: RESEND_API_KEY not configured")
        return False
        
    return send_invitation_email_via_resend(email, invitation_token, invited_by)

def send_cogs_update_email(attachments, recipient_email, potential_updates, new_products, actual_updates, replen_products):
    """
    Send email with COGS update results and attachments using Resend API
    """
    try:
        import base64
        
        if not RESEND_API_KEY:
            print("Resend API key not configured")
            return False
        
        # Build HTML email content
        html_content = """<html>
        <body>
            <h2 style="color: #2c3e50;">Amazon COGS Update Report</h2>
            <div style="margin-bottom: 30px;">"""
        
        if actual_updates:
            html_content += """
            <h3 style="color: #34495e;">Completed Cost Updates</h3>
            <table style="border-collapse: collapse; width: 100%; margin-bottom: 20px;">
                <tr style="background-color: #f8f9fa;">
                    <th style="padding: 12px; border: 1px solid #ddd;">ASIN</th>
                    <th style="padding: 12px; border: 1px solid #ddd;">SKU</th>
                    <th style="padding: 12px; border: 1px solid #ddd;">Name</th>
                    <th style="padding: 12px; border: 1px solid #ddd;">New Cost</th>
                    <th style="padding: 12px; border: 1px solid #ddd;">Source</th>
                </tr>"""
            for update in actual_updates:
                source = update.get('source_worksheet', 'Email Update')
                html_content += f"""
                <tr>
                    <td style="padding: 12px; border: 1px solid #ddd;">{update['ASIN']}</td>
                    <td style="padding: 12px; border: 1px solid #ddd;">{update['SKU']}</td>
                    <td style="padding: 12px; border: 1px solid #ddd;">{update.get('Title', update.get('Name', ''))}</td>
                    <td style="padding: 12px; border: 1px solid #ddd;">${update['new_cost']:.2f}</td>
                    <td style="padding: 12px; border: 1px solid #ddd;">{source}</td>
                </tr>"""
            html_content += "</table>"
        
        html_content += """
            </div>
            <p style="color: #7f8c8d;">
                Your updated Sellerboard COGS file is attached.
            </p>
        </body>
        </html>"""
        
        # Prepare attachments for Resend (base64 encoded)
        resend_attachments = []
        for attachment_data, attachment_filename in attachments:
            attachment_data.seek(0)
            try:
                file_content = attachment_data.read()
                encoded_content = base64.b64encode(file_content).decode('utf-8')
                resend_attachments.append({
                    'filename': attachment_filename,
                    'content': encoded_content,
                    'content_type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                })
            except Exception as e:
                print(f"Failed to encode attachment {attachment_filename}: {e}")
        
        # Send email via Resend API
        from_email = f'DMS Dashboard <{RESEND_FROM_DOMAIN}>'
        
        payload = {
            'from': from_email,
            'to': [recipient_email],
            'subject': 'Amazon COGS Update Report',
            'html': html_content,
            'attachments': resend_attachments
        }
        
        response = requests.post(
            'https://api.resend.com/emails',
            headers={
                'Authorization': f'Bearer {RESEND_API_KEY}',
                'Content-Type': 'application/json'
            },
            json=payload
        )
        
        if response.status_code == 200:
            print(f"COGS update email sent successfully to {recipient_email} via Resend")
            return True
        else:
            print(f"Failed to send COGS update email via Resend. Status: {response.status_code}, Response: {response.text}")
            return False
        
    except Exception as e:
        print(f"Failed to send COGS update email to {recipient_email}: {e}")
        return False

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # If demo mode is OFF but we have demo user session data, clear it
        if (not DEMO_MODE and 
            session.get('discord_id') == '123456789012345678'):
            session.clear()
        
        # In demo mode, automatically set demo user session for all requests
        if DEMO_MODE and 'discord_id' not in session:
            session.permanent = True
            session['discord_id'] = '123456789012345678'  # Demo user ID
            session['discord_username'] = 'DemoUser#1234'
        
        # For production: add a fallback for image endpoints when session issues occur
        if ('discord_id' not in session and 
            ('product-image' in request.path or 'product-images' in request.path)):
            # Allow image requests to proceed with limitations for better UX
            # This handles cases where session cookies have issues
            session.permanent = True
            session['discord_id'] = 'anonymous_user'  # Anonymous fallback
            session['discord_username'] = 'Anonymous'
        
        if 'discord_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function

def is_admin_user(discord_id):
    """Check if a Discord ID is an admin"""
    return discord_id == '712147636463075389'

def has_permission(discord_id, permission):
    """Check if user has specific permission"""
    user_record = get_user_record(discord_id)
    if not user_record:
        return False
    
    user_permissions = get_user_field(user_record, 'account.permissions') or []
    user_type = get_user_field(user_record, 'account.user_type') or 'main'
    
    # Main users and admin have all permissions
    if user_type == 'main' or 'all' in user_permissions or is_admin_user(discord_id):
        return True
    
    # Subusers now have full access to all features
    # This allows VAs to perform all tasks for their main user
    if user_type == 'subuser':
        return True
    
    # Check specific permission (this line should never be reached now)
    return permission in user_permissions

def get_parent_user_record(sub_user_discord_id):
    """Get parent user record for a sub-user"""
    sub_user = get_user_record(sub_user_discord_id)
    if not sub_user or get_user_field(sub_user, 'account.user_type') != 'subuser':
        return None
    
    parent_id = get_user_field(sub_user, 'account.parent_user_id')
    if not parent_id:
        return None
    
    return get_user_record(parent_id)

def permission_required(permission):
    """Decorator to require specific permission"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'discord_id' not in session:
                return jsonify({'error': 'Authentication required'}), 401
            
            if not has_permission(session['discord_id'], permission):
                return jsonify({'error': 'Insufficient permissions'}), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'discord_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        
        # Check if user is admin
        if not is_admin_user(session['discord_id']):
            return jsonify({'error': 'Admin access required'}), 403
        
        return f(*args, **kwargs)
    return decorated_function

def get_feature_config():
    """Get feature launches configuration from S3 with caching"""
    # Check cache first to reduce S3 reads
    cache_key = "config_feature_config.json"
    if cache_key in config_cache:
        cached_data, cached_time = config_cache[cache_key]
        if (datetime.now() - cached_time).total_seconds() < CONFIG_CACHE_EXPIRY_MINUTES * 60:
            return cached_data
    
    s3_client = get_s3_client()
    try:
        response = s3_client.get_object(Bucket=CONFIG_S3_BUCKET, Key='feature_config.json')
        config_data = json.loads(response['Body'].read().decode('utf-8'))
        result = (config_data.get('feature_launches', {}), config_data.get('user_permissions', {}))
        
        # Cache the result
        config_cache[cache_key] = (result, datetime.now())
        return result
    except Exception as e:
        # Cache empty result for error cases
        result = ({}, {})
        config_cache[cache_key] = (result, datetime.now())
        return result

def save_feature_config(feature_launches, user_permissions):
    """Save feature configuration to S3"""
    s3_client = get_s3_client()
    config_data = {
        'feature_launches': feature_launches,
        'user_permissions': user_permissions
    }
    
    try:
        s3_client.put_object(
            Bucket=CONFIG_S3_BUCKET,
            Key='feature_config.json',
            Body=json.dumps(config_data, indent=2),
            ContentType='application/json'
        )
        
        # Invalidate cache after successful update
        cache_key = "config_feature_config.json"
        if cache_key in config_cache:
            del config_cache[cache_key]
            
        return True
    except Exception as e:
        print(f"Error saving feature config to S3: {e}")
        return False

def save_feature_launch_to_s3(feature_key, is_public, launched_by, launch_notes=''):
    """Save feature launch status to S3"""
    feature_launches, user_permissions = get_feature_config()
    
    feature_launches[feature_key] = {
        'is_public': is_public,
        'launched_by': launched_by,
        'launched_at': datetime.utcnow().isoformat(),
        'launch_notes': launch_notes
    }
    
    save_feature_config(feature_launches, user_permissions)

def sync_s3_to_database():
    """Sync feature configuration from S3 to database on startup"""
    try:
        feature_launches, user_permissions = get_feature_config()
        
        # Sync feature launches
        for feature_key, launch_data in feature_launches.items():
            cursor.execute('''
                INSERT OR REPLACE INTO feature_launches 
                (feature_key, is_public, launched_by, launched_at, launch_notes)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                feature_key,
                launch_data.get('is_public', False),
                launch_data.get('launched_by', ''),
                launch_data.get('launched_at', datetime.utcnow().isoformat()),
                launch_data.get('launch_notes', '')
            ))
        
        # Sync user permissions from S3 users.json
        users = get_users_config()
        for user in users:
            discord_id = get_user_field(user, 'identity.discord_id')
            user_feature_perms = get_user_field(user, 'account.feature_permissions') or user.get('feature_permissions', {})
            
            for feature_key, perm_data in user_feature_perms.items():
                if perm_data.get('has_access', False):
                    cursor.execute('''
                        INSERT OR REPLACE INTO user_feature_access (discord_id, feature_key, has_access, granted_by)
                        VALUES (?, ?, ?, ?)
                    ''', (
                        discord_id,
                        feature_key,
                        True,
                        perm_data.get('granted_by', '')
                    ))
        
        conn.commit()
        print("Successfully synced S3 feature config to database")
        
    except Exception as e:
        print(f"Error syncing S3 to database: {e}")

def get_user_record(discord_id):
    users = get_users_config()
    # Handle both string and integer discord_ids for compatibility
    discord_id_str = str(discord_id)
    
    try:
        discord_id_int = int(discord_id)
    except (ValueError, TypeError):
        discord_id_int = None
    
    # Try to find user with either string or integer ID (works with both old and new schema)
    user = None
    for u in users:
        user_discord_id = get_user_field(u, 'identity.discord_id') or u.get('discord_id')
        if str(user_discord_id) == discord_id_str:
            user = u
            break
        if discord_id_int is not None and user_discord_id == discord_id_int:
            user = u
            break
    
    # Normalize the user to new schema and ensure discord_id is string
    if user:
        user = normalize_user(user)
        # Ensure discord_id is consistently a string
        set_user_field(user, 'identity.discord_id', discord_id_str)
    
    return user

def validate_and_fix_token_data(tokens):
    """
    Ensure token data has all required fields with proper types to prevent NoneType arithmetic errors.
    """
    import time
    
    if not tokens:
        return tokens
    
    # Ensure expires_in is a valid integer
    if tokens.get('expires_in') is None:
        tokens['expires_in'] = 3599  # Default 1 hour
    
    # Ensure we have an issued_at timestamp
    if tokens.get('issued_at') is None:
        tokens['issued_at'] = int(time.time())
    
    # Ensure expires_at is calculated properly
    issued_at = tokens.get('issued_at', int(time.time()))
    expires_in = tokens.get('expires_in', 3599)
    
    # Defensive check to ensure both are integers
    if not isinstance(issued_at, (int, float)):
        issued_at = int(time.time())
        tokens['issued_at'] = issued_at
    
    if not isinstance(expires_in, (int, float)):
        expires_in = 3599
        tokens['expires_in'] = expires_in
    
    tokens['expires_at'] = int(issued_at) + int(expires_in)
    
    return tokens


def refresh_google_token(user_record):
    print(f"[refresh_google_token] Starting token refresh for user: {get_user_field(user_record, 'identity.discord_id')}")
    google_tokens = get_user_field(user_record, 'integrations.google.tokens') or {}
    refresh_token = google_tokens.get("refresh_token")
    if not refresh_token:
        print(f"[refresh_google_token] No refresh token found")
        raise Exception("No refresh_token found. User must re-link Google account.")

    print(f"[refresh_google_token] Using refresh token: {refresh_token[:20] if refresh_token else 'None'}...")
    token_url = "https://oauth2.googleapis.com/token"
    payload = {
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token"
    }
    resp = requests.post(token_url, data=payload)
    print(f"[refresh_google_token] Token refresh response status: {resp.status_code}")
    resp.raise_for_status()
    new_tokens = resp.json()
    
    if "refresh_token" not in new_tokens:
        new_tokens["refresh_token"] = refresh_token

    # Validate and fix token data to prevent NoneType arithmetic errors
    new_tokens = validate_and_fix_token_data(new_tokens)

    google_tokens = get_user_field(user_record, 'integrations.google.tokens') or {}
    google_tokens.update(new_tokens)
    set_user_field(user_record, 'integrations.google.tokens', google_tokens)
    
    # Update the users config with the refreshed tokens
    users = get_users_config()
    discord_id = get_user_field(user_record, 'identity.discord_id')
    print(f"[refresh_google_token] Updating user config for discord_id: {discord_id}")
    for i, user in enumerate(users):
        if get_user_field(user, 'identity.discord_id') == discord_id:
            users[i] = user_record
            print(f"[refresh_google_token] Found and updated user at index {i}")
            break
    update_users_config(users)
    print(f"[refresh_google_token] Token refresh completed successfully")
    return new_tokens["access_token"]

def safe_google_api_call(user_record, api_call_func):
    google_tokens = get_user_field(user_record, 'integrations.google.tokens') or {}
    access_token = google_tokens.get("access_token")
    print(f"[safe_google_api_call] Starting API call with token: {access_token[:20] if access_token else 'None'}...")
    try:
        result = api_call_func(access_token)
        print(f"[safe_google_api_call] API call succeeded")
        return result
    except Exception as e:
        # Check for various forms of authentication errors
        error_str = str(e)
        print(f"[safe_google_api_call] API call failed with error: {error_str}")
        if any(indicator in error_str for indicator in ["401", "Invalid Credentials", "UNAUTHENTICATED", "authError"]):
            print(f"[safe_google_api_call] Token refresh needed due to: {error_str}")
            try:
                new_access = refresh_google_token(user_record)
                print(f"[safe_google_api_call] Token refreshed successfully, new token: {new_access[:20] if new_access else 'None'}...")
                result = api_call_func(new_access)
                print(f"[safe_google_api_call] Retry with new token succeeded")
                return result
            except Exception as refresh_error:
                print(f"[safe_google_api_call] Token refresh or retry failed: {refresh_error}")
                raise
        else:
            print(f"[safe_google_api_call] Non-auth error, re-raising: {error_str}")
            raise

@app.route('/auth/discord')
def discord_login():
    # Discord OAuth redirect URI configured
    
    # Get invitation token from query parameters
    invitation_token = request.args.get('invitation')
    pass  # Process invitation token
    state_param = f"&state={invitation_token}" if invitation_token else ""
    # State parameter set
    
    discord_auth_url = (
        f"https://discord.com/api/oauth2/authorize"
        f"?client_id={DISCORD_CLIENT_ID}"
        f"&redirect_uri={urllib.parse.quote(DISCORD_REDIRECT_URI)}"
        f"&response_type=code"
        f"&scope=identify"
        f"{state_param}"
    )
    # Discord auth URL generated
    return redirect(discord_auth_url)

@app.route('/auth/discord/callback')
def discord_callback():
    code = request.args.get('code')
    if not code:
        return jsonify({'error': 'No authorization code provided'}), 400

    # Exchange code for access token
    token_data = {
        'client_id': DISCORD_CLIENT_ID,
        'client_secret': DISCORD_CLIENT_SECRET,
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': DISCORD_REDIRECT_URI,
    }
    
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    token_response = requests.post('https://discord.com/api/oauth2/token', data=token_data, headers=headers)
    
    if token_response.status_code != 200:
        return jsonify({'error': 'Failed to get access token'}), 400
    
    token_json = token_response.json()
    access_token = token_json['access_token']
    
    # Get user info
    user_response = requests.get('https://discord.com/api/users/@me', 
                                headers={'Authorization': f'Bearer {access_token}'})
    
    if user_response.status_code != 200:
        return jsonify({'error': 'Failed to get user info'}), 400
    
    user_data = user_response.json()
    discord_id = user_data['id']
    discord_username = user_data['username']
    
    # Check if user is already registered or has a valid invitation
    users = get_users_config()
    existing_user = next((u for u in users if get_user_field(u, 'identity.discord_id') == discord_id), None)
    
    # Check for invitation token from state parameter (runs for both new and existing users)
    invitation_token = request.args.get('state')  # Discord passes our state parameter back
    print(f"[DISCORD_CALLBACK] Invitation token from state: {invitation_token}")
    
    # Initialize valid_invitation outside scope so it's available later
    valid_invitation = None
    
    # Check for invitation token regardless of whether user exists
    # This allows existing users to be converted to subusers
    if invitation_token:
        # Validate invitation token
        invitations = get_invitations_config()
        print(f"[DISCORD_CALLBACK] Found {len(invitations)} invitations to check")
        # Check invitations for valid token
        for inv in invitations:
            print(f"[DISCORD_CALLBACK] Checking invitation: {inv.get('token')} == {invitation_token}, status: {inv.get('status')}")
            if inv['token'] == invitation_token and inv['status'] == 'pending':
                # Check if invitation is not expired (7 days)
                try:
                    # Parse created_at timestamp (strip any timezone suffix for consistency)
                    created_at_str = inv['created_at'].replace('Z', '').replace('+00:00', '')
                    invitation_date = datetime.fromisoformat(created_at_str)
                    # Use UTC for both comparisons to avoid timezone issues
                    current_time = datetime.utcnow()
                    time_diff = current_time - invitation_date
                    pass  # Check invitation expiry
                    if time_diff < timedelta(days=7):
                        print(f"[DISCORD_CALLBACK] Found valid invitation: {inv}")
                        valid_invitation = inv
                        break
                    else:
                        print(f"[DISCORD_CALLBACK] Invitation expired: {time_diff.days} days old")
                except Exception as date_error:
                    print(f"[DISCORD_CALLBACK] Date parsing error, treating as valid: {date_error}")
                    # If date parsing fails, allow the invitation (fallback)
                    valid_invitation = inv
                    break
            else:
                pass  # Invitation mismatch
        
        # Clean up the invitation only after successful validation
        if valid_invitation:
            invitations = [inv for inv in invitations if inv['token'] != invitation_token]
            update_invitations_config(invitations)
            # Removed accepted invitation from list
    
    # Check if user exists or has valid invitation
    if not existing_user and not valid_invitation:
        # New user without invitation - reject
        return redirect("https://dms-amazon.vercel.app/login?error=no_invitation")
    
    session['discord_id'] = discord_id
    session['discord_username'] = discord_username  
    session['discord_avatar'] = user_data.get('avatar')
    
    
    # Session configured with Discord ID
    
    # Save Discord username to user record for admin panel
    try:
        users = get_users_config()
        discord_id = session['discord_id']
        user_record = next((u for u in users if get_user_field(u, 'identity.discord_id') == discord_id), None)
        
        print(f"[USER_HANDLING] existing user_record: {bool(user_record)}")
        print(f"[USER_HANDLING] valid_invitation: {valid_invitation}")
        
        if user_record is None:
            print(f"[USER_CREATE] Creating new user record")
            
            # Check if this is a sub-user invitation
            if valid_invitation:
                print(f"[USER_CREATE] Processing invitation: {valid_invitation}")
                print(f"[USER_CREATE] Invitation type: {valid_invitation.get('user_type', 'main')}")
                if valid_invitation.get('user_type') == 'subuser':
                    # Create user record with subuser fields pre-populated to avoid normalization override
                    user_record = {
                        "discord_id": discord_id,
                        "user_type": "subuser",  # Old schema field for migration compatibility
                        "parent_user_id": valid_invitation.get('parent_user_id'),
                        "permissions": valid_invitation.get('permissions', ['reimbursements_analysis']),
                        "va_name": valid_invitation.get('va_name', ''),
                        "email": valid_invitation.get('email'),
                        "profile_configured": True  # Old schema field for migration compatibility
                    }
                    print(f"[USER_CREATE] Created subuser with parent: {valid_invitation.get('parent_user_id')}")
                else:
                    user_record = {"discord_id": discord_id}
                    print(f"[USER_CREATE] Created main user")
            else:
                user_record = {"discord_id": discord_id}
                print(f"[USER_CREATE] Created main user (no invitation)")
                
            users.append(user_record)
        else:
            # Handle existing users with invitations (e.g., converting to subuser)
            if valid_invitation:
                print(f"[USER_UPDATE] Processing invitation for existing user: {valid_invitation}")
                if valid_invitation.get('user_type') == 'subuser':
                    set_user_field(user_record, 'account.user_type', 'subuser')
                    set_user_field(user_record, 'account.parent_user_id', valid_invitation.get('parent_user_id'))
                    set_user_field(user_record, 'account.permissions', valid_invitation.get('permissions', ['reimbursements_analysis']))
                    set_user_field(user_record, 'identity.va_name', valid_invitation.get('va_name', ''))
                    set_user_field(user_record, 'identity.email', valid_invitation.get('email'))
                    set_user_field(user_record, 'profile.configured', True)  # Subusers inherit parent's config
                    print(f"[USER_UPDATE] Converted existing user to subuser with parent: {valid_invitation.get('parent_user_id')}")
        
        # Update Discord username, avatar, and last activity in permanent record
        set_user_field(user_record, 'identity.discord_username', user_data['username'])
        set_user_field(user_record, 'identity.avatar', user_data.get('avatar'))
        # Update last activity using helper function
        update_user_last_activity(discord_id)
        update_users_config(users)
        # User record updated with Discord data
    except Exception as e:
        # Failed to update user record
        pass
    
    # FORCE redirect to Vercel frontend - UPDATED
    frontend_url = "https://dms-amazon.vercel.app/dashboard"
    # Redirecting to frontend after Discord auth
    
    # Dynamic redirect based on environment (backup)
    # if os.environ.get('FRONTEND_URL'):
    #     frontend_url = f"{os.environ.get('FRONTEND_URL')}/dashboard"
    
    return redirect(frontend_url)

@app.route('/auth/logout')
def logout():
    session.clear()
    return jsonify({'message': 'Logged out successfully'})

@app.route('/auth/amazon-seller')
@login_required
def amazon_seller_auth():
    """Initiate Amazon Seller authorization"""
    try:
        # Get Amazon OAuth credentials
        client_id = os.getenv('SP_API_LWA_APP_ID')
        redirect_uri = os.getenv('AMAZON_REDIRECT_URI', 'https://internet-money-tools-production.up.railway.app/auth/amazon-seller/callback')
        
        if not client_id:
            return jsonify({'error': 'Amazon OAuth not configured'}), 500
        
        # Generate state parameter for CSRF protection
        state = secrets.token_urlsafe(32)
        session['amazon_oauth_state'] = state
        
        # Amazon OAuth URL for Seller Partner API
        # Using the correct Amazon OAuth endpoint for SP-API
        amazon_auth_url = (
            f"https://sellercentral.amazon.com/apps/authorize/consent"
            f"?application_id={client_id}"
            f"&state={state}"
            f"&redirect_uri={redirect_uri}"
        )
        
        # Generated Amazon OAuth URL
        
        return redirect(amazon_auth_url)
        
    except Exception as e:
        pass  # Error initiating authorization
        return jsonify({'error': 'Failed to initiate Amazon authorization'}), 500

@app.route('/auth/amazon-seller/callback')
@login_required
def amazon_seller_callback():
    """Handle Amazon Seller authorization callback"""
    try:
        # Verify state parameter
        state = request.args.get('state')
        stored_state = session.pop('amazon_oauth_state', None)
        
        if not state or state != stored_state:
            return redirect("https://dms-amazon.vercel.app/dashboard?error=amazon_auth_invalid_state")
        
        # Get authorization code
        code = request.args.get('spapi_oauth_code')
        selling_partner_id = request.args.get('selling_partner_id')
        
        if not code:
            return redirect("https://dms-amazon.vercel.app/dashboard?error=amazon_auth_no_code")
        
        # Exchange code for refresh token
        refresh_token = exchange_amazon_auth_code(code)
        if not refresh_token:
            return redirect("https://dms-amazon.vercel.app/dashboard?error=amazon_auth_token_exchange_failed")
        
        # Encrypt and store the refresh token
        encrypted_token = encrypt_token(refresh_token)
        if not encrypted_token:
            return redirect("https://dms-amazon.vercel.app/dashboard?error=amazon_auth_encryption_failed")
        
        # Update user record with Amazon credentials
        discord_id = session.get('discord_id')
        users = get_users_config()
        
        for user in users:
            if get_user_field(user, 'identity.discord_id') == discord_id:
                set_user_field(user, 'integrations.amazon.refresh_token', encrypted_token)
                set_user_field(user, 'integrations.amazon.selling_partner_id', selling_partner_id)
                set_user_field(user, 'integrations.amazon.connected_at', datetime.now().isoformat())
                break
        
        save_users_config(users)
        
        # Successfully connected Amazon account
        return redirect("https://dms-amazon.vercel.app/dashboard?success=amazon_connected")
        
    except Exception as e:
        pass  # Amazon auth callback error
        return redirect("https://dms-amazon.vercel.app/dashboard?error=amazon_auth_callback_failed")

@app.route('/api/amazon-seller/disconnect', methods=['POST'])
@login_required
def disconnect_amazon_seller():
    """Disconnect Amazon Seller account"""
    try:
        discord_id = session.get('discord_id')
        users = get_users_config()
        
        for user in users:
            if get_user_field(user, 'identity.discord_id') == discord_id:
                # Remove Amazon credentials
                set_user_field(user, 'integrations.amazon.refresh_token', None)
                set_user_field(user, 'integrations.amazon.selling_partner_id', None)
                set_user_field(user, 'integrations.amazon.connected_at', None)
                break
        
        save_users_config(users)
        
        # Disconnected Amazon account
        return jsonify({'message': 'Amazon account disconnected successfully'})
        
    except Exception as e:
        pass  # Amazon disconnect error
        return jsonify({'error': 'Failed to disconnect Amazon account'}), 500

@app.route('/api/amazon-seller/status')
@login_required
def amazon_seller_status():
    """Get Amazon Seller connection status"""
    try:
        discord_id = session.get('discord_id')
        user_record = get_user_record(discord_id)
        
        # Check Amazon connection status
        amazon_connected = False
        amazon_connected_at = None
        selling_partner_id = None
        
        if user_record and get_user_field(user_record, 'account.user_type') == 'subuser':
            parent_user = get_parent_user_record(discord_id)
            if parent_user:
                amazon_connected = get_user_amazon_refresh_token(parent_user) is not None
                amazon_connected_at = get_user_field(parent_user, 'integrations.amazon.connected_at') or parent_user.get('amazon_connected_at')
                selling_partner_id = get_user_field(parent_user, 'integrations.amazon.selling_partner_id') or parent_user.get('amazon_selling_partner_id')
        else:
            if user_record:
                amazon_connected = get_user_amazon_refresh_token(user_record) is not None
                amazon_connected_at = get_user_field(user_record, 'integrations.amazon.connected_at') or user_record.get('amazon_connected_at')
                selling_partner_id = get_user_field(user_record, 'integrations.amazon.selling_partner_id') or user_record.get('amazon_selling_partner_id')
        
        # Check if environment credentials are available
        env_credentials_available = bool(os.getenv('SP_API_REFRESH_TOKEN') and 
                                       os.getenv('SP_API_LWA_APP_ID') and 
                                       os.getenv('SP_API_LWA_CLIENT_SECRET'))
        
        return jsonify({
            'connected': amazon_connected,
            'connected_at': amazon_connected_at,
            'selling_partner_id': selling_partner_id,
            'env_credentials_available': env_credentials_available,
            'sandbox_mode': os.getenv('SP_API_SANDBOX', 'false').lower() == 'true',
            'auth_url': '/auth/amazon-seller' if not amazon_connected else None
        })
        
    except Exception as e:
        pass  # Amazon status error
        return jsonify({'error': 'Failed to get Amazon connection status'}), 500

@app.route('/api/amazon-seller/test')
@login_required
def test_amazon_connection():
    """Test Amazon SP-API connection (admin only)"""
    try:
        # Check if user is admin
        discord_id = session.get('discord_id')
        if not is_admin_user(discord_id):
            return jsonify({'error': 'SP-API testing is restricted to admin users'}), 403
        
        # Check if SP-API is disabled for this user
        user_record = get_user_record(discord_id)
        disable_sp_api = get_user_field(user_record, 'integrations.amazon.disable_sp_api') or user_record.get('disable_sp_api', False) if user_record else False
        
        if disable_sp_api:
            return jsonify({
                'error': 'SP-API is disabled',
                'message': 'SP-API testing is disabled in your settings. Enable it in Settings to test the connection.',
                'disabled': True
            }), 403
        from sp_api_client import create_sp_api_client
        
        # Get environment refresh token
        refresh_token = os.getenv('SP_API_REFRESH_TOKEN')
        if not refresh_token:
            return jsonify({'error': 'No refresh token in environment variables'}), 400
        
        # Test SP-API connection
        sp_client = create_sp_api_client(refresh_token, 'ATVPDKIKX0DER')
        if not sp_client:
            return jsonify({'error': 'Failed to create SP-API client'}), 500
        
        # Try a simple API call to test authentication
        try:
            # Debug: Print credentials structure (without sensitive data)
            # Amazon test credentials verified
            
            # Try the token refresh first to see if that works
            from sp_api.api import Tokens
            
            # Testing token refresh capability
            tokens_client = Tokens(credentials=sp_client.credentials, marketplace=sp_client.marketplace)
            
            # This is a safer test - just check if we can create a restricted data token
            # This doesn't require specific permissions and should work with basic SP-API access
            try:
                token_response = tokens_client.create_restricted_data_token(
                    restrictedResources=[{
                        "method": "GET",
                        "path": "/orders/v0/orders",
                        "dataElements": ["buyerInfo"]
                    }]
                )
                
                pass  # Token creation successful
                
                return jsonify({
                    'success': True,
                    'message': 'SP-API authentication successful (token test)',
                    'sandbox_mode': sp_client.sandbox,
                    'marketplace': str(sp_client.marketplace),
                    'marketplace_id': sp_client.marketplace_id,
                    'test_method': 'restricted_data_token'
                })
                
            except Exception as token_error:
                pass  # Token test failed, trying basic orders call
                
                # Fall back to basic orders call
                from sp_api.api import Orders
                from datetime import datetime, timedelta
                
                orders_client = Orders(credentials=sp_client.credentials, marketplace=sp_client.marketplace)
                
                # Get orders from the last day (minimal request to test auth)
                end_date = datetime.now()
                start_date = end_date - timedelta(days=1)
                
                # Making API call with date range
                
                response = orders_client.get_orders(
                    MarketplaceIds=[sp_client.marketplace_id],
                    CreatedAfter=start_date.isoformat(),
                    CreatedBefore=end_date.isoformat()
                )
                
                pass  # Orders API call successful
                
                return jsonify({
                    'success': True,
                    'message': 'SP-API authentication successful (orders test)',
                    'sandbox_mode': sp_client.sandbox,
                    'marketplace': str(sp_client.marketplace),
                    'marketplace_id': sp_client.marketplace_id,
                    'response_received': bool(hasattr(response, 'payload')),
                    'orders_count': len(response.payload.get('Orders', [])) if hasattr(response, 'payload') and response.payload else 0,
                    'test_method': 'orders_call'
                })
            
        except Exception as api_error:
            return jsonify({
                'success': False,
                'error': f'SP-API call failed: {str(api_error)}',
                'sandbox_mode': sp_client.sandbox,
                'marketplace': str(sp_client.marketplace)
            }), 400
        
    except Exception as e:
        pass  # Amazon test error
        return jsonify({'error': f'Test failed: {str(e)}'}), 500

@app.route('/api/debug/auth')
def debug_auth():
    """Debug endpoint to check authentication status"""
    return jsonify({
        'session_keys': list(session.keys()),
        'discord_id': session.get('discord_id'),
        'discord_username': session.get('discord_username'),
        'has_auth': 'discord_id' in session
    })

@app.route('/api/admin/debug-all-users')
@admin_required
def debug_all_users():
    """Debug endpoint to see all users and their types"""
    try:
        users = get_users_config()
        debug_users = []
        
        for user in users:
            debug_users.append({
                'discord_id': get_user_field(user, 'identity.discord_id'),
                'discord_username': get_user_field(user, 'identity.discord_username'),
                'user_type': get_user_field(user, 'account.user_type'),
                'parent_user_id': get_user_field(user, 'account.parent_user_id'),
                'profile_configured': get_user_field(user, 'profile.configured'),
                'va_name': get_user_field(user, 'identity.va_name'),
                'email': get_user_field(user, 'identity.email')
            })
        
        # Also check pending invitations
        invitations = get_invitations_config()
        
        return jsonify({
            'users': debug_users,
            'pending_invitations': invitations
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/user/debug-subuser')
@login_required
def debug_subuser_setup():
    """Debug endpoint to check subuser setup status"""
    discord_id = session['discord_id']
    user_record = get_user_record(discord_id)
    
    if not user_record:
        return jsonify({'error': 'User not found'}), 404
    
    debug_info = {
        'discord_id': discord_id,
        'user_type': get_user_field(user_record, 'account.user_type'),
        'parent_user_id': get_user_field(user_record, 'account.parent_user_id'),
        'profile_configured': get_user_field(user_record, 'profile.configured'),
        'raw_user_record': user_record,
    }
    
    if get_user_field(user_record, 'account.user_type') == 'subuser':
        parent_user = get_parent_user_record(discord_id)
        debug_info['parent_found'] = bool(parent_user)
        if parent_user:
            debug_info['parent_profile_configured'] = is_user_configured(parent_user)
            debug_info['parent_google_linked'] = bool(get_user_google_tokens(parent_user))
            debug_info['parent_sheet_configured'] = bool(get_user_sheet_id(parent_user))
    
    return jsonify(debug_info)

@app.route('/api/user/debug-settings')
@login_required 
def debug_user_settings():
    """Debug endpoint to check current user settings"""
    discord_id = session['discord_id']
    user_record = get_user_record(discord_id)
    
    if not user_record:
        return jsonify({'error': 'User not found'})
    
    return jsonify({
        'discord_id': discord_id,
        'is_admin': is_admin_user(discord_id),
        'raw_user_record': user_record,
        'disable_sp_api_new_schema': get_user_field(user_record, 'integrations.amazon.disable_sp_api'),
        'disable_sp_api_old_schema': user_record.get('disable_sp_api'),
        'has_integrations': 'integrations' in user_record if user_record else False,
        'has_amazon': 'amazon' in user_record.get('integrations', {}) if user_record and 'integrations' in user_record else False
    })

@app.route('/api/user')
def get_user():
    # If demo mode is OFF but we have demo user session data, clear it
    if (not DEMO_MODE and 
        session.get('discord_id') == '123456789012345678'):
        session.clear()
        return jsonify({'error': 'Authentication required'}), 401
    
    # In demo mode, return the demo user without requiring authentication
    if DEMO_MODE:
        # Set demo session for consistency
        session['discord_id'] = '123456789012345678'
        session['discord_username'] = 'DemoUser#1234'
        demo_users = get_dummy_users()
        demo_user = demo_users[0]  # Use first demo user
        
        # Use new schema helper functions
        return jsonify({
            'discord_id': get_user_discord_id(demo_user),
            'discord_username': get_user_field(demo_user, 'identity.discord_username'),
            'email': get_user_email(demo_user),
            'profile_configured': is_user_configured(demo_user),
            'google_linked': get_user_field(demo_user, 'integrations.google.linked'),
            'sheet_configured': bool(get_user_sheet_id(demo_user)),
            'amazon_connected': get_user_field(demo_user, 'integrations.amazon.configured'),
            'demo_mode': True,
            'user_type': get_user_type(demo_user),
            'permissions': get_user_permissions(demo_user),
            'last_activity': get_user_field(demo_user, 'account.last_activity'),
            'timezone': get_user_timezone(demo_user) or 'America/New_York',
            
            # Settings fields for demo compatibility
            'enable_source_links': get_user_enable_source_links(demo_user),
            'sellerboard_orders_url': get_user_sellerboard_orders_url(demo_user),
            'sellerboard_stock_url': get_user_sellerboard_stock_url(demo_user),
            'sellerboard_cogs_url': get_user_sellerboard_cogs_url(demo_user),
            'disable_sp_api': get_user_field(demo_user, 'integrations.amazon.disable_sp_api') or False,
            'search_all_worksheets': get_user_field(demo_user, 'integrations.google.search_all_worksheets') or False,
            'amazon_lead_time_days': get_user_field(demo_user, 'integrations.amazon.lead_time_days') or 90,
            'run_scripts': get_user_field(demo_user, 'settings.run_scripts') or False,
            'run_prep_center': get_user_field(demo_user, 'settings.run_prep_center') or False,
            
            'user_record': demo_user
        })
    
    # For non-demo mode, require authentication
    if 'discord_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401
        
    discord_id = session['discord_id']
    user_record = get_user_record(discord_id)
    
    # Update last activity for authenticated users
    if user_record:
        update_user_last_activity(discord_id)
    
    # Debug: log what we're finding
    print(f"[USER_API] discord_id: {discord_id}")
    print(f"[USER_API] user_record found: {bool(user_record)}")
    print(f"[USER_API] user_type: {get_user_field(user_record, 'account.user_type') if user_record else 'None'}")
    print(f"[USER_API] profile.configured: {get_user_field(user_record, 'profile.configured') if user_record else 'None'}")
    if user_record:
        print(f"[USER_API] user_record structure: {user_record}")
        print(f"[USER_API] email: {get_user_email(user_record)}")
        print(f"[USER_API] sellerboard_orders_url: {get_user_sellerboard_orders_url(user_record)}")
        print(f"[USER_API] sellerboard_stock_url: {get_user_sellerboard_stock_url(user_record)}")
        
        # Check if it's a subuser and if so, check parent
        if get_user_field(user_record, 'account.user_type') == 'subuser':
            parent_user = get_parent_user_record(discord_id)
            print(f"[USER_API] Is subuser, parent found: {bool(parent_user)}")
            if parent_user:
                print(f"[USER_API] Parent email: {get_user_email(parent_user)}")
                print(f"[USER_API] Parent sellerboard_orders_url: {get_user_sellerboard_orders_url(parent_user)}")
    
    # Check if we're in admin impersonation mode
    admin_impersonating = session.get('admin_impersonating')
    
    # For subusers, check parent's configuration status
    if user_record and get_user_field(user_record, 'account.user_type') == 'subuser':
        parent_user = get_parent_user_record(discord_id)
        profile_configured = (parent_user is not None and 
                            get_user_email(parent_user) and 
                            get_user_sellerboard_orders_url(parent_user) and 
                            get_user_sellerboard_stock_url(parent_user))
        google_linked = parent_user and get_user_google_tokens(parent_user)
        sheet_configured = parent_user and get_user_sheet_id(parent_user) is not None
    else:
        # For main users, check their own configuration
        profile_configured = (user_record is not None and 
                            get_user_email(user_record) and 
                            get_user_sellerboard_orders_url(user_record) and 
                            get_user_sellerboard_stock_url(user_record))
        google_linked = user_record and get_user_google_tokens(user_record)
        sheet_configured = user_record and get_user_sheet_id(user_record) is not None

    # Check Amazon connection status
    amazon_connected = False
    amazon_connected_at = None
    if user_record and get_user_field(user_record, 'account.user_type') == 'subuser':
        parent_user = get_parent_user_record(discord_id)
        amazon_connected = parent_user and get_user_amazon_refresh_token(parent_user) is not None
        amazon_connected_at = get_user_amazon_connected_at(parent_user) if parent_user else None
    else:
        amazon_connected = user_record and get_user_amazon_refresh_token(user_record) is not None
        amazon_connected_at = get_user_amazon_connected_at(user_record) if user_record else None

    response_data = {
        'discord_id': discord_id,
        'discord_username': session.get('discord_username'),
        'discord_avatar': session.get('discord_avatar'),
        'user_type': (get_user_field(user_record, 'account.user_type') or 'main') if user_record else 'main',
        'permissions': get_user_permissions(user_record) if user_record else ['all'],
        'parent_user_id': get_user_parent_id(user_record) if user_record else None,
        'va_name': get_user_field(user_record, 'identity.va_name') if user_record else None,
        'is_admin': is_admin_user(discord_id),
        'profile_configured': profile_configured,
        'google_linked': google_linked,
        'sheet_configured': sheet_configured,
        'amazon_connected': amazon_connected,
        'amazon_connected_at': amazon_connected_at,
        
        # Settings fields exposed for frontend compatibility (use parent config for subusers)
        'email': get_user_email(user_record) if user_record else None,
        'timezone': get_user_timezone(user_record) if user_record else None,
        'enable_source_links': get_user_enable_source_links(get_config_user_for_subuser(user_record)) if user_record else False,
        'sellerboard_orders_url': get_user_sellerboard_orders_url(get_config_user_for_subuser(user_record)) if user_record else None,
        'sellerboard_stock_url': get_user_sellerboard_stock_url(get_config_user_for_subuser(user_record)) if user_record else None,
        'sellerboard_cogs_url': get_user_sellerboard_cogs_url(get_config_user_for_subuser(user_record)) if user_record else None,
        
        # Settings with fallback to old schema for compatibility (use parent config for subusers)
        'disable_sp_api': (get_user_field(get_config_user_for_subuser(user_record), 'integrations.amazon.disable_sp_api') or get_config_user_for_subuser(user_record).get('disable_sp_api', False)) if user_record else False,
        'search_all_worksheets': (get_user_field(get_config_user_for_subuser(user_record), 'integrations.google.search_all_worksheets') or get_config_user_for_subuser(user_record).get('search_all_worksheets', False)) if user_record else False,
        'amazon_lead_time_days': (get_user_field(get_config_user_for_subuser(user_record), 'integrations.amazon.lead_time_days') or get_config_user_for_subuser(user_record).get('amazon_lead_time_days', 90)) if user_record else 90,
        'run_scripts': (get_user_field(get_config_user_for_subuser(user_record), 'settings.run_scripts') or get_config_user_for_subuser(user_record).get('run_scripts', False)) if user_record else False,
        'run_prep_center': (get_user_field(get_config_user_for_subuser(user_record), 'settings.run_prep_center') or get_config_user_for_subuser(user_record).get('run_prep_center', False)) if user_record else False,
        
        # Add user_record object for frontend compatibility (use parent config for subusers)
        'user_record': {
            'email': get_user_email(user_record) if user_record else None,  # Keep subuser's email
            'listing_loader_key': get_user_field(get_config_user_for_subuser(user_record), 'integrations.sellerboard.listing_loader_key') if user_record else None,
            'sb_file_key': get_user_field(get_config_user_for_subuser(user_record), 'integrations.sellerboard.sb_file_key') if user_record else None,
            'run_scripts': (get_user_field(get_config_user_for_subuser(user_record), 'settings.run_scripts') or get_config_user_for_subuser(user_record).get('run_scripts', False)) if user_record else False,
            'run_prep_center': (get_user_field(get_config_user_for_subuser(user_record), 'settings.run_prep_center') or get_config_user_for_subuser(user_record).get('run_prep_center', False)) if user_record else False,
            'sellerboard_orders_url': get_user_sellerboard_orders_url(get_config_user_for_subuser(user_record)) if user_record else None,
            'sellerboard_stock_url': get_user_sellerboard_stock_url(get_config_user_for_subuser(user_record)) if user_record else None,
            'sellerboard_cogs_url': get_user_sellerboard_cogs_url(get_config_user_for_subuser(user_record)) if user_record else None,
            'timezone': get_user_timezone(get_config_user_for_subuser(user_record)) if user_record else None,
            'enable_source_links': get_user_enable_source_links(get_config_user_for_subuser(user_record)) if user_record else False,
            'search_all_worksheets': (get_user_field(get_config_user_for_subuser(user_record), 'integrations.google.search_all_worksheets') or get_config_user_for_subuser(user_record).get('search_all_worksheets', False)) if user_record else False,
            'disable_sp_api': (get_user_field(get_config_user_for_subuser(user_record), 'integrations.amazon.disable_sp_api') or get_config_user_for_subuser(user_record).get('disable_sp_api', False)) if user_record else False,
            'amazon_lead_time_days': (get_user_field(get_config_user_for_subuser(user_record), 'integrations.amazon.lead_time_days') or get_config_user_for_subuser(user_record).get('amazon_lead_time_days', 90)) if user_record else 90,
            # Add sheet configuration fields for SheetConfig component
            'sheet_id': get_user_sheet_id(get_config_user_for_subuser(user_record)) if user_record else None,
            'worksheet_title': get_user_worksheet_title(get_config_user_for_subuser(user_record)) if user_record else None,
            'column_mapping': get_user_column_mapping(get_config_user_for_subuser(user_record)) if user_record else {}
        }
    }
    
    # Add impersonation info if applicable
    if admin_impersonating:
        response_data['admin_impersonating'] = True
        response_data['original_admin_id'] = admin_impersonating['original_discord_id']
        response_data['original_admin_username'] = admin_impersonating['original_discord_username']
        # Return impersonated user data
    
    # Debug log the response for subusers
    if response_data.get('user_type') == 'subuser':
        print(f"[USER_API] Subuser response:")
        print(f"  - user_type: {response_data.get('user_type')}")
        print(f"  - profile_configured: {response_data.get('profile_configured')}")
        print(f"  - google_linked: {response_data.get('google_linked')}")
        print(f"  - sheet_configured: {response_data.get('sheet_configured')}")
    
    return jsonify(response_data)

@app.route('/api/user/profile', methods=['POST'])
@login_required
def update_profile():
    discord_id = session['discord_id']
    data = request.json
    
    users = get_users_config()
    
    # Find the user and normalize it immediately to avoid reference issues
    user_index = None
    for i, u in enumerate(users):
        if get_user_discord_id(u) == discord_id:
            users[i] = normalize_user(u)  # Normalize in place
            user_index = i
            break
    
    user_record = users[user_index] if user_index is not None else None
    
    if user_record is None:
        # Create new user with proper schema
        user_record = {
            "user_id": f"user_{discord_id}_{datetime.now().strftime('%Y%m%d')}",
            "identity": {"discord_id": discord_id, "email": None, "username": None, "avatar": None},
            "account": {"access_token": None, "refresh_token": None, "is_admin": False, "parent_user": None, "created_at": datetime.now().isoformat(), "last_login": None},
            "profile": {"configured": False, "timezone": "UTC"},
            "integrations": {"amazon": {"refresh_token": None, "selling_partner_id": None, "access_token": None, "token_expires": None, "marketplace_id": None, "country_code": "US"}, "sellerboard": {"orders_url": None, "ppc_url": None, "inventory_url": None, "products_url": None, "refunds_url": None, "fba_returns_url": None, "reimbursements_url": None, "storage_fees_url": None}, "google": {"tokens": {}}},
            "files": {"sheet_id": None},
            "settings": {"email_notifications": True, "monitoring": {"enabled": True, "check_interval": 24}, "features": {}, "preferences": {}}
        }
        users.append(user_record)
    
    # Check if user is a subuser - they can only update their timezone
    if get_user_field(user_record, 'account.user_type') == 'subuser':
        # Only allow timezone updates for subusers
        if 'timezone' in data:
            set_user_field(user_record, 'profile.timezone', data['timezone'])
        # Update last activity using helper function
        update_user_last_activity(get_user_field(user_record, 'identity.discord_id'))
        if 'discord_username' in session:
            set_user_field(user_record, 'identity.discord_username', session['discord_username'])
        if 'discord_avatar' in session:
            set_user_field(user_record, 'identity.avatar', session['discord_avatar'])
        
        if update_users_config(users):
            return jsonify({'message': 'Timezone updated successfully'})
        else:
            return jsonify({'error': 'Failed to update timezone'}), 500
    
    # For main users, allow all updates
    # Always update Discord username and last activity from session when available
    if 'discord_username' in session:
        set_user_field(user_record, 'identity.discord_username', session['discord_username'])
    if 'discord_avatar' in session:
        set_user_field(user_record, 'identity.avatar', session['discord_avatar'])
    set_user_field(user_record, 'account.last_activity', datetime.now().isoformat())
    
    # Update user profile fields
    if 'email' in data:
        set_user_field(user_record, 'identity.email', data['email'])
    if 'run_scripts' in data:
        set_user_field(user_record, 'settings.run_scripts', data['run_scripts'])
    if 'run_prep_center' in data:
        set_user_field(user_record, 'settings.run_prep_center', data['run_prep_center'])
    # Note: listing_loader_key and sb_file_key are now deprecated
    # Files are automatically detected from uploaded_files array
    if 'sellerboard_orders_url' in data:
        set_user_field(user_record, 'integrations.sellerboard.orders_url', data['sellerboard_orders_url'])
    if 'sellerboard_stock_url' in data:
        set_user_field(user_record, 'integrations.sellerboard.stock_url', data['sellerboard_stock_url'])
    if 'sellerboard_cogs_url' in data:
        set_user_field(user_record, 'integrations.sellerboard.cogs_url', data['sellerboard_cogs_url'])
    if 'timezone' in data:
        set_user_field(user_record, 'profile.timezone', data['timezone'])
    if 'enable_source_links' in data:
        set_user_field(user_record, 'settings.enable_source_links', data['enable_source_links'])
    if 'search_all_worksheets' in data:
        set_user_field(user_record, 'integrations.google.search_all_worksheets', data['search_all_worksheets'])
    if 'disable_sp_api' in data:
        set_user_field(user_record, 'integrations.amazon.disable_sp_api', data['disable_sp_api'])
    if 'amazon_lead_time_days' in data:
        # Validate lead time is within reasonable bounds
        lead_time = data['amazon_lead_time_days']
        try:
            lead_time_int = int(lead_time)
            if 30 <= lead_time_int <= 180:
                set_user_field(user_record, 'integrations.amazon.lead_time_days', lead_time_int)
            else:
                return jsonify({'error': 'Amazon lead time must be between 30 and 180 days'}), 400
        except (ValueError, TypeError):
            return jsonify({'error': 'Amazon lead time must be a valid number between 30 and 180 days'}), 400
    
    # Check if user is now configured after profile updates
    if is_user_configured(user_record):
        set_user_field(user_record, 'profile.configured', True)
        set_user_field(user_record, 'profile.setup_step', 'completed')
    
    if update_users_config(users):
        return jsonify({'message': 'Profile updated successfully'})
    else:
        return jsonify({'error': 'Failed to update profile'}), 500

@app.route('/api/google/auth-url')
@login_required
def get_google_auth_url():
    discord_id = session['discord_id']
    base_url = "https://accounts.google.com/o/oauth2/v2/auth"
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/spreadsheets https://www.googleapis.com/auth/drive.readonly https://www.googleapis.com/auth/gmail.readonly",
        "access_type": "offline",
        "prompt": "consent",
        "state": str(discord_id)
    }
    oauth_url = f"{base_url}?{urllib.parse.urlencode(params)}"
    return jsonify({'auth_url': oauth_url})

@app.route('/api/google/complete-auth', methods=['POST'])
@login_required
def complete_google_auth():
    data = request.json
    code = data.get('code')
    
    if not code:
        return jsonify({'error': 'Authorization code required'}), 400
    
    try:
        token_url = "https://oauth2.googleapis.com/token"
        payload = {
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code"
        }
        token_response = requests.post(token_url, data=payload)
        token_response.raise_for_status()
        tokens = token_response.json()
        
        discord_id = session['discord_id']
        users = get_users_config()
        user_record = next((u for u in users if get_user_field(u, 'identity.discord_id') == discord_id), None)
        
        if user_record is None:
            # Create new user with proper schema
            user_record = {
                "user_id": f"user_{discord_id}_{datetime.now().strftime('%Y%m%d')}",
                "identity": {"discord_id": discord_id, "email": None, "username": None, "avatar": None},
                "account": {"access_token": None, "refresh_token": None, "is_admin": False, "parent_user": None, "created_at": datetime.now().isoformat(), "last_login": None},
                "profile": {"configured": False, "timezone": "UTC"},
                "integrations": {"amazon": {"refresh_token": None, "selling_partner_id": None, "access_token": None, "token_expires": None, "marketplace_id": None, "country_code": "US"}, "sellerboard": {"orders_url": None, "ppc_url": None, "inventory_url": None, "products_url": None, "refunds_url": None, "fba_returns_url": None, "reimbursements_url": None, "storage_fees_url": None}, "google": {"tokens": {}}},
                "files": {"sheet_id": None},
                "settings": {"email_notifications": True, "monitoring": {"enabled": True, "check_interval": 24}, "features": {}, "preferences": {}}
            }
            users.append(user_record)
        
        old_tokens = get_user_field(user_record, 'integrations.google.tokens') or {}
        if "refresh_token" not in tokens and "refresh_token" in old_tokens:
            tokens["refresh_token"] = old_tokens["refresh_token"]
        
        set_user_field(user_record, 'integrations.google.tokens', tokens)
        
        if update_users_config(users):
            return jsonify({'message': 'Google account linked successfully'})
        else:
            return jsonify({'error': 'Failed to save Google tokens'}), 500
            
    except Exception as e:
        return jsonify({'error': f'Error completing Google OAuth: {str(e)}'}), 500

@app.route('/api/google/disconnect', methods=['POST'])
@login_required
def disconnect_google():
    """Disconnect user's Google account"""
    discord_id = session['discord_id']
    users = get_users_config()
    user_record = next((u for u in users if get_user_field(u, 'identity.discord_id') == discord_id), None)
    
    if not user_record:
        return jsonify({'error': 'User not found'}), 404
    
    # Remove Google tokens and sheet configuration
    set_user_field(user_record, 'integrations.google.tokens', {})
    set_user_field(user_record, 'files.sheet_id', None)
    set_user_field(user_record, 'integrations.google.worksheet_title', None)
    set_user_field(user_record, 'integrations.google.column_mapping', {})
    
    if update_users_config(users):
        return jsonify({'message': 'Google account disconnected successfully'})
    else:
        return jsonify({'error': 'Failed to disconnect Google account'}), 500

# Admin-only discount monitoring Gmail OAuth endpoints
@app.route('/api/admin/discount-monitoring/gmail/auth-url')
@admin_required
def get_admin_discount_gmail_auth_url():
    """Get Google OAuth URL for system-wide discount monitoring Gmail access (Admin only)"""
    scopes = ['https://www.googleapis.com/auth/gmail.readonly']
    auth_url = f"https://accounts.google.com/o/oauth2/auth?response_type=code&client_id={GOOGLE_CLIENT_ID}&redirect_uri={GOOGLE_REDIRECT_URI}&scope={'+'.join(scopes)}&access_type=offline&prompt=consent&state=admin_discount_monitoring"
    
    return jsonify({'auth_url': auth_url})

@app.route('/api/admin/discount-monitoring/gmail/complete-auth', methods=['POST'])
@admin_required
def complete_admin_discount_gmail_auth():
    """Complete Google OAuth for system-wide discount monitoring Gmail access (Admin only)"""
    try:
        data = request.get_json()
        code = data.get('code')
        state = data.get('state')
        
        # Verify this is for admin discount monitoring
        if state != 'admin_discount_monitoring':
            return jsonify({'error': 'Invalid state parameter'}), 400
        
        if not code:
            return jsonify({'error': 'Authorization code is required'}), 400
        
        # Exchange code for tokens
        token_url = "https://oauth2.googleapis.com/token"
        token_data = {
            'code': code,
            'client_id': GOOGLE_CLIENT_ID,
            'client_secret': GOOGLE_CLIENT_SECRET,
            'redirect_uri': GOOGLE_REDIRECT_URI,
            'grant_type': 'authorization_code'
        }
        
        response = requests.post(token_url, data=token_data)
        
        if response.status_code != 200:
            return jsonify({'error': 'Failed to exchange authorization code for tokens'}), 400
        
        tokens = response.json()
        
        # Get Gmail profile to verify which account was connected
        access_token = tokens.get('access_token')
        gmail_email = 'Unknown'
        
        if access_token:
            try:
                profile_response = requests.get(
                    'https://gmail.googleapis.com/gmail/v1/users/me/profile',
                    headers={'Authorization': f'Bearer {access_token}'}
                )
                if profile_response.status_code == 200:
                    profile_data = profile_response.json()
                    gmail_email = profile_data.get('emailAddress')
                    print(f"[INFO] Connected system-wide discount monitoring Gmail: {gmail_email}")
            except Exception as e:
                print(f"Error getting Gmail profile: {e}")
        
        # Store in system-wide admin config
        admin_config = {
            'tokens': tokens,
            'gmail_email': gmail_email,
            'connected_at': datetime.now().isoformat(),
            'connected_by_admin': session.get('discord_id')
        }
        
        if save_admin_gmail_config(admin_config):
            return jsonify({
                'message': 'System-wide discount monitoring Gmail connected successfully',
                'gmail_email': gmail_email,
                'note': 'All users will now use this Gmail account for discount opportunities'
            })
        else:
            return jsonify({'error': 'Failed to save Gmail configuration'}), 500
            
    except Exception as e:
        print(f"Error completing admin discount Gmail auth: {e}")
        return jsonify({'error': 'Failed to complete Gmail authentication'}), 500

@app.route('/api/admin/discount-monitoring/gmail/disconnect', methods=['POST'])
@admin_required
def disconnect_admin_discount_gmail():
    """Disconnect system-wide discount monitoring Gmail access (Admin only)"""
    if save_admin_gmail_config(None):
        return jsonify({
            'message': 'System-wide discount monitoring Gmail disconnected successfully',
            'note': 'All users will now see mock data for discount opportunities'
        })
    else:
        return jsonify({'error': 'Failed to disconnect Gmail'}), 500

@app.route('/api/discount-monitoring/gmail/status')
@login_required 
def get_discount_gmail_status():
    """Get status of system-wide discount monitoring Gmail connection"""
    discount_config = get_discount_email_config()
    
    if discount_config and discount_config.get('tokens'):
        return jsonify({
            'connected': True,
            'gmail_email': discount_config.get('email_address', 'Unknown'),
            'message': 'System-wide discount monitoring Gmail is connected',
            'connected_at': discount_config.get('connected_at'),
            'is_system_wide': True
        })
    else:
        return jsonify({
            'connected': False,
            'gmail_email': None,
            'message': 'System-wide discount monitoring Gmail not configured',
            'note': 'Admin needs to connect Gmail for discount monitoring',
            'is_system_wide': True
        })

@app.route('/admin/gmail-setup')
@admin_required
def gmail_setup_page():
    """Admin page for setting up Gmail for discount monitoring"""
    return send_from_directory('.', 'gmail-setup.html')

@app.route('/api/google/spreadsheets')
@login_required
def list_spreadsheets():
    # Return dummy data in demo mode
    if DEMO_MODE:
        dummy_data = get_dummy_sheet_data()
        return jsonify({'spreadsheets': dummy_data['spreadsheets']})
    
    discord_id = session['discord_id']
    user_record = get_user_record(discord_id)
    
    if not user_record:
        return jsonify({'error': 'User not found'}), 404
    
    # Get user config for Google access (use parent config for subusers)
    config_user_record = user_record
    if user_record and get_user_field(user_record, 'account.user_type') == 'subuser':
        parent_user_id = get_user_field(user_record, 'account.parent_user_id')
        if parent_user_id:
            parent_record = get_user_record(parent_user_id)
            if parent_record:
                config_user_record = parent_record
    
    if not get_user_field(config_user_record, 'integrations.google.tokens'):
        return jsonify({'error': 'Google account not linked'}), 400
    
    try:
        def api_call(access_token):
            url = "https://www.googleapis.com/drive/v3/files"
            query = "mimeType='application/vnd.google-apps.spreadsheet'"
            params = {"q": query, "fields": "files(id, name)"}
            headers = {"Authorization": f"Bearer {access_token}"}
            response = requests.get(url, params=params, headers=headers)
            if response.ok:
                data = response.json()
                return data.get("files", [])
            else:
                raise Exception(f"Error listing spreadsheets: {response.text}")
        
        files = safe_google_api_call(config_user_record, api_call)
        return jsonify({'spreadsheets': files})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/google/worksheets/<spreadsheet_id>')
@login_required
def list_worksheets(spreadsheet_id):
    # Return dummy data in demo mode
    if DEMO_MODE:
        dummy_data = get_dummy_sheet_data()
        worksheets = dummy_data['worksheets'].get(spreadsheet_id, [])
        return jsonify({'worksheets': worksheets})
    
    discord_id = session['discord_id']
    user_record = get_user_record(discord_id)
    
    if not user_record:
        return jsonify({'error': 'User not found'}), 404
    
    # Get user config for Google access (use parent config for subusers)
    config_user_record = user_record
    if user_record and get_user_field(user_record, 'account.user_type') == 'subuser':
        parent_user_id = get_user_field(user_record, 'account.parent_user_id')
        if parent_user_id:
            parent_record = get_user_record(parent_user_id)
            if parent_record:
                config_user_record = parent_record
    
    if not get_user_field(config_user_record, 'integrations.google.tokens'):
        return jsonify({'error': 'Google account not linked'}), 400
    
    try:
        def api_call(access_token):
            url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}"
            params = {"fields": "sheets(properties(sheetId,title))"}
            headers = {"Authorization": f"Bearer {access_token}"}
            r = requests.get(url, params=params, headers=headers)
            r.raise_for_status()
            sheets = r.json().get("sheets", [])
            return [s["properties"] for s in sheets]
        
        worksheets = safe_google_api_call(config_user_record, api_call)
        return jsonify({'worksheets': worksheets})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/sheet/configure', methods=['POST'])
@login_required
def configure_sheet():
    discord_id = session['discord_id']
    data = request.json
    
    spreadsheet_id = data.get('spreadsheet_id')
    worksheet_title = data.get('worksheet_title')
    column_mapping = data.get('column_mapping')
    if not all([spreadsheet_id, worksheet_title, column_mapping]):
        return jsonify({'error': 'Missing required fields'}), 400
    
    users = get_users_config()
    user_record = next((u for u in users if get_user_field(u, 'identity.discord_id') == discord_id), None)
    
    if not user_record:
        return jsonify({'error': 'User profile not found'}), 404
    
    set_user_field(user_record, 'files.sheet_id', spreadsheet_id)
    set_user_field(user_record, 'integrations.google.worksheet_title', worksheet_title)
    set_user_field(user_record, 'integrations.google.column_mapping', column_mapping)
    
    # Check if user is now configured and update their profile status
    if is_user_configured(user_record):
        set_user_field(user_record, 'profile.configured', True)
        set_user_field(user_record, 'profile.setup_step', 'completed')
    
    if update_users_config(users):
        return jsonify({'message': 'Sheet configuration saved successfully'})
    else:
        return jsonify({'error': 'Failed to save sheet configuration'}), 500

@app.route('/api/sheet/headers/<spreadsheet_id>/<worksheet_title>')
@login_required
def get_sheet_headers(spreadsheet_id, worksheet_title):
    discord_id = session['discord_id']
    user_record = get_user_record(discord_id)
    
    if not user_record:
        return jsonify({'error': 'User not found'}), 404
    
    # Get user config for Google access (use parent config for subusers)
    config_user_record = user_record
    if user_record and get_user_field(user_record, 'account.user_type') == 'subuser':
        parent_user_id = get_user_field(user_record, 'account.parent_user_id')
        if parent_user_id:
            parent_record = get_user_record(parent_user_id)
            if parent_record:
                config_user_record = parent_record
    
    if not get_user_field(config_user_record, 'integrations.google.tokens'):
        return jsonify({'error': 'Google account not linked'}), 400
    
    try:
        def api_call(access_token):
            range_ = f"'{worksheet_title}'!A1:Z1"
            url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{range_}"
            headers = {"Authorization": f"Bearer {access_token}"}
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            values = response.json().get("values", [])
            return values[0] if values else []
        
        headers = safe_google_api_call(config_user_record, api_call)
        return jsonify({'headers': headers})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def get_gmail_service_for_user(user_record):
    """Get Gmail API service client for a user"""
    import base64
    from email.mime.text import MIMEText
    
    def api_call(access_token):
        headers = {"Authorization": f"Bearer {access_token}"}
        return headers
    
    try:
        headers = safe_google_api_call(config_user_record, api_call)
        return headers
    except Exception as e:
        print(f"Error creating Gmail service: {e}")
        return None

def search_gmail_messages(user_record, query, max_results=500):
    """Search Gmail messages using the Gmail API"""
    try:
        def api_call(access_token):
            url = "https://gmail.googleapis.com/gmail/v1/users/me/messages"
            headers = {"Authorization": f"Bearer {access_token}"}
            params = {
                "q": query,
                "maxResults": max_results
            }
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()
        
        return safe_google_api_call(user_record, api_call)
    except Exception as e:
        print(f"Error searching Gmail messages: {e}")
        return None

def get_gmail_message(user_record, message_id):
    """Get a specific Gmail message by ID"""
    try:
        def api_call(access_token):
            url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}"
            headers = {"Authorization": f"Bearer {access_token}"}
            params = {"format": "full"}
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()
        
        return safe_google_api_call(user_record, api_call)
    except Exception as e:
        print(f"Error getting Gmail message: {e}")
        return None

def extract_email_content(message_data):
    """Extract subject, sender, date, and HTML content from Gmail message"""
    try:
        headers = message_data.get('payload', {}).get('headers', [])
        
        # Extract headers
        subject = None
        sender = None
        date = None
        
        for header in headers:
            name = header.get('name', '').lower()
            value = header.get('value', '')
            
            if name == 'subject':
                subject = value
            elif name == 'from':
                sender = value
            elif name == 'date':
                date = value
        
        # Extract HTML content
        html_content = extract_html_from_message_payload(message_data.get('payload', {}))
        
        return {
            'subject': subject,
            'sender': sender,
            'date': date,
            'html_content': html_content,
            'message_id': message_data.get('id')
        }
    except Exception as e:
        print(f"Error extracting email content: {e}")
        return None

def extract_html_from_message_payload(payload):
    """Recursively extract HTML content from Gmail message payload"""
    import base64
    
    try:
        # Check if this part has HTML content
        if payload.get('mimeType') == 'text/html':
            body_data = payload.get('body', {}).get('data')
            if body_data:
                # Decode base64 URL-safe encoding
                decoded = base64.urlsafe_b64decode(body_data + '===').decode('utf-8')
                return decoded
        
        # Check multipart content
        parts = payload.get('parts', [])
        for part in parts:
            html_content = extract_html_from_message_payload(part)
            if html_content:
                return html_content
        
        # Check if body has data directly
        body_data = payload.get('body', {}).get('data')
        if body_data and payload.get('mimeType') == 'text/plain':
            # Return plain text as fallback
            decoded = base64.urlsafe_b64decode(body_data + '===').decode('utf-8')
            return decoded
            
        return None
    except Exception as e:
        print(f"Error extracting HTML from payload: {e}")
        return None

# Discount monitoring specific Gmail functions
def get_discount_gmail_token(user_record):
    """Get Gmail access token for discount monitoring (uses separate tokens if available)"""
    # Priority 1: Use discount-specific tokens if available
    if get_user_field(user_record, 'integrations.gmail.discount_tokens') or user_record.get('discount_gmail_tokens'):
        return refresh_discount_gmail_token(user_record)
    
    # Priority 2: Fall back to regular Google tokens
    if get_user_field(user_record, 'integrations.google.tokens'):
        return refresh_google_token(user_record)
    
    return None

def refresh_discount_gmail_token(user_record):
    """Refresh discount monitoring specific Gmail tokens"""
    discount_tokens = get_user_field(user_record, 'integrations.gmail.discount_tokens') or user_record.get('discount_gmail_tokens', {})
    if not discount_tokens:
        return None
    
    try:
        # Use the same refresh logic as regular tokens
        refresh_token = discount_tokens.get('refresh_token')
        if not refresh_token:
            return None
        
        token_url = "https://oauth2.googleapis.com/token"
        data = {
            'client_id': GOOGLE_CLIENT_ID,
            'client_secret': GOOGLE_CLIENT_SECRET,
            'refresh_token': refresh_token,
            'grant_type': 'refresh_token'
        }
        
        response = requests.post(token_url, data=data)
        if response.status_code == 200:
            token_data = response.json()
            access_token = token_data.get('access_token')
            
            # Update the stored tokens with new access token
            discount_tokens['access_token'] = access_token
            set_user_field(user_record, 'integrations.gmail.discount_tokens', discount_tokens)
            
            # Save updated user config
            update_user_config(user_record)
            
            return access_token
        else:
            print(f"Error refreshing discount Gmail token: {response.status_code}")
            return None
    except Exception as e:
        print(f"Error refreshing discount Gmail token: {e}")
        return None

# Admin Gmail config management
def get_discount_email_config():
    """Get discount email configuration from S3"""
    if DEMO_MODE:
        return {
            'email_address': 'demo@distill.io',
            'config_type': 'gmail_oauth',
            'gmail_email': 'demo@distill.io',
            'connected_at': '2024-01-01T00:00:00Z',
            'is_s3_config': True,
            'subject_pattern': r'\[([^\]]+)\]\s*Alert:\s*[^\(]*\(ASIN:\s*([B0-9A-Z]{10})\)',
            'asin_pattern': r'\(ASIN:\s*([B0-9A-Z]{10})\)',
            'retailer_pattern': r'\[([^\]]+)\]\s*Alert:',
            'sender_filter': 'alert@distill.io'
        }
    
    try:
        s3_client = get_s3_client()
        
        # Check cache first
        cache_key = f"config_discount_email_config"
        if cache_key in config_cache:
            cached_data, cached_time = config_cache[cache_key]
            if (datetime.now() - cached_time).total_seconds() < CONFIG_CACHE_EXPIRY_MINUTES * 60:
                return cached_data
        
        # Try to get discount email config from S3
        try:
            response = s3_client.get_object(Bucket=CONFIG_S3_BUCKET, Key='admin/discount_email_config.json')
            config_data = json.loads(response['Body'].read().decode('utf-8'))
            
            # Add cache
            config_cache[cache_key] = (config_data, datetime.now())
            
            # Ensure required fields exist with defaults
            config_data.setdefault('subject_pattern', r'\[([^\]]+)\]\s*Alert:\s*[^\(]*\(ASIN:\s*([B0-9A-Z]{10})\)')
            config_data.setdefault('asin_pattern', r'\(ASIN:\s*([B0-9A-Z]{10})\)')
            config_data.setdefault('retailer_pattern', r'\[([^\]]+)\]\s*Alert:')
            config_data.setdefault('sender_filter', 'alert@distill.io')
            config_data['is_s3_config'] = True
            
            return config_data
            
        except s3_client.exceptions.NoSuchKey:
            # No S3 config exists, return None to fall back to legacy
            return None
        
    except Exception as e:
        print(f"Error getting discount email config from S3: {e}")
        return None

def save_discount_email_config(config_data):
    """Save discount email configuration to S3"""
    if DEMO_MODE:
        return True
    
    try:
        s3_client = get_s3_client()
        
        # Add metadata
        config_data['last_updated'] = datetime.now().isoformat()
        config_data['is_s3_config'] = True
        
        # Save to S3
        s3_client.put_object(
            Bucket=CONFIG_S3_BUCKET,
            Key='admin/discount_email_config.json',
            Body=json.dumps(config_data, indent=2),
            ContentType='application/json'
        )
        
        # Update cache
        cache_key = f"config_discount_email_config"
        config_cache[cache_key] = (config_data, datetime.now())
        
        return True
        
    except Exception as e:
        print(f"Error saving discount email config to S3: {e}")
        return False

def get_admin_gmail_config():
    """Get system-wide admin Gmail configuration from S3"""
    if DEMO_MODE:
        return {
            'email_address': 'admin@demo.com',
            'config_type': 'gmail_oauth',
            'gmail_email': 'admin@demo.com',
            'connected_at': '2024-01-01T00:00:00Z',
            'is_s3_config': True
        }
    
    try:
        s3_client = get_s3_client()
        
        # Check cache first
        cache_key = f"config_admin_gmail_config"
        if cache_key in config_cache:
            cached_data, cached_time = config_cache[cache_key]
            if (datetime.now() - cached_time).total_seconds() < CONFIG_CACHE_EXPIRY_MINUTES * 60:
                return cached_data
        
        # Try to get admin Gmail config from S3
        try:
            response = s3_client.get_object(Bucket=CONFIG_S3_BUCKET, Key='admin_gmail_config.json')
            config_data = json.loads(response['Body'].read().decode('utf-8'))
            config_data['is_s3_config'] = True
            
            # Cache the result
            config_cache[cache_key] = (config_data, datetime.now())
            return config_data
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                # Config doesn't exist yet
                config_cache[cache_key] = (None, datetime.now())
                return None
            else:
                print(f"Error accessing S3 admin Gmail config: {e}")
                return None
                
    except Exception as e:
        print(f"Error getting admin Gmail config: {e}")
        return None

def save_admin_gmail_config(config):
    """Save system-wide admin Gmail configuration"""
    try:
        config_bucket = CONFIG_S3_BUCKET
        if config_bucket:
            s3 = boto3.client('s3', 
                aws_access_key_id=AWS_ACCESS_KEY_ID,
                aws_secret_access_key=AWS_SECRET_ACCESS_KEY
            )
            
            if config is None:
                # Delete the config
                try:
                    s3.delete_object(Bucket=config_bucket, Key='admin_gmail_config.json')
                except ClientError:
                    pass  # File might not exist
            else:
                # Save the config
                s3.put_object(
                    Bucket=config_bucket,
                    Key='admin_gmail_config.json',
                    Body=json.dumps(config, indent=2),
                    ContentType='application/json'
                )
        else:
            # Local file fallback
            config_file = 'admin_gmail_config.json'
            if config is None:
                # Delete the config
                if os.path.exists(config_file):
                    os.remove(config_file)
            else:
                # Save the config
                with open(config_file, 'w') as f:
                    json.dump(config, f, indent=2)
        
        return True
    except Exception as e:
        print(f"Error saving admin Gmail config: {e}")
        return False

def get_admin_gmail_token():
    """Get Gmail access token for system-wide admin configuration"""
    admin_config = get_admin_gmail_config()
    if not admin_config or not admin_config.get('tokens'):
        return None
    
    tokens = admin_config['tokens']
    access_token = tokens.get('access_token')
    refresh_token = tokens.get('refresh_token')
    
    # Try to refresh if needed
    try:
        # Test current token
        test_response = requests.get(
            'https://gmail.googleapis.com/gmail/v1/users/me/profile',
            headers={'Authorization': f'Bearer {access_token}'}
        )
        
        if test_response.status_code == 200:
            return access_token
        
        # Need to refresh
        if refresh_token:
            token_url = "https://oauth2.googleapis.com/token"
            data = {
                'client_id': GOOGLE_CLIENT_ID,
                'client_secret': GOOGLE_CLIENT_SECRET,
                'refresh_token': refresh_token,
                'grant_type': 'refresh_token'
            }
            
            response = requests.post(token_url, data=data)
            if response.status_code == 200:
                token_data = response.json()
                new_access_token = token_data.get('access_token')
                
                # Update stored tokens
                tokens['access_token'] = new_access_token
                admin_config['tokens'] = tokens
                save_admin_gmail_config(admin_config)
                
                return new_access_token
    except Exception as e:
        print(f"Error refreshing admin Gmail token: {e}")
    
    return None

def search_gmail_messages_admin(query, max_results=500):
    """Search Gmail messages using system-wide admin configuration"""
    try:
        access_token = get_admin_gmail_token()
        if not access_token:
            return None
        
        url = "https://gmail.googleapis.com/gmail/v1/users/me/messages"
        headers = {"Authorization": f"Bearer {access_token}"}
        params = {
            "q": query,
            "maxResults": max_results
        }
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()
        
    except Exception as e:
        print(f"Error searching Gmail messages (admin): {e}")
        return None

def get_gmail_message_admin(message_id):
    """Get a specific Gmail message by ID using system-wide admin configuration"""
    try:
        access_token = get_admin_gmail_token()
        if not access_token:
            return None
        
        url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}"
        headers = {"Authorization": f"Bearer {access_token}"}
        params = {"format": "full"}
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()
        
    except Exception as e:
        print(f"Error getting Gmail message (admin): {e}")
        return None

@app.route('/api/debug/stock-direct/<asin>')
@login_required
def debug_stock_direct(asin):
    """Debug endpoint to get stock directly for a specific ASIN"""
    try:
        discord_id = session['discord_id']
        user_record = get_user_record(discord_id)
        
        if not user_record:
            return jsonify({'error': 'User record not found'}), 404
            
        stock_url = get_user_sellerboard_stock_url(user_record)
        if not stock_url:
            return jsonify({'error': 'Stock URL not configured'}), 400
            
        from orders_analysis import EnhancedOrdersAnalysis
        analyzer = EnhancedOrdersAnalysis("dummy", stock_url)
        
        # Download stock CSV
        stock_df = analyzer.download_csv(stock_url)
        
        # Get direct stock value
        direct_stock = analyzer.get_direct_stock_value(stock_df, asin)
        
        # Also get via the normal method for comparison
        stock_info = analyzer.get_stock_info(stock_df)
        normal_stock = 'Not found'
        if asin in stock_info:
            normal_stock = analyzer.extract_current_stock(stock_info[asin])
        
        # Find the actual row for this ASIN
        asin_col = None
        for col in stock_df.columns:
            if col.strip().upper() == 'ASIN':
                asin_col = col
                break
                
        raw_row = {}
        if asin_col:
            asin_rows = stock_df[stock_df[asin_col].astype(str).str.strip() == asin]
            if not asin_rows.empty:
                raw_row = asin_rows.iloc[0].to_dict()
                # Convert to JSON-safe
                for key, value in raw_row.items():
                    if pd.isna(value):
                        raw_row[key] = None
                    elif hasattr(value, 'item'):
                        raw_row[key] = value.item()
                    else:
                        raw_row[key] = str(value)
        
        return jsonify({
            'asin': asin,
            'direct_stock_value': direct_stock,
            'normal_stock_value': normal_stock,
            'raw_csv_row': raw_row,
            'stock_columns_found': [col for col in stock_df.columns if 'stock' in col.lower()],
            'total_rows_in_csv': len(stock_df)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/test/stock-simple')
@login_required
def test_stock_simple():
    """Simple test to show actual stock values from Sellerboard CSV"""
    try:
        discord_id = session['discord_id']
        user_record = get_user_record(discord_id)
        
        stock_url = get_user_sellerboard_stock_url(user_record)
        if not stock_url:
            return jsonify({'error': 'Stock URL not configured'}), 400
        
        # Download CSV directly
        import requests
        from io import StringIO
        import pandas as pd
        
        response = requests.get(stock_url, timeout=30)
        df = pd.read_csv(StringIO(response.text))
        
        # Find ASIN and stock columns
        asin_col = None
        stock_col = None
        
        for col in df.columns:
            if 'ASIN' in col.upper():
                asin_col = col
            # Be more specific - look for FBA/FBM Stock first
            if col == 'FBA/FBM Stock':
                stock_col = col
            elif not stock_col and 'Stock' in col and 'AWD' not in col:
                stock_col = col
                
        if not asin_col:
            return jsonify({'error': 'No ASIN column found', 'columns': list(df.columns)}), 500
        
        # Get first 5 products with stock info
        result = {
            'asin_column': asin_col,
            'stock_column': stock_col,
            'all_columns': list(df.columns),
            'sample_data': []
        }
        
        for i, row in df.head(10).iterrows():
            asin = row[asin_col]
            stock = row[stock_col] if stock_col else 'No stock column found'
            
            result['sample_data'].append({
                'asin': str(asin),
                'stock': str(stock),
                'all_values': {col: str(row[col]) for col in df.columns if 'stock' in col.lower()}
            })
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/debug/stock-raw')
@login_required  
def debug_stock_raw():
    """Debug endpoint to check raw stock CSV data"""
    try:
        discord_id = session['discord_id']
        user_record = get_user_record(discord_id)
        
        if not user_record:
            return jsonify({'error': 'User record not found'}), 404
        
        stock_url = get_user_sellerboard_stock_url(user_record)
        if not stock_url:
            return jsonify({'error': 'Stock URL not configured'}), 400
        
        from orders_analysis import EnhancedOrdersAnalysis
        analyzer = EnhancedOrdersAnalysis("dummy", stock_url)
        
        # Download raw CSV to see exactly what data we get
        import requests
        from io import StringIO
        import pandas as pd
        
        response = requests.get(stock_url, timeout=30)
        response.raise_for_status()
        
        # Show raw CSV content (first 2000 characters)
        raw_csv_preview = response.text[:2000]
        
        # Parse CSV
        df = pd.read_csv(StringIO(response.text))
        
        # Convert first 3 rows to JSON-safe format
        sample_rows = []
        for i in range(min(3, len(df))):
            row = df.iloc[i].to_dict()
            # Convert to JSON-safe format
            safe_row = {}
            for key, value in row.items():
                try:
                    if hasattr(value, 'item'):
                        value = value.item()
                    elif pd.isna(value):
                        value = None
                    safe_row[key] = value
                except:
                    safe_row[key] = str(value)
            sample_rows.append(safe_row)
        
        # Find stock-related columns
        stock_related_cols = [col for col in df.columns if any(keyword in col.lower() for keyword in ['stock', 'inventory', 'qty', 'quantity', 'available'])]
        
        return jsonify({
            'url': stock_url,
            'csv_preview': raw_csv_preview,
            'total_rows': len(df),
            'total_columns': len(df.columns),
            'all_columns': list(df.columns),
            'stock_related_columns': stock_related_cols,
            'sample_rows': sample_rows
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/debug/current-stock-values')
@login_required
def debug_current_stock_values():
    """Debug endpoint to examine current stock values in enhanced analytics"""
    try:
        discord_id = session['discord_id']
        user_record = get_user_record(discord_id)
        
        if not user_record:
            return jsonify({'error': 'User record not found'}), 404
            
        # Get the enhanced analytics data to see what stock values are being used
        orders_analyzer = OrdersAnalysis()
        analytics = orders_analyzer.analyze(user_record, preserve_purchase_history=True)
        
        debug_info = {
            'total_products': len(analytics.get('enhanced_analytics', {})),
            'stock_analysis': {}
        }
        
        # Check first 5 products
        enhanced_analytics = analytics.get('enhanced_analytics', {})
        for i, (asin, product_data) in enumerate(list(enhanced_analytics.items())[:5]):
            restock_data = product_data.get('restock', {})
            stock_info = product_data.get('stock_info', {})
            
            # Extract raw stock values from different potential sources
            debug_info['stock_analysis'][asin] = {
                'current_stock_from_restock': restock_data.get('current_stock'),
                'raw_stock_info_keys': list(stock_info.keys())[:10],  # First 10 columns
                'fba_fbm_stock_raw': stock_info.get('FBA/FBM Stock'),
                'stock_raw': stock_info.get('Stock'),
                'awd_stock_raw': stock_info.get('AWD Stock'),
                'available_stock_raw': stock_info.get('Available Stock'),
                'inventory_raw': stock_info.get('Inventory'),
                'title': stock_info.get('Title', stock_info.get('Product Name', f'Product {asin}'))
            }
            
        return jsonify(debug_info)
        
    except Exception as e:
        print(f"Error in debug current stock values: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/debug/stock-columns')
@login_required
def debug_stock_columns():
    """Debug endpoint to check stock data columns"""
    try:
        # Testing stock columns
        discord_id = session['discord_id']
        user_record = get_user_record(discord_id)
        
        if not user_record:
            return jsonify({'error': 'User record not found'}), 404
        
        # Get user config for Sellerboard access (use parent config for subusers)
        config_user_record = user_record
        if user_record and get_user_field(user_record, 'account.user_type') == 'subuser':
            parent_user_id = get_user_field(user_record, 'account.parent_user_id')
            if parent_user_id:
                parent_record = get_user_record(parent_user_id)
                if parent_record:
                    config_user_record = parent_record
        
        stock_url = get_user_sellerboard_stock_url(config_user_record)
        if not stock_url:
            return jsonify({'error': 'Stock URL not configured'}), 400
        
        from orders_analysis import EnhancedOrdersAnalysis
        analyzer = EnhancedOrdersAnalysis(orders_url="dummy", stock_url=stock_url)
        stock_df = analyzer.download_csv(stock_url)
        
        columns = list(stock_df.columns)
        # Stock columns retrieved
        
        # Get sample data from first row
        if len(stock_df) > 0:
            sample_row_raw = stock_df.iloc[0].to_dict()
            # Convert to JSON-serializable format
            sample_row = {}
            for key, value in sample_row_raw.items():
                try:
                    if hasattr(value, 'item'):  # numpy scalar
                        value = value.item()
                    elif hasattr(value, 'to_pydatetime'):  # pandas timestamp
                        value = value.to_pydatetime().isoformat()
                    elif str(type(value)).startswith('<class \'pandas.'):  # other pandas types
                        value = str(value)
                    elif str(type(value)).startswith('<class \'numpy.'):  # other numpy types
                        value = str(value)
                    sample_row[key] = value
                except Exception:
                    sample_row[key] = str(value)
            # Sample row data retrieved
            
            # Look for source-like columns
            source_columns = [col for col in columns if 'source' in col.lower() or 'link' in col.lower() or 'url' in col.lower()]
            
            # Look for stock-like columns and test stock extraction
            stock_fields = [
                'FBA/FBM Stock', 'FBA stock', 'Inventory (FBA)', 'Stock', 'Current Stock',
                'FBA Stock', 'FBM Stock', 'Total Stock', 'Available Stock', 'Qty Available',
                'Inventory', 'Units Available', 'Available Quantity', 'Stock Quantity'
            ]
            
            potential_stock_columns = [col for col in columns if any(stock_field.lower() in col.lower() for stock_field in ['stock', 'inventory', 'qty', 'quantity', 'available'])]
            
            # Test stock extraction with sample row
            from orders_analysis import EnhancedOrdersAnalysis
            test_analyzer = EnhancedOrdersAnalysis("dummy", "dummy")
            detected_stock = test_analyzer.extract_current_stock(sample_row)
            
            # Find which column was used
            stock_column_used = None
            for field in stock_fields:
                if field in sample_row and sample_row[field] is not None:
                    try:
                        stock_val = str(sample_row[field]).replace(',', '').strip()
                        if stock_val and stock_val.lower() not in ['nan', 'none', '', 'null']:
                            test_stock = float(stock_val)
                            if test_stock >= 0:
                                stock_column_used = field
                                break
                    except (ValueError, TypeError):
                        continue
            
            # Also test the full process to see what happens in the analysis
            stock_info = analyzer.get_stock_info(stock_df)
            
            # Test first 3 products through the full analysis chain
            analysis_test_results = []
            for i, (asin, data) in enumerate(stock_info.items()):
                if i >= 3:
                    break
                
                # Test stock extraction
                extracted_stock = analyzer.extract_current_stock(data)
                
                # Test restock calculation (needs dummy velocity data)
                dummy_velocity = {'weighted_velocity': 1.0, 'trend_factor': 1.0, 'confidence': 0.8}
                try:
                    restock_result = analyzer.calculate_optimal_restock_quantity(
                        asin, dummy_velocity, data, lead_time_days=90, purchase_analytics={}
                    )
                    restock_current_stock = restock_result.get('current_stock', 'ERROR')
                except Exception as e:
                    restock_result = {'error': str(e)}
                    restock_current_stock = 'ERROR'
                
                analysis_test_results.append({
                    'asin': asin,
                    'raw_stock_fields': {k: v for k, v in data.items() if any(keyword in k.lower() for keyword in ['stock', 'inventory', 'qty', 'quantity', 'available'])},
                    'extracted_stock': extracted_stock,
                    'restock_current_stock': restock_current_stock,
                    'restock_result': restock_result
                })
            
            return jsonify({
                'columns': columns,
                'sample_data': sample_row,
                'potential_source_columns': source_columns,
                'potential_stock_columns': potential_stock_columns,
                'detected_stock_value': detected_stock,
                'stock_column_used': stock_column_used,
                'total_rows': len(stock_df),
                'analysis_test_results': analysis_test_results
            })
        else:
            return jsonify({
                'columns': columns,
                'total_rows': 0,
                'message': 'No data in stock sheet'
            })
            
    except Exception as e:
        # Error in stock columns debug
        return jsonify({'error': str(e)}), 500

@app.route('/api/debug/cogs-status', methods=['GET'])
@login_required
def debug_cogs_status():
    """Debug endpoint to check COGS configuration status"""
    try:
        discord_id = session['discord_id']
        user_record = get_user_record(discord_id)
        
        if not user_record:
            return jsonify({'error': 'User record not found'}), 404
        
        debug_info = {
            'enable_source_links': get_user_field(user_record, 'settings.enable_source_links') or user_record.get('enable_source_links', False),
            'sheet_id': bool(get_user_field(user_record, 'files.sheet_id')),
            'worksheet_title': bool(get_user_field(user_record, 'integrations.google.worksheet_title')),
            'google_tokens': bool((get_user_field(user_record, 'integrations.google.tokens') or {}).get('refresh_token')),
            'column_mapping': get_user_column_mapping(user_record),
            'sellerboard_orders_url': bool(get_user_sellerboard_orders_url(user_record)),
            'sellerboard_stock_url': bool(get_user_sellerboard_stock_url(user_record)),
            'user_configured': bool(get_user_field(user_record, 'files.sheet_id') and get_user_field(user_record, 'integrations.google.worksheet_title'))
        }
        
        return jsonify({
            'debug_info': debug_info,
            'message': 'COGS configuration status retrieved successfully'
        })
    
    except Exception as e:
        pass  # COGS error
        return jsonify({'error': str(e)}), 500

@app.route('/api/analytics/orders')
@login_required
def get_orders_analytics():
    try:
        # Get user info first for caching
        discord_id = session['discord_id']
        
        # Get target date
        target_date_str = request.args.get('date')
        if target_date_str:
            try:
                target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
            except ValueError:
                return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
        else:
            # Default logic for target date (moved up for caching)
            user_record = get_user_record(discord_id)
            user_timezone = get_user_field(user_record, 'profile.timezone') if user_record else None
            
            if user_timezone:
                try:
                    tz = pytz.timezone(user_timezone)
                    now = datetime.now(tz)
                except pytz.UnknownTimeZoneError:
                    now = datetime.now()
            else:
                now = datetime.now()
            
            # Show yesterday's data until 11:59 PM today, then show today's data
            if now.hour == 23 and now.minute == 59:
                target_date = now.date()
            else:
                target_date = now.date() - timedelta(days=1)
        
        # Check if demo mode is enabled
        if DEMO_MODE:
            return jsonify(get_dummy_analytics_data(target_date))
        
        # Check cache first
        cache_key = get_cache_key(discord_id, target_date)
        cached_data = get_cached_data(cache_key)
        if cached_data:
            return jsonify(cached_data)
        
        # Process dashboard analytics request
        
        # Try SP-API first, fallback to Sellerboard if needed
        
        # Get user record (already retrieved above if needed)
        if 'user_record' not in locals():
            user_record = get_user_record(discord_id)
        
        # For subusers, we need to check their parent's configuration for Sellerboard URLs
        # but keep their own timezone preference
        config_user_record = user_record
        if user_record and get_user_field(user_record, 'account.user_type') == 'subuser':
            parent_user_id = get_user_field(user_record, 'account.parent_user_id')
            if parent_user_id:
                parent_record = get_user_record(parent_user_id)
                if parent_record:
                    config_user_record = parent_record
        
        user_timezone = get_user_field(user_record, 'profile.timezone') if user_record else None
        
        # Update last activity for analytics access (only if not updated recently)
        if user_record:
            try:
                last_activity = get_user_field(user_record, 'profile.last_activity') or user_record.get('last_activity')
                should_update = True
                
                if last_activity:
                    try:
                        last_update = datetime.fromisoformat(last_activity.replace('Z', '+00:00'))
                        time_since_update = datetime.now() - last_update.replace(tzinfo=None)
                        # Only update if more than 10 minutes since last update
                        should_update = time_since_update.total_seconds() > 600
                    except:
                        should_update = True
                
                if should_update:
                    # Update last activity
                    update_user_last_activity(discord_id)
                    
                    # Update Discord username and avatar if present
                    if 'discord_username' in session or 'discord_avatar' in session:
                        users = get_users_config()
                        for user in users:
                            if get_user_field(user, 'identity.discord_id') == discord_id:
                                if 'discord_username' in session:
                                    set_user_field(user, 'identity.discord_username', session['discord_username'])
                                if 'discord_avatar' in session:
                                    set_user_field(user, 'identity.avatar', session['discord_avatar'])
                                break
                        update_users_config(users)
            except Exception as e:
                # Failed to update last activity - not critical
                pass
        
        # Target date already processed above
        
        
        # Check if user is admin and SP-API should be attempted
        is_admin = is_admin_user(discord_id)
        disable_sp_api = get_user_field(config_user_record, 'integrations.amazon.disable_sp_api') or config_user_record.get('disable_sp_api', False) if config_user_record else False
        
        # Log SP-API usage decisions for clarity
        if is_admin and disable_sp_api:
            print(f"✅ SP-API DISABLED: Admin user {discord_id} has SP-API disabled, using Sellerboard only")
        elif is_admin and not disable_sp_api:
            print(f"⚠️  SP-API ENABLED: Admin user {discord_id} will try SP-API first, fallback to Sellerboard")
        
        if is_admin and not disable_sp_api:
            pass  # Debug print removed
            try:
                from sp_api_client import create_sp_api_client
                from sp_api_analytics import create_sp_api_analytics
                
                # Try to get user's Amazon refresh token first, fallback to environment
                encrypted_token = get_user_field(user_record, 'integrations.amazon.refresh_token') if user_record else None
                refresh_token = None
                
                if encrypted_token:
                    # Decrypt the refresh token
                    refresh_token = decrypt_token(encrypted_token)
                
                if not refresh_token:
                    # Fallback to environment variables (for sandbox or shared credentials)
                    refresh_token = os.getenv('SP_API_REFRESH_TOKEN')
                    if refresh_token:
                        pass  # Debug print removed
                    else:
                        raise Exception("No Amazon refresh token available - user has not connected their Amazon Seller account and no environment token found")
                
                # Create SP-API client with token
                marketplace_id = get_user_field(user_record, 'integrations.amazon.marketplace_id') or user_record.get('marketplace_id', 'ATVPDKIKX0DER')  # Default to US
                sp_client = create_sp_api_client(refresh_token, marketplace_id)
                
                if not sp_client:
                    raise Exception("SP-API client not available. Check credentials.")
                
                # Create analytics processor
                analytics_processor = create_sp_api_analytics(sp_client)
                
                # Get analytics data from SP-API
                pass  # Debug print removed
                analysis = analytics_processor.get_orders_analytics(target_date, user_timezone)
                
                pass  # Debug print removed
                pass  # Debug print removed
                pass  # Debug print removed
                pass  # Debug print removed
                
            except Exception as sp_api_error:
                
                # Fallback to Sellerboard data if SP-API fails for admin
                try:
                    from orders_analysis import OrdersAnalysis
                    
                    # Get user's configured Sellerboard URLs
                    orders_url = get_user_field(config_user_record, 'integrations.sellerboard.orders_url') if config_user_record else None
                    stock_url = get_user_field(config_user_record, 'integrations.sellerboard.stock_url') if config_user_record else None
                    cogs_url = get_user_sellerboard_cogs_url(config_user_record)
                    
                    if not orders_url or not stock_url:
                        return jsonify({
                            'error': 'Admin SP-API failed and no Sellerboard URLs configured. Please configure Sellerboard URLs in Settings.',
                            'status': 'configuration_required'
                        }), 400
                    
                    # Use Sellerboard data with COGS file support
                    analyzer = OrdersAnalysis(orders_url=orders_url, stock_url=stock_url, cogs_url=cogs_url, discord_id=discord_id)
                    
                    # Prepare user settings for COGS data fetching
                    user_settings = {
                        'enable_source_links': get_user_field(user_record, 'settings.enable_source_links') or user_record.get('enable_source_links', False),
                        'search_all_worksheets': get_user_field(config_user_record, 'settings.search_all_worksheets') or config_user_record.get('search_all_worksheets', False),
                        'sheet_id': get_user_field(config_user_record, 'files.sheet_id'),
                        'worksheet_title': get_user_field(config_user_record, 'integrations.google.worksheet_title'),
                        'google_tokens': get_user_field(config_user_record, 'integrations.google.tokens') or {},
                        'column_mapping': get_user_column_mapping(user_record),
                        'amazon_lead_time_days': get_user_field(config_user_record, 'settings.amazon_lead_time_days') or config_user_record.get('amazon_lead_time_days', 90)
                    }
                    
                    analysis = analyzer.analyze(target_date, user_timezone=user_timezone, user_settings=user_settings)
                    
                except Exception as sellerboard_error:
                    pass  # Debug print removed
                    return jsonify({
                        'error': f'Both SP-API and Sellerboard analysis failed: {str(sellerboard_error)}',
                        'sp_api_error': str(sp_api_error),
                        'sellerboard_error': str(sellerboard_error)
                    }), 500
        elif is_admin and disable_sp_api:
            print(f"✅ SP-API DISABLED: Using Sellerboard analytics for admin user {discord_id}")
            # Admin user with SP-API disabled - use Sellerboard
            try:
                from orders_analysis import OrdersAnalysis
                
                # Get user's configured Sellerboard URLs
                orders_url = get_user_field(config_user_record, 'integrations.sellerboard.orders_url') if config_user_record else None
                stock_url = get_user_field(config_user_record, 'integrations.sellerboard.stock_url') if config_user_record else None
                cogs_url = get_user_sellerboard_cogs_url(config_user_record)
                
                if not orders_url or not stock_url:
                    return jsonify({
                        'error': 'SP-API disabled and no Sellerboard URLs configured',
                        'message': 'Please configure Sellerboard report URLs in Settings or re-enable SP-API.',
                        'requires_setup': True,
                        'report_date': target_date.isoformat(),
                        'is_yesterday': is_date_yesterday(target_date, user_timezone)
                    }), 400
                
                pass  # Debug print removed
                analyzer = OrdersAnalysis(orders_url=orders_url, stock_url=stock_url, cogs_url=cogs_url, discord_id=discord_id)
                
                # Prepare user settings for COGS data fetching
                user_settings = {
                    'enable_source_links': get_user_field(user_record, 'settings.enable_source_links') or user_record.get('enable_source_links', False),
                    'search_all_worksheets': get_user_field(config_user_record, 'settings.search_all_worksheets') or config_user_record.get('search_all_worksheets', False),
                    'sheet_id': get_user_field(config_user_record, 'files.sheet_id'),
                    'worksheet_title': get_user_field(config_user_record, 'integrations.google.worksheet_title'),
                    'google_tokens': get_user_field(config_user_record, 'integrations.google.tokens') or {},
                    'column_mapping': get_user_column_mapping(user_record),
                    'amazon_lead_time_days': get_user_field(config_user_record, 'settings.amazon_lead_time_days') or config_user_record.get('amazon_lead_time_days', 90)
                }
                
                analysis = analyzer.analyze(target_date, user_timezone=user_timezone, user_settings=user_settings)
                analysis['source'] = 'sellerboard'
                analysis['message'] = 'Using Sellerboard data (SP-API disabled)'
                
                
            except Exception as sellerboard_error:
                
                # Return basic error structure for admin users with SP-API disabled
                analysis = {
                    'today_sales': {},
                    'velocity': {},
                    'low_stock': {},
                    'restock_priority': {},
                    'stockout_30d': {},
                    'enhanced_analytics': {},
                    'restock_alerts': {},
                    'critical_alerts': [],
                    'total_products_analyzed': 0,
                    'high_priority_count': 0,
                    'sellerboard_orders': [],
                    'basic_mode': True,
                    'error': f'Sellerboard analysis failed: {str(sellerboard_error)}',
                    'source': 'sellerboard_failed'
                }
        else:
            pass  # Debug print removed
            # Non-admin users use Sellerboard only
            try:
                from orders_analysis import OrdersAnalysis
                
                # Get user's configured Sellerboard URLs
                orders_url = get_user_field(config_user_record, 'integrations.sellerboard.orders_url') if config_user_record else None
                stock_url = get_user_field(config_user_record, 'integrations.sellerboard.stock_url') if config_user_record else None
                cogs_url = get_user_sellerboard_cogs_url(config_user_record)
                
                if not orders_url or not stock_url:
                    return jsonify({
                        'error': 'Sellerboard URLs not configured',
                        'message': 'Please configure Sellerboard report URLs in Settings.',
                        'requires_setup': True,
                        'report_date': target_date.isoformat(),
                        'is_yesterday': is_date_yesterday(target_date, user_timezone)
                    }), 400
                
                pass  # Debug print removed
                analyzer = OrdersAnalysis(orders_url=orders_url, stock_url=stock_url, cogs_url=cogs_url, discord_id=discord_id)
                
                # Prepare user settings for COGS data fetching
                user_settings = {
                    'enable_source_links': get_user_field(user_record, 'settings.enable_source_links') or user_record.get('enable_source_links', False),
                    'search_all_worksheets': get_user_field(config_user_record, 'settings.search_all_worksheets') or config_user_record.get('search_all_worksheets', False),
                    'sheet_id': get_user_field(config_user_record, 'files.sheet_id'),
                    'worksheet_title': get_user_field(config_user_record, 'integrations.google.worksheet_title'),
                    'google_tokens': get_user_field(config_user_record, 'integrations.google.tokens') or {},
                    'column_mapping': get_user_column_mapping(user_record),
                    'amazon_lead_time_days': get_user_field(config_user_record, 'settings.amazon_lead_time_days') or config_user_record.get('amazon_lead_time_days', 90)
                }
                
                analysis = analyzer.analyze(target_date, user_timezone=user_timezone, user_settings=user_settings)
                analysis['source'] = 'sellerboard'
                analysis['message'] = 'Using Sellerboard data'
                
                
            except Exception as sellerboard_error:
                
                # Return basic error structure for non-admin users
                analysis = {
                    'today_sales': {},
                    'velocity': {},
                    'low_stock': {},
                    'restock_priority': {},
                    'stockout_30d': {},
                    'enhanced_analytics': {},
                    'restock_alerts': {},
                    'critical_alerts': [],
                    'sellerboard_orders': [],
                    'total_products_analyzed': 0,
                    'high_priority_count': 0,
                    'error': f'Sellerboard analysis failed: {str(sellerboard_error)}',
                    'fallback_mode': True,
                    'source': 'error',
                    'report_date': target_date.isoformat(),
                    'is_yesterday': target_date == (date.today() - timedelta(days=1)),
                    'user_timezone': user_timezone
                }
        
        # Ensure all expected keys exist with default values
        analysis.setdefault('today_sales', {})
        analysis.setdefault('velocity', {})
        analysis.setdefault('low_stock', {})
        analysis.setdefault('restock_priority', {})
        analysis.setdefault('stockout_30d', {})
        # Enhanced analytics defaults
        analysis.setdefault('enhanced_analytics', {})
        analysis.setdefault('restock_alerts', {})
        analysis.setdefault('critical_alerts', [])
        analysis.setdefault('total_products_analyzed', 0)
        analysis.setdefault('high_priority_count', 0)
        
        # Remove non-JSON serializable data (DataFrames)
        if 'orders_df' in analysis:
            del analysis['orders_df']
            
        # Clean all data to ensure JSON serialization
        def clean_for_json(obj):
            """Recursively clean object to ensure JSON serialization"""
            import math
            
            if isinstance(obj, dict):
                return {k: clean_for_json(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [clean_for_json(item) for item in obj]
            elif isinstance(obj, float):
                if math.isnan(obj) or math.isinf(obj):
                    return None  # Convert NaN/Inf to null
                return obj
            elif obj is None or isinstance(obj, (int, str, bool)):
                return obj
            else:
                # Convert other types to string
                return str(obj)
        
        # Clean the entire analysis object
        analysis = clean_for_json(analysis)
        
        # Add metadata about the date being analyzed
        analysis['report_date'] = target_date.isoformat()
        
        # Calculate is_yesterday using timezone-aware logic
        analysis['is_yesterday'] = is_date_yesterday(target_date, user_timezone)
        analysis['user_timezone'] = user_timezone
        
        
        # Cache the successful analysis for future requests
        try:
            set_cached_data(cache_key, analysis)
        except Exception as cache_error:
            # Cache failure is not critical
            pass
        
        response = jsonify(analysis)
        response.headers['Content-Type'] = 'application/json'
        return response
        
    except Exception as e:
        pass  # Debug print removed
        import traceback
        
        # Return error with more details for debugging
        return jsonify({
            'error': f'Failed to fetch analytics data: {str(e)}',
            'report_date': (date.today() - timedelta(days=1)).isoformat(),
            'is_yesterday': True,
            'source': 'error',
            'debug_info': {
                'user_session': session.get('discord_id', 'Not logged in'),
                'error_type': type(e).__name__,
                'timestamp': datetime.now().isoformat()
            }
        }), 500

def allowed_file(filename):
    """Check if file extension is allowed"""
    ALLOWED_EXTENSIONS = {'csv', 'xlsx', 'xlsm', 'xls'}
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# File upload endpoint removed - using URL-based approach
@app.route('/api/upload/sellerboard', methods=['POST'])
@permission_required('sellerboard_upload')
def upload_sellerboard_file():
    # This endpoint is deprecated - using URL-based approach
    return jsonify({'error': 'File uploads are no longer supported. Please configure your Sellerboard URL in settings.'}), 400

def determine_file_type_category(filename):
    """
    Standardized function to determine file type category based on filename.
    Returns: 'listing_loader', 'sellerboard', or 'other'
    """
    filename_lower = filename.lower()
    
    # Listing loader files - check for specific keywords and .xlsm extension
    if ('listingloader' in filename_lower or 
        'listing_loader' in filename_lower or 
        'listing' in filename_lower or 
        'loader' in filename_lower or
        filename_lower.endswith('.xlsm')):
        return 'listing_loader'
    
    # Sellerboard files - broader detection for Excel/CSV files that aren't listing loaders
    elif ('sellerboard' in filename_lower or 
          'sb' in filename_lower or 
          filename_lower.endswith('.xlsx') or 
          filename_lower.endswith('.csv') or
          filename_lower.endswith('.xls')):
        return 'sellerboard'
    
    # Everything else
    else:
        return 'other'

def get_user_files_from_s3(discord_id):
    """
    Get all files belonging to a specific user based on their discord_id.
    This function properly filters files by checking if the filename starts with the discord_id.
    """
    s3_client = get_s3_client()
    user_files = []
    
    try:
        # List all objects in the bucket
        response = s3_client.list_objects_v2(Bucket=CONFIG_S3_BUCKET)
        
        if 'Contents' not in response:
            return user_files
        
        for obj in response['Contents']:
            key = obj['Key']
            filename = key.split('/')[-1]  # Get filename without path
            
            # Check if this file belongs to the user (filename starts with discord_id_)
            if filename.startswith(f"{discord_id}_"):
                
                # Determine file type and category using standardized function
                file_type_category = determine_file_type_category(filename)
                # File categorized
                
                file_info = {
                    'filename': filename,
                    's3_key': key,
                    'file_size': obj['Size'],
                    'upload_date': obj['LastModified'].isoformat(),
                    'file_type_category': file_type_category,
                    'uploaded_by': discord_id  # Track who uploaded it
                }
                user_files.append(file_info)
        
        # Sort files by upload date (newest first)
        user_files.sort(key=lambda x: x['upload_date'], reverse=True)
        
        return user_files
        
    except Exception as e:
        pass  # Debug print removed
        return user_files

def detect_duplicate_files_for_user(discord_id):
    """
    Detect duplicate files for a user (more than one file of the same type).
    Returns a dict with file types that have duplicates.
    """
    user_files = get_user_files_from_s3(discord_id)
    
    # Group files by type
    files_by_type = {
        'listing_loader': [],
        'sellerboard': [],
        'other': []
    }
    
    for file_info in user_files:
        file_category = file_info.get('file_type_category', 'other')
        if file_category == 'listing_loader':
            files_by_type['listing_loader'].append(file_info)
        elif file_category == 'sellerboard':
            files_by_type['sellerboard'].append(file_info)
        else:
            files_by_type['other'].append(file_info)
    
    # Find duplicates
    duplicates = {}
    for file_type, files in files_by_type.items():
        if len(files) > 1:
            duplicates[file_type] = files
    
    # Debug logging
    # Files by type retrieved
    
    if duplicates:
        # Duplicates found
        pass
    else:
        # No duplicates found
        pass
    
    return duplicates

def cleanup_old_files_on_upload(discord_id, new_file_type, new_s3_key):
    """
    Clean up old files of the same type when a new file is uploaded.
    This function deletes old files directly from S3.
    """
    try:
        s3_client = get_s3_client()
        user_files = get_user_files_from_s3(discord_id)
        
        files_to_delete = []
        
        # Find files of the same type (excluding the newly uploaded file)
        for file_info in user_files:
            if (file_info['file_type_category'] == new_file_type and 
                file_info['s3_key'] != new_s3_key):
                files_to_delete.append(file_info)
        
        # Delete old files from S3
        deleted_files = []
        for file_info in files_to_delete:
            try:
                s3_client.delete_object(Bucket=CONFIG_S3_BUCKET, Key=file_info['s3_key'])
                deleted_files.append(file_info['filename'])
                pass  # Debug print removed
            except Exception as e:
                pass  # Error deleting file
        
        return {
            'deleted_count': len(deleted_files),
            'deleted_files': deleted_files
        }
        
    except Exception as e:
        pass  # Debug print removed
        return {
            'deleted_count': 0,
            'deleted_files': []
        }

# File listing endpoint removed - using URL-based approach
@app.route('/api/files/sellerboard', methods=['GET'])
@login_required
def list_sellerboard_files():
    """This endpoint is deprecated - using URL-based approach"""
    return jsonify({'error': 'File management is no longer supported. Data is now fetched automatically from your Sellerboard URL.'}), 400

# Original function commented out below
"""
def list_sellerboard_files_old():
    try:
        discord_id = session['discord_id']
        
        # Return dummy data in demo mode
        if DEMO_MODE:
            dummy_files = [
                {
                    'filename': 'orders_2024_01_15.csv',
                    'upload_date': '2024-01-15T10:30:00Z',
                    'file_size': 2048000,
                    'file_type': 'orders',
                    's3_key': 'demo/orders_2024_01_15.csv',
                    'last_modified': '2024-01-15T10:30:00Z'
                },
                {
                    'filename': 'inventory_snapshot_2024_01_10.xlsx',
                    'upload_date': '2024-01-10T14:20:00Z',
                    'file_size': 1024000,
                    'file_type': 'inventory',
                    's3_key': 'demo/inventory_snapshot_2024_01_10.xlsx',
                    'last_modified': '2024-01-10T14:20:00Z'
                },
                {
                    'filename': 'listing_loader_data_2024_01_12.csv',
                    'upload_date': '2024-01-12T09:15:00Z',
                    'file_size': 512000,
                    'file_type': 'listing_loader',
                    's3_key': 'demo/listing_loader_data_2024_01_12.csv',
                    'last_modified': '2024-01-12T09:15:00Z'
                }
            ]
            
            return jsonify({
                'files': dummy_files,
                'duplicates': {},
                'warnings': [],
                'total_files': len(dummy_files)
            })
        
        # Get files directly from S3 using proper discord_id filtering
        user_files = get_user_files_from_s3(discord_id)
        
        # Check for duplicates
        duplicates = detect_duplicate_files_for_user(discord_id)
        
        # Add warning if duplicates are found
        warnings = []
        if duplicates:
            for file_type, duplicate_files in duplicates.items():
                display_name = 'Listing Loader' if file_type == 'listing_loader' else file_type.title()
                warnings.append(f"You have {len(duplicate_files)} {display_name} files. Please delete {len(duplicate_files)-1} to keep only the latest one.")
                # Warning created for duplicate files
        
        return jsonify({
            'files': user_files,
            'duplicates': duplicates,
            'warnings': warnings,
            'total_files': len(user_files)
        })
        
    except Exception as e:
        pass  # Debug print removed
        return jsonify({'error': str(e)}), 500
"""

@app.route('/api/files/cleanup-duplicates', methods=['POST'])
@login_required
def cleanup_user_duplicates():
    """This endpoint is deprecated - using URL-based approach"""
    return jsonify({'error': 'File management is no longer supported. Data is now fetched automatically from your Sellerboard URL.'}), 400

# Original function commented out
"""
def cleanup_user_duplicates_old():
    try:
        discord_id = session['discord_id']
        
        # Get duplicates
        duplicates = detect_duplicate_files_for_user(discord_id)
        
        if not duplicates:
            return jsonify({
                'success': True,
                'message': 'No duplicate files found',
                'deleted_count': 0,
                'deleted_files': []
            })
        
        s3_client = get_s3_client()
        total_deleted = 0
        all_deleted_files = []
        
        # For each file type with duplicates, keep only the most recent
        for file_type, duplicate_files in duplicates.items():
            # Sort by upload date (newest first)
            duplicate_files.sort(key=lambda x: x['upload_date'], reverse=True)
            
            # Keep the first (newest) file, delete the rest
            files_to_delete = duplicate_files[1:]  # Skip the first (newest) file
            
            for file_info in files_to_delete:
                try:
                    s3_client.delete_object(Bucket=CONFIG_S3_BUCKET, Key=file_info['s3_key'])
                    all_deleted_files.append(file_info['filename'])
                    total_deleted += 1
                    pass  # Debug print removed
                except Exception as e:
                    pass  # Error deleting duplicate
        
        return jsonify({
            'success': True,
            'message': f'Successfully cleaned up {total_deleted} duplicate files',
            'deleted_count': total_deleted,
            'deleted_files': all_deleted_files
        })
        
    except Exception as e:
        pass  # Debug print removed
        return jsonify({'error': str(e)}), 500
"""

@app.route('/api/admin/migrate-all-files', methods=['POST'])
@login_required
def migrate_all_user_files():
    """This endpoint is deprecated - using URL-based approach"""
    return jsonify({'error': 'File migration is no longer needed. Data is now fetched automatically from Sellerboard URLs.'}), 400

# Original function commented out
"""
def migrate_all_user_files_old():
    try:
        discord_id = session['discord_id']
        
        # Check if user has admin permissions (you can adjust this logic)
        if discord_id != '712147636463075389':  # Your Discord ID
            return jsonify({'error': 'Unauthorized'}), 403
        
        s3_client = get_s3_client()
        users = get_users_config()
        
        # Known user mappings
        user_mappings = {
            'oscar': '1208551911976861737',
            'tevin': '712147636463075389', 
            'david': '1189800870125256810'
        }
        
        migration_results = []
        
        # List all objects in the bucket
        response = s3_client.list_objects_v2(Bucket=CONFIG_S3_BUCKET)
        
        if 'Contents' in response:
            for obj in response['Contents']:
                s3_key = obj['Key']
                
                # Skip files already in sellerboard_files/
                if s3_key.startswith('sellerboard_files/'):
                    continue
                
                # Skip system files and generated files
                if s3_key in ['users.json', 'command_permissions.json', 'amznUploadConfig.json', 'config.json']:
                    continue
                
                # Skip generated _updated files - these are script outputs, not user uploads
                if '_updated.' in s3_key:
                    continue
                
                filename = s3_key.lower()
                matched_user = None
                
                # Try to match file to user
                for username, discord_id in user_mappings.items():
                    if username in filename:
                        matched_user = discord_id
                        break
                
                if matched_user:
                    # Create new S3 key in proper directory
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    original_filename = s3_key  # Keep original filename
                    new_s3_key = f"sellerboard_files/{matched_user}_{timestamp}_{original_filename}"
                    
                    try:
                        # Copy file to new location
                        copy_source = {'Bucket': CONFIG_S3_BUCKET, 'Key': s3_key}
                        s3_client.copy_object(
                            CopySource=copy_source,
                            Bucket=CONFIG_S3_BUCKET,
                            Key=new_s3_key
                        )
                        
                        # Delete original file
                        s3_client.delete_object(Bucket=CONFIG_S3_BUCKET, Key=s3_key)
                        
                        # Add to user's uploaded_files
                        for i, user in enumerate(users):
                            if get_user_field(user, 'identity.discord_id') == matched_user:
                                if not get_user_field(user, 'files.uploaded_files'):
                                    set_user_field(user, 'files.uploaded_files', [])
                                
                                # Determine file type
                                if '.xlsm' in filename or 'listing' in filename or 'loader' in filename:
                                    file_type_category = 'listing_loader'
                                    content_type = 'application/vnd.ms-excel.sheet.macroEnabled.12'
                                else:
                                    file_type_category = 'sellerboard'
                                    content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                                
                                file_info = {
                                    'filename': original_filename,
                                    's3_key': new_s3_key,
                                    'upload_date': obj.get('LastModified', datetime.utcnow()).isoformat() + 'Z',
                                    'file_size': obj.get('Size', 0),
                                    'file_type': content_type,
                                    'file_type_category': file_type_category
                                }
                                
                                # Remove any existing files of the same type
                                get_user_field(user, 'files.uploaded_files') or [] = [
                                    f for f in get_user_field(user, 'files.uploaded_files') or [] 
                                    if f.get('file_type_category') != file_type_category
                                ]
                                
                                uploaded_files = get_user_field(user, 'files.uploaded_files') or []
                                uploaded_files.append(file_info)
                                set_user_field(user, 'files.uploaded_files', uploaded_files)
                                users[i] = user
                                break
                        
                        migration_results.append({
                            'original_key': s3_key,
                            'new_key': new_s3_key,
                            'user': matched_user,
                            'status': 'migrated'
                        })
                        
                    except Exception as e:
                        migration_results.append({
                            'original_key': s3_key,
                            'error': str(e),
                            'status': 'failed'
                        })
        
        # Update users config
        update_users_config(users)
        
        return jsonify({
            'message': f'Migration completed. Processed {len(migration_results)} files.',
            'results': migration_results
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
"""

@app.route('/api/admin/cleanup-all-updated', methods=['POST'])
@admin_required
def admin_cleanup_all_updated_files():
    """Admin endpoint to remove all _updated files from all user records"""
    try:
        users = get_users_config()
        total_removed = 0
        
        for user in users:
            if not get_user_field(user, 'files.uploaded_files'):
                continue
                
            uploaded_files = get_user_field(user, 'files.uploaded_files') or []
            original_count = len(uploaded_files)
            filtered_files = [
                f for f in uploaded_files 
                if '_updated.' not in f.get('filename', '') and '_updated.' not in f.get('s3_key', '')
            ]
            set_user_field(user, 'files.uploaded_files', filtered_files)
            removed_count = original_count - len(filtered_files)
            total_removed += removed_count
            
            if removed_count > 0:
                pass  # Files removed
        
        if update_users_config(users):
            return jsonify({
                'message': f'Successfully cleaned {total_removed} _updated files from all users',
                'total_removed': total_removed
            })
        else:
            return jsonify({'error': 'Failed to update users config'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/files/cleanup-updated', methods=['POST'])
@login_required
def cleanup_updated_files():
    """This endpoint is deprecated - using URL-based approach"""
    return jsonify({'error': 'File management is no longer supported. Data is now fetched automatically from your Sellerboard URL.'}), 400

# Original function commented out
"""
def cleanup_updated_files_old():
    try:
        discord_id = session['discord_id']
        users = get_users_config()
        
        user_record = None
        user_index = None
        for i, user in enumerate(users):
            if get_user_field(user, 'identity.discord_id') == discord_id:
                user_record = user
                user_index = i
                break
        
        if not user_record:
            return jsonify({'error': 'User not found'}), 404
        
        uploaded_files = get_user_field(user_record, 'files.uploaded_files') or []
        if not uploaded_files:
            return jsonify({'message': 'No files to clean up', 'removed_count': 0})
        
        # Remove _updated files from uploaded_files
        original_count = len(uploaded_files)
        cleaned_files = [
            f for f in uploaded_files 
            if '_updated.' not in f.get('filename', '') and '_updated.' not in f.get('s3_key', '')
        ]
        removed_count = original_count - len(cleaned_files)
        
        # Update the user record with cleaned files
        set_user_field(user_record, 'files.uploaded_files', cleaned_files)
        set_user_field(user_record, 'files.uploaded_count', len(cleaned_files))
        set_user_field(user_record, 'files.recent_uploads', cleaned_files[-5:])  # Update recent uploads
        
        # Update the users config
        users[user_index] = user_record
        if update_users_config(users):
            return jsonify({
                'message': f'Cleaned up {removed_count} _updated files from your record',
                'removed_count': removed_count
            })
        else:
            return jsonify({'error': 'Failed to update user config'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500
"""

@app.route('/api/files/migrate', methods=['POST'])
@login_required
def migrate_existing_files():
    """This endpoint is deprecated - using URL-based approach"""
    return jsonify({'error': 'File management is no longer supported. Data is now fetched automatically from your Sellerboard URL.'}), 400

# Original function commented out
"""
def migrate_existing_files_old():
    try:
        discord_id = session['discord_id']
        user_record = get_user_record(discord_id)
        
        if not user_record:
            return jsonify({'error': 'User not found'}), 404
        
        # Initialize uploaded_files if it doesn't exist
        if not get_user_field(user_record, 'files.uploaded_files'):
            set_user_field(user_record, 'files.uploaded_files', [])
        
        # Scan S3 for existing files for this user
        s3_client = get_s3_client()
        
        try:
            # List all files in sellerboard_files/ folder that start with user's discord_id
            prefix = f"sellerboard_files/{discord_id}_"
            response = s3_client.list_objects_v2(Bucket=CONFIG_S3_BUCKET, Prefix=prefix)
            
            # Also check for direct files (legacy listing loaders)
            direct_response = s3_client.list_objects_v2(Bucket=CONFIG_S3_BUCKET)
            
            # Combine both responses
            all_objects = []
            if 'Contents' in response:
                all_objects.extend(response['Contents'])
            
            # For direct files, check if they belong to this user (by name pattern)
            if 'Contents' in direct_response:
                for obj in direct_response['Contents']:
                    key = obj['Key']
                    # Skip files already in sellerboard_files/
                    if key.startswith('sellerboard_files/'):
                        continue
                    
                    # Skip generated _updated files - these are script outputs, not user uploads
                    if '_updated.' in key:
                        continue
                    
                    # Check if filename contains user identifier or matches known patterns
                    filename = key.lower()
                    user_record_info = user_record
                    
                    # Known user mappings for legacy files
                    user_mappings = {
                        'oscar': '1208551911976861737',
                        'tevin': '712147636463075389', 
                        'david': '1189800870125256810'
                    }
                    
                    # Try to match by known username mapping first
                    for username, mapped_discord_id in user_mappings.items():
                        if username in filename and discord_id == mapped_discord_id:
                            all_objects.append(obj)
                            break
                    else:
                        # Try to match by email username or listing_loader_key
                        if get_user_field(user_record_info, 'identity.email'):
                            email_username = user_record_info['email'].split('@')[0].lower()
                            if email_username in filename:
                                all_objects.append(obj)
                        
                        # Also check deprecated listing_loader_key field
                        if get_user_field(user_record_info, 'files.listing_loader_key'):
                            if user_record_info['listing_loader_key'].lower() in filename:
                                all_objects.append(obj)
            
            migrated_files = []
            
            for obj in all_objects:
                s3_key = obj['Key']
                filename = s3_key.split('/')[-1]  # Get filename from S3 key
                
                # Handle different file naming patterns
                if s3_key.startswith('sellerboard_files/'):
                    # New format: sellerboard_files/discord_id_timestamp_original_filename
                    parts = filename.split('_', 3)  # discord_id, date, time, original_filename
                    if len(parts) >= 4:
                        original_filename = parts[3]
                    else:
                        original_filename = filename
                else:
                    # Legacy format: direct file in bucket root
                    original_filename = filename
                
                # Check if this file is already in uploaded_files
                already_exists = any(f['s3_key'] == s3_key for f in get_user_field(user_record, 'files.uploaded_files') or [])
                
                if not already_exists:
                    # Determine file type category
                    filename_lower = original_filename.lower()
                    if '.xlsm' in filename_lower or 'listing' in filename_lower or 'loader' in filename_lower:
                        file_type_category = 'listing_loader'
                    else:
                        file_type_category = 'sellerboard'
                    
                    # Get file size
                    file_size = obj.get('Size', 0)
                    
                    # Use LastModified as upload date, ensure it's in UTC format
                    last_modified = obj.get('LastModified')
                    if last_modified:
                        # LastModified from S3 is already in UTC
                        upload_date = last_modified.isoformat() + 'Z'
                    else:
                        upload_date = datetime.utcnow().isoformat() + 'Z'
                    
                    # Determine content type
                    if s3_key.endswith('.xlsx'):
                        content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                    elif s3_key.endswith('.xlsm'):
                        content_type = 'application/vnd.ms-excel.sheet.macroEnabled.12'
                    elif s3_key.endswith('.csv'):
                        content_type = 'text/csv'
                    else:
                        content_type = 'application/octet-stream'
                    
                    file_info = {
                        'filename': original_filename,
                        's3_key': s3_key,
                        'upload_date': upload_date,
                        'file_size': file_size,
                        'file_type': content_type,
                        'file_type_category': file_type_category
                    }
                    
                    migrated_files.append(file_info)
            
            # Group migrated files by type and keep only the most recent of each type
            files_by_type = {}
            files_to_delete_from_s3 = []
            
            for file_info in migrated_files:
                file_type = file_info['file_type_category']
                upload_date = file_info['upload_date']
                
                if file_type not in files_by_type:
                    files_by_type[file_type] = file_info
                elif upload_date > files_by_type[file_type]['upload_date']:
                    # New file is more recent, mark old one for deletion
                    files_to_delete_from_s3.append(files_by_type[file_type])
                    files_by_type[file_type] = file_info
                else:
                    # Current file is older, mark it for deletion
                    files_to_delete_from_s3.append(file_info)
            
            # Remove existing files of the same types that we're migrating
            for file_type in files_by_type.keys():
                get_user_field(user_record, 'files.uploaded_files') or [] = [
                    f for f in get_user_field(user_record, 'files.uploaded_files') or [] 
                    if f.get('file_type_category') != file_type
                ]
            
            # Add the most recent file of each type
            uploaded_files = get_user_field(user_record, 'files.uploaded_files') or []
            for file_info in files_by_type.values():
                uploaded_files.append(file_info)
            set_user_field(user_record, 'files.uploaded_files', uploaded_files)
            
            # Delete duplicate files from S3
            deleted_count = 0
            for file_to_delete in files_to_delete_from_s3:
                try:
                    s3_client.delete_object(Bucket=CONFIG_S3_BUCKET, Key=file_to_delete['s3_key'])
                    deleted_count += 1
                    pass  # Debug print removed
                except Exception as e:
                    pass  # Error deleting file
            
            # Update users config
            users = get_users_config()
            for i, user in enumerate(users):
                if get_user_field(user, 'identity.discord_id') == discord_id:
                    users[i] = user_record
                    break
            
            update_users_config(users)
            
            return jsonify({
                'message': f'Successfully migrated {len(files_by_type)} files (deleted {deleted_count} duplicates)',
                'migrated_files': list(files_by_type.values()),
                'deleted_duplicates': deleted_count
            })
            
        except Exception as e:
            return jsonify({'error': f'S3 error: {str(e)}'}), 500
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
"""

@app.route('/api/files/status', methods=['GET'])
@login_required
def files_upload_status():
    """This endpoint is deprecated - using URL-based approach"""
    # Always return files complete since we're using URL-based approach
    return jsonify({
        'has_sellerboard': True,
        'has_listing_loader': True,
        'files_complete': True
    })

@app.route('/api/files/sellerboard/<path:file_key>', methods=['DELETE', 'OPTIONS'])
def delete_sellerboard_file(file_key):
    """This endpoint is deprecated - using URL-based approach"""
    # Handle preflight OPTIONS request
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers.add('Access-Control-Allow-Origin', request.headers.get('Origin', '*'))
        response.headers.add('Access-Control-Allow-Methods', 'DELETE, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        return response
    
    # Return error for DELETE requests
    return jsonify({'error': 'File management is no longer supported. Data is now fetched automatically from your Sellerboard URL.'}), 400

# Original function commented out below
"""
def delete_sellerboard_file_old(file_key):
    try:
        from urllib.parse import unquote
        discord_id = session['discord_id']
        original_file_key = file_key
        file_key = unquote(file_key)  # Decode URL encoding
        pass  # Debug print removed
        pass  # Debug print removed
        
        users = get_users_config()
        user_record = next((u for u in users if get_user_field(u, 'identity.discord_id') == discord_id), None)
        
        uploaded_files = get_user_field(user_record, 'files.uploaded_files') or []
        if not user_record or not uploaded_files:
            pass  # Debug print removed
            return jsonify({'error': 'User record not found'}), 404
        
        pass  # Debug print removed
        pass  # Debug print removed
        # Find and remove the file - try multiple matching strategies
        file_to_delete = None
        file_index = None
        
        # Strategy 1: Exact match
        for i, file_info in enumerate(uploaded_files):
            if file_info.get('s3_key') == file_key:
                file_to_delete = file_info
                file_index = i
                pass  # Debug print removed
                break
        
        # Strategy 2: Try without URL decoding if exact match failed
        if not file_to_delete:
            for i, file_info in enumerate(uploaded_files):
                if file_info.get('s3_key') == original_file_key:
                    file_to_delete = file_info
                    file_index = i
                    file_key = original_file_key  # Use original for S3 deletion
                    pass  # Debug print removed
                    break
        
        # Strategy 3: Try partial match (in case of encoding differences)
        if not file_to_delete:
            for i, file_info in enumerate(get_user_field(user_record, 'files.uploaded_files') or []):
                s3_key = file_info.get('s3_key', '')
                if (file_key in s3_key or original_file_key in s3_key or 
                    s3_key in file_key or s3_key in original_file_key):
                    file_to_delete = file_info
                    file_index = i
                    file_key = s3_key  # Use the actual S3 key for deletion
                    pass  # Debug print removed
                    break
        
        if not file_to_delete:
            pass  # Debug print removed
            return jsonify({
                'error': 'File not found', 
                'debug': {
                    'requested_key': file_key,
                    'original_key': original_file_key,
                    'available_keys': [f.get('s3_key') for f in uploaded_files]
                }
            }), 404
        
        # Remove file from user record
        uploaded_files.pop(file_index)
        
        # Update user record with modified files list
        set_user_field(user_record, 'files.uploaded_files', uploaded_files)
        set_user_field(user_record, 'files.uploaded_count', len(uploaded_files))
        set_user_field(user_record, 'files.recent_uploads', uploaded_files[-5:])  # Update recent uploads
        
        # Delete from S3 (S3 delete_object is idempotent - no need to check if file exists first)
        s3_client = get_s3_client()
        
        try:
            s3_client.delete_object(Bucket=CONFIG_S3_BUCKET, Key=file_key)
            pass  # Debug print removed
        except Exception as e:
            pass  # S3 deletion error
        
        # Update user config with retry logic
        max_retries = 3
        for retry in range(max_retries):
            try:
                if update_users_config(users):
                    pass  # Debug print removed
                    response = jsonify({'message': 'File deleted successfully'})
                    response.headers.add('Access-Control-Allow-Origin', request.headers.get('Origin', '*'))
                    response.headers.add('Access-Control-Allow-Credentials', 'true')
                    return response
                else:
                    pass  # Debug print removed
                    if retry < max_retries - 1:
                        import time
                        time.sleep(0.1)  # Reduced wait time
                    continue
            except Exception as config_error:
                pass  # Debug print removed
                if retry < max_retries - 1:
                    import time
                    time.sleep(0.1)  # Reduced wait time
                    continue
                raise config_error
        
        # If we get here, all config update attempts failed
        pass  # Debug print removed
        return jsonify({
            'error': 'File deleted from storage but failed to update configuration. Please refresh the page.',
            'partial_success': True
        }), 500
            
    except Exception as e:
        pass  # Debug print removed
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Delete operation failed: {str(e)}'}), 500
"""

# Admin API endpoints
@app.route('/api/admin/users', methods=['GET'])
@admin_required
def admin_get_users():
    """Get all users for admin panel"""
    try:
        users = get_users_config()
        
        # Add derived status fields for each user (temporary for response)
        enhanced_users = []
        for user in users:
            enhanced_user = user.copy()  # Create a copy to avoid modifying original
            enhanced_user['profile_configured'] = is_user_configured(user)
            enhanced_user['google_linked'] = bool(get_user_google_tokens(user))
            enhanced_user['sheet_configured'] = bool(get_user_sheet_id(user))
            
            # Flatten key fields for frontend compatibility
            enhanced_user['discord_username'] = get_user_field(user, 'identity.discord_username') or user.get('discord_username')
            enhanced_user['discord_avatar'] = get_user_field(user, 'identity.avatar') or user.get('discord_avatar')
            enhanced_user['email'] = get_user_field(user, 'identity.email') or user.get('email')
            enhanced_user['discord_id'] = get_user_field(user, 'identity.discord_id') or user.get('discord_id')
            enhanced_user['user_type'] = get_user_field(user, 'account.user_type') or user.get('user_type', 'main')
            enhanced_user['va_name'] = get_user_field(user, 'identity.va_name') or user.get('va_name')
            enhanced_user['parent_user_id'] = get_user_field(user, 'account.parent_user_id') or user.get('parent_user_id')
            # Get last_activity from multiple possible locations
            enhanced_user['last_activity'] = (get_user_field(user, 'profile.last_activity') or 
                                             get_user_field(user, 'account.last_activity') or 
                                             user.get('last_activity'))
            
            enhanced_users.append(enhanced_user)
            
        return jsonify({'users': enhanced_users})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/stats', methods=['GET'])
@admin_required
def admin_get_stats():
    """Get system statistics for admin dashboard"""
    try:
        users = get_users_config()
        
        total_users = len(users)
        
        # Calculate active users - subusers are always considered active since they inherit from parent
        active_users = sum(1 for u in users if 
                          get_user_field(u, 'account.user_type') == 'subuser' or  # Subusers are always active
                          (get_user_field(u, 'identity.email') and get_user_field(u, 'integrations.google.tokens') and get_user_field(u, 'files.sheet_id')))  # Main users need full setup
        
        pending_users = total_users - active_users
        
        return jsonify({
            'total_users': total_users,
            'active_users': active_users,
            'pending_users': pending_users,
            'system_status': 'operational'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/users/<user_id>', methods=['PUT'])
@admin_required
def admin_update_user(user_id):
    """Update a specific user's data"""
    try:
        data = request.json
        pass  # Debug print removed
        
        users = get_users_config()
        
        # Find user in the users list (not just get a reference)
        user_index = None
        for i, u in enumerate(users):
            if str(get_user_field(u, 'identity.discord_id')) == str(user_id):
                user_index = i
                break
        
        if user_index is None:
            pass  # Debug print removed
            return jsonify({'error': 'User not found'}), 404
        
        user_record = users[user_index]
        pass  # Debug print removed
        pass  # Debug print removed
        
        # Update allowed fields using new schema
        field_mappings = {
            'email': 'identity.email',
            'run_scripts': 'permissions.run_scripts',
            'run_prep_center': 'permissions.run_prep_center',
            'sellerboard_orders_url': 'integrations.sellerboard.orders_url',
            'sellerboard_stock_url': 'integrations.sellerboard.stock_url',
            'enable_source_links': 'settings.enable_source_links',
            'search_all_worksheets': 'settings.search_all_worksheets'
        }
        
        for field, schema_path in field_mappings.items():
            if field in data:
                old_value = get_user_field(user_record, schema_path)
                set_user_field(user_record, schema_path, data[field])
                users[user_index] = user_record
        
        pass  # Debug print removed
        pass  # Debug print removed
        
        # Save changes
        if update_users_config(users):
            pass  # Debug print removed
            return jsonify({'message': 'User updated successfully'})
        else:
            pass  # Debug print removed
            return jsonify({'error': 'Failed to update user'}), 500
            
    except Exception as e:
        pass  # Debug print removed
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/users/<user_id>', methods=['DELETE'])
@admin_required
def admin_delete_user(user_id):
    """Delete a user completely"""
    try:
        users = get_users_config()
        
        # Find and remove the user
        user_index = None
        user_id_str = str(user_id)
        for i, user in enumerate(users):
            if str(get_user_field(user, 'identity.discord_id')) == user_id_str:
                user_index = i
                break
        
        if user_index is None:
            return jsonify({'error': 'User not found'}), 404
        
        # Remove user from list
        deleted_user = users.pop(user_index)
        
        # TODO: Clean up user's S3 files if needed
        # This could be added later for complete cleanup
        
        # Save changes
        if update_users_config(users):
            return jsonify({'message': f'User {get_user_field(deleted_user, "identity.discord_username") or deleted_user.get("discord_username", user_id)} deleted successfully'})
        else:
            return jsonify({'error': 'Failed to delete user'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/migrate-users-schema', methods=['POST'])
@admin_required 
def admin_migrate_users_schema():
    """Migrate all users from old flat schema to new organized schema"""
    try:
        success, message = migrate_all_users_to_new_schema()
        if success:
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({
                'success': False, 
                'error': message
            }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f"Migration error: {str(e)}"
        }), 500

@app.route('/api/admin/impersonate/<user_id>', methods=['POST'])
@admin_required  
def admin_impersonate_user(user_id):
    """Temporarily impersonate a user for dashboard viewing"""
    try:
        
        # Find the user
        user_record = get_user_record(user_id)
        if not user_record:
            pass  # Debug print removed
            return jsonify({'error': 'User not found'}), 404
        
        pass  # Debug print removed
        pass  # Debug print removed
        pass  # Debug print removed
        
        # Store original admin session
        session['admin_impersonating'] = {
            'original_discord_id': session['discord_id'],
            'original_discord_username': session['discord_username'],
            'target_user_id': user_id
        }
        
        # Temporarily switch session to target user
        session['discord_id'] = get_user_discord_id(user_record)
        session['discord_username'] = get_user_field(user_record, 'identity.discord_username') or user_record.get('discord_username', 'Unknown User')
        
        
        return jsonify({
            'message': f'Now viewing as {get_user_field(user_record, "identity.discord_username") or user_record.get("discord_username", "Unknown User")}',
            'impersonating': True,
            'target_user': {
                'discord_id': get_user_discord_id(user_record),
                'discord_username': get_user_field(user_record, 'identity.discord_username') or user_record.get('discord_username', 'Unknown User')
            }
        })
        
    except Exception as e:
        pass  # Debug print removed
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/stop-impersonate', methods=['POST'])
@login_required
def admin_stop_impersonate():
    """Stop impersonating a user and return to admin session"""
    try:
        if 'admin_impersonating' not in session:
            return jsonify({'error': 'Not currently impersonating'}), 400
        
        # Restore original admin session
        original_data = session['admin_impersonating']
        session['discord_id'] = original_data['original_discord_id']
        session['discord_username'] = original_data['original_discord_username']
        
        # Remove impersonation data
        del session['admin_impersonating']
        
        return jsonify({
            'message': 'Stopped impersonating, returned to admin session',
            'impersonating': False
        })
        
    except Exception as e:
        pass  # Debug print removed
        return jsonify({'error': str(e)}), 500

@app.route('/api/debug/session', methods=['GET'])
@login_required
def debug_session():
    """Debug endpoint to check session state"""
    try:
        discord_id = session.get('discord_id')
        user_record = get_user_record(discord_id)
        
        return jsonify({
            'session_discord_id': discord_id,
            'session_username': session.get('discord_username'),
            'is_impersonating': 'admin_impersonating' in session,
            'impersonation_data': session.get('admin_impersonating') if 'admin_impersonating' in session else None,
            'user_record_found': bool(user_record),
            'user_has_cogs_url': bool(user_record and get_user_field(user_record, 'integrations.sellerboard.cogs_url')) if user_record else False,
            'cogs_url_preview': (get_user_field(user_record, 'integrations.sellerboard.cogs_url') or '')[:50] + '...' if user_record and get_user_field(user_record, 'integrations.sellerboard.cogs_url') else None
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500




@app.route('/api/admin/users/bulk', methods=['PUT'])
@admin_required
def admin_bulk_update():
    """Bulk update users data (dangerous operation)"""
    try:
        data = request.json
        new_users = data.get('users', [])
        
        # Validate that it's a list
        if not isinstance(new_users, list):
            return jsonify({'error': 'Users data must be an array'}), 400
        
        # Basic validation - ensure each user has a discord_id
        for user in new_users:
            if not get_user_field(user, 'identity.discord_id'):
                return jsonify({'error': 'Each user must have a discord_id'}), 400
        
        # Replace the entire users array
        if update_users_config(new_users):
            return jsonify({'message': f'Bulk update completed - {len(new_users)} users updated'})
        else:
            return jsonify({'error': 'Failed to perform bulk update'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/dashboard')
@app.route('/dashboard/')
@app.route('/dashboard/<path:path>')
def serve_dashboard(path=None):
    """Serve dashboard routes - redirect to API instructions for now"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>DMS Dashboard</title>
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 40px; background: #f8fafc; }
            .container { background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); max-width: 600px; }
            .success { color: #059669; }
            .info { color: #0369a1; }
            .warning { color: #d97706; }
            h1 { color: #1e293b; }
            .code { background: #f1f5f9; padding: 10px; border-radius: 6px; font-family: monospace; margin: 10px 0; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🚀 DMS Dashboard</h1>
            <p class="success">✅ Authentication successful!</p>
            <p class="info">You've been logged in via Discord OAuth.</p>
            
            <div class="warning">
                <h3>⚠️ Frontend Deployment Needed</h3>
                <p>The React frontend needs to be deployed to access the full dashboard.</p>
            </div>
            
            <h3>Options to Access Your Dashboard:</h3>
            
            <h4>Option 1: Run Frontend Locally</h4>
            <div class="code">
cd dashboard/frontend<br>
REACT_APP_API_URL=https://internet-money-tools-production.up.railway.app npm start
            </div>
            <p>This will open the dashboard at <code>http://localhost:3000</code></p>
            
            <h4>Option 2: Deploy Frontend to Vercel (Recommended)</h4>
            <ol>
                <li>Go to <a href="https://vercel.com" target="_blank">vercel.com</a></li>
                <li>Import your GitHub repository</li>
                <li>Set root directory to: <code>dashboard/frontend</code></li>
                <li>Add environment variable: <code>REACT_APP_API_URL=https://internet-money-tools-production.up.railway.app</code></li>
            </ol>
            
            <h4>Available Now:</h4>
            <ul>
                <li><a href="/api/health">Health Check</a></li>
                <li><a href="/api/user">User Info</a></li>
                <li><a href="/api/analytics/orders">Analytics API</a></li>
                <li><a href="/auth/logout">Logout</a></li>
            </ul>
        </div>
    </body>
    </html>
    """


@app.route('/debug/redirect')
def debug_redirect():
    """Debug endpoint to test redirect logic"""
    # Same logic as Discord callback
    if os.environ.get('FRONTEND_URL'):
        frontend_url = f"{os.environ.get('FRONTEND_URL')}/dashboard"
    else:
        frontend_url = "https://dms-amazon.vercel.app/dashboard"
    
    return jsonify({
        'redirect_url': frontend_url,
        'frontend_env': os.environ.get('FRONTEND_URL'),
        'railway_env': os.environ.get('RAILWAY_STATIC_URL'),
        'message': f'Would redirect to: {frontend_url}'
    })

@app.route('/test/redirect')
def test_redirect():
    """Test actual redirect behavior"""
    return redirect("https://dms-amazon.vercel.app/dashboard")

@app.route('/api/admin/invitations', methods=['GET'])
@admin_required
def admin_get_invitations():
    """Get all invitations for admin panel"""
    try:
        invitations = get_invitations_config()
        return jsonify({'invitations': invitations})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/invitations', methods=['POST'])
@admin_required
def admin_create_invitation():
    """Create a new invitation"""
    try:
        data = request.json
        email = data.get('email')
        
        if not email:
            return jsonify({'error': 'Email is required'}), 400
        
        # Check if email already has a pending invitation
        invitations = get_invitations_config()
        existing_invitation = next((inv for inv in invitations if inv['email'] == email and inv['status'] == 'pending'), None)
        
        if existing_invitation:
            return jsonify({'error': 'Email already has a pending invitation'}), 400
        
        # Check if user already exists
        users = get_users_config()
        existing_user = next((u for u in users if get_user_field(u, 'identity.email') == email), None)
        
        if existing_user:
            return jsonify({'error': 'User with this email already exists'}), 400
        
        # Create new invitation
        invitation_token = str(uuid.uuid4())
        invitation = {
            'token': invitation_token,
            'email': email,
            'status': 'pending',
            'created_at': datetime.utcnow().isoformat(),
            'invited_by': session.get('discord_username', 'Admin'),
            'expires_at': (datetime.utcnow() + timedelta(days=7)).isoformat()
        }
        
        invitations.append(invitation)
        
        if update_invitations_config(invitations):
            # Send invitation email
            email_sent = send_invitation_email(email, invitation_token, session.get('discord_username', 'Admin'))
            
            if not RESEND_API_KEY:
                return jsonify({
                    'message': 'Invitation created successfully. Note: Email notifications are disabled (Resend not configured).',
                    'invitation': invitation,
                    'warning': 'Email service not configured. Please share the invitation link manually.',
                    'invitation_url': f"https://dms-amazon.vercel.app/login?invitation={invitation_token}"
                })
            elif email_sent:
                return jsonify({'message': 'Invitation sent successfully', 'invitation': invitation})
            else:
                return jsonify({
                    'message': 'Invitation created but email failed to send', 
                    'invitation': invitation,
                    'warning': 'Email could not be sent. Please share the invitation link manually.',
                    'invitation_url': f"https://dms-amazon.vercel.app/login?invitation={invitation_token}"
                })
        else:
            return jsonify({'error': 'Failed to create invitation'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/available-permissions', methods=['GET'])
@login_required
def get_available_permissions():
    """Get all available features that can be granted as permissions to subusers"""
    try:
        discord_id = session['discord_id']
        
        # Get all features the main user has access to
        user_features = get_user_features(discord_id)
        
        # Convert features to permission format
        available_permissions = []
        for feature_key, feature_info in user_features.items():
            if feature_info.get('has_access'):
                available_permissions.append({
                    'key': feature_key,
                    'name': feature_info.get('name', feature_key),
                    'description': feature_info.get('description', ''),
                    'is_beta': feature_info.get('is_beta', False)
                })
        
        # Always include basic permissions
        basic_permissions = [
            # sellerboard_upload permission removed - using URL-based approach
            {
                'key': 'reimbursements_analysis',
                'name': 'Reimbursements Analysis',
                'description': 'View and analyze reimbursements',
                'is_beta': False
            }
        ]
        
        # Merge basic permissions with feature permissions
        permission_keys = {p['key'] for p in available_permissions}
        for perm in basic_permissions:
            if perm['key'] not in permission_keys:
                available_permissions.append(perm)
        
        return jsonify({'permissions': available_permissions})
        
    except Exception as e:
        return jsonify({'error': f'Error fetching available permissions: {str(e)}'}), 500

@app.route('/api/invite-subuser', methods=['POST'])
@login_required
def invite_subuser():
    """Invite a sub-user/VA with specific permissions"""
    try:
        data = request.json
        email = data.get('email')
        permissions = data.get('permissions', ['reimbursements_analysis'])  # Default to reimbursements analysis permission
        va_name = data.get('va_name', '')
        
        if not email:
            return jsonify({'error': 'Email is required'}), 400
            
        # Get current user info
        discord_id = session['discord_id']
        users = get_users_config()
        current_user = get_user_record(discord_id)
        
        if not current_user:
            return jsonify({'error': 'User not found'}), 404
        
        # Check if email already has a pending invitation
        invitations = get_invitations_config()
        existing_invitation = next((inv for inv in invitations if inv['email'] == email and inv['status'] == 'pending'), None)
        
        if existing_invitation:
            return jsonify({'error': 'Email already has a pending invitation'}), 400
        
        # Check if user already exists
        existing_user = next((u for u in users if get_user_field(u, 'identity.email') == email), None)
        
        if existing_user:
            return jsonify({'error': 'User with this email already exists'}), 400
        
        # Create new sub-user invitation
        invitation_token = str(uuid.uuid4())
        invitation = {
            'token': invitation_token,
            'email': email,
            'va_name': va_name,
            'status': 'pending',
            'created_at': datetime.utcnow().isoformat(),
            'invited_by': session.get('discord_username', current_user.get('username', 'User')),
            'invited_by_id': discord_id,
            'expires_at': (datetime.utcnow() + timedelta(days=7)).isoformat(),
            'user_type': 'subuser',
            'parent_user_id': discord_id,
            'permissions': permissions
        }
        
        invitations.append(invitation)
        
        if update_invitations_config(invitations):
            # Send invitation email
            inviter_name = current_user.get('username', session.get('discord_username', 'User'))
            email_sent = send_invitation_email(email, invitation_token, inviter_name)
            
            if not RESEND_API_KEY:
                return jsonify({
                    'message': 'Sub-user invitation created successfully. Note: Email notifications are disabled (Resend not configured).',
                    'invitation': invitation,
                    'warning': 'Email service not configured. Please share the invitation link manually.',
                    'invitation_url': f"https://dms-amazon.vercel.app/login?invitation={invitation_token}"
                })
            elif email_sent:
                return jsonify({'message': 'Sub-user invitation sent successfully', 'invitation': invitation})
            else:
                return jsonify({
                    'message': 'Sub-user invitation created but email failed to send', 
                    'invitation': invitation,
                    'warning': 'Email could not be sent. Please share the invitation link manually.',
                    'invitation_url': f"https://dms-amazon.vercel.app/login?invitation={invitation_token}"
                })
        else:
            return jsonify({'error': 'Failed to create invitation'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/my-subusers', methods=['GET'])
@login_required
def get_my_subusers():
    """Get current user's sub-users"""
    try:
        discord_id = session['discord_id']
        users = get_users_config()
        
        print(f"[SUBUSERS] Looking for subusers with parent_id: {discord_id}")
        print(f"[SUBUSERS] Total users in config: {len(users)}")
        
        # Find all sub-users for this parent
        subusers = []
        for user in users:
            user_type = get_user_field(user, 'account.user_type')
            parent_id = get_user_field(user, 'account.parent_user_id')
            
            print(f"[SUBUSERS] User {get_user_field(user, 'identity.discord_id')} - type: {user_type}, parent: {parent_id}")
            
            if user_type == 'subuser' and parent_id == discord_id:
                subuser_data = {
                    'discord_id': get_user_field(user, 'identity.discord_id'),
                    'discord_username': get_user_field(user, 'identity.discord_username'),
                    'va_name': get_user_field(user, 'identity.va_name'),
                    'email': get_user_field(user, 'identity.email'),
                    'permissions': get_user_field(user, 'account.permissions') or [],
                    'last_activity': get_user_field(user, 'account.last_activity'),
                    'user_type': get_user_field(user, 'account.user_type')
                }
                print(f"[SUBUSERS] Found subuser: {subuser_data}")
                subusers.append(subuser_data)
        
        print(f"[SUBUSERS] Returning {len(subusers)} subusers")
        return jsonify({'subusers': subusers})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/my-invitations', methods=['GET'])
@login_required
def get_my_invitations():
    """Get current user's pending invitations"""
    try:
        discord_id = session['discord_id']
        invitations = get_invitations_config()
        
        # Clean up any "accepted" invitations that should have been removed
        users = get_users_config()
        initial_count = len(invitations)
        
        # Remove invitations that have been accepted (user exists with matching email)
        cleaned_invitations = []
        for inv in invitations:
            if inv.get('status') == 'accepted':
                # Check if user with this email actually exists
                user_exists = any(get_user_field(u, 'identity.email') == inv.get('email') for u in users)
                if user_exists:
                    pass  # Debug print removed
                    continue  # Skip this invitation (remove it)
            cleaned_invitations.append(inv)
        
        # Update config if we cleaned up any invitations
        if len(cleaned_invitations) < initial_count:
            update_invitations_config(cleaned_invitations)
        
        # Find all invitations from this user (use cleaned list)
        my_invitations = [
            inv for inv in cleaned_invitations 
            if inv.get('invited_by_id') == discord_id
        ]
        
        return jsonify({'invitations': my_invitations})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/my-invitations/<invitation_token>', methods=['DELETE'])
@login_required
def delete_my_invitation(invitation_token):
    """Delete a pending invitation that the current user created"""
    try:
        discord_id = session['discord_id']
        invitations = get_invitations_config()
        
        # Find the invitation (allow removal of both pending and accepted invitations)
        invitation_to_delete = None
        invitation_index = None
        
        for i, inv in enumerate(invitations):
            if inv['token'] == invitation_token and inv.get('invited_by_id') == discord_id:
                invitation_to_delete = inv
                invitation_index = i
                break
        
        if not invitation_to_delete:
            return jsonify({'error': 'Invitation not found or you do not have permission to delete it'}), 404
        
        # Remove the invitation
        invitations.pop(invitation_index)
        
        if update_invitations_config(invitations):
            return jsonify({'message': 'Invitation deleted successfully'})
        else:
            return jsonify({'error': 'Failed to delete invitation'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/edit-subuser/<subuser_id>', methods=['PUT'])
@login_required
def edit_subuser(subuser_id):
    """Edit a sub-user's permissions and details"""
    try:
        discord_id = session['discord_id']
        data = request.json
        users = get_users_config()
        
        # Find the sub-user
        subuser_index = None
        for i, user in enumerate(users):
            if get_user_field(user, 'identity.discord_id') == subuser_id and get_user_field(user, 'account.parent_user_id') == discord_id:
                subuser_index = i
                break
        
        if subuser_index is None:
            return jsonify({'error': 'Sub-user not found or not authorized'}), 404
        
        # Update the sub-user's information
        if 'va_name' in data:
            set_user_field(users[subuser_index], 'identity.va_name', data['va_name'])
        
        if 'permissions' in data:
            # Validate permissions - include all feature keys the main user has access to
            main_user_features = get_user_features(discord_id)
            valid_feature_keys = [key for key, info in main_user_features.items() if info.get('has_access')]
            
            # Include basic permissions
            basic_permissions = ['reimbursements_analysis', 'all']
            valid_permissions = basic_permissions + valid_feature_keys
            
            # Filter to only valid permissions
            permissions = [p for p in data['permissions'] if p in valid_permissions]
            set_user_field(users[subuser_index], 'account.permissions', permissions)
        
        # Update last modified timestamp
        set_user_field(users[subuser_index], 'account.updated_at', datetime.utcnow().isoformat())
        
        if update_users_config(users):
            return jsonify({
                'success': True, 
                'message': 'Sub-user updated successfully',
                'subuser': {
                    'discord_id': get_user_discord_id(users[subuser_index]),
                    'va_name': get_user_field(users[subuser_index], 'identity.va_name'),
                    'permissions': get_user_permissions(users[subuser_index]),
                    'updated_at': get_user_field(users[subuser_index], 'profile.updated_at') or users[subuser_index].get('updated_at')
                }
            })
        else:
            return jsonify({'error': 'Failed to update users configuration'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/revoke-subuser/<subuser_id>', methods=['DELETE'])
@login_required
def revoke_subuser_access(subuser_id):
    """Revoke access for a sub-user"""
    try:
        discord_id = session['discord_id']
        users = get_users_config()
        
        # Find the sub-user
        subuser = next((u for u in users if get_user_field(u, 'identity.discord_id') == subuser_id and get_user_field(u, 'account.parent_user_id') == discord_id), None)
        
        if not subuser:
            return jsonify({'error': 'Sub-user not found or not authorized'}), 404
        
        # Remove the sub-user
        users = [u for u in users if not (get_user_field(u, 'identity.discord_id') == subuser_id and get_user_field(u, 'account.parent_user_id') == discord_id)]
        
        if update_users_config(users):
            return jsonify({'message': 'Sub-user access revoked successfully'})
        else:
            return jsonify({'error': 'Failed to revoke access'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/invitations/<invitation_id>', methods=['DELETE'])
@admin_required
def admin_delete_invitation(invitation_id):
    """Delete an invitation"""
    try:
        invitations = get_invitations_config()
        invitation_to_delete = None
        
        for i, inv in enumerate(invitations):
            if inv['token'] == invitation_id:
                invitation_to_delete = invitations.pop(i)
                break
        
        if not invitation_to_delete:
            return jsonify({'error': 'Invitation not found'}), 404
        
        if update_invitations_config(invitations):
            return jsonify({'message': 'Invitation deleted successfully'})
        else:
            return jsonify({'error': 'Failed to delete invitation'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Manual Script Control Endpoints
@app.route('/api/admin/script-configs', methods=['GET'])
@admin_required
def get_script_configs():
    """Get current script configuration from S3"""
    try:
        s3_client = get_s3_client()
        configs = {}
        
        # Get amznUploadConfig (listing loader and sellerboard script)
        try:
            response = s3_client.get_object(Bucket=CONFIG_S3_BUCKET, Key='amznUploadConfig.json')
            amzn_config = json.loads(response['Body'].read().decode('utf-8'))
            # Extract date only (no time) from the stored date
            last_date = amzn_config.get('last_processed_date', '')
            if last_date:
                try:
                    # Parse the date and extract just the date part
                    parsed_date = datetime.fromisoformat(last_date.replace('Z', '+00:00'))
                    date_only = parsed_date.strftime('%Y-%m-%d')
                except:
                    # If parsing fails, use as-is
                    date_only = last_date
            else:
                date_only = ''
            
            configs['amznUploadConfig'] = {
                'last_processed_date': date_only,
                'status': 'found'
            }
        except Exception as e:
            pass  # Debug print removed
            configs['amznUploadConfig'] = {
                'last_processed_date': '',
                'status': 'not_found',
                'error': str(e)
            }
        
        # Get config.json (prepuploader script)
        try:
            response = s3_client.get_object(Bucket=CONFIG_S3_BUCKET, Key='config.json')
            prep_config = json.loads(response['Body'].read().decode('utf-8'))
            # Extract date only (no time) from the stored date
            last_date = prep_config.get('last_processed_date', '')
            if last_date:
                try:
                    # Parse the date and extract just the date part
                    parsed_date = datetime.fromisoformat(last_date.replace('Z', '+00:00'))
                    date_only = parsed_date.strftime('%Y-%m-%d')
                except:
                    # If parsing fails, use as-is
                    date_only = last_date
            else:
                date_only = ''
            
            configs['config'] = {
                'last_processed_date': date_only,
                'status': 'found'
            }
        except Exception as e:
            pass  # Debug print removed
            configs['config'] = {
                'last_processed_date': '',
                'status': 'not_found',
                'error': str(e)
            }
        
        return jsonify(configs)
        
    except Exception as e:
        pass  # Debug print removed
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/script-configs', methods=['POST'])
@admin_required
def update_script_configs():
    """Update script configuration in S3"""
    try:
        data = request.json
        s3_client = get_s3_client()
        results = {}
        
        
        # Update amznUploadConfig if provided
        if 'amznUploadConfig' in data:
            try:
                # Convert date to datetime with time set to start of day
                date_str = data['amznUploadConfig']['last_processed_date']
                if date_str:
                    # Use simple date format (YYYY-MM-DD)
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                    simple_date = date_obj.strftime('%Y-%m-%d')
                else:
                    simple_date = ''
                
                new_config = {
                    'last_processed_date': simple_date
                }
                
                s3_client.put_object(
                    Bucket=CONFIG_S3_BUCKET,
                    Key='amznUploadConfig.json',
                    Body=json.dumps(new_config, indent=2),
                    ContentType='application/json'
                )
                
                results['amznUploadConfig'] = {
                    'status': 'updated',
                    'last_processed_date': new_config['last_processed_date']
                }
                
            except Exception as e:
                pass  # Debug print removed
                results['amznUploadConfig'] = {
                    'status': 'error',
                    'error': str(e)
                }
        
        # Update config.json if provided
        if 'config' in data:
            try:
                # Use simple date format
                date_str = data['config']['last_processed_date']
                if date_str:
                    # Use simple date format (YYYY-MM-DD)
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                    simple_date = date_obj.strftime('%Y-%m-%d')
                else:
                    simple_date = ''
                
                new_config = {
                    'last_processed_date': simple_date
                }
                
                s3_client.put_object(
                    Bucket=CONFIG_S3_BUCKET,
                    Key='config.json',
                    Body=json.dumps(new_config, indent=2),
                    ContentType='application/json'
                )
                
                results['config'] = {
                    'status': 'updated',  
                    'last_processed_date': new_config['last_processed_date']
                }
                
            except Exception as e:
                pass  # Debug print removed
                results['config'] = {
                    'status': 'error',
                    'error': str(e)
                }
        
        return jsonify({
            'message': 'Script configurations updated',
            'results': results
        })
        
    except Exception as e:
        pass  # Debug print removed
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

def fetch_flexible_cogs_from_all_worksheets(access_token, sheet_id, column_mapping):
    """
    Flexibly fetch COGS data from all worksheets with loose column matching
    Returns combined data from all worksheets that contain ASIN and COGS columns
    """
    import urllib.parse
    
    try:
        # Get all worksheets using HTTP API
        url = f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}"
        headers = {"Authorization": f"Bearer {access_token}"}
        resp = requests.get(url, headers=headers)
        
        if resp.status_code != 200:
            print(f"ERROR: Failed to get sheet metadata: {resp.status_code}")
            return []
        
        sheet_metadata = resp.json()
        worksheets = [sheet['properties']['title'] for sheet in sheet_metadata.get('sheets', [])]
        
        print(f"DEBUG: Found {len(worksheets)} worksheets: {worksheets}")
        
        all_cogs_data = []
        processed_worksheets = 0
        
        for worksheet_name in worksheets:
            try:
                print(f"DEBUG: Processing worksheet: {worksheet_name}")
                
                # Get worksheet data using HTTP API
                range_name = f"'{worksheet_name}'!A1:Z1000"
                url = (
                    f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}"
                    f"/values/{urllib.parse.quote(range_name)}?majorDimension=ROWS"
                )
                headers = {"Authorization": f"Bearer {access_token}"}
                resp = requests.get(url, headers=headers)
                
                if resp.status_code != 200:
                    print(f"DEBUG: Failed to fetch {worksheet_name}: {resp.status_code}")
                    continue
                
                data = resp.json()
                values = data.get('values', [])
                if not values or len(values) < 2:  # Need at least header + 1 data row
                    print(f"DEBUG: Skipping {worksheet_name} - insufficient data")
                    continue
                
                # Convert to DataFrame
                df = pd.DataFrame(values[1:], columns=values[0])
                
                # Look for ASIN column (flexible matching)
                asin_col = None
                for col in df.columns:
                    if 'asin' in str(col).lower():
                        asin_col = col
                        break
                
                # Look for COGS/Cost column (flexible matching)
                cogs_col = None
                for col in df.columns:
                    col_lower = str(col).lower()
                    if any(keyword in col_lower for keyword in ['cogs', 'cost']):
                        cogs_col = col
                        break
                
                if not asin_col or not cogs_col:
                    print(f"DEBUG: Skipping {worksheet_name} - missing ASIN ({asin_col}) or COGS ({cogs_col}) column")
                    continue
                
                # Filter rows with valid ASIN and COGS data
                valid_data = df[(df[asin_col].notna()) & (df[asin_col] != '') & 
                               (df[cogs_col].notna()) & (df[cogs_col] != '')]
                
                if valid_data.empty:
                    print(f"DEBUG: Skipping {worksheet_name} - no valid ASIN/COGS pairs")
                    continue
                
                # Process valid rows
                for _, row in valid_data.iterrows():
                    asin = str(row[asin_col]).strip()
                    cogs = row[cogs_col]
                    
                    # Try to convert COGS to float
                    try:
                        if isinstance(cogs, str):
                            cogs = cogs.replace('$', '').replace(',', '').strip()
                        cogs_value = float(cogs)
                        
                        all_cogs_data.append({
                            'asin': asin,
                            'cogs': cogs_value,
                            'worksheet': worksheet_name
                        })
                    except (ValueError, TypeError):
                        print(f"DEBUG: Invalid COGS value in {worksheet_name}: {cogs}")
                        continue
                
                processed_worksheets += 1
                print(f"DEBUG: Extracted {len(valid_data)} COGS entries from {worksheet_name}")
                
            except Exception as e:
                print(f"DEBUG: Error processing worksheet {worksheet_name}: {str(e)}")
                continue
        
        print(f"DEBUG: Successfully processed {processed_worksheets} worksheets, found {len(all_cogs_data)} total COGS entries")
        return all_cogs_data
        
    except Exception as e:
        print(f"ERROR: Failed to fetch flexible COGS data: {str(e)}")
        return []

@app.route('/api/manual-sellerboard-update', methods=['POST'])
@login_required
def manual_sellerboard_update():
    """Manually trigger Sellerboard COGS update for the current user"""
    try:
        data = request.json or {}
        full_update = data.get('full_update', False)
        discord_id = session.get('discord_id')
        
        
        if not discord_id:
            return jsonify({'error': 'User not authenticated or discord_id not found'}), 401
        
        # Get user configuration
        users = get_users_config()
        user_config = None
        
        for user in users:
            if get_user_field(user, 'identity.discord_id') == discord_id:
                user_config = user
                break
        
        if not user_config:
            return jsonify({'error': 'User configuration not found'}), 404
        
        
        # Check if user has required settings
        user_record = user_config.get('user_record', {})
        
        # If user_record is empty, check if settings are at the top level
        if not user_record:
            user_record = user_config  # Use the main config if no nested user_record
        
        # Note: We no longer require Sellerboard COGS URL since we fetch from email
        # Check for email access instead
        
        if not (get_user_field(user_record, 'integrations.google.tokens') or {}).get('refresh_token'):
            return jsonify({'error': 'Google account not linked. Please link your Google account.'}), 400
        
        if not get_user_field(user_record, 'files.sheet_id') or not get_user_field(user_record, 'integrations.google.worksheet_title'):
            return jsonify({'error': 'Google Sheet not configured. Please complete sheet setup.'}), 400
        
        
        # Prepare Lambda payload
        lambda_payload = {
            'manual_trigger': True,
            'target_user': discord_id,
            'full_update': full_update,
            'force_process_all_data': full_update  # For full update, ignore date filtering
        }
        
        # Process Sellerboard COGS update directly in dashboard backend
        # This avoids AWS Lambda IP blocking issues
        
        try:
            # Import required modules for processing
            from orders_analysis import EnhancedOrdersAnalysis
            from io import BytesIO
            import base64
            import pandas as pd
            from datetime import datetime
            import tempfile
            import os
            
            # Fetch Sellerboard COGS data from email instead of URL
            print(f"[MANUAL UPDATE] Fetching Sellerboard COGS data from email for user {discord_id}")
            cogs_data = fetch_sellerboard_cogs_data_from_email(discord_id)
            
            if not cogs_data:
                return jsonify({
                    'success': False,
                    'message': 'Could not fetch Sellerboard COGS data from email.',
                    'full_update': full_update,
                    'emails_sent': 0,
                    'users_processed': 0,
                    'errors': ['Email COGS fetch failed'],
                    'details': 'Reasons: Unable to fetch COGS data from Sellerboard emails. Please ensure Gmail permissions are granted and recent COGS emails are available.'
                })
            
            # Get user's Google Sheet data for COGS processing
            sheet_id = get_user_sheet_id(user_record)
            worksheet_title = get_user_field(user_record, 'integrations.google.worksheet_title') or user_record.get('worksheet_title')
            google_tokens = get_user_field(user_record, 'integrations.google.tokens') or {}
            refresh_token = google_tokens.get('refresh_token')
            
            if not (sheet_id and worksheet_title and refresh_token):
                return jsonify({
                    'success': False,
                    'message': 'Update completed but no emails were sent.',
                    'full_update': full_update,
                    'emails_sent': 0,
                    'users_processed': 0,
                    'errors': ['Google Sheet configuration incomplete'],
                    'details': 'Reasons: Missing Google Sheet ID, worksheet title, or authentication. Please complete your Google Sheet setup.'
                })
            
            # Use email data we already fetched
            # The fetch_sellerboard_cogs_data_from_email returns a dict with various keys
            if isinstance(cogs_data, dict) and 'data' in cogs_data:
                # It seems to return data in a different format
                sb_df = pd.DataFrame(cogs_data['data'])
                original_filename = cogs_data.get('filename', 'sellerboard_cogs.csv')
            elif isinstance(cogs_data, dict) and 'dataframe' in cogs_data:
                # If it has a dataframe key, use that
                sb_df = pd.DataFrame(cogs_data['data'])
                original_filename = cogs_data.get('filename', 'sellerboard_cogs.csv')
            else:
                # Try to handle it as the dataframe directly
                return jsonify({
                    'success': False,
                    'message': 'Unexpected COGS data format from email.',
                    'full_update': full_update,
                    'emails_sent': 0,
                    'users_processed': 0,
                    'errors': ['COGS data format error'],
                    'details': f'Expected dict with dataframe, got: {type(cogs_data)}'
                })
            
            print(f"[MANUAL UPDATE] Using Sellerboard COGS data from email: {original_filename}")
            print(f"[MANUAL UPDATE] Found {len(sb_df)} products in COGS data")
            # Normalize ASIN column name if needed
            asin_column = cogs_data.get('asin_column', 'ASIN')
            if asin_column != 'ASIN' and asin_column in sb_df.columns:
                sb_df = sb_df.rename(columns={asin_column: 'ASIN'})
            
            # Ensure required columns exist
            required_columns = ['ASIN', 'SKU', 'Title', 'Cost']
            missing_columns = [col for col in required_columns if col not in sb_df.columns]
            
            if missing_columns:
                return jsonify({
                    'success': False,
                    'message': f'Sellerboard COGS file missing required columns: {", ".join(missing_columns)}',
                    'full_update': full_update,
                    'emails_sent': 0,
                    'users_processed': 0,
                    'errors': [f'Missing columns: {", ".join(missing_columns)}'],
                    'details': f'The Sellerboard COGS email file is missing required columns: {", ".join(missing_columns)}'
                })
            
            sellerboard_df = sb_df  # Use consistent variable name
            print(f"DEBUG: Successfully loaded COGS data from email: {len(sellerboard_df)} rows, {len(sellerboard_df.columns)} columns")
            print(f"DEBUG: COGS data columns: {list(sellerboard_df.columns)}")
            
            # Get Google Sheet data for COGS processing
            print("DEBUG: Fetching Google Sheet data...")
            
            # Get column mapping for processing
            column_mapping = get_user_column_mapping(user_record)
            
            # Check if user has search_all_worksheets enabled OR if this is a full update
            search_all_worksheets = get_user_field(user_record, 'integrations.google.search_all_worksheets') or user_record.get('search_all_worksheets', False)
            
            # For full updates, always scan all worksheets (like the dedicated lead sheet button)
            use_all_worksheets = search_all_worksheets or full_update
            
            # Fetch COGS data from ALL worksheets if enabled or full update, otherwise just main worksheet
            print(f"DEBUG: search_all_worksheets = {search_all_worksheets}, full_update = {full_update}, use_all_worksheets = {use_all_worksheets}")
            
            if use_all_worksheets:
                print("DEBUG: Fetching COGS data from ALL worksheets with flexible column matching...")
                
                # Get fresh access token
                access_token = refresh_google_token(user_record)
                
                # Use custom function to fetch from all worksheets with flexible matching
                cogs_data_all = fetch_flexible_cogs_from_all_worksheets(
                    access_token, sheet_id, column_mapping
                )
                
                if not cogs_data_all:
                    return jsonify({
                        'success': False,
                        'message': 'No COGS data found in any worksheets.',
                        'full_update': full_update,
                        'emails_sent': 0,
                        'users_processed': 0,
                        'errors': ['No COGS data in worksheets'],
                        'details': 'No ASIN/COGS data found across all worksheets in the Google Sheet.'
                    })
                
                # Convert to DataFrame for processing
                sheet_df = pd.DataFrame(cogs_data_all)
                print(f"DEBUG: Fetched COGS data for {len(sheet_df)} products from ALL worksheets with flexible matching")
                print(f"DEBUG: All worksheets DataFrame columns: {list(sheet_df.columns)}")
                
                # Data is already in standardized format from our custom function
                asin_field = 'asin'
                cogs_field = 'cogs'
                print(f"DEBUG: Using standardized columns - ASIN: {asin_field}, COGS: {cogs_field}")
            else:
                sheet_df = pd.DataFrame()  # Empty DataFrame if no data returned
                
                # If all worksheets approach failed, fallback to main worksheet
                if sheet_df.empty:
                    print("DEBUG: All worksheets approach found no valid data, falling back to main worksheet...")
                    use_all_worksheets = False
                
            if not use_all_worksheets:
                print("DEBUG: Fetching data from main worksheet only...")
                # Fetch Google Sheet data (handles token refresh internally)
                sheet_df = fetch_google_sheet_as_df(user_record, worksheet_title)
                
                if sheet_df.empty:
                    return jsonify({
                        'success': False,
                        'message': 'No data found in Google Sheet.',
                        'full_update': full_update,
                        'emails_sent': 0,
                        'users_processed': 0,
                        'errors': ['Empty Google Sheet'],
                        'details': f'No data found in worksheet "{worksheet_title}".'
                    })
                
                print(f"DEBUG: Fetched {len(sheet_df)} rows from main worksheet")
                
                # Set field mappings for main worksheet
                asin_field = column_mapping.get("ASIN", "ASIN") 
                cogs_field = column_mapping.get("COGS", "COGS")
            
            # Get date field mapping (used in both cases)
            date_field = column_mapping.get("Date", "Date")
            
            # Filter data for processing (date filtering only if not using all worksheets data)
            from datetime import datetime, timedelta
            
            if use_all_worksheets:
                # When using all worksheets, we already have COGS-specific data
                filtered_df = sheet_df.copy()
                print(f"DEBUG: Using all worksheets COGS data - {len(filtered_df)} products")
            else:
                # Apply date filtering for single worksheet
                if full_update:
                    filtered_df = sheet_df.copy()
                    print(f"DEBUG: Full update - processing all {len(filtered_df)} rows")
                else:
                    # Quick update - only process recent data (last 30 days)
                    cutoff_date = datetime.now() - timedelta(days=30)
                    
                    if date_field in sheet_df.columns:
                        sheet_df[date_field] = pd.to_datetime(sheet_df[date_field], errors='coerce')
                        filtered_df = sheet_df[sheet_df[date_field] >= cutoff_date].copy()
                        print(f"DEBUG: Quick update - processing {len(filtered_df)} rows from last 30 days")
                    else:
                        filtered_df = sheet_df.copy()
                        print(f"DEBUG: No date field found, processing all {len(filtered_df)} rows")
            
            # Process COGS updates
            actual_updates = []
            potential_updates = []
            new_products = []
            seen_asins = set()
            
            # Clean and prepare data
            if asin_field in filtered_df.columns and cogs_field in filtered_df.columns:
                # Remove rows with missing ASIN or COGS
                valid_rows = filtered_df.dropna(subset=[asin_field, cogs_field])
                
                for _, row in valid_rows.iterrows():
                    asin = str(row[asin_field]).strip()
                    
                    if not asin or asin in seen_asins:
                        continue
                    seen_asins.add(asin)
                    
                    # Extract new cost
                    new_cost_raw = row[cogs_field]
                    try:
                        if isinstance(new_cost_raw, str):
                            new_cost = float(new_cost_raw.replace('$', '').replace(',', ''))
                        else:
                            new_cost = float(new_cost_raw)
                    except (ValueError, TypeError):
                        continue
                    
                    # Check if ASIN exists in Sellerboard data (may be multiple SKUs per ASIN)
                    existing = sellerboard_df[sellerboard_df["ASIN"] == asin]
                    
                    if existing.empty:
                        # New product - add to Sellerboard
                        new_sku = f"ABCD-{asin[-6:]}"
                        new_product = {
                            'ASIN': asin,
                            'SKU': new_sku,
                            'Title': str(row.get('Name', asin)),
                            'Cost': new_cost
                        }
                        
                        # Add to dataframe
                        new_row_df = pd.DataFrame([new_product])
                        sellerboard_df = pd.concat([sellerboard_df, new_row_df], ignore_index=True)
                        new_products.append(new_product)
                        actual_updates.append({
                            'ASIN': asin,
                            'SKU': new_sku,
                            'Name': str(row.get('Name', asin)),
                            'new_cost': new_cost,
                            'old_cost': None,
                            'action': 'added'
                        })
                        
                    else:
                        # Existing product(s) - update ALL rows with this ASIN (multiple SKUs per ASIN)
                        print(f"DEBUG: Found {len(existing)} rows with ASIN {asin}")
                        
                        # Process each row with this ASIN
                        for existing_idx, existing_row in existing.iterrows():
                            old_cost = existing_row['Cost']
                            sku = existing_row['SKU']
                            title = existing_row['Title']
                            
                            try:
                                if pd.isna(old_cost) or old_cost is None:
                                    # No existing cost - update automatically
                                    sellerboard_df.loc[existing_idx, "Cost"] = new_cost
                                    actual_updates.append({
                                        'ASIN': asin,
                                        'SKU': sku,
                                        'Name': title,
                                        'new_cost': new_cost,
                                        'old_cost': None,
                                        'action': 'updated'
                                    })
                                elif abs(float(old_cost) - new_cost) > 0.01:
                                    # Cost difference detected - add to potential updates
                                    potential_updates.append({
                                        'ASIN': asin,
                                        'SKU': sku,
                                        'Name': title,
                                        'new_cost': new_cost,
                                        'old_cost': float(old_cost),
                                        'action': 'suggested'
                                    })
                            except (ValueError, TypeError):
                                # Old cost invalid - update with new cost
                                sellerboard_df.loc[existing_idx, "Cost"] = new_cost
                                actual_updates.append({
                                    'ASIN': asin,
                                    'SKU': sku,
                                    'Name': title,
                                    'new_cost': new_cost,
                                    'old_cost': old_cost,
                                    'action': 'updated'
                                })
            
            # Also check Sellerboard products with Hide=yes for COGS updates from purchase data
            print("DEBUG: Checking hidden Sellerboard products for COGS updates...")
            if 'Hide' in sellerboard_df.columns:
                hidden_products = sellerboard_df[sellerboard_df['Hide'].str.upper() == 'YES']
                print(f"DEBUG: Found {len(hidden_products)} hidden products in Sellerboard")
                
                for _, hidden_row in hidden_products.iterrows():
                    hidden_asin = str(hidden_row['ASIN']).strip()
                    
                    if hidden_asin in seen_asins:
                        continue  # Already processed
                    
                    # Check if this ASIN has cost data in purchase records
                    matching_purchases = filtered_df[filtered_df[asin_field].astype(str).str.strip() == hidden_asin]
                    
                    if not matching_purchases.empty:
                        # Get the most recent cost for this ASIN
                        latest_purchase = matching_purchases.iloc[-1]  # Most recent
                        new_cost_raw = latest_purchase[cogs_field]
                        
                        try:
                            if isinstance(new_cost_raw, str):
                                new_cost = float(new_cost_raw.replace('$', '').replace(',', ''))
                            else:
                                new_cost = float(new_cost_raw)
                        except (ValueError, TypeError):
                            continue
                        
                        # Check if cost needs updating
                        old_cost = hidden_row['Cost']
                        
                        # Update ALL hidden products with this ASIN (multiple SKUs per ASIN)
                        all_hidden_with_asin = sellerboard_df[sellerboard_df["ASIN"] == hidden_asin]
                        
                        for hidden_idx, hidden_item in all_hidden_with_asin.iterrows():
                            old_cost = hidden_item['Cost']
                            
                            try:
                                if pd.isna(old_cost) or old_cost is None:
                                    # No existing cost - update automatically
                                    sellerboard_df.loc[hidden_idx, "Cost"] = new_cost
                                    actual_updates.append({
                                        'ASIN': hidden_asin,
                                        'SKU': hidden_item['SKU'],
                                        'Name': hidden_item['Title'],
                                        'new_cost': new_cost,
                                        'old_cost': None,
                                        'action': 'updated (hidden product)'
                                    })
                                elif abs(float(old_cost) - new_cost) > 0.01:
                                    # Cost difference detected - add to potential updates
                                    potential_updates.append({
                                        'ASIN': hidden_asin,
                                        'SKU': hidden_item['SKU'],
                                        'Name': hidden_item['Title'],
                                        'new_cost': new_cost,
                                        'old_cost': float(old_cost),
                                        'action': 'suggested (hidden product)'
                                    })
                            except (ValueError, TypeError):
                                # Old cost invalid - update with new cost
                                sellerboard_df.loc[hidden_idx, "Cost"] = new_cost
                                actual_updates.append({
                                    'ASIN': hidden_asin,
                                    'SKU': hidden_item['SKU'],
                                    'Name': hidden_item['Title'],
                                    'new_cost': new_cost,
                                    'old_cost': old_cost,
                                    'action': 'updated (hidden product)'
                                })
                        
                        seen_asins.add(hidden_asin)
            
            print(f"DEBUG: COGS Update Summary:")
            print(f"  - Actual updates: {len(actual_updates)}")
            print(f"  - Potential updates: {len(potential_updates)}")
            print(f"  - New products: {len(new_products)}")
            
            updated_sellerboard_data = sellerboard_df
            
            # Convert DataFrame to Excel for email attachment
            print("DEBUG: Converting to Excel format...")
            excel_buffer = BytesIO()
            updated_sellerboard_data.to_excel(excel_buffer, index=False, engine='openpyxl')
            excel_buffer.seek(0)
            excel_data = excel_buffer.getvalue()
            excel_buffer.close()
            
            # Send email with updated file
            print("DEBUG: Sending email with updated Sellerboard file...")
            user_email = get_user_field(user_record, 'identity.email')
            if not user_email:
                return jsonify({
                    'success': False,
                    'message': 'Update completed but no emails were sent.',
                    'full_update': full_update,
                    'emails_sent': 0,
                    'users_processed': 1,
                    'errors': ['User email not configured'],
                    'details': 'Reasons: User email not found in configuration.'
                })
            
            # Email configuration using Resend API
            if not RESEND_API_KEY:
                return jsonify({
                    'success': False,
                    'message': 'Update completed but no emails were sent.',
                    'full_update': full_update,
                    'emails_sent': 0,
                    'users_processed': 1,
                    'errors': ['Email configuration missing'],
                    'details': 'Reasons: Resend API key not configured on server.'
                })
            
            # Create attachment for Resend
            filename = f"sellerboard_cogs_updated_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            encoded_excel = base64.b64encode(excel_data).decode('utf-8')
            
            # Build HTML email content with update tracking
            update_type = "Full" if full_update else "Quick"
            html_content = f"""
            <html>
            <body>
                <h2 style="color: #2c3e50;">Sellerboard COGS Update Complete</h2>
                <p>Hello,</p>
                <p>Your Sellerboard COGS report has been successfully updated.</p>
                
                <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <h3 style="color: #34495e; margin-top: 0;">Update Details:</h3>
                    <ul style="margin: 0;">
                        <li><strong>Update Type:</strong> {update_type}</li>
                        <li><strong>Total Products in File:</strong> {len(updated_sellerboard_data)} items</li>
                        <li><strong>COGS Actually Updated:</strong> {len(actual_updates)} items</li>
                        <li><strong>New Products Added:</strong> {len(new_products)} items</li>
                        <li><strong>Potential Updates (Review Needed):</strong> {len(potential_updates)} items</li>
                        <li><strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC</li>
                    </ul>
                </div>
                
                {'''<div style="background-color: #e8f5e8; padding: 10px; border-radius: 5px; margin: 15px 0;">
                    <h4 style="color: #2d5016; margin-top: 0;">Actual Updates Made:</h4>''' + ''.join([f'<p style="margin: 2px 0; font-size: 12px;">• {update["ASIN"]} - ${update["new_cost"]:.2f} ({update["action"]})</p>' for update in actual_updates[:10]]) + (f'<p style="margin: 2px 0; font-size: 12px; font-style: italic;">...and {len(actual_updates) - 10} more</p>' if len(actual_updates) > 10 else '') + '</div>' if actual_updates else ''}
                
                <p>The updated file is attached to this email.</p>
                
                <p>Best regards,<br>DMS Team</p>
            </body>
            </html>
            """
            
            # Send email via Resend API
            from_email = f'DMS Dashboard <{RESEND_FROM_DOMAIN}>'
            
            payload = {
                'from': from_email,
                'to': [user_email],
                'subject': f'Updated Sellerboard COGS Report - {update_type} Update',
                'html': html_content,
                'attachments': [{
                    'filename': filename,
                    'content': encoded_excel,
                    'content_type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                }]
            }
            
            response = requests.post(
                'https://api.resend.com/emails',
                headers={
                    'Authorization': f'Bearer {RESEND_API_KEY}',
                    'Content-Type': 'application/json'
                },
                json=payload
            )
            
            if response.status_code != 200:
                print(f"Failed to send email via Resend. Status: {response.status_code}, Response: {response.text}")
                return jsonify({
                    'success': False,
                    'message': 'Update completed but email failed to send.',
                    'full_update': full_update,
                    'emails_sent': 0,
                    'users_processed': 1,
                    'errors': ['Email delivery failed'],
                    'details': f'Resend API error: {response.status_code}'
                })
            
            print(f"DEBUG: Email sent successfully to {user_email}")
            
            return jsonify({
                'success': True,
                'message': f'Update completed successfully! {len(actual_updates)} COGS updated, {len(new_products)} new products added.',
                'full_update': full_update,
                'emails_sent': 1,
                'users_processed': 1,
                'actual_updates': len(actual_updates),
                'potential_updates': len(potential_updates),
                'new_products': len(new_products),
                'total_products': len(updated_sellerboard_data),
                'details': f'{"Full" if full_update else "Quick"} update processed {len(actual_updates)} COGS updates and {len(new_products)} new products.'
            })
            
        except Exception as processing_error:
            print(f"DEBUG: Error in dashboard COGS processing: {processing_error}")
            import traceback
            traceback.print_exc()
            
            return jsonify({
                'success': False,
                'message': 'Update completed but no emails were sent.',
                'full_update': full_update,
                'emails_sent': 0,
                'users_processed': 0,
                'errors': [str(processing_error)],
                'details': f'Error during processing: {str(processing_error)}'
            })
            
    except Exception as e:
        print(f"Error in manual sellerboard update: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/manual-cogs-update-from-leadsheet', methods=['POST'])
@login_required
def manual_cogs_update_from_leadsheet():
    """Manually update COGS of all ASINs in Sellerboard from lead sheet worksheets"""
    try:
        discord_id = session.get('discord_id')
        
        if not discord_id:
            return jsonify({'error': 'User not authenticated or discord_id not found'}), 401
        
        # Get user configuration  
        user_record = get_user_record(discord_id)
        if not user_record:
            return jsonify({'error': 'User configuration not found'}), 404
        
        # Check if user has required settings
        google_tokens = get_user_field(user_record, 'integrations.google.tokens') or {}
        sheet_id = get_user_sheet_id(user_record) 
        enable_source_links = get_user_field(user_record, 'settings.enable_source_links') or False
        search_all_worksheets = get_user_field(user_record, 'integrations.google.search_all_worksheets') or False
        
        if not google_tokens.get('refresh_token'):
            return jsonify({'error': 'Google account not linked. Please link your Google account.'}), 400
        
        if not sheet_id:
            return jsonify({'error': 'Google Sheet not configured. Please complete sheet setup.'}), 400
        
        if not enable_source_links or not search_all_worksheets:
            return jsonify({
                'error': 'Lead sheet scanning not enabled. Please enable "Source Links" and "Search All Worksheets" in your settings.'
            }), 400
        
        # First fetch the latest Sellerboard COGS data from email
        print(f"[MANUAL COGS UPDATE] Fetching Sellerboard COGS data from email for user {discord_id}")
        cogs_data = fetch_sellerboard_cogs_data_from_email(discord_id)
        
        if not cogs_data:
            return jsonify({
                'error': 'Could not fetch Sellerboard COGS data from email',
                'message': 'Please ensure Gmail permissions are granted and recent COGS emails are available.'
            }), 400
        
        sb_df = pd.DataFrame(cogs_data['data'])
        print(f"[MANUAL COGS UPDATE] Found {len(sb_df)} products in Sellerboard COGS data")
        
        # Get fresh access token
        access_token = refresh_google_token(user_record)
        
        # Fetch all worksheets from the Google Sheet
        print(f"[MANUAL COGS UPDATE] Scanning all worksheets in lead sheet for cost data")
        worksheets_url = f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}"
        headers = {"Authorization": f"Bearer {access_token}"}
        
        response = requests.get(worksheets_url, headers=headers)
        if not response.ok:
            return jsonify({'error': 'Failed to access Google Sheet'}), 400
        
        sheet_info = response.json()
        worksheets = sheet_info.get('sheets', [])
        
        print(f"[MANUAL COGS UPDATE] Found {len(worksheets)} worksheets to scan")
        
        # Collect cost data from all worksheets
        cost_lookup = {}  # {ASIN: {cost: float, worksheet: str, last_seen: datetime}}
        
        for sheet in worksheets:
            worksheet_name = sheet['properties']['title']
            print(f"[MANUAL COGS UPDATE] Scanning worksheet: {worksheet_name}")
            
            try:
                # Fetch worksheet data
                ws_df = fetch_google_sheet_api(access_token, sheet_id, worksheet_name)
                
                if ws_df.empty:
                    continue
                
                # Look for ASIN and COGS columns
                asin_col = None
                cogs_col = None
                date_col = None
                
                for col in ws_df.columns:
                    col_lower = col.lower()
                    if 'asin' in col_lower and not asin_col:
                        asin_col = col
                    elif 'cogs' in col_lower or 'cost' in col_lower:
                        cogs_col = col
                    elif 'date' in col_lower:
                        date_col = col
                
                if not asin_col or not cogs_col:
                    print(f"[MANUAL COGS UPDATE] Skipping {worksheet_name} - missing ASIN or COGS column")
                    continue
                
                # Process each row for cost data
                for _, row in ws_df.iterrows():
                    asin = str(row[asin_col]).strip()
                    if not asin or asin.lower() in ['nan', 'none', '']:
                        continue
                    
                    try:
                        cost_value = pd.to_numeric(str(row[cogs_col]).replace('$', '').replace(',', ''), errors='coerce')
                        if pd.isna(cost_value):
                            continue
                        
                        # Get date if available
                        date_value = datetime.now()
                        if date_col and date_col in row.index:
                            try:
                                date_value = pd.to_datetime(row[date_col], errors='coerce')
                                if pd.isna(date_value):
                                    date_value = datetime.now()
                            except:
                                date_value = datetime.now()
                        
                        # Keep the most recent cost for each ASIN
                        if asin not in cost_lookup or date_value > cost_lookup[asin]['last_seen']:
                            cost_lookup[asin] = {
                                'cost': float(cost_value),
                                'worksheet': worksheet_name,
                                'last_seen': date_value
                            }
                    
                    except Exception as row_error:
                        continue
                
                print(f"[MANUAL COGS UPDATE] Found {len([k for k in cost_lookup if cost_lookup[k]['worksheet'] == worksheet_name])} cost entries in {worksheet_name}")
                
            except Exception as ws_error:
                print(f"[MANUAL COGS UPDATE] Error processing worksheet {worksheet_name}: {ws_error}")
                continue
        
        print(f"[MANUAL COGS UPDATE] Total unique ASINs with cost data found: {len(cost_lookup)}")
        
        # Update Sellerboard COGS data with found costs
        updates_made = 0
        potential_updates = []
        
        for _, row in sb_df.iterrows():
            asin = str(row['ASIN']).strip()
            if asin in cost_lookup:
                current_cost = pd.to_numeric(str(row.get('Cost', 0)).replace('$', ''), errors='coerce')
                new_cost = cost_lookup[asin]['cost']
                worksheet_source = cost_lookup[asin]['worksheet']
                
                if pd.isna(current_cost) or current_cost != new_cost:
                    sb_df.loc[sb_df['ASIN'] == asin, 'Cost'] = new_cost
                    updates_made += 1
                    
                    potential_updates.append({
                        'ASIN': asin,
                        'SKU': row.get('SKU', ''),
                        'Title': row.get('Title', ''),
                        'old_cost': current_cost if not pd.isna(current_cost) else 0,
                        'new_cost': new_cost,
                        'source_worksheet': worksheet_source
                    })
        
        if updates_made == 0:
            return jsonify({
                'success': True,
                'message': 'No cost updates needed - all COGS data is already up to date',
                'updates_made': 0,
                'total_asins_checked': len(sb_df),
                'cost_sources_found': len(cost_lookup)
            })
        
        # Save updated Sellerboard file and send email
        sb_buffer = BytesIO()
        sb_df.to_excel(sb_buffer, index=False, engine='openpyxl')
        sb_buffer.seek(0)
        
        # Send email with updated file
        attachments = [(sb_buffer, f"sellerboard_cogs_updated_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")]
        
        # Create update summary email
        user_email = get_user_field(user_record, 'identity.email') or session.get('email')
        
        try:
            send_cogs_update_email(attachments, user_email, [], [], potential_updates, [])
            
            return jsonify({
                'success': True,
                'message': f'Successfully updated {updates_made} COGS entries from lead sheet data',
                'updates_made': updates_made,
                'total_asins_checked': len(sb_df),
                'cost_sources_found': len(cost_lookup),
                'email_sent': True,
                'updates': potential_updates[:10]  # Show first 10 updates
            })
            
        except Exception as email_error:
            print(f"Error sending email: {email_error}")
            return jsonify({
                'success': True,
                'message': f'Successfully updated {updates_made} COGS entries from lead sheet data (email failed)',
                'updates_made': updates_made,
                'total_asins_checked': len(sb_df),
                'cost_sources_found': len(cost_lookup),
                'email_sent': False,
                'email_error': str(email_error),
                'updates': potential_updates[:10]
            })
        
    except Exception as e:
        print(f"Error in manual COGS update from lead sheet: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/trigger-script', methods=['POST'])
@admin_required
def trigger_script():
    """Trigger manual script execution by invoking Lambda functions (like Discord bot)"""
    try:
        data = request.json
        script_type = data.get('script_type')  # 'listing_loader' or 'prep_uploader'
        
        
        if script_type == 'listing_loader':
            lambda_name = os.getenv('COST_UPDATER_LAMBDA_NAME', 'amznAndSBUpload')
        elif script_type == 'prep_uploader':
            lambda_name = os.getenv('PREP_UPLOADER_LAMBDA_NAME', 'prepUploader')
        else:
            return jsonify({'error': 'Invalid script_type. Use "listing_loader" or "prep_uploader"'}), 400
        
        # Simply invoke the Lambda function (like Discord bot does)
        try:
            # Debug AWS credentials and region
            aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
            aws_region = os.getenv('AWS_REGION', 'us-east-1')
            pass  # Debug print removed
            pass  # Debug print removed
            
            lambda_client = boto3.client(
                'lambda',
                aws_access_key_id=aws_access_key,
                aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
                region_name=aws_region
            )
            
            # Test if Lambda function exists first
            try:
                lambda_client.get_function(FunctionName=lambda_name)
                pass  # Debug print removed
            except lambda_client.exceptions.ResourceNotFoundException:
                pass  # Debug print removed
                return jsonify({
                    'error': f'Lambda function {lambda_name} not found. Please check the function name and region.'
                }), 404
            except Exception as get_error:
                pass  # Debug print removed
                return jsonify({
                    'error': f'Failed to verify Lambda function {lambda_name}: {str(get_error)}'
                }), 500
            
            response = lambda_client.invoke(
                FunctionName=lambda_name,
                InvocationType='Event',  # Async invocation
                Payload=json.dumps({})
            )
            pass  # Debug print removed
            
            return jsonify({
                'message': f'{script_type} Lambda function ({lambda_name}) invoked successfully',
                'script_type': script_type,
                'lambda_name': lambda_name,
                'lambda_invoked': True,
                'status_code': response.get('StatusCode')
            })
            
        except Exception as lambda_error:
            pass  # Debug print removed
            return jsonify({
                'error': f'Failed to invoke Lambda function {lambda_name}: {str(lambda_error)}'
            }), 500
            
    except Exception as e:
        pass  # Debug print removed
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/lambda-diagnostics', methods=['GET'])
@admin_required
def lambda_diagnostics():
    """Check Lambda configuration and connectivity"""
    try:
        # Check environment variables
        diagnostics = {
            'aws_access_key_configured': bool(os.getenv('AWS_ACCESS_KEY_ID')),
            'aws_secret_key_configured': bool(os.getenv('AWS_SECRET_ACCESS_KEY')),
            'aws_region': os.getenv('AWS_REGION', 'us-east-1'),
            'cost_updater_lambda_name': os.getenv('COST_UPDATER_LAMBDA_NAME', 'amznAndSBUpload'),
            'prep_uploader_lambda_name': os.getenv('PREP_UPLOADER_LAMBDA_NAME', 'prepUploader'),
        }
        
        # Test AWS connection
        try:
            lambda_client = boto3.client(
                'lambda',
                aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
                region_name=os.getenv('AWS_REGION', 'us-east-1')
            )
            
            # Test connection by listing functions (limited to 10)
            response = lambda_client.list_functions(MaxItems=10)
            diagnostics['aws_connection'] = 'success'
            diagnostics['lambda_functions_found'] = len(response.get('Functions', []))
            
            # Check if our specific functions exist
            function_names = [f['FunctionName'] for f in response.get('Functions', [])]
            diagnostics['cost_updater_exists'] = diagnostics['cost_updater_lambda_name'] in function_names
            diagnostics['prep_uploader_exists'] = diagnostics['prep_uploader_lambda_name'] in function_names
            diagnostics['available_functions'] = function_names[:10]  # Show first 10
            
        except Exception as aws_error:
            diagnostics['aws_connection'] = 'failed'
            diagnostics['aws_error'] = str(aws_error)
        
        return jsonify(diagnostics)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/lambda-logs', methods=['GET'])
@admin_required
def get_lambda_logs():
    """Get Lambda function logs from CloudWatch"""
    try:
        lambda_function = request.args.get('function')  # 'cost_updater' or 'prep_uploader'
        hours = int(request.args.get('hours', 24))  # Default to last 24 hours
        
        # Map function names to actual Lambda function names
        lambda_functions = {
            'cost_updater': os.getenv('COST_UPDATER_LAMBDA_NAME', 'amznAndSBUpload'),
            'prep_uploader': os.getenv('PREP_UPLOADER_LAMBDA_NAME', 'prepUploader')
        }
        
        if lambda_function not in lambda_functions:
            return jsonify({'error': 'Invalid lambda function specified'}), 400
        
        function_name = lambda_functions[lambda_function]
        log_group_name = f'/aws/lambda/{function_name}'
        
        # Create CloudWatch Logs client
        logs_client = boto3.client(
            'logs',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=os.getenv('AWS_REGION', 'us-east-1')  # Use same region as Lambda
        )
        
        # Calculate time range
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours)
        
        start_timestamp = int(start_time.timestamp() * 1000)
        end_timestamp = int(end_time.timestamp() * 1000)
        
        
        # Get log events
        response = logs_client.filter_log_events(
            logGroupName=log_group_name,
            startTime=start_timestamp,
            endTime=end_timestamp,
            limit=1000  # Limit to prevent overwhelming response
        )
        
        # Format log events
        logs = []
        for event in response.get('events', []):
            logs.append({
                'timestamp': datetime.fromtimestamp(event['timestamp'] / 1000).isoformat(),
                'message': event['message'].strip(),
                'ingestionTime': datetime.fromtimestamp(event['ingestionTime'] / 1000).isoformat()
            })
        
        # Sort by timestamp (most recent first)
        logs.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return jsonify({
            'function': lambda_function,
            'function_name': function_name,
            'log_group': log_group_name,
            'logs': logs,
            'count': len(logs),
            'time_range': {
                'start': start_time.isoformat(),
                'end': end_time.isoformat(),
                'hours': hours
            }
        })
        
    except Exception as e:
        pass  # Debug print removed
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/lambda-logs-latest', methods=['GET'])
@admin_required
def get_latest_lambda_logs():
    """Get logs from the most recent Lambda execution"""
    try:
        lambda_function = request.args.get('function')  # 'cost_updater' or 'prep_uploader'
        
        # Map function names to actual Lambda function names
        lambda_functions = {
            'cost_updater': os.getenv('COST_UPDATER_LAMBDA_NAME', 'amznAndSBUpload'),
            'prep_uploader': os.getenv('PREP_UPLOADER_LAMBDA_NAME', 'prepUploader')
        }
        
        if lambda_function not in lambda_functions:
            return jsonify({'error': 'Invalid lambda function specified'}), 400
        
        function_name = lambda_functions[lambda_function]
        log_group_name = f'/aws/lambda/{function_name}'
        
        # Create CloudWatch Logs client
        logs_client = boto3.client(
            'logs',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=os.getenv('AWS_REGION', 'us-east-1')
        )
        
        # Get the most recent log stream first
        streams_response = logs_client.describe_log_streams(
            logGroupName=log_group_name,
            orderBy='LastEventTime',
            descending=True,
            limit=1
        )
        
        if not streams_response.get('logStreams'):
            return jsonify({
                'function': lambda_function,
                'function_name': function_name,
                'logs': [],
                'count': 0,
                'message': 'No recent executions found'
            })
        
        latest_stream = streams_response['logStreams'][0]
        stream_name = latest_stream['logStreamName']
        
        # Get logs from the latest stream
        events_response = logs_client.get_log_events(
            logGroupName=log_group_name,
            logStreamName=stream_name
        )
        
        # Format log events
        logs = []
        for event in events_response.get('events', []):
            logs.append({
                'timestamp': datetime.fromtimestamp(event['timestamp'] / 1000).isoformat(),
                'message': event['message'].strip()
            })
        
        # Sort by timestamp (chronological order for single execution)
        logs.sort(key=lambda x: x['timestamp'])
        
        return jsonify({
            'function': lambda_function,
            'function_name': function_name,
            'log_stream': stream_name,
            'logs': logs,
            'count': len(logs),
            'execution_time': latest_stream.get('lastEventTime')
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/deploy-lambda', methods=['POST'])
@admin_required
def deploy_lambda():
    """Deploy code to Lambda function by uploading files and creating zip"""
    try:
        import zipfile
        import tempfile
        import os
        
        deployment_type = request.form.get('deployment_type')
        lambda_name = request.form.get('lambda_name')
        
        if not deployment_type or not lambda_name:
            return jsonify({'error': 'deployment_type and lambda_name are required'}), 400
            
        files = request.files.getlist('files')
        if not files:
            return jsonify({'error': 'No files provided for deployment'}), 400
        
        # Create a temporary zip file
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as temp_zip:
            with zipfile.ZipFile(temp_zip.name, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for file in files:
                    if file.filename:
                        # Save file content to zip
                        zip_file.writestr(file.filename, file.read())
            
            # Read the zip file content
            with open(temp_zip.name, 'rb') as zip_data:
                zip_content = zip_data.read()
            
            # Clean up temp file
            os.unlink(temp_zip.name)
        
        # Deploy to Lambda
        lambda_client = boto3.client(
            'lambda',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=os.getenv('AWS_REGION', 'us-east-1')
        )
        
        # Update function code
        response = lambda_client.update_function_code(
            FunctionName=lambda_name,
            ZipFile=zip_content
        )
        
        return jsonify({
            'message': f'Successfully deployed {len(files)} files to {lambda_name}',
            'function_name': lambda_name,
            'deployment_type': deployment_type,
            'files_deployed': [f.filename for f in files if f.filename],
            'code_size': response.get('CodeSize'),
            'last_modified': response.get('LastModified')
        })
        
    except Exception as e:
        pass  # Debug print removed
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/download-lambda-code/<function_name>', methods=['GET'])
@admin_required
def download_lambda_code(function_name):
    """Download current Lambda function code as zip"""
    try:
        lambda_client = boto3.client(
            'lambda',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=os.getenv('AWS_REGION', 'us-east-1')
        )
        
        # Get function information
        response = lambda_client.get_function(FunctionName=function_name)
        
        # Get the download URL for the code
        code_location = response['Code']['Location']
        
        # Download the zip file
        import requests
        zip_response = requests.get(code_location)
        
        if zip_response.status_code == 200:
            from flask import Response
            return Response(
                zip_response.content,
                mimetype='application/zip',
                headers={
                    'Content-Disposition': f'attachment; filename={function_name}-code.zip'
                }
            )
        else:
            return jsonify({'error': 'Failed to download Lambda code'}), 500
            
    except Exception as e:
        pass  # Debug print removed
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/deploy-lambda-smart', methods=['POST'])
@admin_required
def deploy_lambda_smart():
    """Smart Lambda deployment with requirements.txt support"""
    try:
        import zipfile
        import tempfile
        import os
        import subprocess
        import shutil
        
        deployment_type = request.form.get('deployment_type')
        lambda_name = request.form.get('lambda_name')
        
        if not deployment_type or not lambda_name:
            return jsonify({'error': 'deployment_type and lambda_name are required'}), 400
            
        files = request.files.getlist('files')
        if not files:
            return jsonify({'error': 'No files provided for deployment'}), 400
        
        # Create temporary working directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Save uploaded files to temp directory
            uploaded_files = []
            has_requirements = False
            requirements_content = None
            
            for file in files:
                if file.filename:
                    file_path = os.path.join(temp_dir, file.filename)
                    file.save(file_path)
                    uploaded_files.append(file.filename)
                    
                    if file.filename == 'requirements.txt':
                        has_requirements = True
                        with open(file_path, 'r') as f:
                            requirements_content = f.read()
            
            # Create deployment package directory
            package_dir = os.path.join(temp_dir, 'package')
            os.makedirs(package_dir)
            
            deployment_info = {
                'files_uploaded': uploaded_files,
                'has_requirements': has_requirements,
                'requirements_content': requirements_content.split('\n') if requirements_content else [],
                'dependencies_installed': [],
                'deployment_method': 'unknown'
            }
            
            if has_requirements:
                # Smart deployment with requirements.txt
                deployment_info['deployment_method'] = 'requirements.txt'
                
                # Install dependencies using pip with target directory
                requirements_path = os.path.join(temp_dir, 'requirements.txt')
                
                # Install packages to package directory
                pip_cmd = [
                    'pip', 'install', 
                    '-r', requirements_path,
                    '-t', package_dir,
                    '--no-deps',  # Don't install dependencies of dependencies
                    '--only-binary=:all:',  # Only use wheel files for compatibility
                ]
                
                try:
                    result = subprocess.run(pip_cmd, capture_output=True, text=True, timeout=300)
                    if result.returncode != 0:
                        # Try without --no-deps and --only-binary flags
                        pip_cmd = ['pip', 'install', '-r', requirements_path, '-t', package_dir]
                        result = subprocess.run(pip_cmd, capture_output=True, text=True, timeout=300)
                    
                    if result.returncode == 0:
                        deployment_info['dependencies_installed'] = result.stdout.split('\n')
                        deployment_info['pip_output'] = result.stdout
                    else:
                        return jsonify({
                            'error': f'Failed to install dependencies: {result.stderr}',
                            'pip_stdout': result.stdout,
                            'pip_stderr': result.stderr
                        }), 500
                        
                except subprocess.TimeoutExpired:
                    return jsonify({'error': 'Dependency installation timed out after 5 minutes'}), 500
                except Exception as e:
                    return jsonify({'error': f'Failed to run pip install: {str(e)}'}), 500
            else:
                # Manual deployment - copy all files directly
                deployment_info['deployment_method'] = 'manual_files'
            
            # Copy Python files to package directory
            for filename in uploaded_files:
                if filename.endswith('.py') or filename.endswith('.json') or filename.endswith('.txt'):
                    src_path = os.path.join(temp_dir, filename)
                    dst_path = os.path.join(package_dir, filename)
                    shutil.copy2(src_path, dst_path)
            
            # Create deployment zip
            zip_path = os.path.join(temp_dir, 'deployment.zip')
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for root, dirs, files in os.walk(package_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arc_name = os.path.relpath(file_path, package_dir)
                        zip_file.write(file_path, arc_name)
            
            # Read the zip file content
            with open(zip_path, 'rb') as zip_data:
                zip_content = zip_data.read()
            
            deployment_info['package_size'] = len(zip_content)
            deployment_info['package_size_mb'] = round(len(zip_content) / 1024 / 1024, 2)
        
        # Deploy to Lambda
        lambda_client = boto3.client(
            'lambda',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=os.getenv('AWS_REGION', 'us-east-1')
        )
        
        # Update function code
        response = lambda_client.update_function_code(
            FunctionName=lambda_name,
            ZipFile=zip_content
        )
        
        return jsonify({
            'message': f'Successfully deployed to {lambda_name}',
            'function_name': lambda_name,
            'deployment_type': deployment_type,
            'deployment_info': deployment_info,
            'lambda_response': {
                'code_size': response.get('CodeSize'),
                'last_modified': response.get('LastModified')
            }
        })
        
    except Exception as e:
        pass  # Debug print removed
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/analyze-lambda/<function_name>', methods=['GET'])
@admin_required
def analyze_lambda_structure(function_name):
    """Analyze Lambda function structure and dependencies"""
    import requests
    import zipfile
    import tempfile
    import os
    
    try:
        lambda_client = boto3.client(
            'lambda',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=os.getenv('AWS_REGION', 'us-east-1')
        )
        
        # Get function information
        function_info = lambda_client.get_function(FunctionName=function_name)
        
        # Get the download URL for the code
        code_location = function_info['Code']['Location']
        
        zip_response = requests.get(code_location)
        
        if zip_response.status_code == 200:
            analysis = {
                'function_name': function_name,
                'code_size': function_info['Configuration']['CodeSize'],
                'runtime': function_info['Configuration']['Runtime'],
                'handler': function_info['Configuration']['Handler'],
                'last_modified': function_info['Configuration']['LastModified'],
                'files': [],
                'dependencies': [],
                'has_requirements_txt': False,
                'python_files': [],
                'config_files': [],
                'package_directories': []
            }
            
            # Create temporary file to analyze zip contents
            with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as temp_zip:
                temp_zip.write(zip_response.content)
                temp_zip_path = temp_zip.name
            
            try:
                with zipfile.ZipFile(temp_zip_path, 'r') as zip_file:
                    file_list = zip_file.namelist()
                    
                    for file_path in file_list:
                        analysis['files'].append({
                            'name': file_path,
                            'is_directory': file_path.endswith('/'),
                            'size': zip_file.getinfo(file_path).file_size if not file_path.endswith('/') else 0
                        })
                        
                        # Categorize files
                        if file_path.endswith('.py'):
                            analysis['python_files'].append(file_path)
                        elif file_path == 'requirements.txt':
                            analysis['has_requirements_txt'] = True
                            # Try to read requirements.txt content
                            try:
                                requirements_content = zip_file.read(file_path).decode('utf-8')
                                analysis['requirements_content'] = requirements_content.strip().split('\n')
                            except:
                                analysis['requirements_content'] = ['Could not read requirements.txt']
                        elif file_path.endswith(('.json', '.yml', '.yaml', '.ini', '.cfg', '.conf')):
                            analysis['config_files'].append(file_path)
                        elif '/' in file_path and not file_path.endswith('.py'):
                            # This might be a package directory
                            dir_name = file_path.split('/')[0]
                            if dir_name not in analysis['package_directories']:
                                analysis['package_directories'].append(dir_name)
                
                # Clean up temp file
                os.unlink(temp_zip_path)
                
                return jsonify(analysis)
                
            except zipfile.BadZipFile:
                os.unlink(temp_zip_path)
                return jsonify({'error': 'Downloaded file is not a valid zip file'}), 500
            except Exception as e:
                os.unlink(temp_zip_path)
                return jsonify({'error': f'Failed to analyze zip file: {str(e)}'}), 500
                
        else:
            return jsonify({'error': 'Failed to download Lambda code'}), 500
            
    except Exception as e:
        pass  # Debug print removed
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/extract-requirements/<function_name>', methods=['GET'])
@admin_required
def extract_requirements_from_lambda(function_name):
    """Extract requirements.txt from current Lambda deployment"""
    try:
        import requests
        import zipfile
        import tempfile
        import os
        import re
        
        lambda_client = boto3.client(
            'lambda',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=os.getenv('AWS_REGION', 'us-east-1')
        )
        
        # Get function information
        function_info = lambda_client.get_function(FunctionName=function_name)
        code_location = function_info['Code']['Location']
        
        # Download the zip file
        zip_response = requests.get(code_location)
        
        if zip_response.status_code == 200:
            # Create temporary file to analyze zip contents
            with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as temp_zip:
                temp_zip.write(zip_response.content)
                temp_zip_path = temp_zip.name
            
            try:
                package_mapping = {
                    'dotenv': 'python-dotenv',
                    'boto3': 'boto3',
                    'botocore': 'botocore', 
                    's3transfer': 's3transfer',
                    'urllib3': 'urllib3',
                    'certifi': 'certifi',
                    'charset_normalizer': 'charset-normalizer',
                    'idna': 'idna',
                    'requests': 'requests',
                    'openpyxl': 'openpyxl',
                    'pandas': 'pandas',
                    'numpy': 'numpy',
                    'pytz': 'pytz',
                    'dateutil': 'python-dateutil',
                    'six': 'six',
                    'et_xmlfile': 'et-xmlfile',
                    'jdcal': 'jdcal'
                }
                
                detected_packages = set()
                
                with zipfile.ZipFile(temp_zip_path, 'r') as zip_file:
                    file_list = zip_file.namelist()
                    
                    # Look for package directories and dist-info folders
                    for file_path in file_list:
                        if '/' in file_path and not file_path.endswith('.py'):
                            parts = file_path.split('/')
                            potential_package = parts[0]
                            
                            # Check for dist-info folders to get exact package names
                            if potential_package.endswith('.dist-info'):
                                package_name = potential_package.replace('.dist-info', '').lower()
                                # Try to extract version from METADATA if available
                                metadata_path = f"{potential_package}/METADATA"
                                if metadata_path in file_list:
                                    try:
                                        metadata_content = zip_file.read(metadata_path).decode('utf-8')
                                        version_match = re.search(r'Version: ([\d\.]+)', metadata_content)
                                        if version_match:
                                            version = version_match.group(1)
                                            detected_packages.add(f"{package_name}=={version}")
                                        else:
                                            detected_packages.add(package_name)
                                    except:
                                        detected_packages.add(package_name)
                                else:
                                    detected_packages.add(package_name)
                            
                            # Also check for regular package directories
                            elif potential_package in package_mapping:
                                detected_packages.add(package_mapping[potential_package])
                            elif potential_package.replace('_', '-') in package_mapping.values():
                                detected_packages.add(potential_package.replace('_', '-'))
                
                # Clean up temp file
                os.unlink(temp_zip_path)
                
                # Sort packages alphabetically
                requirements_list = sorted(list(detected_packages))
                
                return jsonify({
                    'function_name': function_name,
                    'detected_packages': requirements_list,
                    'requirements_txt': '\n'.join(requirements_list),
                    'package_count': len(requirements_list),
                    'extraction_method': 'dist-info_analysis'
                })
                
            except zipfile.BadZipFile:
                os.unlink(temp_zip_path)
                return jsonify({'error': 'Downloaded file is not a valid zip file'}), 500
            except Exception as e:
                os.unlink(temp_zip_path)
                return jsonify({'error': f'Failed to analyze zip file: {str(e)}'}), 500
                
        else:
            return jsonify({'error': 'Failed to download Lambda code'}), 500
            
    except Exception as e:
        pass  # Debug print removed
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Simple health check endpoint for Railway"""
    try:
        return {'status': 'ok', 'timestamp': datetime.utcnow().isoformat()}, 200
    except Exception as e:
        # Fallback response that should always work
        return 'OK', 200

@app.route('/healthz', methods=['GET'])
def health_check_detailed():
    """Detailed health check endpoint"""
    try:
        # Basic health checks
        status = 'healthy'
        checks = {
            'flask': True,
            'environment': {
                'port': os.environ.get('PORT', 'default:5000'),
                'flask_env': os.environ.get('FLASK_ENV', 'not_set')
            }
        }
        
        # Check if critical environment variables are set
        required_env_vars = ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'CONFIG_S3_BUCKET']
        missing_vars = [var for var in required_env_vars if not os.environ.get(var)]
        
        if missing_vars:
            checks['environment']['missing_vars'] = missing_vars
            status = 'degraded'
        else:
            checks['environment']['aws_configured'] = True
        
        return jsonify({
            'status': status,
            'timestamp': datetime.utcnow().isoformat(),
            'service': 'internet-money-tools-backend',
            'checks': checks
        }), 200
        
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'timestamp': datetime.utcnow().isoformat(),
            'service': 'internet-money-tools-backend',
            'error': str(e)
        }), 500

@app.route('/', methods=['GET'])
def root():
    """Root endpoint to confirm the service is running"""
    return jsonify({
        'message': 'Internet Money Tools Backend API',
        'status': 'running',
        'version': '2.0',
        'timestamp': datetime.utcnow().isoformat(),
        'endpoints': {
            'health': 'api/health',
            'api': '/api/*'
        }
    }), 200

@app.route('/ping', methods=['GET'])
def ping():
    """Simple ping endpoint for quick health checks"""
    return 'pong', 200

@app.route('/api/asin/<asin>/purchase-sources', methods=['GET'])
@login_required
def get_asin_purchase_sources(asin):
    """Get all purchase sources/websites for a specific ASIN from purchase history"""
    try:
        discord_id = session['discord_id']
        user_record = get_user_record(discord_id)
        
        if not user_record:
            return jsonify({'error': 'User not found'}), 404
        
        # Check if source links are enabled
        if not (get_user_field(user_record, 'settings.enable_source_links') or user_record.get('enable_source_links')):
            return jsonify({
                'sources': [],
                'message': 'Source links are not enabled. Enable them in Settings to see purchase sources.'
            })
        
        # Get user's Google Sheet settings
        sheet_id = get_user_field(user_record, 'files.sheet_id')
        worksheet_title = get_user_field(user_record, 'integrations.google.worksheet_title')
        google_tokens = get_user_google_tokens(user_record) or {}
        column_mapping = get_user_column_mapping(user_record)
        
        if not all([sheet_id, google_tokens.get('access_token')]):
            return jsonify({
                'sources': [],
                'message': 'Google Sheets not configured. Set up Google Sheets in Settings to see purchase sources.'
            })
        
        # Import OrdersAnalysis to fetch COGS data
        from orders_analysis import OrdersAnalysis
        
        # Create analyzer instance
        analyzer = OrdersAnalysis("", "")  # URLs not needed for COGS fetch
        
        # Fetch COGS data (which includes all sources)
        if get_user_field(user_record, 'settings.search_all_worksheets') or user_record.get('search_all_worksheets'):
            cogs_data, _ = analyzer.fetch_google_sheet_cogs_data_all_worksheets(
                google_tokens.get('access_token'),
                sheet_id,
                column_mapping
            )
        else:
            cogs_data = analyzer.fetch_google_sheet_cogs_data(
                google_tokens.get('access_token'),
                sheet_id,
                worksheet_title,
                column_mapping
            )
        
        # Extract sources for the specific ASIN
        asin_data = cogs_data.get(asin, {})
        all_sources = asin_data.get('all_sources', [])
        
        if not all_sources:
            return jsonify({
                'sources': [],
                'message': f'No purchase history found for ASIN {asin}'
            })
        
        # Parse sources to extract unique websites
        unique_websites = {}
        for source in all_sources:
            if not source:
                continue
                
            # Extract domain/website name from URL or source string
            website_name = extract_website_name(source)
            if website_name not in unique_websites:
                unique_websites[website_name] = {
                    'website': website_name,
                    'url': source,
                    'display_name': format_website_display_name(website_name)
                }
        
        # Convert to list and sort by website name
        sources_list = list(unique_websites.values())
        sources_list.sort(key=lambda x: x['display_name'])
        
        return jsonify({
            'asin': asin,
            'sources': sources_list,
            'total_purchases': asin_data.get('total_purchases', 0),
            'last_purchase_date': asin_data.get('last_purchase_date')
        })
        
    except Exception as e:
        pass  # Debug print removed
        return jsonify({'error': str(e)}), 500

def extract_website_name(source_url):
    """Extract website name from URL or source string"""
    if not source_url:
        return "Unknown"
    
    import re
    from urllib.parse import urlparse
    
    # If it's a URL, extract domain
    if source_url.startswith(('http://', 'https://')):
        try:
            parsed = urlparse(source_url)
            domain = parsed.netloc.lower()
            # Remove www. prefix
            if domain.startswith('www.'):
                domain = domain[4:]
            return domain
        except:
            return source_url
    
    # If it's not a URL, try to extract website name from text
    source_lower = source_url.lower().strip()
    
    # Common website patterns
    website_patterns = {
        'amazon': ['amazon', 'amzn'],
        'walmart': ['walmart', 'wmart'],
        'costco': ['costco'],
        'target': ['target'],
        'ebay': ['ebay'],
        'alibaba': ['alibaba', '1688'],
        'aliexpress': ['aliexpress'],
        'dhgate': ['dhgate'],
        'wholesale': ['wholesale'],
        'supplier': ['supplier'],
        'manufacturer': ['manufacturer', 'factory']
    }
    
    for website, patterns in website_patterns.items():
        if any(pattern in source_lower for pattern in patterns):
            return website
    
    # If no pattern matches, return the original (truncated if too long)
    return source_url[:20] + '...' if len(source_url) > 20 else source_url

def format_website_display_name(website_name):
    """Format website name for display"""
    if not website_name:
        return "Unknown"
    
    # Special formatting for known websites
    formatting_map = {
        'amazon.com': 'Amazon',
        'walmart.com': 'Walmart', 
        'costco.com': 'Costco',
        'target.com': 'Target',
        'ebay.com': 'eBay',
        'alibaba.com': 'Alibaba',
        'aliexpress.com': 'AliExpress',
        'dhgate.com': 'DHgate',
        'amazon': 'Amazon',
        'walmart': 'Walmart',
        'costco': 'Costco',
        'target': 'Target',
        'ebay': 'eBay',
        'alibaba': 'Alibaba',
        'aliexpress': 'AliExpress',
        'dhgate': 'DHgate',
        'wholesale': 'Wholesale',
        'supplier': 'Supplier',
        'manufacturer': 'Manufacturer'
    }
    
    return formatting_map.get(website_name.lower(), website_name.title())

# ─── UNDERPAID REIMBURSEMENTS HELPER FUNCTIONS ─────────────────────────────

def fetch_all_sheet_titles_for_user(user_record) -> list[str]:
    """
    Uses the stored refresh_token to get a fresh access_token,
    then calls spreadsheets.get?fields=sheets(properties(title))
    to return a list of all worksheet titles in that user's Sheet.
    """
    # 1) Grab a valid access_token (refresh if needed)
    google_tokens = get_user_field(user_record, 'integrations.google.tokens') or {}
    access_token = google_tokens.get("access_token")
    # Try one request; if 401, refresh and retry
    sheet_id = get_user_field(user_record, 'files.sheet_id')
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}?fields=sheets(properties(title))"
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = requests.get(url, headers=headers)
    if resp.status_code == 401:
        access_token = refresh_google_token(user_record)
        headers = {"Authorization": f"Bearer {access_token}"}
        resp = requests.get(url, headers=headers)
    resp.raise_for_status()

    data = resp.json()
    return [sheet["properties"]["title"] for sheet in data.get("sheets", [])]

def fetch_google_sheet_as_df(user_record, worksheet_title):
    """
    Fetches one worksheet's entire A1:ZZ range, pads/truncates rows to match headers,
    and returns a DataFrame with the first row as column names.
    """
    import pandas as pd
    import urllib.parse
    
    sheet_id = get_user_field(user_record, 'files.sheet_id')
    google_tokens = get_user_field(user_record, 'integrations.google.tokens') or {}
    access_token = google_tokens.get("access_token")
    range_ = f"'{worksheet_title}'!A1:ZZ"
    url = (
        f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}"
        f"/values/{urllib.parse.quote(range_)}?majorDimension=ROWS"
    )
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = requests.get(url, headers=headers)
    if resp.status_code == 401:
        access_token = refresh_google_token(user_record)
        headers = {"Authorization": f"Bearer {access_token}"}
        resp = requests.get(url, headers=headers)
    resp.raise_for_status()

    values = resp.json().get("values", [])
    if not values:
        return pd.DataFrame()

    headers_row = values[0]
    records = []
    for row in values[1:]:
        # pad or truncate so len(row) == len(headers_row)
        if len(row) < len(headers_row):
            row = row + [""] * (len(headers_row) - len(row))
        elif len(row) > len(headers_row):
            row = row[: len(headers_row)]
        records.append(row)

    return pd.DataFrame(records, columns=headers_row)

def build_highest_cogs_map_for_user(user_record) -> dict[str, float]:
    """
    Fetches every worksheet title, then for each sheet:
      - normalizes headers to lowercase
      - finds any "asin" column and any "cogs" column (by substring match)
      - strips "$" and commas from COGS, coercing to float
      - groups by ASIN and takes max(COGS)
    Returns a map { asin_string: highest_cogs_float } across all worksheets.
    """
    import pandas as pd
    
    max_cogs: dict[str, float] = {}
    titles = fetch_all_sheet_titles_for_user(user_record)

    for title in titles:
        df = fetch_google_sheet_as_df(user_record, title)
        if df.empty:
            continue

        # lowercase all headers
        df.columns = [c.strip().lower() for c in df.columns]

        # pick first column that contains "asin" and first that contains "cogs"
        asin_cols = [c for c in df.columns if "asin" in c]
        cogs_cols = [c for c in df.columns if "cogs" in c]
        if not asin_cols or not cogs_cols:
            # skip sheets that don't have an ASIN or COGS header
            continue

        asin_col = asin_cols[0]
        cogs_col = cogs_cols[0]

        # strip "$" and commas from COGS, coerce to float
        df[cogs_col] = (
            df[cogs_col]
            .astype(str)
            .str.replace("$", "", regex=False)
            .str.replace(",", "", regex=False)
        )
        df[cogs_col] = pd.to_numeric(df[cogs_col], errors="coerce")
        df = df.dropna(subset=[asin_col, cogs_col])
        if df.empty:
            continue

        grouped = df.groupby(asin_col, as_index=False)[cogs_col].max()
        for _, row in grouped.iterrows():
            asin = str(row[asin_col]).strip()
            cogs = float(row[cogs_col])
            if asin in max_cogs:
                if cogs > max_cogs[asin]:
                    max_cogs[asin] = cogs
            else:
                max_cogs[asin] = cogs

    return max_cogs

def filter_underpaid_reimbursements(aura_df, max_cogs_map: dict[str, float]):
    """
    Given a DataFrame of reimbursements (with columns including "asin" and "amount-per-unit"),
    returns a new DataFrame containing only rows where 
      (amount-per-unit < max_cogs_map[asin]) and reason != "Reimbursement_Reversal".

    Output columns: 
      reimbursement-id, reason, sku, asin, product-name,
      amount-per-unit, amount-total, quantity-reimbursed-total,
      highest_cogs, shortfall_amount
    """
    import pandas as pd
    
    # lowercase columns for consistency
    aura_df.columns = [c.strip().lower() for c in aura_df.columns]

    required_cols = {
        "reimbursement-id", "reason", "sku", "asin",
        "product-name", "amount-per-unit", "amount-total", "quantity-reimbursed-total"
    }
    if not required_cols.issubset(set(aura_df.columns)):
        raise ValueError(f"Missing columns {required_cols - set(aura_df.columns)} in reimbursement CSV")

    # parse "amount-per-unit" into float
    def parse_money(x):
        try:
            return float(str(x).replace("$", "").replace(",", "").strip())
        except:
            return None

    aura_df["reimb_amount_per_unit"] = aura_df["amount-per-unit"].apply(parse_money)
    aura_df = aura_df.dropna(subset=["asin", "reimb_amount_per_unit"])

    rows = []
    for _, r in aura_df.iterrows():
        if str(r["reason"]).strip().lower() == "reimbursement_reversal":
            continue
        asin = str(r["asin"]).strip()
        reimb_amt = float(r["reimb_amount_per_unit"])
        highest = max_cogs_map.get(asin)
        if highest is not None and reimb_amt < highest:
            shortfall = round(highest - reimb_amt, 2)
            rows.append({
                "reimbursement-id": r["reimbursement-id"],
                "reason": r["reason"],
                "sku": r["sku"],
                "asin": r["asin"],
                "product-name": r["product-name"],
                "amount-per-unit": r["amount-per-unit"],
                "amount-total": r["amount-total"],
                "quantity-reimbursed-total": r["quantity-reimbursed-total"],
                "highest_cogs": highest,
                "shortfall_amount": shortfall
            })

    cols = [
        "reimbursement-id", "reason", "sku", "asin", "product-name",
        "amount-per-unit", "amount-total", "quantity-reimbursed-total",
        "highest_cogs", "shortfall_amount"
    ]
    return pd.DataFrame(rows, columns=cols)

# Duplicate function removed - using the one defined earlier in the file

@app.route('/status', methods=['GET'])
def status():
    """Ultra-simple status check"""
    return 'OK'

@app.route('/api/reimbursements/analyze', methods=['POST'])
@login_required
@permission_required('reimbursements_analysis')
def analyze_underpaid_reimbursements():
    """Analyze uploaded reimbursement CSV for underpaid reimbursements"""
    try:
        # Return dummy data in demo mode
        if DEMO_MODE:
            return jsonify(get_dummy_reimbursements_data())
        
        discord_id = session['discord_id']
        user_record = get_user_record(discord_id)
        
        if not user_record:
            return jsonify({'error': 'User not found'}), 404
        
        # For subusers, use parent's configuration
        if get_user_field(user_record, 'account.user_type') == 'subuser':
            config_user = get_parent_user_record(discord_id)
            if not config_user:
                return jsonify({'error': 'Parent user not found'}), 404
        else:
            config_user = user_record
        
        # Check if Google Sheet is configured
        if not get_user_field(config_user, 'files.sheet_id') or not get_user_field(config_user, 'integrations.google.tokens'):
            return jsonify({
                'error': 'No Google Sheet configured. Please complete setup first.',
                'setup_required': True
            }), 400
        
        # Check if file was uploaded
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Validate file type
        if not file.filename.lower().endswith('.csv'):
            return jsonify({'error': 'Invalid file type. Please upload a CSV file.'}), 400
        
        # Read the CSV file
        try:
            import pandas as pd
            from io import StringIO
            csv_content = file.read().decode('utf-8')
            reimburse_df = pd.read_csv(StringIO(csv_content))
        except UnicodeDecodeError:
            # Try with latin-1 encoding as fallback
            file.seek(0)
            csv_content = file.read().decode('latin-1')
            reimburse_df = pd.read_csv(StringIO(csv_content))
        except Exception as e:
            return jsonify({'error': f'Error reading CSV file: {str(e)}'}), 400
        
        # Build the highest COGS map from Google Sheets
        try:
            max_cogs_map = build_highest_cogs_map_for_user(config_user)
        except Exception as e:
            return jsonify({'error': f'Error fetching Google Sheets data: {str(e)}'}), 500
        
        if not max_cogs_map:
            return jsonify({
                'error': 'Could not find any COGS data in your Google Sheets',
                'max_cogs_count': 0
            }), 400
        
        # Filter for underpaid reimbursements
        try:
            underpaid_df = filter_underpaid_reimbursements(reimburse_df, max_cogs_map)
        except Exception as e:
            return jsonify({'error': f'Error processing reimbursements: {str(e)}'}), 500
        
        # Convert results to JSON for the frontend
        if underpaid_df.empty:
            return jsonify({
                'underpaid_count': 0,
                'total_shortfall': 0,
                'max_cogs_count': len(max_cogs_map),
                'underpaid_reimbursements': []
            })
        
        # Calculate total shortfall
        total_shortfall = underpaid_df['shortfall_amount'].sum()
        
        # Convert DataFrame to list of dictionaries
        underpaid_list = underpaid_df.to_dict('records')
        
        return jsonify({
            'underpaid_count': len(underpaid_df),
            'total_shortfall': round(total_shortfall, 2),
            'max_cogs_count': len(max_cogs_map),
            'underpaid_reimbursements': underpaid_list
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/reimbursements/download', methods=['POST'])
@login_required  
@permission_required('reimbursements_analysis')
def download_underpaid_reimbursements():
    """Download underpaid reimbursements as CSV"""
    try:
        # Get the underpaid reimbursements data from request
        data = request.get_json()
        underpaid_reimbursements = data.get('underpaid_reimbursements', [])
        
        if not underpaid_reimbursements:
            return jsonify({'error': 'No data to download'}), 400
        
        # Convert to DataFrame and then CSV
        import pandas as pd
        from io import StringIO
        
        df = pd.DataFrame(underpaid_reimbursements)
        csv_buffer = StringIO()
        df.to_csv(csv_buffer, index=False)
        csv_content = csv_buffer.getvalue()
        
        # Return CSV as downloadable response
        response = make_response(csv_content)
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = 'attachment; filename=underpaid_reimbursements.csv'
        
        return response
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/discount-leads/fetch', methods=['GET'])
@login_required
def fetch_discount_leads():
    """Fetch discount leads from Google Sheets CSV"""
    try:
        # CSV URL provided by the user
        csv_url = 'https://docs.google.com/spreadsheets/d/e/2PACX-1vRz7iEc-6eA4pfImWfSs_qVyUWHmqDw8ET1PTWugLpqDHU6txhwyG9lCMA65Z9AHf-6lcvCcvbE4MPT/pub?output=csv'
        
        # Fetch CSV data
        response = requests.get(csv_url, timeout=30)
        response.raise_for_status()
        
        # Parse CSV
        from io import StringIO
        csv_data = StringIO(response.text)
        df = pd.read_csv(csv_data)
        
        # Clean and process the data
        leads = []
        for _, row in df.iterrows():
            lead = {}
            for col in df.columns:
                # Clean column names and values
                clean_col = col.strip().lower().replace(' ', '_')
                value = row[col]
                
                # Handle NaN values
                if pd.isna(value):
                    lead[clean_col] = None
                elif isinstance(value, str):
                    lead[clean_col] = value.strip()
                else:
                    lead[clean_col] = value
            
            leads.append(lead)
        
        return jsonify({
            'leads': leads,
            'total_count': len(leads),
            'columns': list(df.columns),
            'fetched_at': datetime.now(pytz.UTC).isoformat()
        })
        
    except requests.RequestException as e:
        return jsonify({'error': f'Failed to fetch CSV data: {str(e)}'}), 500
    except pd.errors.EmptyDataError:
        return jsonify({'error': 'CSV file is empty or invalid'}), 400
    except Exception as e:
        return jsonify({'error': f'Error processing CSV data: {str(e)}'}), 500

def get_cached_discount_opportunities(discord_id, retailer_filter=''):
    """Get cached discount opportunities from database"""
    try:
        # Create discount_opportunities_cache table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS discount_opportunities_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                discord_id TEXT NOT NULL,
                retailer_filter TEXT NOT NULL DEFAULT '',
                data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL
            )
        ''')
        conn.commit()
        
        # Check for valid cached data with smart expiry (24 hours for daily use, but allow refresh)
        cursor.execute('''
            SELECT data, created_at FROM discount_opportunities_cache 
            WHERE discord_id = ? AND retailer_filter = ? AND expires_at > datetime('now')
            ORDER BY created_at DESC LIMIT 1
        ''', (discord_id, retailer_filter))
        
        result = cursor.fetchone()
        if result:
            data = json.loads(result[0])
            created_at = result[1]
            
            # Add cache info
            data['cached'] = True
            data['cache_created_at'] = created_at
            
            # Calculate cache age for display
            try:
                cache_time = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                cache_age_hours = (datetime.now() - cache_time).total_seconds() / 3600
                data['cache_age_hours'] = round(cache_age_hours, 1)
            except:
                data['cache_age_hours'] = 0
                
            return data
        return None
        
    except Exception as e:
        print(f"Error retrieving cached discount opportunities: {e}")
        return None

def cache_discount_opportunities(discord_id, retailer_filter, data):
    """Cache discount opportunities data to database"""
    try:
        # Delete old cache entries for this user/filter combination
        cursor.execute('''
            DELETE FROM discount_opportunities_cache 
            WHERE discord_id = ? AND retailer_filter = ?
        ''', (discord_id, retailer_filter))
        
        # Insert new cache entry with 24-hour expiry for daily use
        expires_at = (datetime.now() + timedelta(hours=24)).isoformat()
        cursor.execute('''
            INSERT INTO discount_opportunities_cache (discord_id, retailer_filter, data, expires_at)
            VALUES (?, ?, ?, ?)
        ''', (discord_id, retailer_filter, json.dumps(data), expires_at))
        
        conn.commit()
        
        # Cleanup old expired entries (housekeeping)
        cursor.execute('''
            DELETE FROM discount_opportunities_cache 
            WHERE expires_at < datetime('now')
        ''')
        conn.commit()
        
    except Exception as e:
        print(f"Error caching discount opportunities: {e}")

@app.route('/api/discount-opportunities/analyze', methods=['POST'])
@login_required
def analyze_discount_opportunities():
    """Analyze discount opportunities from email alerts against user's inventory"""
    try:
        # Return dummy data in demo mode
        if DEMO_MODE:
            return jsonify(get_dummy_discount_opportunities())
        
        data = request.get_json() or {}
        retailer_filter = data.get('retailer', '')
        
        # Get user's current analytics data
        discord_id = session['discord_id']
        
        # Check database cache first (24 hour expiry for daily use)
        cached_opportunities = get_cached_discount_opportunities(discord_id, retailer_filter)
        if cached_opportunities:
            return jsonify(cached_opportunities)
        
        user = get_user_record(discord_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get user config for analytics
        config_user_record = user
        if user and get_user_field(user, 'account.user_type') == 'subuser':
            parent_user_id = get_user_field(user, 'account.parent_user_id')
            if parent_user_id:
                parent_record = get_user_record(parent_user_id)
                if parent_record:
                    config_user_record = parent_record
        
        # Get the user's timezone
        user_timezone = get_user_field(user, 'profile.timezone') if user else None
        
        # Use today's date for analysis
        if user_timezone:
            try:
                user_tz = pytz.timezone(user_timezone)
                today = datetime.now(user_tz).date()
            except:
                today = datetime.now(pytz.UTC).date()
        else:
            today = datetime.now(pytz.UTC).date()
        
        # Get user's inventory analysis (with aggressive caching)
        enhanced_analytics = None
        analytics_cache_key = f"enhanced_analytics_{discord_id}_{today}"
        
        # Check for cached enhanced analytics (24 hour cache for discount opportunities)
        analysis = None
        if analytics_cache_key in analytics_cache:
            cache_entry = analytics_cache[analytics_cache_key]
            if datetime.now() - cache_entry['timestamp'] < timedelta(hours=24):
                enhanced_analytics = cache_entry['data']
                analysis = cache_entry.get('analysis')
        
        if enhanced_analytics is None:
            try:
                from orders_analysis import EnhancedOrdersAnalysis
                
                orders_url = get_user_sellerboard_orders_url(config_user_record)
                stock_url = get_user_sellerboard_stock_url(config_user_record)
                
                if not orders_url or not stock_url:
                    return jsonify({
                        'opportunities': [],
                        'message': 'Sellerboard URLs not configured. Please configure in Settings.'
                    })
                
                orders_analysis = EnhancedOrdersAnalysis(
                    orders_url=orders_url,
                    stock_url=stock_url
                )
                
                analysis = orders_analysis.analyze(
                    for_date=today,
                    user_timezone=user_timezone,
                    user_settings={
                        'enable_source_links': get_user_field(user, 'settings.enable_source_links') or user.get('enable_source_links', False),
                        'search_all_worksheets': get_user_field(config_user_record, 'settings.search_all_worksheets') or config_user_record.get('search_all_worksheets', False),
                        'disable_sp_api': get_user_field(config_user_record, 'integrations.amazon.disable_sp_api') or config_user_record.get('disable_sp_api', False),
                        'amazon_lead_time_days': get_user_field(config_user_record, 'settings.amazon_lead_time_days') or config_user_record.get('amazon_lead_time_days', 90),
                        'discord_id': discord_id,
                        # Add Google Sheet settings for purchase analytics (same as Smart Restock)
                        'sheet_id': get_user_field(config_user_record, 'files.sheet_id'),
                        'worksheet_title': get_user_field(config_user_record, 'integrations.google.worksheet_title'), 
                        'google_tokens': get_user_field(config_user_record, 'integrations.google.tokens') or {},
                        'column_mapping': get_user_column_mapping(user)
                    }
                )
                
                if not analysis or not analysis.get('enhanced_analytics'):
                    return jsonify({
                        'opportunities': [],
                        'message': 'No inventory data available for analysis'
                    })
                    
                enhanced_analytics = analysis['enhanced_analytics']
                
                # Cache the enhanced analytics with the analysis object
                analytics_cache[analytics_cache_key] = {
                    'data': enhanced_analytics,
                    'analysis': analysis,  # Store the full analysis for purchase insights
                    'timestamp': datetime.now()
                }
                
            except Exception as e:
                print(f"[ERROR] Failed to generate analytics: {str(e)}")
                return jsonify({
                    'opportunities': [],
                    'message': f'Failed to generate analytics: {str(e)}'
                }), 500
        
        # Get the global purchase analytics for recent purchase lookups (same as Smart Restock)
        global_purchase_analytics = analysis.get('purchase_insights', {}) if analysis else {}
        
        # Fetch recent email alerts
        email_alerts = fetch_discount_email_alerts()
        if email_alerts:
            sample_alerts = email_alerts[:3]
            pass
        
        # Fetch source links from user's Google Sheet (same approach as Smart Restock)
        asin_to_source_link = {}
        
        # Check if user has source links enabled and Google Sheet configured
        enable_source_links = get_user_field(config_user_record, 'settings.enable_source_links') or config_user_record.get('enable_source_links', False)
        sheet_id = get_user_field(config_user_record, 'files.sheet_id')
        google_tokens = get_user_field(config_user_record, 'integrations.google.tokens') or {}
        search_all_worksheets = get_user_field(config_user_record, 'settings.search_all_worksheets') or config_user_record.get('search_all_worksheets', True)
        column_mapping = get_user_column_mapping(config_user_record)
        
        if enable_source_links and sheet_id and google_tokens.get('access_token'):
            try:
                # Use EXACT same approach as Smart Restock
                from orders_analysis import OrdersAnalysis
                analyzer = OrdersAnalysis("", "")  # URLs not needed for COGS fetch
                
                if search_all_worksheets:
                    # Search ALL worksheets
                    def api_call(access_token):
                        return analyzer.fetch_google_sheet_cogs_data_all_worksheets(
                            access_token,
                            sheet_id,
                            column_mapping
                        )
                    
                    # Use safe API call with token refresh
                    result = safe_google_api_call(config_user_record, api_call)
                    cogs_data = result[0] if result and isinstance(result, tuple) else result
                    
                    if cogs_data:
                        # Process COGS data - it's a dictionary keyed by ASIN
                        for asin, data in cogs_data.items():
                            if asin and len(str(asin)) == 10 and str(asin).replace('-', '').isalnum():
                                # Look for sources in the all_sources array (same as Smart Restock)
                                all_sources = data.get('all_sources', [])
                                if all_sources:
                                    # Use the most recent (last) source
                                    source_link = all_sources[-1]
                                    if source_link and str(source_link).startswith('http'):
                                        asin_to_source_link[str(asin).upper()] = str(source_link)
                else:
                    # Single worksheet mode
                    worksheet_title = get_user_field(config_user_record, 'integrations.google.worksheet_title')
                    if worksheet_title:
                        cogs_data = analyzer.fetch_google_sheet_cogs_data(
                            google_tokens.get('access_token'),
                            sheet_id,
                            worksheet_title,
                            column_mapping
                        )
                        
                        if cogs_data:
                            for asin, data in cogs_data.items():
                                if asin and len(str(asin)) == 10 and str(asin).replace('-', '').isalnum():
                                    # Look for sources in the all_sources array (same as Smart Restock)
                                    all_sources = data.get('all_sources', [])
                                    if all_sources:
                                        # Use the most recent (last) source
                                        source_link = all_sources[-1]
                                        if source_link and str(source_link).startswith('http'):
                                            asin_to_source_link[str(asin).upper()] = str(source_link)
                
                
            except Exception as e:
                print(f"[WARNING] Failed to fetch source links from Google Sheets: {str(e)}")
        opportunities = []
        
        # Process email alerts using multithreading
        def process_email_alert(email_alert):
            """Process a single email alert and return opportunity data"""
            retailer = email_alert['retailer']
            asin = email_alert['asin']
            
            # Skip if retailer filter is specified and doesn't match
            if retailer_filter and retailer_filter.lower() not in retailer.lower():
                return None
            
            # Check if this ASIN is in user's inventory (debug enhanced_analytics)
            if enhanced_analytics and len(enhanced_analytics) > 0:
                sample_keys = list(enhanced_analytics.keys())[:5]
            
            if asin in enhanced_analytics:
                inventory_data = enhanced_analytics[asin]
                restock_data = inventory_data.get('restock', {})
                
                # Get restock information
                current_stock = restock_data.get('current_stock', 0)
                suggested_quantity = restock_data.get('suggested_quantity', 0)
                days_left = restock_data.get('days_left', None)
                
                # Use the SAME approach as Smart Restock Recommendations for recent purchases
                monthly_purchase_adjustment = restock_data.get('monthly_purchase_adjustment', 0)
                
                # If monthly_purchase_adjustment has data, use it as recent_purchases
                # Otherwise try to get it from the analysis purchase insights (same as Smart Restock does with global_purchase_analytics)
                if monthly_purchase_adjustment > 0:
                    recent_purchases = monthly_purchase_adjustment
                else:
                    # Use global_purchase_analytics exactly like Smart Restock does
                    recent_purchases = get_recent_2_months_purchases_for_lead_analysis(asin, global_purchase_analytics)
                
                # Additional debugging for recent purchases
                if asin == 'B0017TF1E8':
                    print(f"DEBUG: ASIN {asin} monthly_purchase_adjustment: {monthly_purchase_adjustment}")
                    print(f"DEBUG: ASIN {asin} global_purchase_analytics keys: {list(global_purchase_analytics.keys()) if global_purchase_analytics else 'None'}")
                    print(f"DEBUG: ASIN {asin} final recent_purchases: {recent_purchases}")
                
                # Determine if restocking is needed - loosened criteria
                # Show opportunities if:
                # 1. System suggests restocking (suggested_quantity > 0), OR
                # 2. Low stock (current_stock < 20), OR  
                # 3. Running low based on velocity (days_left < 30 if available)
                low_stock_threshold = 20
                velocity_based_need = False
                if days_left is not None and days_left < 30:
                    velocity_based_need = True
                
                needs_restock = (
                    suggested_quantity > 0 or 
                    current_stock < low_stock_threshold or
                    velocity_based_need
                )
                
                # Fast lookup for source link using pre-processed dictionary
                source_link = asin_to_source_link.get(asin.upper())
                
                # Extract special promotional text for Vitacost
                promo_message = None
                if retailer.lower() == 'vitacost':
                    html_content = email_alert.get('html_content', '')
                    promo_message = extract_vitacost_promo_message(html_content)
                
                # Determine status based on restock need with more granular categories
                if suggested_quantity > 0:
                    status = 'Restock Needed'
                    priority_score = calculate_opportunity_priority(inventory_data, days_left, suggested_quantity)
                elif current_stock < low_stock_threshold:
                    status = 'Low Stock'
                    priority_score = calculate_opportunity_priority(inventory_data, days_left, max(10, current_stock))
                elif velocity_based_need:
                    status = 'Running Low'
                    priority_score = calculate_opportunity_priority(inventory_data, days_left, max(5, current_stock))
                else:
                    status = 'Not Needed'
                    priority_score = 0  # Lower priority for items not needed
                
                # Debug logging for recent purchases
                print(f"DEBUG: ASIN {asin} - recent_purchases: {recent_purchases}, restock_data keys: {list(restock_data.keys())}")
                
                opportunity = {
                    'asin': asin,
                    'retailer': retailer,
                    'product_name': inventory_data.get('product_name', ''),
                    'current_stock': current_stock,
                    'recent_purchases': recent_purchases,
                    'suggested_quantity': suggested_quantity if needs_restock else 0,
                    'days_left': days_left if needs_restock else None,
                    'velocity': inventory_data.get('velocity', {}).get('weighted_velocity', 0),
                    'source_link': source_link,
                    'promo_message': promo_message,
                    'note': email_alert.get('note'),
                    'alert_time': email_alert['alert_time'],
                    'priority_score': priority_score,
                    'restock_priority': inventory_data.get('priority', {}).get('category', 'normal'),
                    'status': status,
                    'needs_restock': needs_restock
                }
                return opportunity
            else:
                # ASIN not in inventory - still show it but mark as not tracked
                opportunity = {
                    'asin': asin,
                    'retailer': retailer,
                    'product_name': 'Product not tracked',
                    'current_stock': 0,
                    'recent_purchases': 0,
                    'suggested_quantity': 0,
                    'days_left': None,
                    'velocity': 0,
                    'source_link': None,
                    'promo_message': None,
                    'note': email_alert.get('note'),
                    'alert_time': email_alert['alert_time'],
                    'priority_score': 0,
                    'restock_priority': 'not_tracked',
                    'status': 'Not Tracked',
                    'needs_restock': False
                }
                return opportunity
        
        # Use ThreadPoolExecutor to process alerts in parallel
        max_workers = min(20, len(email_alerts))  # Increased to 20 threads since operations are now much faster
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all email alerts for processing
            future_to_alert = {executor.submit(process_email_alert, alert): alert for alert in email_alerts}
            
            # Collect results as they complete
            for future in as_completed(future_to_alert):
                try:
                    opportunity = future.result()
                    if opportunity is not None:  # Skip filtered alerts
                        opportunities.append(opportunity)
                except Exception as e:
                    alert = future_to_alert[future]
                    print(f"[ERROR] Failed to process alert for ASIN {alert.get('asin', 'unknown')}: {str(e)}")
                    # Continue processing other alerts even if one fails
        
        # Sort by restock need first, then by priority score
        def sort_key(x):
            # Priority order: Restock Needed (1), Not Needed (2), Not Tracked (3)
            if x['status'] == 'Restock Needed':
                status_priority = 1
            elif x['status'] == 'Not Needed':
                status_priority = 2
            else:  # Not Tracked
                status_priority = 3
            
            return (status_priority, -x['priority_score'])  # Negative for descending order
        
        opportunities.sort(key=sort_key)
        
        # Count different status types
        restock_needed_count = len([o for o in opportunities if o['status'] == 'Restock Needed'])
        not_needed_count = len([o for o in opportunities if o['status'] == 'Not Needed'])
        not_tracked_count = len([o for o in opportunities if o['status'] == 'Not Tracked'])
        
        
        result = {
            'opportunities': opportunities,
            'total_alerts_processed': len(email_alerts),
            'matched_products': len(opportunities),
            'restock_needed_count': restock_needed_count,
            'not_needed_count': not_needed_count,
            'not_tracked_count': not_tracked_count,
            'retailer_filter': retailer_filter,
            'analyzed_at': datetime.now(pytz.UTC).isoformat(),
            'message': f'Found {len(opportunities)} discount leads ({restock_needed_count} need restocking, {not_needed_count} not needed, {not_tracked_count} not tracked)'
        }
        
        # Cache the result in database for 24 hours
        cache_discount_opportunities(discord_id, retailer_filter, result)
        
        # Add cache metadata for fresh data
        result['cached'] = False  # This is fresh data
        result['cache_age_hours'] = 0
        
        return jsonify(result)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Error analyzing opportunities: {str(e)}'}), 500

@app.route('/api/discount-opportunities/refresh', methods=['POST'])
@login_required
def refresh_discount_opportunities():
    """Force refresh discount opportunities cache"""
    try:
        data = request.get_json() or {}
        retailer_filter = data.get('retailer', '')
        discord_id = session['discord_id']
        
        # Clear existing cache
        cursor.execute('''
            DELETE FROM discount_opportunities_cache 
            WHERE discord_id = ? AND retailer_filter = ?
        ''', (discord_id, retailer_filter))
        conn.commit()
        
        # Redirect to analyze endpoint to regenerate data
        return analyze_discount_opportunities()
        
    except Exception as e:
        return jsonify({'error': f'Error refreshing opportunities: {str(e)}'}), 500

@app.route('/api/discount-opportunities/debug-emails', methods=['GET'])
@admin_required  
def debug_discount_emails():
    """Focused debug endpoint for DMS email processing"""
    try:
        from datetime import datetime, timedelta
        import re
        
        result = {
            'timestamp': datetime.now().isoformat(),
            'config': {},
            'email_search': {},
            'asin_extraction': [],
            'summary': {}
        }
        
        # Get configuration
        discount_config = get_discount_email_config()
        days_back = get_discount_email_days_back()
        
        result['config'] = {
            'days_back': days_back,
            'sender_filter': discount_config.get('sender_filter', 'alert@distill.io') if discount_config else 'alert@distill.io',
            'asin_pattern': discount_config.get('asin_pattern', r'\b(B[0-9A-Z]{9})\b') if discount_config else r'\b(B[0-9A-Z]{9})\b',
            'has_email_config': bool(discount_config),
            'email_address': discount_config.get('email_address') if discount_config else None
        }
        
        # Create user record for Gmail API - only use discount email config
        if discount_config and discount_config.get('tokens'):
            user_record = {
                'google_tokens': discount_config.get('tokens', {})
            }
        else:
            # No fallback to admin users - discount email must be configured independently
            user_record = {}
            result['config']['error'] = 'Discount email not configured with Gmail tokens'
        
        # Test email search
        cutoff_date = datetime.now() - timedelta(days=days_back)
        query = f"from:{result['config']['sender_filter']} after:{cutoff_date.strftime('%Y/%m/%d')}"
        
        result['email_search'] = {
            'query': query,
            'cutoff_date': cutoff_date.strftime('%Y/%m/%d'),
            'user_record_available': bool(user_record),
            'messages_found': 0,
            'gmail_api_error': None
        }
        
        # Try Gmail search
        try:
            messages = search_gmail_messages(user_record, query, max_results=500)
            if messages:
                result['email_search']['messages_found'] = len(messages.get('messages', []))
                result['email_search']['gmail_api_success'] = True
                
                # Process all emails for ASIN extraction testing
                if messages.get('messages'):
                    b008_found = False
                    for i, msg in enumerate(messages['messages'][:100]):  # Test first 100 for debugging
                        try:
                            email_data = get_gmail_message(user_record, msg['id'])
                            if email_data:
                                headers = {h['name']: h['value'] for h in email_data.get('payload', {}).get('headers', [])}
                                subject = headers.get('Subject', '')
                                sender = headers.get('From', '')
                                date_received = headers.get('Date', '')
                                
                                # Test ASIN extraction
                                asin = None
                                asin_pattern = result['config']['asin_pattern']
                                asin_match = re.search(asin_pattern, subject, re.IGNORECASE)
                                
                                # Check if this is the B008XQO7WA email we're looking for
                                is_b008_email = 'B008XQO7WA' in subject
                                if is_b008_email:
                                    b008_found = True
                                
                                extraction_result = {
                                    'email_index': i + 1,
                                    'subject': subject,
                                    'sender': sender,
                                    'date': date_received,
                                    'pattern_used': asin_pattern,
                                    'pattern_matched': bool(asin_match),
                                    'extracted_asin': None,
                                    'asin_valid': False,
                                    'final_asin': None,
                                    'is_b008_email': is_b008_email
                                }
                                
                                if asin_match:
                                    potential_asin = asin_match.group(1)
                                    extraction_result['extracted_asin'] = potential_asin
                                    extraction_result['asin_valid'] = is_valid_asin(potential_asin)
                                    if extraction_result['asin_valid']:
                                        asin = potential_asin
                                        extraction_result['final_asin'] = asin
                                
                                result['asin_extraction'].append(extraction_result)
                        except Exception as e:
                            result['asin_extraction'].append({
                                'email_index': i + 1,
                                'error': str(e)
                            })
            else:
                result['email_search']['gmail_api_success'] = False
                result['email_search']['gmail_api_error'] = 'No messages returned'
                
        except Exception as e:
            result['email_search']['gmail_api_success'] = False
            result['email_search']['gmail_api_error'] = str(e)
        
        # Summary
        valid_asins = [item['final_asin'] for item in result['asin_extraction'] if item.get('final_asin')]
        b008_emails = [item for item in result['asin_extraction'] if item.get('is_b008_email')]
        
        result['summary'] = {
            'emails_processed': len(result['asin_extraction']),
            'valid_asins_found': len(valid_asins),
            'asins': valid_asins,
            'b008_found_in_search': b008_found,
            'b008_emails_count': len(b008_emails),
            'issues_detected': []
        }
        
        if result['email_search']['messages_found'] == 0:
            result['summary']['issues_detected'].append('No emails found with current search criteria')
        if len(valid_asins) == 0 and result['email_search']['messages_found'] > 0:
            result['summary']['issues_detected'].append('Emails found but no valid ASINs extracted')
        
        # Multiple B008XQO7WA searches to find today's email
        result['b008_searches'] = {}
        
        # Search 1: No date restriction
        try:
            no_date_query = f"from:{result['config']['sender_filter']} B008XQO7WA"
            no_date_messages = search_gmail_messages(user_record, no_date_query, max_results=500)
            
            result['b008_searches']['no_date_restriction'] = {
                'query': no_date_query,
                'messages_found': len(no_date_messages.get('messages', [])) if no_date_messages else 0,
                'recent_subjects': []
            }
            
            if no_date_messages and no_date_messages.get('messages'):
                for msg in no_date_messages['messages'][:50]:  # Show more results
                    try:
                        email_data = get_gmail_message(user_record, msg['id'])
                        if email_data:
                            headers = {h['name']: h['value'] for h in email_data.get('payload', {}).get('headers', [])}
                            subject = headers.get('Subject', '')
                            date_received = headers.get('Date', '')
                            result['b008_searches']['no_date_restriction']['recent_subjects'].append({
                                'subject': subject,
                                'date': date_received
                            })
                    except:
                        continue
        except Exception as e:
            result['b008_searches']['no_date_restriction'] = {'error': str(e)}
        
        # Search 2: Today specifically
        try:
            today = datetime.now().strftime('%Y/%m/%d')
            today_query = f"from:{result['config']['sender_filter']} B008XQO7WA after:{today}"
            today_messages = search_gmail_messages(user_record, today_query, max_results=500)
            
            result['b008_searches']['today_only'] = {
                'query': today_query,
                'date': today,
                'messages_found': len(today_messages.get('messages', [])) if today_messages else 0
            }
        except Exception as e:
            result['b008_searches']['today_only'] = {'error': str(e)}
        
        # Search 3: All emails from sender today (to see what's actually there)
        try:
            all_today_query = f"from:{result['config']['sender_filter']} after:{today}"
            all_today_messages = search_gmail_messages(user_record, all_today_query, max_results=500)
            
            result['b008_searches']['all_today'] = {
                'query': all_today_query,
                'messages_found': len(all_today_messages.get('messages', [])) if all_today_messages else 0,
                'subjects_with_b008': []
            }
            
            if all_today_messages and all_today_messages.get('messages'):
                for msg in all_today_messages['messages']:
                    try:
                        email_data = get_gmail_message(user_record, msg['id'])
                        if email_data:
                            headers = {h['name']: h['value'] for h in email_data.get('payload', {}).get('headers', [])}
                            subject = headers.get('Subject', '')
                            if 'B008XQO7WA' in subject:
                                date_received = headers.get('Date', '')
                                result['b008_searches']['all_today']['subjects_with_b008'].append({
                                    'subject': subject,
                                    'date': date_received
                                })
                    except:
                        continue
                        
        except Exception as e:
            result['b008_searches']['all_today'] = {'error': str(e)}
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/discount-opportunities/email-diagnostics', methods=['GET'])
@admin_required
def discount_email_diagnostics():
    """Comprehensive diagnostics for email date and fetching issues"""
    try:
        from datetime import datetime, timedelta
        import pytz
        import re
        
        result = {
            'current_time': {
                'utc': datetime.utcnow().isoformat(),
                'local': datetime.now().isoformat(),
                'timezone': str(datetime.now(pytz.timezone('US/Eastern')))
            },
            'date_ranges_tested': {},
            'raw_email_data': [],
            'processing_results': []
        }
        
        # Get config
        discount_config = get_discount_email_config()
        sender_filter = discount_config.get('sender_filter', 'alert@distill.io') if discount_config else 'alert@distill.io'
        
        # Create user record
        if discount_config and discount_config.get('tokens'):
            user_record = {'google_tokens': discount_config.get('tokens', {})}
        else:
            users = get_users_config()
            admin_user = None
            for user in users:
                if get_user_field(user, 'integrations.google.tokens'):
                    admin_user = user
                    break
            user_record = admin_user if admin_user else {}
        
        # Test different date ranges
        date_tests = [
            ('last_24_hours', 1),
            ('last_48_hours', 2),
            ('last_7_days', 7),
            ('last_14_days', 14)
        ]
        
        for test_name, days in date_tests:
            cutoff = datetime.now() - timedelta(days=days)
            query = f"from:{sender_filter} after:{cutoff.strftime('%Y/%m/%d')}"
            
            try:
                messages = search_gmail_messages(user_record, query, max_results=10)
                count = len(messages.get('messages', [])) if messages else 0
                
                result['date_ranges_tested'][test_name] = {
                    'query': query,
                    'cutoff_date': cutoff.strftime('%Y/%m/%d %H:%M:%S'),
                    'messages_found': count
                }
                
                # For last 24 hours, get detailed info
                if test_name == 'last_24_hours' and messages and messages.get('messages'):
                    for i, msg in enumerate(messages['messages'][:5]):
                        try:
                            email_data = get_gmail_message(user_record, msg['id'])
                            if email_data:
                                headers = {h['name']: h['value'] for h in email_data.get('payload', {}).get('headers', [])}
                                subject = headers.get('Subject', '')
                                date_str = headers.get('Date', '')
                                
                                # Parse date multiple ways
                                parsed_dates = {}
                                
                                # Try direct parsing
                                try:
                                    from email.utils import parsedate_to_datetime
                                    parsed_date = parsedate_to_datetime(date_str)
                                    parsed_dates['email_utils'] = parsed_date.isoformat()
                                    parsed_dates['email_utils_utc'] = parsed_date.astimezone(pytz.UTC).isoformat()
                                except Exception as e:
                                    parsed_dates['email_utils_error'] = str(e)
                                
                                # Try manual parsing
                                try:
                                    alert_time = convert_gmail_date_to_iso(date_str)
                                    parsed_dates['convert_gmail_date'] = alert_time
                                except Exception as e:
                                    parsed_dates['convert_gmail_date_error'] = str(e)
                                
                                result['raw_email_data'].append({
                                    'index': i + 1,
                                    'subject': subject,
                                    'raw_date': date_str,
                                    'parsed_dates': parsed_dates,
                                    'contains_asin': bool(re.search(r'B[0-9A-Z]{9}', subject))
                                })
                        except Exception as e:
                            result['raw_email_data'].append({
                                'index': i + 1,
                                'error': str(e)
                            })
                            
            except Exception as e:
                result['date_ranges_tested'][test_name]['error'] = str(e)
        
        # Test the actual processing function
        try:
            alerts = fetch_discount_email_alerts()
            result['processing_results'] = {
                'total_alerts': len(alerts),
                'is_mock_data': len(alerts) > 0 and alerts[0].get('retailer') == 'Vitacost' and alerts[0].get('asin') == 'B07XVTRJKX',
                'latest_alert_times': []
            }
            
            # Get the latest alert times
            for alert in sorted(alerts, key=lambda x: x.get('alert_time', ''), reverse=True)[:5]:
                result['processing_results']['latest_alert_times'].append({
                    'asin': alert.get('asin'),
                    'time': alert.get('alert_time'),
                    'subject': alert.get('subject', '')[:80]
                })
                
        except Exception as e:
            result['processing_results'] = {'error': str(e)}
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/discount-opportunities/test-recent', methods=['GET'])
@admin_required
def test_recent_discount_emails():
    """Quick test to see recent emails and their processing"""
    try:
        from datetime import datetime, timedelta
        
        # Get the actual function results
        alerts = fetch_discount_email_alerts()
        
        # Check if we're getting mock data
        is_mock = len(alerts) > 0 and alerts[0].get('asin') == 'B07XVTRJKX' and alerts[0].get('retailer') == 'Vitacost'
        
        # Get latest alerts
        sorted_alerts = sorted(alerts, key=lambda x: x.get('alert_time', ''), reverse=True)
        
        return jsonify({
            'is_using_mock_data': is_mock,
            'total_alerts': len(alerts),
            'latest_5_alerts': [
                {
                    'asin': a.get('asin'),
                    'time': a.get('alert_time'),
                    'subject': a.get('subject', '')[:100],
                    'retailer': a.get('retailer')
                }
                for a in sorted_alerts[:5]
            ],
            'days_back_setting': get_discount_email_days_back()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/discount-email/config-source', methods=['GET'])
@admin_required
def get_discount_email_config_source():
    """Debug endpoint to show which config source is being used"""
    try:
        result = {
            's3_config': None,
            'db_config': None,
            'active_config': None,
            'config_priority': 'S3 -> Database -> None'
        }
        
        # Check S3 config
        try:
            s3_client = get_s3_client()
            response = s3_client.get_object(Bucket=CONFIG_S3_BUCKET, Key='admin/discount_email_config.json')
            s3_config = json.loads(response['Body'].read().decode('utf-8'))
            result['s3_config'] = {
                'exists': True,
                'email': s3_config.get('email_address'),
                'last_updated': s3_config.get('last_updated'),
                'has_tokens': bool(s3_config.get('tokens'))
            }
        except:
            result['s3_config'] = {'exists': False}
        
        # Check database config
        try:
            conn = sqlite3.connect(DATABASE_FILE)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT email_address, config_type, created_at, gmail_access_token IS NOT NULL as has_tokens
                FROM discount_email_config
                WHERE is_active = 1
                ORDER BY created_at DESC
                LIMIT 1
            ''')
            row = cursor.fetchone()
            conn.close()
            
            if row:
                result['db_config'] = {
                    'exists': True,
                    'email': row[0],
                    'config_type': row[1],
                    'created_at': row[2],
                    'has_tokens': bool(row[3])
                }
            else:
                result['db_config'] = {'exists': False}
        except:
            result['db_config'] = {'error': 'Could not check database'}
        
        # Get active config
        active_config = get_discount_email_config()
        if active_config:
            result['active_config'] = {
                'email': active_config.get('email_address'),
                'is_s3_config': active_config.get('is_s3_config', False),
                'has_tokens': bool(active_config.get('tokens'))
            }
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/discount-email/migrate-to-s3', methods=['POST'])
@admin_required
def migrate_discount_email_to_s3():
    """Migrate discount email config from database to S3"""
    try:
        from datetime import datetime
        # Get database config
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT email_address, config_type, gmail_access_token, gmail_refresh_token, 
                   gmail_token_expires_at
            FROM discount_email_config
            WHERE is_active = 1
            ORDER BY created_at DESC
            LIMIT 1
        ''')
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return jsonify({'error': 'No active database configuration found'}), 404
        
        email_address, config_type, access_token, refresh_token, token_expires_at = row
        
        if config_type != 'gmail_oauth' or not access_token:
            return jsonify({'error': 'Only Gmail OAuth configurations can be migrated'}), 400
        
        # Create S3 config
        config_data = {
            'email_address': email_address,
            'config_type': 'gmail_oauth',
            'tokens': {
                'access_token': access_token,
                'refresh_token': refresh_token,
                'token_expires_at': token_expires_at
            },
            'connected_at': datetime.now().isoformat(),
            'connected_by': session.get('discord_id', 'admin'),
            'is_active': True,
            'subject_pattern': r'\[([^\]]+)\]\s*Alert:\s*[^\(]*\(ASIN:\s*([B0-9A-Z]{10})\)',
            'asin_pattern': r'\b(B[0-9A-Z]{9})\b',
            'retailer_pattern': r'\[([^\]]+)\]\s*Alert:',
            'sender_filter': 'alert@distill.io'
        }
        
        # Save to S3
        save_discount_email_config(config_data)
        
        # Clear cache
        cache_key = f"config_discount_email_config"
        if cache_key in config_cache:
            del config_cache[cache_key]
        
        return jsonify({
            'success': True,
            'message': f'Configuration for {email_address} migrated to S3',
            'note': 'Configuration will now persist across redeploys'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/discount-opportunities/check-stale', methods=['POST'])
@login_required
def check_stale_opportunities():
    """Check if opportunities data is stale and suggest refresh"""
    try:
        data = request.get_json() or {}
        retailer_filter = data.get('retailer', '')
        discord_id = session['discord_id']
        
        # Get cache info
        cursor.execute('''
            SELECT created_at FROM discount_opportunities_cache 
            WHERE discord_id = ? AND retailer_filter = ? AND expires_at > datetime('now')
            ORDER BY created_at DESC LIMIT 1
        ''', (discord_id, retailer_filter))
        
        result = cursor.fetchone()
        if result:
            created_at = result[0]
            try:
                cache_time = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                hours_old = (datetime.now() - cache_time).total_seconds() / 3600
                
                return jsonify({
                    'has_cache': True,
                    'hours_old': round(hours_old, 1),
                    'is_stale': hours_old > 8,  # Consider stale after 8 hours
                    'recommend_update': hours_old > 12  # Strong recommendation after 12 hours
                })
            except:
                return jsonify({'has_cache': False, 'hours_old': 0, 'is_stale': True})
        else:
            return jsonify({'has_cache': False, 'hours_old': 0, 'is_stale': True})
            
    except Exception as e:
        return jsonify({'error': f'Error checking cache status: {str(e)}'}), 500

# ===== FEATURE FLAG SYSTEM =====

def init_feature_flags():
    """Initialize feature flags database tables"""
    print(f"🔧 Initializing database tables in {DATABASE_FILE}...")
    try:
        # Create a local connection for initialization
        init_conn = sqlite3.connect(DATABASE_FILE)
        init_cursor = init_conn.cursor()
        
        # Create features table
        init_cursor.execute('''
            CREATE TABLE IF NOT EXISTS features (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                feature_key TEXT UNIQUE NOT NULL,
                feature_name TEXT NOT NULL,
                description TEXT,
                is_beta BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create user_feature_access table for per-user permissions
        init_cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_feature_access (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                discord_id TEXT NOT NULL,
                feature_key TEXT NOT NULL,
                has_access BOOLEAN DEFAULT 0,
                granted_by TEXT,
                granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (feature_key) REFERENCES features (feature_key),
                UNIQUE (discord_id, feature_key)
            )
        ''')
        
        # Create feature launch status table
        init_cursor.execute('''
            CREATE TABLE IF NOT EXISTS feature_launches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                feature_key TEXT UNIQUE NOT NULL,
                is_public BOOLEAN DEFAULT 0,
                launched_by TEXT,
                launched_at TIMESTAMP,
                launch_notes TEXT,
                FOREIGN KEY (feature_key) REFERENCES features (feature_key)
            )
        ''')
        
        # Create user groups table
        init_cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_key TEXT UNIQUE NOT NULL,
                group_name TEXT NOT NULL,
                description TEXT,
                created_by TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create user group membership table  
        init_cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_group_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                discord_id TEXT NOT NULL,
                group_key TEXT NOT NULL,
                added_by TEXT NOT NULL,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (group_key) REFERENCES user_groups (group_key),
                UNIQUE (discord_id, group_key)
            )
        ''')
        
        # Create group feature access table
        init_cursor.execute('''
            CREATE TABLE IF NOT EXISTS group_feature_access (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_key TEXT NOT NULL,
                feature_key TEXT NOT NULL,
                has_access BOOLEAN DEFAULT 0,
                granted_by TEXT NOT NULL,
                granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (group_key) REFERENCES user_groups (group_key),
                FOREIGN KEY (feature_key) REFERENCES features (feature_key),
                UNIQUE (group_key, feature_key)
            )
        ''')
        
        # Create email monitoring configuration table
        init_cursor.execute('''
            CREATE TABLE IF NOT EXISTS email_monitoring (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                discord_id TEXT NOT NULL,
                email_address TEXT NOT NULL,
                auth_type TEXT DEFAULT 'imap', -- 'imap' or 'oauth'
                imap_server TEXT,
                imap_port INTEGER DEFAULT 993,
                username TEXT,
                password_encrypted TEXT,
                oauth_access_token TEXT,
                oauth_refresh_token TEXT, 
                oauth_token_expires_at TIMESTAMP,
                is_active BOOLEAN DEFAULT 1,
                last_checked TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (discord_id, email_address)
            )
        ''')
        
        # Create email monitoring rules table
        init_cursor.execute('''
            CREATE TABLE IF NOT EXISTS email_monitoring_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                discord_id TEXT NOT NULL,
                rule_name TEXT NOT NULL,
                sender_filter TEXT,
                subject_filter TEXT,
                content_filter TEXT,
                webhook_url TEXT NOT NULL,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create email monitoring logs table
        init_cursor.execute('''
            CREATE TABLE IF NOT EXISTS email_monitoring_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                discord_id TEXT NOT NULL,
                rule_id INTEGER NOT NULL,
                email_subject TEXT,
                email_sender TEXT,
                email_date TIMESTAMP,
                webhook_sent BOOLEAN DEFAULT 0,
                webhook_response TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (rule_id) REFERENCES email_monitoring_rules (id)
            )
        ''')
        
        # Create discount opportunities email configuration table (admin only)
        init_cursor.execute('''
            CREATE TABLE IF NOT EXISTS discount_email_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email_address TEXT NOT NULL,
                config_type TEXT NOT NULL DEFAULT 'gmail_oauth', -- 'gmail_oauth' or 'imap'
                imap_server TEXT,
                imap_port INTEGER DEFAULT 993,
                username TEXT,
                password_encrypted TEXT,
                gmail_access_token TEXT,
                gmail_refresh_token TEXT,
                gmail_token_expires_at TIMESTAMP,
                is_active BOOLEAN DEFAULT 1,
                created_by TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                -- Custom format patterns for email parsing
                subject_pattern TEXT DEFAULT '\\[([^\\]]+)\\]\\s*Alert:\\s*[^\\(]*\\(ASIN:\\s*([B0-9A-Z]{10})\\)',
                asin_pattern TEXT DEFAULT '\\(ASIN:\\s*([B0-9A-Z]{10})\\)',
                retailer_pattern TEXT DEFAULT '\\[([^\\]]+)\\]\\s*Alert:',
                sender_filter TEXT DEFAULT 'alert@distill.io'
            )
        ''')
        
        # Add new columns to existing discount_email_config table if they don't exist
        try:
            init_cursor.execute("PRAGMA table_info(discount_email_config)")
            columns = [col[1] for col in init_cursor.fetchall()]
            
            if 'subject_pattern' not in columns:
                init_cursor.execute('ALTER TABLE discount_email_config ADD COLUMN subject_pattern TEXT DEFAULT \'\\\\[([^\\\\]]+)\\\\]\\\\s*Alert:.*?\\\\(ASIN:\\\\s*([B0-9A-Z]{10})\\\\)\'')
                print("Added subject_pattern column to discount_email_config")
            
            if 'asin_pattern' not in columns:
                init_cursor.execute('ALTER TABLE discount_email_config ADD COLUMN asin_pattern TEXT DEFAULT \'\\\\(ASIN:\\\\s*([B0-9A-Z]{10})\\\\)\'')
                print("Added asin_pattern column to discount_email_config")
            
            if 'retailer_pattern' not in columns:
                init_cursor.execute('ALTER TABLE discount_email_config ADD COLUMN retailer_pattern TEXT DEFAULT \'\\\\[([^\\\\]]+)\\\\]\\\\s*Alert:\'')
                print("Added retailer_pattern column to discount_email_config")
            
            if 'sender_filter' not in columns:
                init_cursor.execute('ALTER TABLE discount_email_config ADD COLUMN sender_filter TEXT DEFAULT \'alert@distill.io\'')
                print("Added sender_filter column to discount_email_config")
                
        except Exception as e:
            print(f"Note: Could not add discount email format columns: {e}")
        
        # Create admin email monitoring webhook configuration table
        init_cursor.execute('''
            CREATE TABLE IF NOT EXISTS email_monitoring_webhook_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                webhook_url TEXT NOT NULL,
                webhook_name TEXT,
                is_active BOOLEAN DEFAULT 1,
                created_by TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Add new columns to existing email_monitoring table if they don't exist
        try:
            init_cursor.execute("ALTER TABLE email_monitoring ADD COLUMN auth_type TEXT DEFAULT 'oauth'")
        except sqlite3.OperationalError:
            pass  # Column already exists
            
        try:
            init_cursor.execute("ALTER TABLE email_monitoring ADD COLUMN oauth_access_token TEXT")
        except sqlite3.OperationalError:
            pass
            
        try:
            init_cursor.execute("ALTER TABLE email_monitoring ADD COLUMN oauth_refresh_token TEXT")
        except sqlite3.OperationalError:
            pass
            
        try:
            init_cursor.execute("ALTER TABLE email_monitoring ADD COLUMN oauth_token_expires_at TIMESTAMP")
        except sqlite3.OperationalError:
            pass
        
        # Remove webhook_url from individual rules since it's now system-wide
        try:
            init_cursor.execute("ALTER TABLE email_monitoring_rules DROP COLUMN webhook_url")
        except sqlite3.OperationalError:
            pass
        
        init_conn.commit()
        
        # Insert default features
        default_features = [
            ('smart_restock', 'Smart Restock Analytics', 'Advanced restock recommendations and analytics', False),
            ('discount_opportunities', 'Discount Opportunities', 'Email-based discount opportunity analysis', False),
            ('reimbursements', 'Reimbursement Analyzer', 'FBA reimbursement tracking and analysis', False),
            ('ebay_lister', 'eBay Lister', 'Automated eBay listing management', True),
            ('missing_listings', 'Missing Listings', 'Track expected arrivals and missing listings', False),
            ('purchase_manager', 'Purchase Manager', 'VA purchase tracking with live inventory integration', True),
            ('va_management', 'VA Management', 'Virtual assistant user management', False),
            ('lambda_deployment', 'Lambda Deployment', 'AWS Lambda function deployment', True),
            ('email_monitoring', 'Email Monitoring', 'Monitor emails for refunds and notifications', True)
        ]
        
        for feature_key, name, description, is_beta in default_features:
            init_cursor.execute('''
                INSERT OR IGNORE INTO features (feature_key, feature_name, description, is_beta)
                VALUES (?, ?, ?, ?)
            ''', (feature_key, name, description, is_beta))
        
        # Insert default user groups
        default_groups = [
            ('beta_testers', 'Beta Testers', 'Users who test new features before general release', '712147636463075389'),
            ('power_users', 'Power Users', 'Advanced users with access to premium features', '712147636463075389'),
            ('basic_users', 'Basic Users', 'Standard users with core feature access', '712147636463075389'),
            ('va_users', 'VA Users', 'Virtual assistants with limited feature access', '712147636463075389')
        ]
        
        for group_key, group_name, description, created_by in default_groups:
            init_cursor.execute('''
                INSERT OR IGNORE INTO user_groups (group_key, group_name, description, created_by)
                VALUES (?, ?, ?, ?)
            ''', (group_key, group_name, description, created_by))
        
        init_conn.commit()
        init_conn.close()
        
        # Sync S3 data to database to restore any lost data
        sync_s3_to_database()
        
        print("✅ Email monitoring tables created successfully")
        
    except Exception as e:
        print(f"Error initializing feature flags: {e}")

def has_feature_access(discord_id, feature_key):
    """Check if user has access to a specific feature (individual or group-based)"""
    try:
        # In demo mode, block access to beta features
        if DEMO_MODE:
            # Check if this feature is beta
            cursor.execute('SELECT is_beta FROM features WHERE feature_key = ?', (feature_key,))
            beta_result = cursor.fetchone()
            if beta_result and beta_result[0]:  # is_beta is True
                print(f"[DEMO MODE] Blocking access to beta feature: {feature_key}")
                return False
        
        # Admin always has access to everything (except beta features in demo mode)
        user = get_user_record(discord_id)
        if user and get_user_field(user, 'identity.discord_id') == '712147636463075389':  # Admin discord ID
            return True
            
        # If user is a subuser, check parent's access instead
        if user and get_user_field(user, 'account.user_type') == 'subuser':
            parent_user_id = get_user_field(user, 'account.parent_user_id')
            if parent_user_id:
                return has_feature_access(parent_user_id, feature_key)
            
        # Check if feature is publicly launched (database first, S3 fallback)
        cursor.execute('''
            SELECT is_public FROM feature_launches WHERE feature_key = ?
        ''', (feature_key,))
        launch_result = cursor.fetchone()
        
        is_launched_db = launch_result and launch_result[0]
        
        # Fallback to S3 if database doesn't have launch data
        if not is_launched_db:
            feature_launches, _ = get_feature_config()
            if feature_key in feature_launches:
                is_launched_db = feature_launches[feature_key].get('is_public', False)
        
        if is_launched_db:
            return True
        
        # Check user-specific access (database first, S3 fallback)
        cursor.execute('''
            SELECT has_access FROM user_feature_access 
            WHERE discord_id = ? AND feature_key = ?
        ''', (discord_id, feature_key))
        
        access_result = cursor.fetchone()
        has_user_access = access_result and access_result[0]
        
        # Fallback to S3 user permissions
        if not has_user_access:
            user = get_user_record(discord_id)
            feature_perms = get_user_field(user, 'account.feature_permissions') or {}
            if user and feature_perms:
                user_perm = feature_perms.get(feature_key, {})
                has_user_access = user_perm.get('has_access', False)
        
        if has_user_access:
            return True
        
        # Check group-based access
        cursor.execute('''
            SELECT gfa.has_access FROM group_feature_access gfa
            JOIN user_group_members ugm ON gfa.group_key = ugm.group_key
            WHERE ugm.discord_id = ? AND gfa.feature_key = ? AND gfa.has_access = 1
        ''', (discord_id, feature_key))
        
        group_access_result = cursor.fetchone()
        return bool(group_access_result)
        
    except Exception as e:
        print(f"Error checking feature access for {discord_id}, {feature_key}: {e}")
        return False

def get_user_features(discord_id):
    """Get all features accessible to a user"""
    try:
        # Create local database connection
        local_conn = sqlite3.connect(DATABASE_FILE)
        local_cursor = local_conn.cursor()
        
        user_features = {}
        
        # Get all features
        local_cursor.execute('SELECT feature_key, feature_name, description, is_beta FROM features')
        all_features = local_cursor.fetchall()
        
        for feature_key, name, description, is_beta in all_features:
            # Skip beta features in demo mode
            if DEMO_MODE and bool(is_beta):
                print(f"[DEMO MODE] Hiding beta feature: {feature_key}")
                continue
            
            # has_feature_access already handles subuser logic
            has_access = has_feature_access(discord_id, feature_key)
            user_features[feature_key] = {
                'name': name,
                'description': description,
                'is_beta': bool(is_beta),
                'has_access': has_access
            }
        
        local_conn.close()
        return user_features
        
    except Exception as e:
        print(f"Error getting user features for {discord_id}: {e}")
        return {}

# Initialize feature flags on startup
init_feature_flags()

@app.route('/api/admin/features', methods=['GET'])
@login_required
def get_all_features():
    """Admin endpoint to get all features and their status"""
    try:
        discord_id = session['discord_id']
        if discord_id != '712147636463075389':  # Only admin can access
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Create local database connection
        local_conn = sqlite3.connect(DATABASE_FILE)
        local_cursor = local_conn.cursor()
        
        local_cursor.execute('''
            SELECT f.feature_key, f.feature_name, f.description, f.is_beta,
                   fl.is_public, fl.launched_at, fl.launch_notes
            FROM features f
            LEFT JOIN feature_launches fl ON f.feature_key = fl.feature_key
            ORDER BY f.feature_name
        ''')
        
        features = []
        for row in local_cursor.fetchall():
            feature_key, name, description, is_beta, is_public, launched_at, launch_notes = row
            features.append({
                'feature_key': feature_key,
                'display_name': name,  # Frontend expects display_name
                'description': description,
                'is_beta': bool(is_beta),
                'is_launched': bool(is_public) if is_public is not None else False,  # Frontend expects is_launched
                'launched_at': launched_at,
                'launch_notes': launch_notes
            })
        
        local_conn.close()
        response = jsonify({'features': features})
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
        
    except Exception as e:
        return jsonify({'error': f'Error fetching features: {str(e)}'}), 500

@app.route('/api/admin/features/launch', methods=['POST'])
@login_required 
def launch_feature():
    """Admin endpoint to launch a feature publicly"""
    try:
        discord_id = session['discord_id']
        if discord_id != '712147636463075389':  # Only admin can access
            return jsonify({'error': 'Unauthorized'}), 403
            
        data = request.get_json()
        feature_key = data.get('feature_key')
        launch_notes = data.get('notes', '')
        
        if not feature_key:
            return jsonify({'error': 'Feature key required'}), 400
        
        # Insert or update launch status
        cursor.execute('''
            INSERT OR REPLACE INTO feature_launches 
            (feature_key, is_public, launched_by, launched_at, launch_notes)
            VALUES (?, 1, ?, datetime('now'), ?)
        ''', (feature_key, discord_id, launch_notes))
        
        conn.commit()
        
        # Also store in S3 for persistence
        save_feature_launch_to_s3(feature_key, True, discord_id, launch_notes)
        
        return jsonify({'message': f'Feature {feature_key} launched successfully'})
        
    except Exception as e:
        return jsonify({'error': f'Error launching feature: {str(e)}'}), 500

@app.route('/api/admin/features/unlaunch', methods=['POST'])
@login_required
def unlaunch_feature():
    """Admin endpoint to remove a feature from public access"""
    try:
        discord_id = session['discord_id']
        if discord_id != '712147636463075389':  # Only admin can access
            return jsonify({'error': 'Unauthorized'}), 403
            
        data = request.get_json()
        feature_key = data.get('feature_key')
        
        if not feature_key:
            return jsonify({'error': 'Feature key required'}), 400
        
        # Update launch status to not public
        cursor.execute('''
            UPDATE feature_launches SET is_public = 0 WHERE feature_key = ?
        ''', (feature_key,))
        
        if cursor.rowcount == 0:
            # Insert if not exists
            cursor.execute('''
                INSERT INTO feature_launches (feature_key, is_public, launched_by, launched_at)
                VALUES (?, 0, ?, datetime('now'))
            ''', (feature_key, discord_id))
        
        conn.commit()
        
        # Also store in S3 for persistence
        save_feature_launch_to_s3(feature_key, False, discord_id)
        
        return jsonify({'message': f'Feature {feature_key} removed from public access'})
        
    except Exception as e:
        return jsonify({'error': f'Error unlaunching feature: {str(e)}'}), 500

@app.route('/api/user/features', methods=['GET'])
@login_required
def get_user_accessible_features():
    """Get features accessible to current user"""
    try:
        discord_id = session['discord_id']
        features = get_user_features(discord_id)
        response = jsonify({'features': features})
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
        
    except Exception as e:
        return jsonify({'error': f'Error fetching user features: {str(e)}'}), 500

def fetch_sellerboard_cogs_data(cogs_url):
    """
    Fetch and process Sellerboard Cost of Goods Sold CSV data
    Returns cleaned inventory data with products that have SKUs and are not hidden
    """
    import pandas as pd
    import requests
    from io import StringIO
    
    try:
        # Check if URL has required parameters
        if 'sellerboard.com' in cogs_url and 'format=csv' not in cogs_url:
            # Add CSV format if missing
            separator = '&' if '?' in cogs_url else '?'
            cogs_url = f"{cogs_url}{separator}format=csv"
        
        # Create a session to handle cookies properly
        session = requests.Session()
        
        # Add headers that might be expected by Sellerboard
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/csv,application/csv,text/plain,*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        }
        
        # First, get the redirect URL without following it
        initial_response = session.get(cogs_url, timeout=30, allow_redirects=False, headers=headers)
        
        if initial_response.status_code == 302:
            redirect_url = initial_response.headers.get('Location')
            print(f"Got redirect to: {redirect_url}")
            
            # Now follow the redirect with the same session (preserving automation cookies)
            response = session.get(redirect_url, timeout=30, headers=headers)
            
            if response.status_code == 401:
                print(f"❌ 401 error - download URL requires additional authentication")
                print(f"🔍 The automation token creates a session but download needs browser login")
                print(f"💡 Solution: User must download manually through logged-in browser")
                raise Exception(f"AUTHENTICATION_REQUIRED: Sellerboard COGS downloads require browser login session. Please download manually: {cogs_url}")
                
        else:
            response = initial_response
        
        response.raise_for_status()
        
        # Parse CSV data
        csv_data = StringIO(response.text)
        df = pd.read_csv(csv_data)
        
        # Clean the data according to requirements:
        # 1. Remove products without SKUs
        # 2. Remove products where Hide column is "Yes"
        
        # Check for SKU column (might be named differently)
        sku_column = None
        for col in df.columns:
            if 'sku' in col.lower():
                sku_column = col
                break
        
        if sku_column is None:
            raise ValueError("No SKU column found in Sellerboard COGS data")
            
        # Check for Hide column
        hide_column = None
        for col in df.columns:
            if 'hide' in col.lower():
                hide_column = col
                break
        
        # Filter out products without SKUs
        df_filtered = df[df[sku_column].notna() & (df[sku_column] != '')]
        
        # Filter out hidden products if Hide column exists
        if hide_column is not None:
            df_filtered = df_filtered[df_filtered[hide_column] != 'Yes']
        
        # Look for ASIN column
        asin_column = None
        for col in df_filtered.columns:
            if 'asin' in col.lower():
                asin_column = col
                break
                
        if asin_column is None:
            raise ValueError("No ASIN column found in Sellerboard COGS data")
        
        # Convert to list of dictionaries for easier processing
        inventory_data = df_filtered.to_dict('records')
        
        return {
            'data': inventory_data,
            'sku_column': sku_column,
            'asin_column': asin_column,
            'hide_column': hide_column,
            'total_products': len(inventory_data)
        }
        
    except requests.exceptions.RequestException as e:
        if hasattr(e, 'response') and e.response is not None:
            if e.response.status_code == 401:
                raise ValueError(
                    "Authentication failed (401 Unauthorized). This usually means the token in your automation report URL has expired.\n\n"
                    "To fix this:\n"
                    "1. Go to Sellerboard → Reports → Cost of Goods Sold\n"
                    "2. Click 'Share/Export' button\n"
                    "3. Generate a new 'Automated Report URL'\n"
                    "4. Update the URL in your settings\n\n"
                    "Note: Automation report URLs contain time-limited tokens that need to be refreshed periodically."
                )
            elif e.response.status_code == 403:
                raise ValueError(
                    "Access forbidden (403). Please check that the report URL is correct and accessible."
                )
            else:
                raise ValueError(f"HTTP error {e.response.status_code}: {str(e)}")
        else:
            raise ValueError(f"Network error when fetching Sellerboard COGS data: {str(e)}")
    except Exception as e:
        raise ValueError(f"Error processing Sellerboard COGS data: {str(e)}")


def fetch_sellerboard_cogs_data_from_email(discord_id: str) -> Optional[Dict]:
    """
    Fetch Sellerboard COGS data directly from latest email
    Returns data in same format as fetch_sellerboard_cogs_data for compatibility
    """
    try:
        print(f"[fetch_sellerboard_cogs_data_from_email] Starting for user: {discord_id}")
        from email_monitoring_s3 import email_monitoring_manager
        
        # First try to get access token from email monitoring OAuth configs
        email_configs = email_monitoring_manager.get_email_configs(discord_id)
        access_token = None
        
        print(f"[fetch_sellerboard_cogs_data_from_email] Found {len(email_configs)} email configs")
        for config in email_configs:
            if config.get('auth_type') == 'oauth' and config.get('oauth_access_token'):
                access_token = config['oauth_access_token']
                print(f"[fetch_sellerboard_cogs_data_from_email] Found email monitoring OAuth token")
                
                # Check if token needs refresh
                if config.get('oauth_token_expires_at'):
                    try:
                        from datetime import datetime, timedelta
                        expires_at = datetime.fromisoformat(config['oauth_token_expires_at'].replace('Z', '+00:00'))
                        if datetime.utcnow() >= expires_at - timedelta(minutes=5):
                            # Token needs refresh
                            refresh_token = config.get('oauth_refresh_token')
                            if refresh_token:
                                new_token = refresh_email_oauth_token(refresh_token)
                                if new_token:
                                    access_token = new_token['access_token']
                                    # Update token in email monitoring system
                                    email_monitoring_manager.update_oauth_tokens(
                                        discord_id, config['email_address'],
                                        new_token['access_token'],
                                        refresh_token,
                                        new_token.get('expires_at')
                                    )
                    except Exception as e:
                        print(f"Error refreshing email monitoring token: {e}")
                break
        
        # If no email monitoring OAuth token, try main Google integration
        if not access_token:
            print(f"[fetch_sellerboard_cogs_data_from_email] No email monitoring token, trying main Google integration")
            user_record = get_user_record(discord_id)
            if not user_record:
                print(f"[fetch_sellerboard_cogs_data_from_email] No user record found")
                return None
            
            # Check for subuser and get parent config if needed
            config_user_record = user_record
            if get_user_field(user_record, 'account.user_type') == 'subuser':
                parent_user_id = get_user_field(user_record, 'account.parent_user_id')
                if parent_user_id:
                    parent_record = get_user_record(parent_user_id)
                    if parent_record:
                        config_user_record = parent_record
                        print(f"[fetch_sellerboard_cogs_data_from_email] Using parent user config for subuser")
            
            google_tokens = get_user_field(config_user_record, 'integrations.google.tokens') or {}
            current_token = google_tokens.get('access_token')
            print(f"[fetch_sellerboard_cogs_data_from_email] Google token available: {bool(current_token)}")
            
            if not current_token:
                print("No Gmail access token available for COGS email processing")
                print("💡 User needs to set up email monitoring OAuth or Google integration with Gmail permissions")
                return None
            
            # Use safe_google_api_call to handle token refresh
            def api_call(access_token):
                return fetch_latest_sellerboard_cogs_email(access_token)
            
            print(f"[fetch_sellerboard_cogs_data_from_email] Using safe_google_api_call with main Google integration")
            return safe_google_api_call(config_user_record, api_call)
        
        # Use email monitoring OAuth token with token refresh support
        print(f"[fetch_sellerboard_cogs_data_from_email] Using email monitoring OAuth token")
        # Create a mock user record for token refresh if needed
        mock_user_record = {
            'integrations': {
                'google': {
                    'tokens': {
                        'access_token': access_token,
                        'refresh_token': None  # Email monitoring may not have refresh tokens
                    }
                }
            }
        }
        
        def api_call(token):
            return fetch_latest_sellerboard_cogs_email(token)
        
        try:
            print(f"[fetch_sellerboard_cogs_data_from_email] Trying email monitoring token directly")
            return api_call(access_token)
        except Exception as e:
            error_str = str(e)
            if any(indicator in error_str for indicator in ["401", "Invalid Credentials", "UNAUTHENTICATED", "authError"]):
                print(f"Email monitoring token expired, trying main Google integration fallback")
                # Fallback to main Google integration
                user_record = get_user_record(discord_id)
                if user_record:
                    config_user_record = user_record
                    if get_user_field(user_record, 'account.user_type') == 'subuser':
                        parent_user_id = get_user_field(user_record, 'account.parent_user_id')
                        if parent_user_id:
                            parent_record = get_user_record(parent_user_id)
                            if parent_record:
                                config_user_record = parent_record
                    
                    return safe_google_api_call(config_user_record, api_call)
                else:
                    raise
            else:
                raise
        
    except Exception as e:
        print(f"Error fetching COGS data from email: {e}")
        return None


def refresh_email_oauth_token(refresh_token: str) -> Optional[Dict]:
    """Refresh OAuth token for email access"""
    try:
        google_client_id = os.getenv('GOOGLE_CLIENT_ID')
        google_client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
        
        if not google_client_id or not google_client_secret:
            return None
        
        token_data = {
            'client_id': google_client_id,
            'client_secret': google_client_secret,
            'refresh_token': refresh_token,
            'grant_type': 'refresh_token'
        }
        
        response = requests.post('https://oauth2.googleapis.com/token', data=token_data)
        
        if response.ok:
            tokens = response.json()
            access_token = tokens.get('access_token')
            expires_in = tokens.get('expires_in', 3600)
            expires_at = (datetime.utcnow() + timedelta(seconds=expires_in)).isoformat()
            
            return {
                'access_token': access_token,
                'expires_at': expires_at
            }
        else:
            return None
            
    except Exception as e:
        print(f"Error refreshing OAuth token: {e}")
        return None


def fetch_latest_sellerboard_cogs_email(access_token: str) -> Optional[Dict]:
    """Fetch the most recent Sellerboard COGS email and process its attachment"""
    try:
        import pandas as pd
        from io import StringIO
        
        # Search for emails from team@sellerboard.com with "Your report is ready" in subject
        search_url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages"
        headers = {"Authorization": f"Bearer {access_token}"}
        params = {
            "q": 'from:"team@sellerboard.com" subject:"sellerboard: Your report is ready"',
            "maxResults": 5
        }
        
        response = requests.get(search_url, headers=headers, params=params)
        if not response.ok:
            print(f"Gmail search failed: {response.status_code} - {response.text}")
            if response.status_code == 401:
                print("Gmail API authentication failed - user may need to re-authorize Google integration with Gmail permissions")
                # Raise exception so safe_google_api_call can catch it and refresh token
                raise Exception(f"Gmail API 401 error: {response.text}")
            return None
        
        search_results = response.json()
        messages = search_results.get('messages', [])
        
        if not messages:
            print("No Sellerboard report emails found")
            return None
        
        # Process the most recent message
        message_id = messages[0]['id']
        
        # Get full message details
        message_url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}"
        msg_response = requests.get(message_url, headers=headers)
        
        if not msg_response.ok:
            print(f"Failed to fetch message details: {msg_response.status_code}")
            return None
            
        email_data = msg_response.json()
        
        # Extract attachments
        payload = email_data.get('payload', {})
        attachments = []
        
        def find_attachments(part):
            body = part.get('body', {})
            if body.get('attachmentId'):
                filename = part.get('filename', '')
                if filename.lower().endswith('.csv'):
                    attachments.append({
                        'filename': filename,
                        'attachmentId': body['attachmentId'],
                        'mimeType': part.get('mimeType')
                    })
            
            for subpart in part.get('parts', []):
                find_attachments(subpart)
        
        for part in payload.get('parts', []):
            find_attachments(part)
        
        if not attachments:
            print("No CSV attachments found in Sellerboard email")
            return None
        
        # Use the first CSV attachment (should be the COGS report)
        attachment = attachments[0]
        
        # Download the attachment
        attachment_url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}/attachments/{attachment['attachmentId']}"
        attachment_response = requests.get(attachment_url, headers=headers)
        
        if not attachment_response.ok:
            print(f"Failed to download attachment: {attachment_response.status_code}")
            return None
        
        attachment_data = attachment_response.json()
        csv_data = attachment_data.get('data', '')
        
        if not csv_data:
            print("No attachment data received")
            return None
        
        # Decode and parse CSV
        csv_content = base64.urlsafe_b64decode(csv_data + '===').decode('utf-8')
        df = pd.read_csv(StringIO(csv_content))
        
        # Detect ASIN column
        asin_column = None
        asin_candidates = ['ASIN', 'asin', 'Asin', 'SKU', 'sku', 'Product ID', 'product_id']
        for col in asin_candidates:
            if col in df.columns:
                asin_column = col
                break
        
        if not asin_column:
            print("No ASIN column found in CSV")
            return None
        
        print(f"✅ Successfully processed Sellerboard email with {len(df)} products from {attachment['filename']}")
        
        return {
            'data': df.to_dict('records'),
            'asin_column': asin_column,
            'total_products': len(df),
            'filename': attachment['filename'],
            'source': 'sellerboard_email'
        }
        
    except Exception as e:
        print(f"Error processing Sellerboard email: {e}")
        return None


@app.route('/api/test-cogs-email', methods=['POST'])
@login_required
def test_cogs_email():
    """Test fetching COGS data from latest Sellerboard email"""
    try:
        discord_id = session.get('discord_id')
        if not discord_id:
            return jsonify({'error': 'User not authenticated'}), 401
        
        cogs_data = fetch_sellerboard_cogs_data_from_email(discord_id)
        
        if cogs_data:
            return jsonify({
                'success': True,
                'message': f'Successfully processed COGS data from {cogs_data["filename"]}',
                'total_products': cogs_data['total_products'],
                'filename': cogs_data['filename'],
                'sample_data': cogs_data['data'][:3] if cogs_data['data'] else []
            })
        else:
            return jsonify({
                'success': False,
                'error': 'No COGS email found or failed to process'
            }), 404
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error testing COGS email: {str(e)}'
        }), 500


@app.route('/api/missing-listings', methods=['GET'])
@login_required
def get_expected_arrivals():
    """Get items purchased that don't have Amazon listings created yet"""
    try:
        # Get scope parameter (all or current_month)
        scope = request.args.get('scope', 'all')
        
        # Return dummy data in demo mode
        if DEMO_MODE:
            return jsonify(get_dummy_expected_arrivals_data())
        
        discord_id = session['discord_id']
        
        # Check for cached missing listings data (24 hour cache)
        from datetime import datetime, timedelta
        missing_listings_cache_key = f"missing_listings_{discord_id}_{scope}"
        
        if missing_listings_cache_key in analytics_cache:
            cache_entry = analytics_cache[missing_listings_cache_key]
            if datetime.now() - cache_entry['timestamp'] < timedelta(hours=24):
                return jsonify(cache_entry['data'])
        user_record = get_user_record(discord_id)
        
        if not user_record:
            return jsonify({"error": "User not found"}), 404

        # Handle parent-child relationship for configuration
        config_user_record = user_record
        parent_user_id = user_record.get('parent_user_id')
        if parent_user_id:
            parent_record = get_user_record(parent_user_id)
            if parent_record:
                config_user_record = parent_record

        # Security check: Ensure we're not mixing impersonation data
        if 'admin_impersonating' in session:
            target_user_id = session['admin_impersonating'].get('target_user_id')
            if str(discord_id) != str(target_user_id):
                return jsonify({"error": "Session impersonation mismatch"}), 403

        # Get user config for Google access (use parent config for subusers)
        config_user_record = user_record
        if user_record and get_user_field(user_record, 'account.user_type') == 'subuser':
            parent_user_id = get_user_field(user_record, 'account.parent_user_id')
            if parent_user_id:
                parent_record = get_user_record(parent_user_id)
                if parent_record:
                    config_user_record = parent_record

        # Get the Google Sheet settings for purchase data
        sheet_id = get_user_field(config_user_record, 'files.sheet_id')
        google_tokens = get_user_field(config_user_record, 'integrations.google.tokens') or {}
        column_mapping = get_user_column_mapping(user_record)
        
        # Try email-based COGS first
        inventory_data = None
        try:
            email_cogs_data = fetch_sellerboard_cogs_data_from_email(discord_id)
            if email_cogs_data:
                inventory_data = email_cogs_data
                print(f"✅ Successfully fetched COGS data from email: {email_cogs_data['filename']}")
        except Exception as email_error:
            print(f"Email COGS fetch failed: {email_error}")
        
        # If email COGS failed, check Google Sheets requirement
        if not inventory_data:
            if not sheet_id or not google_tokens.get('access_token'):
                return jsonify({
                    "error": "No COGS data source available. Email processing failed (likely missing Gmail permissions) and Google Sheets not configured.",
                    "suggestion": "Go to Settings → Google Integration and ensure Gmail permissions are granted, or configure Google Sheets for COGS data"
                }), 400

        # Initialize OrdersAnalysis to get purchase data
        from orders_analysis import OrdersAnalysis
        import pandas as pd
        analysis = OrdersAnalysis()
        
        # Get purchase data from Google Sheets based on scope
        
        try:
            if scope == 'current_month':
                
                # Get current month worksheet name
                current_month = datetime.now().strftime('%B').upper()
                
                # Use safe_google_api_call to get worksheet list first
                def get_worksheets_api_call(access_token):
                    import requests
                    metadata_url = f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}?fields=sheets.properties"
                    headers = {"Authorization": f"Bearer {access_token}"}
                    r = requests.get(metadata_url, headers=headers)
                    r.raise_for_status()
                    sheets_info = r.json().get("sheets", [])
                    return [sheet["properties"]["title"] for sheet in sheets_info]
                
                worksheet_names = safe_google_api_call(config_user_record, get_worksheets_api_call)
                
                # Find current month worksheet
                current_month_worksheet = None
                for ws_name in worksheet_names:
                    if current_month in ws_name.upper():
                        current_month_worksheet = ws_name
                        break
                
                if not current_month_worksheet:
                    # Fallback to first worksheet if no current month found
                    current_month_worksheet = worksheet_names[0] if worksheet_names else None
                
                if not current_month_worksheet:
                    return jsonify({"error": "No worksheets found in the spreadsheet"}), 400
                
                
                # Fetch data from current month worksheet only
                def api_call(access_token):
                    return analysis.fetch_google_sheet_cogs_data(
                        access_token=access_token,
                        sheet_id=sheet_id,
                        worksheet_title=current_month_worksheet,
                        column_mapping=column_mapping
                    ), analysis.fetch_google_sheet_data(
                        access_token=access_token,
                        sheet_id=sheet_id,
                        worksheet_title=current_month_worksheet,
                        column_mapping=column_mapping
                    )[1]  # Get the dataframe part
                
                result = safe_google_api_call(config_user_record, api_call)
                cogs_data, combined_purchase_df = result
                
            else:
                
                # Use safe_google_api_call to handle token refresh
                def api_call(access_token):
                    return analysis.fetch_google_sheet_cogs_data_all_worksheets(
                        access_token=access_token,
                        sheet_id=sheet_id,
                        column_mapping=column_mapping
                    )
                
                cogs_data, combined_purchase_df = safe_google_api_call(config_user_record, api_call)
            
        except Exception as e:
            return jsonify({"error": f"Failed to fetch purchase data: {str(e)}"}), 500

        if combined_purchase_df.empty:
            return jsonify({
                "missing_listings": [],
                "summary": {"total_items": 0, "total_cost": 0},
                "message": "No recent purchase data found"
            }), 200

        # Analyze purchases based on scope
        from purchase_analytics import PurchaseAnalytics
        purchase_analytics = PurchaseAnalytics()
        purchase_insights = purchase_analytics.analyze_purchase_data(
            combined_purchase_df, 
            column_mapping
        )
        
        if scope == 'current_month':
            # For current month scope, analyze all purchases from the current month worksheet
            recent_purchases_data = {}
            
            # Process current month data directly from DataFrame
            if not combined_purchase_df.empty:
                for _, row in combined_purchase_df.iterrows():
                    asin = row.get('ASIN')
                    if pd.notna(asin) and asin.strip():
                        asin = str(asin).strip()
                        
                        if asin not in recent_purchases_data:
                            recent_purchases_data[asin] = {
                                'total_quantity_purchased': 0,
                                'purchase_count': 0,
                                'last_purchase_date': None,
                                'first_purchase_date': None,
                                'avg_cogs_recent': 0,
                                'source_worksheets': set(),
                                'analysis_period': 'Current month only'
                            }
                        
                        # Update purchase data
                        quantity = row.get('Quantity', 0) or row.get('Amount Purchased', 0)
                        if pd.notna(quantity):
                            recent_purchases_data[asin]['total_quantity_purchased'] += int(quantity)
                            recent_purchases_data[asin]['purchase_count'] += 1
                        
                        # Update COGS
                        cogs = row.get('COGS', 0)
                        if pd.notna(cogs) and cogs > 0:
                            recent_purchases_data[asin]['avg_cogs_recent'] = float(cogs)
                        
                        # Update dates
                        date_val = row.get('Date')
                        if pd.notna(date_val):
                            date_str = str(date_val)
                            if recent_purchases_data[asin]['last_purchase_date'] is None or date_str > recent_purchases_data[asin]['last_purchase_date']:
                                recent_purchases_data[asin]['last_purchase_date'] = date_str
                            if recent_purchases_data[asin]['first_purchase_date'] is None or date_str < recent_purchases_data[asin]['first_purchase_date']:
                                recent_purchases_data[asin]['first_purchase_date'] = date_str
                        
                        # Update source worksheets
                        worksheet_source = row.get('_worksheet_source')
                        if pd.notna(worksheet_source):
                            recent_purchases_data[asin]['source_worksheets'].add(str(worksheet_source))
                
                # Convert source_worksheets sets to lists
                for asin_data in recent_purchases_data.values():
                    asin_data['source_worksheets'] = list(asin_data['source_worksheets'])
            
            analysis_period_msg = "current month"
        else:
            # Use existing 2-month analysis
            recent_purchases_data = purchase_insights.get('recent_2_months_purchases', {})
            analysis_period_msg = "last 2 months"
        
        
        if not recent_purchases_data:
            return jsonify({
                "missing_listings": [],
                "summary": {"total_items": 0, "total_cost": 0},
                "message": f"No recent purchases found in the {analysis_period_msg}"
            }), 200

        # Get ALL Sellerboard data (not just current inventory) to check for any listings
        sellerboard_url = get_user_sellerboard_stock_url(config_user_record)
        if not sellerboard_url:
            return jsonify({"error": "Sellerboard stock URL not configured"}), 400

        # Get COGS URL for complete inventory data (includes out-of-stock items)
        sellerboard_cogs_url = get_user_sellerboard_cogs_url(config_user_record)

        # Get inventory data (ASINs that have Amazon listings)
        all_known_asins = set()
        
        if sellerboard_cogs_url and inventory_data:
            # Use Sellerboard COGS data (complete inventory)
            asin_column = inventory_data['asin_column']
            
            for product in inventory_data['data']:
                asin = product.get(asin_column)
                if asin and str(asin).strip():
                    all_known_asins.add(str(asin).upper())
            
        else:
            # Fallback to original Sellerboard Analytics approach
            try:
                # Get complete Sellerboard analysis (includes all ASINs with any history)
                # Create a new analysis instance with the sellerboard URL
                sellerboard_analysis = OrdersAnalysis(orders_url=sellerboard_url, stock_url=sellerboard_url)
                from datetime import date
                inventory_analysis = sellerboard_analysis.analyze(for_date=date.today())
                
                # Check both current inventory AND historical data for listings
                current_inventory = inventory_analysis.get('enhanced_analytics', {})
                
                # Add ASINs from enhanced analytics (normalize case)
                for asin_key in current_inventory.keys():
                    all_known_asins.add(asin_key.upper())
                
                # Also check basic analytics for any ASIN that has ever appeared
                basic_analytics = inventory_analysis.get('analytics', {})
                for asin_key in basic_analytics.keys():
                    all_known_asins.add(asin_key.upper())
                
                
            except Exception as e:
                return jsonify({"error": f"Failed to fetch Sellerboard data: {str(e)}"}), 500

        # Find items purchased recently but have NO Amazon listing created (not in Sellerboard at all)
        missing_listings = []
        total_cost = 0
        total_quantity = 0

        for asin, purchase_data in recent_purchases_data.items():
            # Check if this ASIN has ANY presence in Sellerboard (case-insensitive comparison)
            asin_upper = asin.upper()
            has_listing = asin_upper in all_known_asins
            
            
            if not has_listing:
                # This item was purchased recently but has no Amazon listing created yet
                item_info = {
                    "asin": asin,
                    "quantity_purchased": purchase_data.get('total_quantity_purchased', 0),
                    "purchase_count": purchase_data.get('purchase_count', 0),
                    "last_purchase_date": purchase_data.get('last_purchase_date'),
                    "first_purchase_date": purchase_data.get('first_purchase_date'),
                    "avg_cogs": purchase_data.get('avg_cogs_recent', 0),
                    "total_cost": purchase_data.get('avg_cogs_recent', 0) * purchase_data.get('total_quantity_purchased', 0),
                    "source_worksheets": purchase_data.get('source_worksheets', []),
                    "analysis_period": purchase_data.get('analysis_period', 'Last 2 months'),
                    "product_name": "",  # Will be filled from sheet data if available
                    "status": "No Amazon listing created"
                }
                
                # Try to get product name from the purchase data
                asin_rows = combined_purchase_df[combined_purchase_df['ASIN'] == asin]
                if not asin_rows.empty and 'Name' in asin_rows.columns:
                    product_name = asin_rows['Name'].iloc[-1]  # Get most recent name
                    if pd.notna(product_name) and product_name.strip():
                        item_info["product_name"] = str(product_name).strip()
                
                missing_listings.append(item_info)
                total_cost += item_info["total_cost"]
                total_quantity += item_info["quantity_purchased"]

        # Sort by most recent purchase date
        missing_listings.sort(key=lambda x: x.get('last_purchase_date', ''), reverse=True)

        # Prepare response data
        response_data = {
            "missing_listings": missing_listings,
            "summary": {
                "total_items": len(missing_listings),
                "total_quantity": int(total_quantity),
                "total_cost": round(total_cost, 2)
            },
            "analyzed_at": datetime.now().isoformat(),
            "analysis_period": "Current month only" if scope == 'current_month' else "Last 2 months",
            "message": f"Found {len(missing_listings)} purchased items without Amazon listings ({analysis_period_msg})",
            "inventory_source": "sellerboard_cogs" if sellerboard_cogs_url else "sellerboard_analytics",
            "total_inventory_asins": len(all_known_asins)
        }
        
        # Cache the response data
        analytics_cache[missing_listings_cache_key] = {
            'data': response_data,
            'timestamp': datetime.now()
        }

        return jsonify(response_data)

    except Exception as e:
        app.logger.error(f"Expected arrivals error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Failed to analyze expected arrivals: {str(e)}"}), 500

@app.route('/api/retailer-leads/target-worksheets', methods=['GET'])
@login_required
def get_target_worksheets():
    """Get available worksheets from the target spreadsheet"""
    try:
        discord_id = session['discord_id']
        user = get_user_record(discord_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get user config
        config_user_record = user
        if user and get_user_field(user, 'account.user_type') == 'subuser':
            parent_user_id = get_user_field(user, 'account.parent_user_id')
            if parent_user_id:
                parent_record = get_user_record(parent_user_id)
                if parent_record:
                    config_user_record = parent_record
        
        # Check if user has Google tokens
        if not get_user_field(config_user_record, 'integrations.google.tokens'):
            return jsonify({'worksheets': ['Unknown', 'Other', 'Misc', 'No Source']})
        
        try:
            # Get Google access token
            google_tokens = get_user_field(config_user_record, 'integrations.google.tokens') or {}
            
            import requests as req
            refresh_data = {
                'refresh_token': google_tokens.get('refresh_token'),
                'client_id': os.environ.get('GOOGLE_CLIENT_ID'),
                'client_secret': os.environ.get('GOOGLE_CLIENT_SECRET'),
                'grant_type': 'refresh_token'
            }
            
            token_response = req.post('https://oauth2.googleapis.com/token', data=refresh_data)
            token_response.raise_for_status()
            token_data = token_response.json()
            access_token = token_data['access_token']
            
            # Target spreadsheet
            sheet_id = '1Q5weSRaRd7r1zdiA2bwWwcWIwP6pxplGYmY7k9a3aqw'
            
            # Get list of all worksheets
            metadata_url = f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}?fields=sheets.properties"
            headers = {"Authorization": f"Bearer {access_token}"}
            metadata_response = requests.get(metadata_url, headers=headers)
            metadata_response.raise_for_status()
            sheets_info = metadata_response.json().get("sheets", [])
            worksheet_names = [sheet["properties"]["title"] for sheet in sheets_info]
            
            return jsonify({'worksheets': worksheet_names})
            
        except Exception as e:
            print(f"Error fetching target worksheets: {e}")
            # Return default list on error
            return jsonify({'worksheets': ['Unknown', 'Other', 'Misc', 'No Source']})
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/retailer-leads/worksheets', methods=['GET'])
@login_required
def get_available_worksheets():
    """Get available retailer lead worksheets from Google Sheets API"""
    try:
        discord_id = session['discord_id']
        user = get_user_record(discord_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get user config for Google access
        config_user_record = user
        if user and get_user_field(user, 'account.user_type') == 'subuser':
            parent_user_id = get_user_field(user, 'account.parent_user_id')
            if parent_user_id:
                parent_record = get_user_record(parent_user_id)
                if parent_record:
                    config_user_record = parent_record
        
        # Check if user has Google tokens
        if not get_user_field(config_user_record, 'integrations.google.tokens'):
            return jsonify({
                'error': 'Google account not linked',
                'worksheets': ['All Leads']  # Fallback option
            })
            
        sheet_id = '1Q5weSRaRd7r1zdiA2bwWwcWIwP6pxplGYmY7k9a3aqw'  # Your leads sheet ID
        
        # Get Google access token
        google_tokens = get_user_field(config_user_record, 'integrations.google.tokens') or {}
        
        # Create a simple access token refresh
        refresh_data = {
            'refresh_token': google_tokens.get('refresh_token'),
            'client_id': os.environ.get('GOOGLE_CLIENT_ID'),
            'client_secret': os.environ.get('GOOGLE_CLIENT_SECRET'),
            'grant_type': 'refresh_token'
        }
        
        token_response = requests.post('https://oauth2.googleapis.com/token', data=refresh_data)
        token_response.raise_for_status()
        token_data = token_response.json()
        access_token = token_data['access_token']
        
        # Get list of all worksheets in the sheet
        metadata_url = f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}?fields=sheets.properties"
        headers = {"Authorization": f"Bearer {access_token}"}
        metadata_response = requests.get(metadata_url, headers=headers)
        metadata_response.raise_for_status()
        sheets_info = metadata_response.json().get("sheets", [])
        worksheet_names = [sheet["properties"]["title"] for sheet in sheets_info]
        
        # Add "All Leads" as first option to combine all worksheets
        worksheets = ['All Leads'] + worksheet_names
        
        return jsonify({
            'worksheets': worksheets,
            'total': len(worksheets),
            'note': 'Fetched from Google Sheets API'
        })
        
    except Exception as e:
        print(f"Error fetching worksheets: {e}")
        # Fallback to basic options if API fails
        return jsonify({
            'worksheets': ['All Leads', 'Kohls - Flat', 'Walmart', 'Target'],
            'warning': 'Using fallback worksheet list due to API error'
        })

def get_recent_2_months_purchases_for_lead_analysis(asin: str, global_purchase_analytics: dict) -> int:
    """Get the quantity purchased for this ASIN in the last 2 months (using same logic as Smart Restock)"""
    if not global_purchase_analytics:
        return 0
    
    # Use the EXACT same logic as Smart Restock: Check the dedicated recent 2 months purchases data
    recent_2_months_data = global_purchase_analytics.get('recent_2_months_purchases', {})
    if asin in recent_2_months_data:
        qty_purchased = recent_2_months_data[asin].get('total_quantity_purchased', 0)
        if qty_purchased and qty_purchased > 0:
            return int(qty_purchased)
    
    # Fallback to velocity analysis approach (same as Smart Restock)
    velocity_analysis = global_purchase_analytics.get('purchase_velocity_analysis', {}).get(asin, {})
    if velocity_analysis:
        days_since_last = velocity_analysis.get('days_since_last_purchase', 999)
        
        # If purchased within the last 2 months (last 60 days), return the last purchase quantity
        if days_since_last <= 60:
            qty = int(velocity_analysis.get('avg_quantity_per_purchase', 0))
            if qty > 0:
                return qty
    
    return 0

def extract_retailer_from_url(url):
    """Extract retailer name from URL"""
    import re
    if not url or url == 'nan':
        return None
    
    # Extract domain from URL
    match = re.search(r'https?://(?:www\.)?([^/]+)', url)
    if match:
        domain = match.group(1).lower()
        # Map domains to friendly names
        retailer_map = {
            'lowes.com': "Lowe's",
            'homedepot.com': 'Home Depot',
            'walmart.com': 'Walmart',
            'target.com': 'Target',
            'costco.com': 'Costco',
            'samsclub.com': "Sam's Club",
            'bjs.com': "BJ's",
            'kohls.com': "Kohl's",
            'bedbathandbeyond.com': 'Bed Bath & Beyond',
            'wayfair.com': 'Wayfair',
            'overstock.com': 'Overstock',
            'amazon.com': 'Amazon'
        }
        return retailer_map.get(domain, domain.replace('.com', '').title())
    return None

@app.route('/api/test-inventory-analysis', methods=['GET'])
@login_required  
def test_inventory_analysis():
    """Test endpoint to verify OrdersAnalysis is working"""
    try:
        discord_id = session['discord_id']
        user = get_user_record(discord_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        config_user_record = user
        if user and get_user_field(user, 'account.user_type') == 'subuser':
            parent_user_id = get_user_field(user, 'account.parent_user_id')
            if parent_user_id:
                parent_record = get_user_record(parent_user_id)
                if parent_record:
                    config_user_record = parent_record
        
        orders_url = get_user_sellerboard_orders_url(config_user_record)
        stock_url = get_user_sellerboard_stock_url(config_user_record)
        
        if not orders_url or not stock_url:
            return jsonify({'error': 'Sellerboard URLs not configured'}), 400
            
        from datetime import datetime
        import pytz
        from orders_analysis import OrdersAnalysis
        
        user_timezone = get_user_field(config_user_record, 'profile.timezone') or 'America/New_York'
        tz = pytz.timezone(user_timezone)
        today = datetime.now(tz).date()
        
        orders_analysis = OrdersAnalysis(orders_url, stock_url)
        analysis = orders_analysis.analyze(
            for_date=today,
            user_timezone=user_timezone,
            user_settings={
                'enable_source_links': get_user_field(user_record, 'settings.enable_source_links') or user_record.get('enable_source_links', False),
                'search_all_worksheets': get_user_field(config_user_record, 'settings.search_all_worksheets') or config_user_record.get('search_all_worksheets', False),
                'disable_sp_api': get_user_field(config_user_record, 'integrations.amazon.disable_sp_api') or config_user_record.get('disable_sp_api', False),
                'amazon_lead_time_days': get_user_field(config_user_record, 'settings.amazon_lead_time_days') or config_user_record.get('amazon_lead_time_days', 90),
                'discord_id': discord_id
            }
        )
        
        enhanced_analytics = analysis.get('enhanced_analytics', {})
        
        return jsonify({
            'success': True,
            'analysis_keys': list(analysis.keys()),
            'enhanced_analytics_count': len(enhanced_analytics),
            'sample_asins': list(enhanced_analytics.keys())[:10],
            'basic_mode': analysis.get('basic_mode', False),
            'message': analysis.get('message', 'No message')
        })
        
    except Exception as e:
        import traceback
        return jsonify({
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

@app.route('/api/retailer-leads/analyze', methods=['POST'])
@login_required
def analyze_retailer_leads():
    """Analyze all leads from a specific retailer's worksheet and provide buying recommendations"""
    try:
        data = request.get_json() or {}
        worksheet = data.get('worksheet', '').strip()
        
        if not worksheet:
            return jsonify({'error': 'Worksheet name is required'}), 400
        
        # Get user's current analytics data
        discord_id = session['discord_id']
        user = get_user_record(discord_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get user config for analytics
        config_user_record = user
        if user and get_user_field(user, 'account.user_type') == 'subuser':
            parent_user_id = get_user_field(user, 'account.parent_user_id')
            if parent_user_id:
                parent_record = get_user_record(parent_user_id)
                if parent_record:
                    config_user_record = parent_record
        
        # Check if user has necessary configurations
        if not get_user_sellerboard_orders_url(config_user_record) or not get_user_sellerboard_stock_url(config_user_record):
            return jsonify({
                'error': 'Sellerboard URLs not configured',
                'message': 'Please configure your Sellerboard URLs in Settings first'
            }), 400
        
        # Get current inventory analysis
        orders_url = get_user_sellerboard_orders_url(config_user_record)
        stock_url = get_user_sellerboard_stock_url(config_user_record)
        user_timezone = get_user_field(config_user_record, 'profile.timezone') or 'America/New_York'
        
        from datetime import datetime
        import pytz
        from orders_analysis import OrdersAnalysis
        
        tz = pytz.timezone(user_timezone)
        today = datetime.now(tz).date()
        
        try:
            orders_analysis = OrdersAnalysis(orders_url, stock_url)
            
            analysis = orders_analysis.analyze(
                for_date=today,
                user_timezone=user_timezone,
                user_settings={
                    'enable_source_links': get_user_field(config_user_record, 'settings.enable_source_links') or config_user_record.get('enable_source_links', False),
                    'search_all_worksheets': get_user_field(config_user_record, 'settings.search_all_worksheets') or config_user_record.get('search_all_worksheets', False),
                    'disable_sp_api': get_user_field(config_user_record, 'integrations.amazon.disable_sp_api') or config_user_record.get('disable_sp_api', False),
                    'amazon_lead_time_days': get_user_field(config_user_record, 'settings.amazon_lead_time_days') or config_user_record.get('amazon_lead_time_days', 90),
                    'discord_id': discord_id,
                    # Add Google Sheet settings for purchase analytics (same as Smart Restock)
                    'sheet_id': get_user_field(config_user_record, 'files.sheet_id'),
                    'worksheet_title': get_user_field(config_user_record, 'integrations.google.worksheet_title'), 
                    'google_tokens': get_user_field(config_user_record, 'integrations.google.tokens') or {},
                    'column_mapping': get_user_column_mapping(config_user_record)
                }
            )
            
            enhanced_analytics = analysis.get('enhanced_analytics', {})
            
            # Get the global purchase analytics for recent purchase lookups
            global_purchase_analytics = analysis.get('purchase_insights', {})
            
            # Check if we're getting fallback/basic mode
            if analysis.get('basic_mode'):
                return jsonify({
                    'error': 'Analytics in fallback mode',
                    'message': f'OrdersAnalysis fell back to basic mode: {analysis.get("message", "Unknown reason")}'
                }), 500
        except Exception as e:
            return jsonify({
                'error': 'Failed to fetch inventory data',
                'message': f'Failed to generate analytics: {str(e)}'
            }), 500
        
        # Use Google Sheets API to fetch data from the sheet
        sheet_id = '1Q5weSRaRd7r1zdiA2bwWwcWIwP6pxplGYmY7k9a3aqw'  # Your leads sheet ID
        
        # Check if user has Google tokens for API access
        if not get_user_field(config_user_record, 'integrations.google.tokens'):
            return jsonify({
                'error': 'Google account not linked',
                'message': 'Please link your Google account in Settings to access the leads sheet'
            }), 400
            
        try:
            # Get Google access token - use the refresh_google_token function from app.py
            discord_id_temp = discord_id  # Store temporarily
            google_tokens = get_user_field(config_user_record, 'integrations.google.tokens') or {}
            
            # Create a simple access token refresh
            import requests as req
            refresh_data = {
                'refresh_token': google_tokens.get('refresh_token'),
                'client_id': os.environ.get('GOOGLE_CLIENT_ID'),
                'client_secret': os.environ.get('GOOGLE_CLIENT_SECRET'),
                'grant_type': 'refresh_token'
            }
            
            token_response = req.post('https://oauth2.googleapis.com/token', data=refresh_data)
            token_response.raise_for_status()
            token_data = token_response.json()
            access_token = token_data['access_token']
            
            # First, get list of all worksheets in the sheet
            metadata_url = f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}?fields=sheets.properties"
            headers = {"Authorization": f"Bearer {access_token}"}
            metadata_response = requests.get(metadata_url, headers=headers)
            metadata_response.raise_for_status()
            sheets_info = metadata_response.json().get("sheets", [])
            worksheet_names = [sheet["properties"]["title"] for sheet in sheets_info]
            
            print(f"Available worksheets in leads sheet: {worksheet_names}")
            
            # Check if requested worksheet exists
            if worksheet not in worksheet_names and worksheet != 'All Leads':
                return jsonify({
                    'error': f'Worksheet not found: {worksheet}',
                    'message': f'Available worksheets: {", ".join(worksheet_names)}'
                }), 404
            
            # Fetch data from the specified worksheet or all worksheets
            if worksheet == 'All Leads':
                # Combine data from all worksheets
                all_data = []
                for sheet_name in worksheet_names:
                    try:
                        range_ = f"'{sheet_name}'!A1:Z"
                        url = f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values/{range_}"
                        response = requests.get(url, headers=headers)
                        response.raise_for_status()
                        
                        values = response.json().get("values", [])
                        if values and len(values) > 1:  # Has header and at least one data row
                            headers_row = values[0]
                            for row in values[1:]:
                                # Pad row to match headers length
                                padded_row = row + [''] * (len(headers_row) - len(row))
                                row_dict = dict(zip(headers_row, padded_row))
                                row_dict['_source_worksheet'] = sheet_name
                                all_data.append(row_dict)
                    except Exception as e:
                        print(f"Error fetching data from worksheet {sheet_name}: {e}")
                        continue
                
                if not all_data:
                    return jsonify({
                        'error': 'No data found',
                        'message': 'No lead data found in any worksheet'
                    }), 404
                    
                worksheet_df = pd.DataFrame(all_data)
            else:
                # Fetch data from specific worksheet
                range_ = f"'{worksheet}'!A1:Z"
                url = f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values/{range_}"
                response = requests.get(url, headers=headers)
                response.raise_for_status()
                
                values = response.json().get("values", [])
                if not values or len(values) < 2:
                    return jsonify({
                        'error': f'No data found for: {worksheet}',
                        'message': f'The worksheet "{worksheet}" appears to be empty'
                    }), 404
                
                # Convert to DataFrame - pad rows to match header length
                headers = values[0]
                data = values[1:]
                
                # Pad each row to match the number of headers
                padded_data = []
                for row in data:
                    padded_row = row + [''] * (len(headers) - len(row))
                    padded_data.append(padded_row)
                
                worksheet_df = pd.DataFrame(padded_data, columns=headers)
                
            if worksheet_df.empty:
                return jsonify({
                    'error': f'No data found for: {worksheet}',
                    'message': f'The worksheet "{worksheet}" appears to be empty'
                }), 404
                
        except Exception as e:
            import traceback
            print(f"Error fetching Google Sheets data: {e}")
            traceback.print_exc()
            return jsonify({
                'error': f'Failed to fetch data for: {worksheet}',
                'message': f'Could not load worksheet data: {str(e)}'
            }), 500
        
        recommendations = []
        
        # Analyze each lead
        for _, row in worksheet_df.iterrows():
            asin = str(row.get('ASIN', '')).strip().upper()  # Normalize to uppercase
            if not asin or asin == 'nan' or asin == 'NAN':
                continue
                
            # Get product name from CSV - check multiple possible column names
            csv_product_name = None
            for col_name in ['name', 'Name', 'Product Name', 'product_name', 'title', 'Title', 'Product Title', 'product_title']:
                if col_name in row.index:
                    potential_name = row.get(col_name, None)
                    if pd.notna(potential_name) and str(potential_name) != 'nan' and str(potential_name).strip():
                        csv_product_name = str(potential_name).strip()
                        break
            
            # If still no product name, look for any column that might contain product names
            if not csv_product_name:
                for col in row.index:
                    if any(keyword in col.lower() for keyword in ['name', 'title', 'product']):
                        potential_name = row[col]
                        if pd.notna(potential_name) and str(potential_name) != 'nan' and str(potential_name).strip():
                            csv_product_name = str(potential_name).strip()
                            break
                
            # Get source link - check multiple possible column names
            source_link = None
            for col_name in ['source', 'Source', 'URL', 'url', 'Link', 'link']:
                if col_name in row.index:
                    potential_link = row.get(col_name, None)
                    if pd.notna(potential_link) and str(potential_link) != 'nan' and str(potential_link).startswith('http'):
                        source_link = str(potential_link)
                        break
            
            # If still no source link, look for any column containing URL
            if not source_link:
                for col in row.index:
                    if any(keyword in col.lower() for keyword in ['url', 'link', 'source']):
                        potential_link = row[col]
                        if pd.notna(potential_link) and str(potential_link).startswith('http'):
                            source_link = str(potential_link)
                            break
            
            # Check if ASIN is in user's inventory - try both cases
            inventory_data = enhanced_analytics.get(asin, {})
            if not inventory_data:
                # Try lowercase version if uppercase didn't work
                inventory_data = enhanced_analytics.get(asin.lower(), {})
            
            
            # Get retailer name for this specific row
            retailer_name = extract_retailer_from_url(source_link) if source_link else 'Unknown'
            
            # Determine product name - prefer inventory data, fallback to CSV
            product_name = ''
            if inventory_data:
                product_name = inventory_data.get('product_name', '')
            elif csv_product_name:
                product_name = csv_product_name
                
            recommendation = {
                'asin': asin,
                'retailer': retailer_name,
                'worksheet': worksheet,
                'source_link': source_link,
                'in_inventory': bool(inventory_data),
                'recommendation': 'SKIP',
                'reason': '',
                'priority_score': 0,
                'product_name': product_name,
                'recent_purchases': 0  # Will be filled in based on logic below
            }
            
            if inventory_data:
                # Product is in inventory - check if needs restocking
                restock_data = inventory_data.get('restock', {})
                purchase_analytics_data = inventory_data.get('purchase_analytics', {})
                velocity_data = inventory_data.get('velocity', {})
                priority_data = inventory_data.get('priority', {})
                
                current_stock = restock_data.get('current_stock', 0)
                suggested_quantity = restock_data.get('suggested_quantity', 0)
                velocity = velocity_data.get('weighted_velocity', 0)  # Use the same velocity as Smart Restock
                
                # Check for recent purchases (last 2 months) and adjust recommendations
                # The monthly_purchase_adjustment field already contains the recent purchase data from Smart Restock calculation
                monthly_purchase_adjustment = restock_data.get('monthly_purchase_adjustment', 0)
                
                # If monthly_purchase_adjustment has data, use it as recent_purchases
                # Otherwise try to get it from global purchase analytics
                if monthly_purchase_adjustment > 0:
                    recent_purchases = monthly_purchase_adjustment
                else:
                    recent_purchases = get_recent_2_months_purchases_for_lead_analysis(asin, global_purchase_analytics)
                
                recommendation['recent_purchases'] = recent_purchases
                
                # Get additional data
                cogs_data = inventory_data.get('cogs_data', {})
                cogs = cogs_data.get('cogs', 0)
                last_price = inventory_data.get('stock_info', {}).get('Price', 0)
                
                # Use the same logic as Smart Restock: check priority category
                priority_category = priority_data.get('category', 'low')
                priority_score = priority_data.get('score', 0)
                
                # Apply EXACT same logic as Smart Restock, factoring in recent purchases
                if suggested_quantity > 0:
                    # Check if it's in a restock alert category (same as Smart Restock)
                    alert_categories = ['critical_immediate', 'critical_very_soon', 'urgent_restock', 'moderate_restock']
                    
                    if priority_category in alert_categories:
                        # Check if we recently purchased this item
                        if recent_purchases > 0 and monthly_purchase_adjustment > 0:
                            recommendation['recommendation'] = 'MONITOR'  
                            recommendation['reason'] = f'Restock needed but purchased {recent_purchases} units in last 2 months (adjusted from {suggested_quantity + monthly_purchase_adjustment} to {suggested_quantity})'
                            recommendation['priority_score'] = priority_score * 0.7  # Lower priority due to recent purchase
                        else:
                            recommendation['recommendation'] = 'BUY - RESTOCK'
                            recommendation['reason'] = f'Smart Restock Alert: {priority_data.get("reasoning", "Needs restocking")}'
                            recommendation['priority_score'] = priority_score
                    else:
                        recommendation['recommendation'] = 'MONITOR'
                        if recent_purchases > 0:
                            recommendation['reason'] = f'Stock OK, recently purchased {recent_purchases} units: {current_stock} units in stock'
                        else:
                            recommendation['reason'] = f'Stock OK but watch levels: {current_stock} units'
                        recommendation['priority_score'] = priority_score * 0.5
                    
                    recommendation['inventory_details'] = {
                        'current_stock': current_stock,
                        'suggested_quantity': suggested_quantity,
                        'units_per_day': velocity,
                        'days_of_stock': restock_data.get('estimated_coverage_days', 0),
                        'cogs': cogs,
                        'last_price': last_price,
                        'priority_category': priority_category,
                        'confidence': restock_data.get('confidence', 'medium')
                    }
                elif velocity > 0.1:  # Has some sales
                    recommendation['recommendation'] = 'MONITOR'
                    recommendation['reason'] = f'Low/no restock needed, velocity: {velocity:.1f} units/day'
                    recommendation['priority_score'] = velocity * 5
                else:
                    recommendation['recommendation'] = 'SKIP'
                    recommendation['reason'] = f'Very low velocity: {velocity:.1f} units/day'
                    recommendation['priority_score'] = 0
            else:
                # Product not in inventory - but check if we recently purchased it
                # This could happen if we purchased it but it's not yet reflected in stock report
                
                # Try to get purchase analytics from the analysis data (if available) 
                # Even if product isn't in current inventory, it might have purchase history
                recent_purchases_for_new = get_recent_2_months_purchases_for_lead_analysis(asin, global_purchase_analytics)
                
                if recent_purchases_for_new > 0:
                    recommendation['recommendation'] = 'MONITOR'
                    recommendation['reason'] = f'Recently purchased {recent_purchases_for_new} units in last 2 months - monitor arrival/stock levels'  
                    recommendation['priority_score'] = 30  # Lower priority since recently purchased
                    recommendation['recent_purchases'] = recent_purchases_for_new
                else:
                    recommendation['recommendation'] = 'BUY - NEW'
                    recommendation['reason'] = 'Not in inventory - potential new product'
                    recommendation['priority_score'] = 50  # Medium priority for new products
                    recommendation['recent_purchases'] = 0
            
            recommendations.append(recommendation)
        
        # Sort by priority
        recommendations.sort(key=lambda x: x['priority_score'], reverse=True)
        
        
        # Summary statistics
        summary = {
            'total_leads': len(recommendations),
            'buy_restock': len([r for r in recommendations if r['recommendation'] == 'BUY - RESTOCK']),
            'buy_new': len([r for r in recommendations if r['recommendation'] == 'BUY - NEW']),
            'monitor': len([r for r in recommendations if r['recommendation'] == 'MONITOR']),
            'skip': len([r for r in recommendations if r['recommendation'] == 'SKIP'])
        }
        
        return jsonify({
            'worksheet': worksheet,
            'recommendations': recommendations,
            'summary': summary,
            'analyzed_at': datetime.now(pytz.UTC).isoformat()
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Error analyzing retailer leads: {str(e)}'}), 500

@app.route('/api/retailer-leads/sync-to-sheets', methods=['POST'])
@login_required
def sync_leads_to_sheets():
    """Sync leads from user's leads sheet to appropriate worksheets in the target spreadsheet"""
    try:
        data = request.get_json() or {}
        # Optional: default worksheet for leads without source URLs
        default_worksheet_for_no_source = data.get('default_worksheet', 'Unknown')
        
        discord_id = session['discord_id']
        user = get_user_record(discord_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get user config
        config_user_record = user
        if user and get_user_field(user, 'account.user_type') == 'subuser':
            parent_user_id = get_user_field(user, 'account.parent_user_id')
            if parent_user_id:
                parent_record = get_user_record(parent_user_id)
                if parent_record:
                    config_user_record = parent_record
        
        # Check if user has configured their leads sheet
        user_sheet_id = get_user_field(config_user_record, 'files.sheet_id')
        user_worksheet_title = get_user_field(config_user_record, 'integrations.google.worksheet_title')
        
        if not user_sheet_id or not user_worksheet_title:
            return jsonify({
                'error': 'Leads sheet not configured',
                'message': 'Please configure your leads sheet in Settings first'
            }), 400
        
        # Check if user has Google tokens for API access
        if not get_user_field(config_user_record, 'integrations.google.tokens'):
            return jsonify({
                'error': 'Google account not linked',
                'message': 'Please link your Google account in Settings to access the leads sheet'
            }), 400
        
        # Get Google access token
        google_tokens = get_user_field(config_user_record, 'integrations.google.tokens') or {}
        
        import requests as req
        refresh_data = {
            'refresh_token': google_tokens.get('refresh_token'),
            'client_id': os.environ.get('GOOGLE_CLIENT_ID'),
            'client_secret': os.environ.get('GOOGLE_CLIENT_SECRET'),
            'grant_type': 'refresh_token'
        }
        
        token_response = req.post('https://oauth2.googleapis.com/token', data=refresh_data)
        token_response.raise_for_status()
        token_data = token_response.json()
        access_token = token_data['access_token']
        
        headers = {"Authorization": f"Bearer {access_token}"}
        
        # First, fetch all leads from user's connected sheet
        user_leads = []
        # Also create a lookup dictionary for source links from all worksheets
        asin_to_source_lookup = {}
        
        # Import urllib.parse at the beginning
        import urllib.parse
        
        try:
            # Get column mapping
            column_mapping = get_user_column_mapping(config_user_record)
            
            # Check if user has search_all_worksheets enabled
            search_all_worksheets = get_user_field(config_user_record, 'settings.search_all_worksheets') or config_user_record.get('search_all_worksheets', True)  # Default to True
            
            # If search_all_worksheets is enabled, first build a lookup of all ASINs and their sources
            if search_all_worksheets:
                print(f"Building source lookup from all worksheets...")
                # Get all worksheet names
                metadata_url = f"https://sheets.googleapis.com/v4/spreadsheets/{user_sheet_id}"
                metadata_response = requests.get(metadata_url, headers=headers)
                metadata_response.raise_for_status()
                sheets_info = metadata_response.json().get("sheets", [])
                worksheet_names = [sheet["properties"]["title"] for sheet in sheets_info]
                
                # Search each worksheet for ASINs and sources
                for worksheet_name in worksheet_names:
                    try:
                        encoded_range = urllib.parse.quote(f"'{worksheet_name}'!A1:Z")
                        url = f"https://sheets.googleapis.com/v4/spreadsheets/{user_sheet_id}/values/{encoded_range}"
                        worksheet_response = requests.get(url, headers=headers)
                        worksheet_response.raise_for_status()
                        
                        worksheet_values = worksheet_response.json().get("values", [])
                        if worksheet_values and len(worksheet_values) > 1:
                            worksheet_headers = worksheet_values[0]
                            worksheet_rows = worksheet_values[1:]
                            
                            # Find ASIN and source columns
                            asin_col_idx = None
                            source_col_idx = None
                            
                            for idx, header in enumerate(worksheet_headers):
                                header_lower = header.lower()
                                # Find ASIN column - be more flexible
                                if 'asin' in header_lower and asin_col_idx is None:
                                    asin_col_idx = idx
                                # Also check exact match
                                elif header == 'ASIN' and asin_col_idx is None:
                                    asin_col_idx = idx
                                # Find source column (same logic as Smart Restock)
                                if any(keyword in header_lower for keyword in ['source', 'link', 'url', 'supplier', 'vendor', 'store']):
                                    if not any(skip_word in header_lower for skip_word in ['amazon', 'sell', 'listing']):
                                        source_col_idx = idx
                            
                            # Log which columns were found
                            if asin_col_idx is not None or source_col_idx is not None:
                                print(f"Worksheet {worksheet_name}: ASIN column index: {asin_col_idx}, Source column index: {source_col_idx}")
                                if asin_col_idx is not None:
                                    print(f"  ASIN column header: {worksheet_headers[asin_col_idx]}")
                                if source_col_idx is not None:
                                    print(f"  Source column header: {worksheet_headers[source_col_idx]}")
                            
                            # Build lookup
                            if asin_col_idx is not None and source_col_idx is not None:
                                for row in worksheet_rows:
                                    if len(row) > max(asin_col_idx, source_col_idx):
                                        asin = str(row[asin_col_idx]).strip().upper()
                                        source = str(row[source_col_idx]).strip()
                                        # More thorough check for valid ASIN and source
                                        if (asin and asin not in ['NAN', 'NONE', '', 'N/A', 'NULL'] and 
                                            source and source.lower() not in ['nan', 'none', '', 'n/a', 'null'] and
                                            len(source) > 0):
                                            # Store the source for this ASIN (overwrite if found in multiple places)
                                            # Add http:// if it looks like a domain without protocol
                                            if '.' in source and not source.startswith('http'):
                                                source = f'https://{source}'
                                            asin_to_source_lookup[asin] = source
                                            if len(asin_to_source_lookup) <= 5:  # Log first few
                                                print(f"Worksheet {worksheet_name}: Found source for ASIN {asin}: {source}")
                                            
                    except Exception as ws_error:
                        print(f"Error reading worksheet {worksheet_name}: {ws_error}")
                        continue
                
                print(f"Found sources for {len(asin_to_source_lookup)} ASINs across all worksheets")
            
            # Fetch data from user's main sheet
            # Properly encode worksheet title for URL
            encoded_range = urllib.parse.quote(f"'{user_worksheet_title}'!A1:Z")
            url = f"https://sheets.googleapis.com/v4/spreadsheets/{user_sheet_id}/values/{encoded_range}"
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            values = response.json().get("values", [])
            if not values or len(values) < 2:
                return jsonify({
                    'error': 'No leads found',
                    'message': 'Your leads sheet appears to be empty'
                }), 404
            
            headers_row = values[0]
            data_rows = values[1:]
            
            print(f"Found headers: {headers_row}")
            print(f"Processing {len(data_rows)} data rows")
            print(f"Column mapping: {column_mapping}")
            
            # Process each row
            for row_index, row in enumerate(data_rows):
                # Pad row to match headers length
                padded_row = row + [''] * (len(headers_row) - len(row))
                row_dict = dict(zip(headers_row, padded_row))
                
                # Extract ASIN, name, and source using column mapping
                asin = None
                name = None
                source = None
                
                # Column mapping maps logical names to actual column names
                # e.g., {"ASIN": "Product ASIN", "COGS": "Cost", etc.}
                
                # Get ASIN - use column mapping to find the right column
                asin_col = column_mapping.get('ASIN', 'ASIN')  # Default to 'ASIN' if not mapped
                if asin_col in row_dict:
                    asin = str(row_dict[asin_col]).strip().upper()
                else:
                    # Fallback: try common ASIN column names
                    for possible_asin_col in ['ASIN', 'asin', 'Asin', 'product_asin', 'Product ASIN']:
                        if possible_asin_col in row_dict:
                            potential_asin = str(row_dict[possible_asin_col]).strip().upper()
                            if potential_asin and potential_asin != 'NAN' and potential_asin != 'NONE':
                                asin = potential_asin
                                break
                
                # Get name - there's no standard mapping for name, so try common names
                name = None
                for possible_name_col in ['Name', 'name', 'Product Name', 'product_name', 'Title', 'title', 'Product Title', 'product_title', 'Description']:
                    if possible_name_col in row_dict:
                        potential_name = str(row_dict[possible_name_col]).strip()
                        if potential_name and potential_name != 'nan':
                            name = potential_name
                            break
                
                # Get source - look for source/link columns
                source = None
                source_col = None
                
                # Smart detection: Find source column like Smart Restock does
                for col in headers_row:
                    col_lower = col.lower()
                    if any(keyword in col_lower for keyword in ['source', 'link', 'url', 'supplier', 'vendor', 'store']):
                        # Skip Amazon-specific columns
                        if any(skip_word in col_lower for skip_word in ['amazon', 'sell', 'listing']):
                            continue
                        source_col = col
                        if row_index == 0:  # Log first time only
                            print(f"Detected source column: '{source_col}'")
                        break
                
                # Get source value from the detected column
                if source_col and source_col in row_dict:
                    raw_value = row_dict[source_col]
                    if row_index < 5:  # Debug first 5 rows
                        print(f"Row {row_index}: Raw source value: '{raw_value}' (type: {type(raw_value)})")
                    
                    potential_source = str(raw_value).strip() if raw_value else ''
                    # More thorough check for empty/invalid values
                    if (potential_source and 
                        potential_source.lower() not in ['nan', 'none', '', 'n/a', 'null'] and 
                        potential_source != 'None' and
                        len(potential_source) > 0):
                        # Accept any non-empty value, not just URLs starting with http
                        source = potential_source
                        # Add http:// if it looks like a domain without protocol
                        if '.' in source and not source.startswith('http'):
                            source = f'https://{source}'
                
                # If no source found in current row but we have search_all_worksheets enabled, 
                # check the lookup from other worksheets
                if not source and search_all_worksheets and asin:
                    if asin in asin_to_source_lookup:
                        source = asin_to_source_lookup[asin]
                        if row_index < 10:  # Debug first 10 rows
                            print(f"Row {row_index}: Found source from other worksheet for ASIN {asin}: '{source}'")
                    else:
                        if row_index < 10:  # Debug first 10 rows
                            print(f"Row {row_index}: ASIN {asin} not found in lookup. Available ASINs in lookup: {list(asin_to_source_lookup.keys())[:5]}...")
                
                # Get cost - use COGS mapping
                cost = ''
                cost_col = column_mapping.get('COGS', 'COGS')  # Default to 'COGS' if not mapped
                if cost_col in row_dict:
                    cost = str(row_dict[cost_col]).strip()
                
                if asin and asin not in ['NAN', 'NONE', '', 'N/A', 'NULL']:
                    # Ensure ASIN is clean and uppercase
                    clean_asin = asin.strip().upper()
                    user_leads.append({
                        'asin': clean_asin,
                        'name': name or '',
                        'source': source or '',
                        'cost': cost or ''
                    })
                    if row_index < 5:  # Log first 5 successful extractions
                        print(f"Row {row_index}: Found ASIN {clean_asin} with source '{source}'")
                else:
                    if row_index < 5:  # Log first 5 failed extractions
                        print(f"Row {row_index}: No valid ASIN found. Raw data: {row_dict}")
            
            print(f"Total leads found: {len(user_leads)}")
            
        except Exception as e:
            return jsonify({
                'error': 'Failed to fetch user leads',
                'message': f'Could not read from your leads sheet: {str(e)}'
            }), 500
        
        if not user_leads:
            return jsonify({
                'error': 'No valid leads found',
                'message': 'No leads with valid ASINs found in your sheet'
            }), 404
        
        # Target spreadsheet where we'll add missing leads
        target_sheet_id = '1Q5weSRaRd7r1zdiA2bwWwcWIwP6pxplGYmY7k9a3aqw'
        
        # Function to map source URL to worksheet name
        def get_worksheet_name_from_source(source_link):
            if not source_link:
                return None
            
            source_lower = source_link.lower()
            # Map to your existing worksheets
            if 'walmart.com' in source_lower:
                return 'Walmart - Flat'
            elif 'lowes.com' in source_lower:
                return 'Lowes - Flat'
            elif 'samsclub.com' in source_lower or 'sams club' in source_lower:
                return 'Sam\'s Club - Flat'
            elif 'kohls.com' in source_lower:
                return 'Kohls - Flat'
            elif 'keurig.com' in source_lower:
                return 'Keurig - Flat'
            elif 'jcpenney.com' in source_lower or 'jcp.com' in source_lower:
                return 'JC Penney - Flat'
            elif 'walgreens.com' in source_lower:
                return 'Walgreens'
            elif 'zoro.com' in source_lower:
                return 'Zoro - Flat'
            elif 'vitacost.com' in source_lower:
                return 'vitacost'
            elif 'swansonvitamins.com' in source_lower or 'swanson.com' in source_lower:
                return 'swanson'
            # Common ones that might need worksheets created
            elif 'amazon.com' in source_lower:
                return 'Amazon - Flat' 
            elif 'target.com' in source_lower:
                return 'Target - Flat'
            elif 'bestbuy.com' in source_lower:
                return 'Best Buy - Flat'
            elif 'homedepot.com' in source_lower:
                return 'Home Depot - Flat'
            elif 'costco.com' in source_lower:
                return 'Costco - Flat'
            elif 'bathandbodyworks.com' in source_lower or 'bbw' in source_lower:
                return 'BBW'
            elif 'crocs.com' in source_lower:
                return 'Crocs'
            elif 'yankeecandle.com' in source_lower:
                return 'Yankee Candles'
            # Generic "Misc" for unrecognized sources
            elif source_link and source_link.strip():
                # If there's a source but we don't recognize it, put it in Misc
                return 'Misc'
            # Only return None if there's truly no source
            return None
        
        # Get list of existing worksheets in target spreadsheet
        metadata_url = f"https://sheets.googleapis.com/v4/spreadsheets/{target_sheet_id}?fields=sheets.properties"
        metadata_response = requests.get(metadata_url, headers=headers)
        metadata_response.raise_for_status()
        sheets_info = metadata_response.json().get("sheets", [])
        existing_worksheets = [sheet["properties"]["title"] for sheet in sheets_info]
        
        sync_results = {
            'added': 0,
            'skipped': 0,
            'errors': 0,
            'already_existed': 0,
            'details': [],
            'debug_info': {
                'total_user_leads': len(user_leads),
                'existing_worksheets': existing_worksheets,
                'worksheet_not_found': [],
                'search_all_worksheets': search_all_worksheets,
                'sources_found_from_other_worksheets': len(asin_to_source_lookup) if search_all_worksheets else 0
            }
        }
        
        # Get all ASINs from all worksheets in target spreadsheet first
        all_existing_asins = {}  # worksheet_name -> set of ASINs
        
        for worksheet_name in existing_worksheets:
            try:
                # Properly encode worksheet title for URL
                encoded_range = urllib.parse.quote(f"'{worksheet_name}'!A1:Z")
                url = f"https://sheets.googleapis.com/v4/spreadsheets/{target_sheet_id}/values/{encoded_range}"
                response = requests.get(url, headers=headers)
                response.raise_for_status()
                
                values = response.json().get("values", [])
                if values and len(values) > 1:
                    headers_row = values[0]
                    existing_data = values[1:]
                    
                    # Find ASIN column - be more flexible with detection
                    asin_col_index = None
                    for i, header in enumerate(headers_row):
                        if 'ASIN' in header.upper():
                            asin_col_index = i
                            break
                    
                    if asin_col_index is not None:
                        worksheet_asins = set()
                        for row in existing_data:
                            if len(row) > asin_col_index:
                                asin = row[asin_col_index].strip().upper()
                                if asin and asin not in ['NAN', 'NONE', '', 'N/A', 'NULL']:
                                    worksheet_asins.add(asin)
                        all_existing_asins[worksheet_name] = worksheet_asins
                        print(f"Worksheet {worksheet_name}: Found {len(worksheet_asins)} existing ASINs")
                        if len(worksheet_asins) > 0 and len(worksheet_asins) <= 10:
                            print(f"  Sample ASINs: {list(worksheet_asins)[:5]}")
                    else:
                        all_existing_asins[worksheet_name] = set()
                        print(f"Worksheet {worksheet_name}: No ASIN column found in headers: {headers_row[:5]}...")
                else:
                    all_existing_asins[worksheet_name] = set()
            except Exception as e:
                print(f"Error reading worksheet {worksheet_name}: {e}")
                all_existing_asins[worksheet_name] = set()
        
        # Group user leads by target worksheet with deduplication
        leads_by_worksheet = {}
        no_source_leads = []  # Track leads without source URLs
        processed_asins_per_worksheet = {}  # Track ASINs we're about to add in this batch
        
        for lead in user_leads:
            target_worksheet = get_worksheet_name_from_source(lead.get('source'))
            
            if not target_worksheet:
                # No source URL - collect these separately
                no_source_leads.append(lead)
                if len(no_source_leads) <= 5:  # Debug first few
                    print(f"No source for ASIN {lead.get('asin')} - source value was: '{lead.get('source')}'")
                continue
            
            if target_worksheet not in existing_worksheets:
                sync_results['errors'] += 1
                sync_results['debug_info']['worksheet_not_found'].append({
                    'asin': lead.get('asin'),
                    'source': lead.get('source'),
                    'target_worksheet': target_worksheet
                })
                continue
            
            # Check if ASIN already exists in the target worksheet
            existing_asins_in_worksheet = all_existing_asins.get(target_worksheet, set())
            if lead['asin'] in existing_asins_in_worksheet:
                sync_results['already_existed'] += 1
                if sync_results['already_existed'] <= 5:  # Debug first few
                    print(f"ASIN {lead['asin']} already exists in {target_worksheet}")
                continue
            else:
                # Debug: Check why it's not finding the ASIN as existing
                if len(leads_by_worksheet.get(target_worksheet, [])) < 3:  # Debug first few per worksheet
                    print(f"ASIN {lead['asin']} NOT found in {target_worksheet}. Worksheet has {len(existing_asins_in_worksheet)} ASINs")
                    if len(existing_asins_in_worksheet) > 0:
                        # Check if there's a close match (case issue)
                        for existing_asin in list(existing_asins_in_worksheet)[:5]:
                            if existing_asin.lower() == lead['asin'].lower():
                                print(f"  WARNING: Case mismatch? Existing: '{existing_asin}' vs New: '{lead['asin']}'")
            
            # Initialize tracking for this worksheet if needed
            if target_worksheet not in processed_asins_per_worksheet:
                processed_asins_per_worksheet[target_worksheet] = set()
            
            # Check if we've already processed this ASIN for this worksheet in this batch
            if lead['asin'] in processed_asins_per_worksheet[target_worksheet]:
                sync_results['already_existed'] += 1
                continue
            
            # Track this ASIN as processed for this worksheet
            processed_asins_per_worksheet[target_worksheet].add(lead['asin'])
            
            if target_worksheet not in leads_by_worksheet:
                leads_by_worksheet[target_worksheet] = []
            
            leads_by_worksheet[target_worksheet].append(lead)
        
        # Handle leads without source URLs
        if no_source_leads:
            # Use the specified default worksheet or try to find one
            if default_worksheet_for_no_source in existing_worksheets:
                # Initialize tracking for default worksheet if needed
                if default_worksheet_for_no_source not in processed_asins_per_worksheet:
                    processed_asins_per_worksheet[default_worksheet_for_no_source] = set()
                
                # Add leads without sources to the default worksheet (with deduplication)
                for lead in no_source_leads:
                    # Check if already exists in target spreadsheet
                    if lead['asin'] in all_existing_asins.get(default_worksheet_for_no_source, set()):
                        sync_results['already_existed'] += 1
                        continue
                    
                    # Check if we've already processed this ASIN for this worksheet in this batch
                    if lead['asin'] in processed_asins_per_worksheet[default_worksheet_for_no_source]:
                        sync_results['already_existed'] += 1
                        continue
                    
                    # Track this ASIN as processed for this worksheet
                    processed_asins_per_worksheet[default_worksheet_for_no_source].add(lead['asin'])
                    
                    if default_worksheet_for_no_source not in leads_by_worksheet:
                        leads_by_worksheet[default_worksheet_for_no_source] = []
                    leads_by_worksheet[default_worksheet_for_no_source].append(lead)
            else:
                # Default worksheet doesn't exist - report these
                sync_results['no_source_count'] = len(no_source_leads)
                sync_results['no_source_worksheet_missing'] = True
                sync_results['suggested_worksheet'] = default_worksheet_for_no_source
                sync_results['debug_info']['no_source_leads'] = [
                    {'asin': lead.get('asin'), 'name': lead.get('name', '')} 
                    for lead in no_source_leads[:5]  # First 5 for debugging
                ]
        
        # Process each worksheet - add missing leads
        for worksheet_name, worksheet_leads in leads_by_worksheet.items():
            try:
                # Get existing data from worksheet to get the current row count
                # Properly encode worksheet title for URL
                encoded_range = urllib.parse.quote(f"'{worksheet_name}'!A1:Z")
                url = f"https://sheets.googleapis.com/v4/spreadsheets/{target_sheet_id}/values/{encoded_range}"
                response = requests.get(url, headers=headers)
                response.raise_for_status()
                
                values = response.json().get("values", [])
                if not values:
                    # Empty worksheet - add header
                    values = [['ASIN', 'Name', 'Source', 'Sell', 'Cost']]
                    # First add the header row
                    header_body = {'values': [['ASIN', 'Name', 'Source', 'Sell', 'Cost']]}
                    encoded_header_range = urllib.parse.quote(f"'{worksheet_name}'!A1:E1")
                    header_url = f"https://sheets.googleapis.com/v4/spreadsheets/{target_sheet_id}/values/{encoded_header_range}?valueInputOption=RAW"
                    requests.put(header_url, headers=headers, json=header_body)
                
                # Prepare new rows to add
                new_rows = []
                added_count = 0
                
                for lead in worksheet_leads:
                    # Prepare row data
                    asin = lead.get('asin', '')
                    name = lead.get('name', '')
                    source = lead.get('source', '')
                    sell = f"https://www.amazon.com/dp/{asin}"  # Amazon link
                    cost = lead.get('cost', '')  # Use cost from user's sheet if available
                    
                    new_rows.append([asin, name, source, sell, cost])
                    added_count += 1
                
                # Add new rows to spreadsheet if any
                if new_rows:
                    # Determine the range for new data
                    start_row = len(values) + 1  # Next available row
                    end_row = start_row + len(new_rows) - 1
                    range_ = f"'{worksheet_name}'!A{start_row}:E{end_row}"
                    
                    # Prepare the request body
                    body = {
                        'values': new_rows
                    }
                    
                    # Update the spreadsheet - properly encode the range
                    encoded_update_range = urllib.parse.quote(range_)
                    update_url = f"https://sheets.googleapis.com/v4/spreadsheets/{target_sheet_id}/values/{encoded_update_range}?valueInputOption=RAW"
                    update_response = requests.put(update_url, headers=headers, json=body)
                    update_response.raise_for_status()
                    
                    # Highlight the newly added rows with light green background
                    try:
                        # Get worksheet ID for formatting
                        metadata_response = requests.get(f"https://sheets.googleapis.com/v4/spreadsheets/{target_sheet_id}", headers=headers)
                        metadata_response.raise_for_status()
                        sheets_info = metadata_response.json().get("sheets", [])
                        
                        worksheet_id = None
                        for sheet in sheets_info:
                            if sheet["properties"]["title"] == worksheet_name:
                                worksheet_id = sheet["properties"]["sheetId"]
                                break
                        
                        if worksheet_id is not None:
                            # Prepare formatting request
                            format_requests = [{
                                "repeatCell": {
                                    "range": {
                                        "sheetId": worksheet_id,
                                        "startRowIndex": start_row - 1,  # 0-indexed
                                        "endRowIndex": end_row,  # 0-indexed, exclusive
                                        "startColumnIndex": 0,  # Column A
                                        "endColumnIndex": 5  # Up to column E
                                    },
                                    "cell": {
                                        "userEnteredFormat": {
                                            "backgroundColor": {
                                                "red": 1.0,     # Yellow background
                                                "green": 1.0,
                                                "blue": 0.6
                                            }
                                        }
                                    },
                                    "fields": "userEnteredFormat.backgroundColor"
                                }
                            }]
                            
                            # Apply formatting
                            format_body = {"requests": format_requests}
                            format_url = f"https://sheets.googleapis.com/v4/spreadsheets/{target_sheet_id}:batchUpdate"
                            format_response = requests.post(format_url, headers=headers, json=format_body)
                            format_response.raise_for_status()
                            
                    except Exception as format_error:
                        print(f"Warning: Failed to highlight rows in {worksheet_name}: {format_error}")
                        # Continue without failing the entire sync if highlighting fails
                
                sync_results['added'] += added_count
                
                if added_count > 0:
                    sync_results['details'].append({
                        'worksheet': worksheet_name,
                        'count': added_count,
                        'highlighted': True
                    })
                
            except Exception as e:
                print(f"Error processing worksheet {worksheet_name}: {e}")
                sync_results['errors'] += len(worksheet_leads)
                continue
        
        return jsonify(sync_results)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Error syncing leads to sheets: {str(e)}'}), 500

def fetch_discount_email_alerts():
    """Fetch recent email alerts from admin-configured email using IMAP or Gmail API"""
    try:
        # Get email configuration from S3 (single source of truth)
        admin_gmail_config = get_discount_email_config()
        
        if admin_gmail_config and admin_gmail_config.get('email_address'):
            # Check configuration type
            config_type = admin_gmail_config.get('config_type', 'gmail_oauth')
            if config_type == 'imap':
                return fetch_discount_alerts_from_imap(admin_gmail_config)
            else:  # gmail_oauth
                return fetch_discount_alerts_from_gmail_api(admin_gmail_config)
        
        else:
            # No discount email configuration found - return mock data
            return fetch_mock_discount_alerts()
    
    except Exception as e:
        print(f"Error fetching discount email alerts: {e}")
        return fetch_mock_discount_alerts()

def fetch_discount_alerts_from_imap(email_config):
    """Fetch discount alerts using IMAP configuration"""
    try:
        import imaplib
        import email
        from datetime import datetime, timedelta
        import pytz
        
        # Decrypt password
        password = email_cipher.decrypt(email_config['password_encrypted'].encode()).decode()
        
        # Connect to IMAP server
        mail = imaplib.IMAP4_SSL(email_config['imap_server'], email_config['imap_port'])
        mail.login(email_config['username'], password)
        mail.select('inbox')
        
        # Search for discount-related emails from the last few days
        days_back = get_discount_email_days_back()
        cutoff_date = (datetime.now() - timedelta(days=days_back)).strftime('%d-%b-%Y')
        
        # Search for emails from discount sender or with discount-related subjects
        sender_query = f'FROM "{DISCOUNT_SENDER_EMAIL}"' if DISCOUNT_SENDER_EMAIL else ''
        subject_query = 'OR SUBJECT "discount" OR SUBJECT "clearance" OR SUBJECT "sale" OR SUBJECT "alert"'
        date_query = f'SINCE "{cutoff_date}"'
        
        search_query = f'{sender_query} {subject_query} {date_query}' if sender_query else f'{subject_query} {date_query}'
        
        
        result, messages = mail.search(None, search_query.strip())
        
        if result != 'OK' or not messages[0]:
            mail.logout()
            return fetch_mock_discount_alerts()
        
        email_ids = messages[0].split()
        alerts = []
        
        # Process the most recent emails (limit to 50 for performance)
        for email_id in email_ids[-50:]:
            try:
                result, msg_data = mail.fetch(email_id, '(RFC822)')
                if result != 'OK':
                    continue
                
                email_msg = email.message_from_bytes(msg_data[0][1])
                
                # Extract email details
                subject = email_msg.get('Subject', '')
                sender = email_msg.get('From', '')
                date_received = email_msg.get('Date', '')
                
                # Get email body
                html_content = ""
                if email_msg.is_multipart():
                    for part in email_msg.walk():
                        if part.get_content_type() == "text/html":
                            charset = part.get_content_charset() or 'utf-8'
                            html_content = part.get_payload(decode=True).decode(charset, errors='ignore')
                            break
                        elif part.get_content_type() == "text/plain" and not html_content:
                            charset = part.get_content_charset() or 'utf-8'
                            plain_content = part.get_payload(decode=True).decode(charset, errors='ignore')
                            html_content = f"<div>{plain_content}</div>"
                else:
                    charset = email_msg.get_content_charset() or 'utf-8'
                    content = email_msg.get_payload(decode=True).decode(charset, errors='ignore')
                    html_content = f"<div>{content}</div>"
                
                # Extract ASIN from subject or content
                import re
                asin_match = re.search(r'B[0-9A-Z]{9}', subject + ' ' + html_content)
                asin = asin_match.group() if asin_match else f'UNKNOWN_{len(alerts)}'
                
                # Determine retailer from sender or subject
                retailer = 'Unknown'
                sender_lower = sender.lower()
                subject_lower = subject.lower()
                
                if 'vitacost' in sender_lower or 'vitacost' in subject_lower:
                    retailer = 'Vitacost'
                elif 'walmart' in sender_lower or 'walmart' in subject_lower:
                    retailer = 'Walmart'
                elif 'amazon' in sender_lower or 'amazon' in subject_lower:
                    retailer = 'Amazon'
                elif 'target' in sender_lower or 'target' in subject_lower:
                    retailer = 'Target'
                
                alerts.append({
                    'retailer': retailer,
                    'asin': asin,
                    'subject': subject,
                    'html_content': html_content,
                    'alert_time': date_received,
                    'sender': sender
                })
                
            except Exception as e:
                continue
        
        mail.logout()
        
        return alerts if alerts else fetch_mock_discount_alerts()
        
    except Exception as e:
        return fetch_mock_discount_alerts()

def is_valid_asin(asin):
    """Validate if a string is a proper Amazon ASIN format"""
    import re
    if not asin or len(asin) != 10:
        return False
    
    # Must start with B followed by 9 alphanumeric characters  
    if not re.match(r'^B[0-9A-Z]{9}$', asin):
        return False
        
    # Additional validation - avoid common false positives
    false_positives = [
        'BXT5V5XPNW',  # Seen in Stumptown coffee emails
        'BOOPSS7GDF',  # Another false positive pattern
        'BJZN9KFZ3K',  # Another false positive pattern  
        'BGFZD1HP12',  # Another false positive pattern
    ]
    
    if asin in false_positives:
        return False
        
    return True

def fetch_discount_alerts_from_gmail_api(gmail_config):
    """Fetch discount alerts using Gmail API configuration"""
    try:
        
        # Create a mock user record for API calls
        user_record = {
            'google_tokens': gmail_config.get('tokens', {})
        }
        
        # Search for discount-related emails from the last few days
        days_back = get_discount_email_days_back()
        from datetime import datetime, timedelta
        
        # Get email format configuration from S3-based discount config 
        discount_config = get_discount_email_config()
        sender_filter = discount_config.get('sender_filter', 'alert@distill.io') if discount_config else 'alert@distill.io'
        
        # Build search query using configurable sender filter
        query = f'from:{sender_filter}'
        
        # Add date filter
        cutoff_date = datetime.now() - timedelta(days=days_back)
        query += f' after:{cutoff_date.strftime("%Y/%m/%d")}'
        
        # Search for messages - increase limit to ensure we get all recent emails
        messages = search_gmail_messages(user_record, query, max_results=500)
        
        if not messages or not messages.get('messages'):
            return fetch_mock_discount_alerts()
        
        alerts = []
        
        
        # Process each message
        for i, message in enumerate(messages['messages']):  # Process all messages
            try:
                message_id = message['id']
                email_data = get_gmail_message(user_record, message_id)
                
                if not email_data:
                    continue
                
                # Extract email details
                headers = {h['name']: h['value'] for h in email_data.get('payload', {}).get('headers', [])}
                subject = headers.get('Subject', '')
                sender = headers.get('From', '')
                date_received = headers.get('Date', '')
                
                # Debug log each email being processed
                
                
                # Get email body
                html_content = ""
                payload = email_data.get('payload', {})
                
                def extract_html_from_payload(payload):
                    if payload.get('mimeType') == 'text/html':
                        data = payload.get('body', {}).get('data', '')
                        if data:
                            import base64
                            return base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                    
                    if payload.get('mimeType') == 'text/plain' and not html_content:
                        data = payload.get('body', {}).get('data', '')
                        if data:
                            import base64
                            plain_text = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                            return f"<div>{plain_text}</div>"
                    
                    # Check multipart messages
                    for part in payload.get('parts', []):
                        result = extract_html_from_payload(part)
                        if result:
                            return result
                    
                    return None
                
                html_content = extract_html_from_payload(payload) or "<div>No content</div>"
                
                # Extract ASIN from subject or content
                import re
                
                
                # Extract ASIN using configurable pattern from admin settings
                asin = None
                
                # Get custom patterns from discount config (S3-based) - use flexible pattern as default
                asin_pattern = discount_config.get('asin_pattern', r'\b(B[0-9A-Z]{9})\b') if discount_config else r'\b(B[0-9A-Z]{9})\b'
                
                # Extract ASIN from subject line using custom pattern
                asin_match = re.search(asin_pattern, subject, re.IGNORECASE)
                
                if asin_match:
                    potential_asin = asin_match.group(1)
                    if is_valid_asin(potential_asin):
                        asin = potential_asin
                
                # Fallback: try to find ASIN in email content
                if not asin:
                    content_patterns = [
                        r'\b(B[0-9A-Z]{9})\b',  # Any ASIN with word boundaries
                        r'\(ASIN:\s*([B0-9A-Z]{10})\)',  # (ASIN: B123456789)
                        r'amazon\.com/[^/]*/dp/([B0-9A-Z]{10})',  # Amazon URL
                        r'ASIN[:\s]*([B0-9A-Z]{10})',  # ASIN: B123456789
                    ]
                    
                    for pattern in content_patterns:
                        content_match = re.search(pattern, html_content, re.IGNORECASE)
                        if content_match:
                            potential_asin = content_match.group(1)
                            if is_valid_asin(potential_asin):
                                asin = potential_asin
                                break
                
                # Skip emails without valid ASINs (not discount opportunities)
                if not asin:
                    continue
                
                # Extract retailer using configurable pattern from admin settings
                retailer = 'Unknown'
                
                # Get custom retailer pattern from discount config (S3-based)
                retailer_pattern = discount_config.get('retailer_pattern', r'\[([^\]]+)\]\s*Alert:') if discount_config else r'\[([^\]]+)\]\s*Alert:'
                retailer_match = re.search(retailer_pattern, subject, re.IGNORECASE)
                
                if retailer_match:
                    retailer = retailer_match.group(1).strip()
                else:
                    # Fallback: check sender and subject for retailer keywords
                    sender_lower = sender.lower()
                    subject_lower = subject.lower()
                    
                    retailers_map = {
                        'vitacost': 'Vitacost',
                        'walmart': 'Walmart',
                        'target': 'Target',
                        'amazon': 'Amazon',
                        'costco': 'Costco',
                        'lowes': 'Lowes',
                        'lowe': 'Lowes'
                    }
                    
                    for key, name in retailers_map.items():
                        if key in sender_lower or key in subject_lower:
                            retailer = name
                            break
                
                # Convert Gmail date to ISO format
                alert_time = convert_gmail_date_to_iso(date_received)
                
                alert = {
                    'retailer': retailer,
                    'asin': asin,
                    'subject': subject,
                    'html_content': html_content,
                    'alert_time': alert_time
                }
                
                alerts.append(alert)
                
                
            except Exception as e:
                continue
        
        return alerts if alerts else fetch_mock_discount_alerts()
        
    except Exception as e:
        print(f"Error fetching Gmail API alerts: {e}")
        return fetch_mock_discount_alerts()

def fetch_mock_discount_alerts():
    """Return mock discount alerts for testing"""
    return [
        {
            'retailer': 'Vitacost',
            'asin': 'B07XVTRJKX',
            'subject': 'Vitacost (ASIN: B07XVTRJKX)',
            'html_content': '''<div>Price alert for product B07XVTRJKX</div>
                           <div id="m_731648639157524744topPromoMessages">== $10 off orders $50+ ==</div>
                           <a href="https://vitacost.com/product">View Product</a>''',
            'alert_time': '2025-08-09T19:53:00Z'
        },
        {
            'retailer': 'Walmart', 
            'asin': 'B07D83HV1M',
            'subject': 'Walmart (ASIN: B07D83HV1M) (Note: Amazon is two pack)',
            'html_content': '''<div>Discount available for B07D83HV1M</div>
                           <p>Special promotion: 20% off</p>''',
            'alert_time': '2025-08-09T18:30:00Z'
        }
    ]

def convert_gmail_date_to_iso(gmail_date):
    """Convert Gmail date string to ISO format"""
    try:
        from email.utils import parsedate_to_datetime
        if gmail_date:
            dt = parsedate_to_datetime(gmail_date)
            return dt.isoformat()
        else:
            # Default to current time if no date
            from datetime import datetime
            import pytz
            return datetime.now(pytz.UTC).isoformat()
    except Exception as e:
        print(f"Error converting Gmail date: {e}")
        from datetime import datetime
        import pytz
        return datetime.now(pytz.UTC).isoformat()

def parse_email_subject(subject):
    """Parse email subject to extract retailer, ASIN, and notes
    
    Handles formats like:
    - [Walmart] Alert: Walmart (ASIN: B00F3DCZ6Q) (Note: Locally)
    - [Lowes] Alert: Lowes (ASIN: B00TW2XZ04) (Note: TESTING)
    """
    import re
    
    # Primary pattern for new format: [Retailer] Alert: Retailer (ASIN: XXXXXXXXXX) (Note: ...)
    # Example: [Walmart] Alert: Walmart (ASIN: B00F3DCZ6Q) (Note: Locally)
    new_format_pattern = r'\[([^\]]+)\]\s*Alert:\s*[^(]*\(ASIN:\s*([B-Z][0-9A-Z]{9})\)(?:\s*\(Note:\s*([^)]+)\))?'
    
    match = re.search(new_format_pattern, subject, re.IGNORECASE)
    if match:
        retailer_bracket, asin, note = match.groups()
        return {
            'retailer': retailer_bracket.strip(),
            'asin': asin.strip(),
            'note': note.strip() if note else None
        }
    
    # Legacy pattern: Retailer (ASIN: XXXXXXXXXX) (Note: additional info)
    # Example: Walmart (ASIN: B07D83HV1M) (Note: Amazon is two pack)
    legacy_pattern = r'([A-Za-z]+)\s*\(ASIN:\s*([B-Z][0-9A-Z]{9})\)(?:\s*\(Note:\s*([^)]+)\))?'
    match = re.search(legacy_pattern, subject)
    
    if match:
        retailer, asin, note = match.groups()
        return {
            'retailer': retailer.strip(),
            'asin': asin.strip(),
            'note': note.strip() if note else None
        }
    
    # Fallback patterns for other email formats
    patterns = [
        r'.*?([A-Za-z]+).*?([B-Z][0-9A-Z]{9})',  # Retailer followed by ASIN
        r'.*?([B-Z][0-9A-Z]{9}).*?([A-Za-z]+)',  # ASIN followed by retailer
        r'([A-Za-z]+)\s*-\s*([B-Z][0-9A-Z]{9})', # Retailer - ASIN
        r'([B-Z][0-9A-Z]{9})\s*-\s*([A-Za-z]+)', # ASIN - Retailer
    ]
    
    retailers = ['vitacost', 'walmart', 'target', 'amazon', 'costco', 'sam', 'lowes', 'lowe']
    
    for pattern in patterns:
        match = re.search(pattern, subject, re.IGNORECASE)
        if match:
            part1, part2 = match.groups()
            
            # Check which part is the retailer
            if any(retailer in part1.lower() for retailer in retailers):
                return {
                    'retailer': part1.strip(),
                    'asin': part2.strip(),
                    'note': None
                }
            elif any(retailer in part2.lower() for retailer in retailers):
                return {
                    'retailer': part2.strip(),
                    'asin': part1.strip(),
                    'note': None
                }
            elif re.match(r'^[B-Z][0-9A-Z]{9}$', part1.strip()):
                return {
                    'retailer': part2.strip(),
                    'asin': part1.strip(),
                    'note': None
                }
            elif re.match(r'^[B-Z][0-9A-Z]{9}$', part2.strip()):
                return {
                    'retailer': part1.strip(),
                    'asin': part2.strip(),
                    'note': None
                }
    
    return None

def extract_vitacost_promo_message(html_content):
    """Extract promotional message from Vitacost HTML containing topPromoMessages"""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Look for divs containing topPromoMessages
        promo_divs = soup.find_all('div', id=lambda x: x and 'topPromoMessages' in x)
        
        if promo_divs:
            promo_text = promo_divs[0].get_text(strip=True)
            return promo_text
        
        # Fallback: look for any div containing promotional text patterns
        for div in soup.find_all('div'):
            text = div.get_text(strip=True)
            if any(keyword in text.lower() for keyword in ['$', 'off', 'free shipping', 'promo', 'sale', '%']):
                return text
                
    except ImportError:
        # BeautifulSoup not available, use basic regex
        import re
        # Look for content between topPromoMessages div tags
        pattern = r'<div[^>]*topPromoMessages[^>]*>(.*?)</div>'
        match = re.search(pattern, html_content, re.DOTALL | re.IGNORECASE)
        if match:
            # Clean up HTML tags
            clean_text = re.sub(r'<[^>]+>', '', match.group(1))
            return clean_text.strip()
    except Exception:
        pass
    
    return None

def calculate_opportunity_priority(inventory_data, days_left, suggested_quantity):
    """Calculate priority score for discount opportunities"""
    score = 0
    
    # Higher priority for products that need restocking soon
    if days_left is not None:
        if days_left < 7:
            score += 100
        elif days_left < 14:
            score += 50
        elif days_left < 30:
            score += 25
    
    # Higher priority for products with high suggested quantities
    if suggested_quantity > 100:
        score += 50
    elif suggested_quantity > 50:
        score += 25
    elif suggested_quantity > 0:
        score += 10
    
    # Higher priority for high-velocity products
    velocity = inventory_data.get('velocity', {}).get('weighted_velocity', 0)
    if velocity > 5:
        score += 30
    elif velocity > 2:
        score += 15
    elif velocity > 1:
        score += 5
    
    # Higher priority for products with existing priority flags
    priority_category = inventory_data.get('priority', {}).get('category', '')
    if 'critical' in priority_category:
        score += 75
    elif 'warning' in priority_category:
        score += 40
    elif 'opportunity' in priority_category:
        score += 20
    
    return score

@app.route('/api/discount-opportunities/debug', methods=['GET'])
@admin_required
def debug_discount_opportunities():
    """Debug endpoint to troubleshoot email configuration and search"""
    try:
        debug_info = {
            'config': {
                'monitor_email': DISCOUNT_MONITOR_EMAIL,
                'sender_email': DISCOUNT_SENDER_EMAIL,
                'days_back': get_discount_email_days_back(),
                'demo_mode': DEMO_MODE
            },
            'gmail_access': None,
            'search_results': None,
            'parsing_test': None
        }
        
        # Check Gmail access
        if DISCOUNT_MONITOR_EMAIL:
            users = get_users_config()
            admin_user = None
            for user in users:
                if get_user_field(user, 'identity.email') == DISCOUNT_MONITOR_EMAIL:
                    admin_user = user
                    break
            
            if admin_user:
                debug_info['gmail_access'] = {
                    'user_found': True,
                    'has_google_tokens': bool(get_user_field(admin_user, 'integrations.google.tokens')),
                    'google_linked': admin_user.get('google_linked', False),
                    'tokens_keys': list((get_user_field(admin_user, 'integrations.google.tokens') or {}).keys()) if get_user_field(admin_user, 'integrations.google.tokens') else []
                }
                
                # Try Gmail search
                if get_user_field(admin_user, 'integrations.google.tokens'):
                    try:
                        from datetime import datetime, timedelta
                        import pytz
                        
                        # Test Gmail API access
                        cutoff_date = datetime.now(pytz.UTC) - timedelta(days=get_discount_email_days_back())
                        date_str = cutoff_date.strftime('%Y/%m/%d')
                        query = f'from:{DISCOUNT_SENDER_EMAIL} after:{date_str}'
                        
                        # Get Gmail service
                        access_token = refresh_google_token(admin_user)
                        
                        if access_token:
                            headers = {"Authorization": f"Bearer {access_token}"}
                            gmail_url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages?q={query}&maxResults=50"
                            
                            import requests
                            response = requests.get(gmail_url, headers=headers, timeout=30)
                            
                            if response.status_code == 200:
                                gmail_data = response.json()
                                message_count = len(gmail_data.get('messages', []))
                                
                                debug_info['search_results'] = {
                                    'query': query,
                                    'status_code': response.status_code,
                                    'message_count': message_count,
                                    'total_size_estimate': gmail_data.get('resultSizeEstimate', 0)
                                }
                                
                                # Get details of first few messages for debugging
                                if message_count > 0:
                                    sample_messages = []
                                    for msg in gmail_data.get('messages', [])[:3]:  # Get first 3 messages
                                        msg_url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg['id']}"
                                        msg_response = requests.get(msg_url, headers=headers, timeout=30)
                                        if msg_response.status_code == 200:
                                            msg_data = msg_response.json()
                                            
                                            # Extract subject and sender
                                            headers_data = msg_data.get('payload', {}).get('headers', [])
                                            subject = next((h['value'] for h in headers_data if h['name'].lower() == 'subject'), 'No subject')
                                            sender = next((h['value'] for h in headers_data if h['name'].lower() == 'from'), 'No sender')
                                            date = next((h['value'] for h in headers_data if h['name'].lower() == 'date'), 'No date')
                                            
                                            # Test parsing
                                            parsed = parse_email_subject(subject)
                                            
                                            sample_messages.append({
                                                'id': msg['id'],
                                                'subject': subject,
                                                'sender': sender,
                                                'date': date,
                                                'parsed_result': parsed
                                            })
                                    
                                    debug_info['search_results']['sample_messages'] = sample_messages
                            else:
                                debug_info['search_results'] = {
                                    'query': query,
                                    'status_code': response.status_code,
                                    'error': response.text
                                }
                        else:
                            debug_info['search_results'] = {'error': 'Failed to get access token'}
                            
                    except Exception as e:
                        import traceback
                        debug_info['search_results'] = {
                            'error': str(e),
                            'traceback': traceback.format_exc()
                        }
            else:
                debug_info['gmail_access'] = {
                    'user_found': False,
                    'error': f'No user found with email {DISCOUNT_MONITOR_EMAIL}'
                }
        else:
            debug_info['gmail_access'] = {'error': 'DISCOUNT_MONITOR_EMAIL not configured'}
        
        # Test parsing with your example subjects
        test_subjects = [
            '[Walmart] Alert: Walmart (ASIN: B00F3DCZ6Q) (Note: Locally)',
            '[Lowes] Alert: Lowes (ASIN: B00TW2XZ04) (Note: TESTING)',
            'Walmart (ASIN: B00F3DCZ6Q) (Note: Locally)',  # Legacy format
            'Price Alert from Distill.io'  # Non-matching format
        ]
        
        debug_info['parsing_test'] = []
        for subject in test_subjects:
            result = parse_email_subject(subject)
            debug_info['parsing_test'].append({
                'subject': subject,
                'parsed': result
            })
        
        return jsonify(debug_info)
        
    except Exception as e:
        import traceback
        return jsonify({
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

@app.route('/api/admin/discount-monitoring/status', methods=['GET'])
@admin_required
def get_discount_monitoring_status():
    """Get discount monitoring configuration status (Admin only)"""
    try:
        # Check if admin user has Gmail access configured
        gmail_configured = False
        admin_user_record = None
        
        if DISCOUNT_MONITOR_EMAIL:
            users = get_users_config()
            for user in users:
                if get_user_field(user, 'identity.email') == DISCOUNT_MONITOR_EMAIL and get_user_field(user, 'integrations.google.tokens'):
                    admin_user_record = user
                    gmail_configured = True
                    break
        
        # Get current config settings
        discount_config = get_discount_monitoring_config()
        
        # Determine overall status
        if gmail_configured and DISCOUNT_MONITOR_EMAIL:
            status = 'active'
        elif DISCOUNT_MONITOR_EMAIL and not gmail_configured:
            status = 'gmail_not_configured'
        else:
            status = 'not_configured'
        
        return jsonify({
            'email_configured': bool(DISCOUNT_MONITOR_EMAIL),
            'gmail_configured': gmail_configured,
            'monitor_email': DISCOUNT_MONITOR_EMAIL if DISCOUNT_MONITOR_EMAIL else None,
            'sender_email': DISCOUNT_SENDER_EMAIL,
            'days_back': discount_config.get('days_back', 7),
            'config_last_updated': discount_config.get('last_updated'),
            'status': status,
            'status_details': {
                'email_set': bool(DISCOUNT_MONITOR_EMAIL),
                'gmail_linked': gmail_configured,
                'ready_to_fetch': gmail_configured and bool(DISCOUNT_MONITOR_EMAIL)
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/discount-monitoring/test', methods=['POST'])
@admin_required  
def test_discount_monitoring():
    """Test discount monitoring setup including Gmail API access (Admin only)"""
    try:
        if not DISCOUNT_MONITOR_EMAIL:
            return jsonify({
                'success': False,
                'error': 'Discount monitor email not configured'
            }), 400
        
        # Find admin user record
        admin_user_record = None
        users = get_users_config()
        for user in users:
            if get_user_field(user, 'identity.email') == DISCOUNT_MONITOR_EMAIL and get_user_field(user, 'integrations.google.tokens'):
                admin_user_record = user
                break
        
        if not admin_user_record:
            return jsonify({
                'success': False,
                'error': f'Admin user {DISCOUNT_MONITOR_EMAIL} not found or Gmail not linked'
            }), 400
        
        # Test Gmail API access by searching for recent messages
        try:
            # Simple test query for recent messages
            test_query = f'from:{DISCOUNT_SENDER_EMAIL}'
            search_results = search_gmail_messages(admin_user_record, test_query, max_results=5)
            
            if search_results:
                message_count = len(search_results.get('messages', []))
                return jsonify({
                    'success': True,
                    'message': f'Gmail API test successful! Found {message_count} recent messages from {DISCOUNT_SENDER_EMAIL}',
                    'details': {
                        'monitor_email': DISCOUNT_MONITOR_EMAIL,
                        'sender_email': DISCOUNT_SENDER_EMAIL,
                        'days_back': get_discount_email_days_back(),
                        'test_message_count': message_count
                    }
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Gmail API test failed - no search results returned'
                }), 500
                
        except Exception as gmail_error:
            return jsonify({
                'success': False,
                'error': f'Gmail API test failed: {str(gmail_error)}'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False, 
            'error': str(e)
        }), 500

@app.route('/api/admin/discount-monitoring/settings', methods=['PUT'])
@admin_required
def update_discount_monitoring_settings():
    """Update discount monitoring settings (Admin only)"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Request body required'}), 400
        
        # Get current config
        current_config = get_discount_monitoring_config()
        
        # Update days_back if provided
        days_back = data.get('days_back')
        if days_back is not None:
            try:
                days_back = int(days_back)
                if days_back < 1 or days_back > 30:
                    return jsonify({'error': 'days_back must be between 1 and 30'}), 400
                current_config['days_back'] = days_back
            except (ValueError, TypeError):
                return jsonify({'error': 'days_back must be a valid integer'}), 400
        
        # Update enabled status if provided
        enabled = data.get('enabled')
        if enabled is not None:
            current_config['enabled'] = bool(enabled)
        
        # Save updated config
        if update_discount_monitoring_config(current_config):
            return jsonify({
                'success': True,
                'message': 'Discount monitoring settings updated successfully',
                'settings': current_config
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to save settings'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/admin/discount-monitoring/settings', methods=['GET'])
@admin_required
def get_discount_monitoring_settings():
    """Get current discount monitoring settings (Admin only)"""
    try:
        config = get_discount_monitoring_config()
        return jsonify({
            'success': True,
            'settings': config
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/test-discount-email', methods=['GET'])
@login_required
def test_discount_email_endpoint():
    """Test endpoint to diagnose discount email configuration"""
    import os
    from datetime import datetime, timedelta
    
    results = {
        'environment': {
            'DISCOUNT_MONITOR_EMAIL': os.getenv('DISCOUNT_MONITOR_EMAIL', 'Not Set'),
            'DISCOUNT_SENDER_EMAIL': os.getenv('DISCOUNT_SENDER_EMAIL', 'Not Set'),
            'DISCOUNT_EMAIL_DAYS_BACK': os.getenv('DISCOUNT_EMAIL_DAYS_BACK', '7')
        },
        'checks': []
    }
    
    # Check environment variables
    monitor_email = os.getenv('DISCOUNT_MONITOR_EMAIL')
    if not monitor_email:
        results['checks'].append({
            'check': 'Environment Variable',
            'status': 'FAIL',
            'message': 'DISCOUNT_MONITOR_EMAIL not set in Railway'
        })
        return jsonify(results), 200
    
    results['checks'].append({
        'check': 'Environment Variable',
        'status': 'PASS',
        'message': f"Monitor email: {monitor_email}"
    })
    
    # Check if user exists
    users = get_users_config()
    user_found = False
    user_has_tokens = False
    
    for user in users:
        if get_user_field(user, 'identity.email') == monitor_email:
            user_found = True
            user_has_tokens = bool(get_user_field(user, 'integrations.google.tokens'))
            results['user_info'] = {
                'discord_id': get_user_field(user, 'identity.discord_id'),
                'has_google_tokens': user_has_tokens,
                'google_linked': user.get('google_linked', False)
            }
            break
    
    if user_found:
        results['checks'].append({
            'check': 'User Exists',
            'status': 'PASS',
            'message': f"User found with email {monitor_email}"
        })
        
        if user_has_tokens:
            results['checks'].append({
                'check': 'Gmail Tokens',
                'status': 'PASS',
                'message': 'User has Gmail tokens'
            })
        else:
            results['checks'].append({
                'check': 'Gmail Tokens',
                'status': 'FAIL',
                'message': 'User does NOT have Gmail tokens - need to link Gmail in Settings'
            })
    else:
        results['checks'].append({
            'check': 'User Exists',
            'status': 'FAIL',
            'message': f"No user found with email {monitor_email}"
        })
        # Show available emails (masked for privacy)
        results['available_users'] = [
            f"{email[:3]}***{email[-10:]}" if email and len(email) > 13 else email
            for email in [get_user_field(u, 'identity.email') or 'No email' for u in users]
        ]
    
    return jsonify(results), 200


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({'error': 'Not found', 'path': request.path}), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    return jsonify({'error': 'Internal server error'}), 500

# Product image caching and queue system
product_image_cache = {}
IMAGE_CACHE_EXPIRY_HOURS = 24
image_queue = []
queue_lock = threading.Lock()
queue_worker_running = False
last_amazon_request_time = 0
MIN_REQUEST_INTERVAL = 1.5  # Balanced interval - 1.5 seconds between requests

import time
import random
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

# Create a persistent session for Amazon requests with better anti-detection
amazon_session = None
session_last_used = 0
SESSION_TIMEOUT = 900  # 15 minutes

def get_amazon_session():
    """Get or create a persistent Amazon session with anti-detection measures"""
    global amazon_session, session_last_used
    
    current_time = time.time()
    
    # Create new session if doesn't exist or is too old
    if not amazon_session or (current_time - session_last_used) > SESSION_TIMEOUT:
        amazon_session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        amazon_session.mount("http://", adapter)
        amazon_session.mount("https://", adapter)
        
        # Set realistic browser headers that rotate
        user_agents = [
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0'
        ]
        
        selected_ua = random.choice(user_agents)
        
        # More realistic browser headers
        amazon_session.headers.update({
            'User-Agent': selected_ua,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
            'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"macOS"'
        })
        
        # Set a realistic referrer pattern
        amazon_session.headers['Referer'] = 'https://www.amazon.com/'
        
        print(f"Created new Amazon session with UA: {selected_ua[:50]}...")
    
    session_last_used = current_time
    return amazon_session

def rate_limit_amazon_request():
    """Ensure we don't make requests too frequently to Amazon"""
    global last_amazon_request_time
    current_time = time.time()
    time_since_last = current_time - last_amazon_request_time
    
    if time_since_last < MIN_REQUEST_INTERVAL:
        sleep_time = MIN_REQUEST_INTERVAL - time_since_last + random.uniform(0.2, 0.8)
        time.sleep(sleep_time)
    
    last_amazon_request_time = time.time()

def fetch_amazon_page_with_retry(asin, max_retries=2):
    """Fetch Amazon page with sophisticated anti-detection and retry logic"""
    
    for attempt in range(max_retries):
        try:
            # Rate limiting with random jitter
            rate_limit_amazon_request()
            
            # Get fresh session with rotating headers
            session = get_amazon_session()
            
            # Add random delay to simulate human behavior
            if attempt > 0:
                human_delay = random.uniform(2, 6)
                print(f"Human-like delay: {human_delay:.1f}s before retry {attempt + 1}")
                time.sleep(human_delay)
            
            # Try different URL patterns to avoid detection
            urls_to_try = [
                f'https://www.amazon.com/dp/{asin}',
                f'https://www.amazon.com/gp/product/{asin}',
                f'https://amazon.com/dp/{asin}'
            ]
            
            url = urls_to_try[attempt % len(urls_to_try)]
            print(f"Attempting {url} (attempt {attempt + 1})")
            
            # Update referrer to look more natural
            if attempt > 0:
                session.headers['Referer'] = f'https://www.amazon.com/s?k={asin}'
            
            response = session.get(url, timeout=20)
            
            # Enhanced detection of blocking
            if response.status_code == 503:
                print(f"Amazon returned 503 for {asin} - service unavailable")
                if attempt < max_retries - 1:
                    time.sleep(3 ** attempt + random.uniform(2, 5))
                    continue
                return None
            
            if response.status_code == 429:
                print(f"Rate limited by Amazon for {asin}")
                if attempt < max_retries - 1:
                    time.sleep(5 + random.uniform(3, 8))
                    continue
                return None
            
            if response.status_code == 404:
                print(f"Product {asin} not found on Amazon")
                return None
            
            if response.status_code != 200:
                print(f"Amazon returned status {response.status_code} for {asin}")
                if attempt < max_retries - 1:
                    time.sleep(2 + random.uniform(1, 3))
                    continue
                return None
            
            # Check response size (blocked pages are often small)
            if len(response.content) < 15000:
                print(f"Amazon response too small for {asin}: {len(response.content)} bytes - likely blocked")
                if attempt < max_retries - 1:
                    time.sleep(2 + random.uniform(1, 4))
                    continue
                return None
            
            # Check for various blocking indicators
            content_text = response.text.lower()
            blocking_indicators = [
                'sorry, we just need to make sure you\'re not a robot',
                'enter the characters you see below',
                'captcha',
                'robot check',
                'blocked',
                'access denied',
                'unusual traffic',
                'automated requests'
            ]
            
            if any(indicator in content_text for indicator in blocking_indicators):
                print(f"Amazon detected automation for {asin} - found blocking indicator")
                if attempt < max_retries - 1:
                    # Reset session on detection
                    global amazon_session
                    amazon_session = None
                    time.sleep(5 + random.uniform(3, 8))
                    continue
                return None
            
            # Success - we got a valid page
            print(f"Successfully fetched {asin} on attempt {attempt + 1}")
            return response
            
        except requests.exceptions.Timeout:
            print(f"Timeout fetching {asin} on attempt {attempt + 1}")
            if attempt < max_retries - 1:
                time.sleep(2 + random.uniform(1, 3))
                continue
        except requests.exceptions.ConnectionError:
            print(f"Connection error fetching {asin} on attempt {attempt + 1}")
            if attempt < max_retries - 1:
                time.sleep(3 + random.uniform(1, 4))
                continue
        except Exception as e:
            print(f"Unexpected error fetching {asin} on attempt {attempt + 1}: {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(2 + random.uniform(1, 3))
                continue
    
    print(f"All attempts failed for {asin}")
    return None

def queue_worker():
    """Background worker that processes image requests one at a time with long delays"""
    global queue_worker_running, image_queue, product_image_cache
    
    while queue_worker_running:
        try:
            with queue_lock:
                if not image_queue:
                    time.sleep(1)
                    continue
                asin = image_queue.pop(0)
            
            print(f"Processing queued image request for {asin}")
            
            # Check if already cached while in queue
            cache_key = f"image_{asin}"
            if cache_key in product_image_cache:
                cached_data = product_image_cache[cache_key]
                if cached_data.get('timestamp') and (datetime.now() - cached_data['timestamp']).total_seconds() < IMAGE_CACHE_EXPIRY_HOURS * 3600:
                    continue
            
            # Try to fetch the image with very conservative approach
            response = fetch_amazon_page_with_retry(asin, max_retries=1)
            
            if response:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Use your identified selector
                img_tag_wrapper = soup.select_one('#imgTagWrapperId')
                if img_tag_wrapper:
                    img_elements = img_tag_wrapper.select('img')
                    for img in img_elements:
                        for attr in ['data-old-hires', 'data-a-hires', 'src', 'data-src']:
                            url = img.get(attr)
                            if url and url.startswith('http'):
                                product_image_cache[cache_key] = {
                                    'image_url': url,
                                    'timestamp': datetime.now()
                                }
                                print(f"Successfully cached image for {asin}")
                                break
                        if cache_key in product_image_cache:
                            break
            
            # Long delay between requests to avoid any detection
            time.sleep(random.uniform(8, 15))
            
        except Exception as e:
            print(f"Queue worker error for {asin}: {str(e)}")
            time.sleep(5)

def start_queue_worker():
    """Start the background queue worker"""
    global queue_worker_running
    if not queue_worker_running:
        queue_worker_running = True
        worker_thread = threading.Thread(target=queue_worker, daemon=True)
        worker_thread.start()
        print("Image queue worker started")

def stop_queue_worker():
    """Stop the background queue worker"""
    global queue_worker_running
    queue_worker_running = False
    print("Image queue worker stopped")

# Start the queue worker when the module loads
start_queue_worker()

@app.route('/api/demo/product-image/<asin>/proxy', methods=['GET'])
def demo_proxy_product_image(asin):
    """Demo proxy for product images - no auth required"""
    if not DEMO_MODE:
        return jsonify({'error': 'Demo mode not enabled'}), 403
    
    # For demo mode, return placeholder images to avoid scraping issues
    try:
        placeholder_url = f"https://via.placeholder.com/200x200/4f46e5/ffffff?text={asin[:6]}"
        
        # Fetch and proxy the placeholder image
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        
        img_response = requests.get(placeholder_url, headers=headers, timeout=5, stream=True)
        img_response.raise_for_status()
        
        response = make_response(img_response.content)
        response.headers['Content-Type'] = img_response.headers.get('Content-Type', 'image/png')
        response.headers['Cache-Control'] = 'public, max-age=3600'
        return response
        
    except Exception as e:
        print(f"Error fetching demo image for {asin}: {str(e)}")
        return '', 404

@app.route('/api/demo/product-images/batch', methods=['POST'])
def demo_get_product_images_batch():
    """Demo batch endpoint - no auth required"""
    if not DEMO_MODE:
        return jsonify({'error': 'Demo mode not enabled'}), 403
    
    try:
        data = request.get_json()
        asins = data.get('asins', [])
        
        results = {}
        for asin in asins:
            results[asin] = {
                'image_url': f"https://via.placeholder.com/200x200/4f46e5/ffffff?text={asin[:6]}",
                'cached': False,
                'method': 'demo_placeholder'
            }
        
        return jsonify({'results': results})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/demo/product-image/<asin>', methods=['GET'])
def demo_get_product_image(asin):
    """Demo individual image endpoint - no auth required"""
    if not DEMO_MODE:
        return jsonify({'error': 'Demo mode not enabled'}), 403
    
    return jsonify({
        'asin': asin,
        'image_url': f"https://via.placeholder.com/200x200/4f46e5/ffffff?text={asin[:6]}",
        'cached': False,
        'method': 'demo_placeholder'
    })

@app.route('/api/product-image/<asin>/proxy', methods=['GET'])
@login_required
def proxy_product_image(asin):
    """Proxy product image to avoid CORS and hotlinking issues"""
    return proxy_product_image_logic(asin)

@app.route('/api/product-image/<asin>/proxy/public', methods=['GET'])
def proxy_product_image_public(asin):
    """Public proxy for product images - no auth required for better UX"""
    return proxy_product_image_logic(asin)

@app.route('/api/product-image/<asin>/placeholder', methods=['GET'])
def get_product_image_placeholder(asin):
    """Always return a placeholder image for testing - no auth required"""
    try:
        placeholder_url = f"https://via.placeholder.com/200x200/4f46e5/ffffff?text={asin[:6]}"
        
        # Fetch and proxy the placeholder image
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        
        import requests
        img_response = requests.get(placeholder_url, headers=headers, timeout=5, stream=True)
        img_response.raise_for_status()
        
        response = make_response(img_response.content)
        response.headers['Content-Type'] = img_response.headers.get('Content-Type', 'image/png')
        response.headers['Cache-Control'] = 'public, max-age=3600'
        return response
        
    except Exception as e:
        print(f"Error fetching placeholder image for {asin}: {str(e)}")
        return '', 404

def proxy_product_image_logic(asin):
    """Shared logic for product image proxying"""
    try:
        # First get the image URL using existing logic
        cache_key = f"image_{asin}"
        image_url = None
        
        if cache_key in product_image_cache:
            cached_data = product_image_cache[cache_key]
            image_url = cached_data.get('image_url')
        
        if not image_url:
            # Fetch fresh if not cached - use demo endpoint if in demo mode
            if DEMO_MODE:
                data = get_product_image_logic(asin)
            else:
                response = get_product_image(asin)
                data = response.get_json()
            
            if data and 'image_url' in data:
                image_url = data['image_url']
        
        if not image_url:
            return '', 404
        
        # Fetch the image through our server
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
            'Referer': 'https://www.amazon.com/'
        }
        
        img_response = requests.get(image_url, headers=headers, timeout=10, stream=True)
        img_response.raise_for_status()
        
        # Return the image with appropriate headers
        return Response(
            img_response.content,
            mimetype=img_response.headers.get('Content-Type', 'image/jpeg'),
            headers={
                'Cache-Control': 'public, max-age=86400',  # Cache for 24 hours
                'Access-Control-Allow-Origin': '*'
            }
        )
        
    except Exception as e:
        print(f"Error proxying image for {asin}: {str(e)}")
        return '', 404

@app.route('/api/product-image/<asin>', methods=['GET'])
@login_required
def get_product_image(asin):
    """Get product image URL by scraping Amazon HTML"""
    try:
        # Check cache first
        cache_key = f"image_{asin}"
        now = datetime.now()
        
        if cache_key in product_image_cache:
            cached_data = product_image_cache[cache_key]
            cache_time = cached_data.get('timestamp')
            if cache_time and (now - cache_time).total_seconds() < IMAGE_CACHE_EXPIRY_HOURS * 3600:
                return jsonify({
                    'asin': asin,
                    'image_url': cached_data['image_url'],
                    'cached': True,
                    'cache_age': int((now - cache_time).total_seconds())
                })
        
        # Primary method: HTML scraping with the correct selector
        image_url = None
        method_used = None
        
        try:
            amazon_url = f'https://www.amazon.com/dp/{asin}'
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none'
            }
            
            response = requests.get(amazon_url, headers=headers, timeout=10)
            if response.status_code == 200:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Use the exact selector: #imgTagWrapperId
                img_wrapper = soup.select_one('#imgTagWrapperId')
                if img_wrapper:
                    img = img_wrapper.select_one('img')
                    if img:
                        # Try data-old-hires first (high-res), then src
                        scraped_url = img.get('data-old-hires') or img.get('src')
                        if scraped_url and scraped_url.startswith('http'):
                            image_url = scraped_url
                            method_used = 'html_scraping'
                            
        except Exception as e:
            # Log the error but continue to fallback
            print(f"HTML scraping failed for {asin}: {str(e)}")
        
        # Fallback: Try Amazon Associates widget (often bypasses restrictions)
        if not image_url:
            try:
                associate_url = f'https://ws-na.amazon-adsystem.com/widgets/q?_encoding=UTF8&ASIN={asin}&Format=_SL250_&ID=AsinImage&MarketPlace=US&ServiceVersion=20070822&WS=1'
                response = requests.head(associate_url, timeout=5)
                if response.status_code == 200:
                    image_url = associate_url
                    method_used = 'amazon_associates'
            except:
                pass
        
        # If we found an image, cache it and return
        if image_url:
            product_image_cache[cache_key] = {
                'image_url': image_url,
                'timestamp': now
            }
            
            return jsonify({
                'asin': asin,
                'image_url': image_url,
                'cached': False,
                'method': method_used
            })
        
        # Generate a meaningful placeholder with ASIN
        placeholder_url = f'https://via.placeholder.com/300x300/f0f0f0/666666?text={asin[:8]}'
        
        return jsonify({
            'asin': asin,
            'image_url': placeholder_url,
            'cached': False,
            'method': 'placeholder_fallback',
            'note': f'No image found for ASIN {asin}'
        })
            
    except Exception as e:
        return jsonify({
            'asin': asin,
            'image_url': f'https://via.placeholder.com/300x300/ffcccc/cc0000?text=ERROR',
            'error': f'Server error: {str(e)}',
            'method': 'error_placeholder'
        }), 500

@app.route('/api/product-images/batch', methods=['POST'])
@login_required
def get_product_images_batch():
    """Get multiple product image URLs efficiently"""
    try:
        data = request.get_json()
        asins = data.get('asins', [])
        
        if not asins or len(asins) > 10:  # Reduced batch size to avoid rate limits
            return jsonify({'error': 'Invalid ASIN list (max 10 ASINs)'}), 400
        
        results = {}
        uncached_asins = []
        now = datetime.now()
        
        # Check cache for all ASINs first
        for asin in asins:
            cache_key = f"image_{asin}"
            if cache_key in product_image_cache:
                cached_data = product_image_cache[cache_key]
                cache_time = cached_data.get('timestamp')
                if cache_time and (now - cache_time).total_seconds() < IMAGE_CACHE_EXPIRY_HOURS * 3600:
                    results[asin] = {
                        'image_url': cached_data['image_url'],
                        'cached': True
                    }
                else:
                    uncached_asins.append(asin)
            else:
                uncached_asins.append(asin)
        
        # For batch processing, use the same simplified approach
        for asin in uncached_asins:
            try:
                found_image = False
                
                # Primary method: HTML scraping with the correct selector
                try:
                    amazon_url = f'https://www.amazon.com/dp/{asin}'
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.5',
                        'Accept-Encoding': 'gzip, deflate, br',
                        'DNT': '1',
                        'Connection': 'keep-alive',
                        'Upgrade-Insecure-Requests': '1'
                    }
                    
                    response = requests.get(amazon_url, headers=headers, timeout=10)
                    if response.status_code == 200:
                        from bs4 import BeautifulSoup
                        soup = BeautifulSoup(response.content, 'html.parser')
                        
                        # Use the exact selector: #imgTagWrapperId
                        img_wrapper = soup.select_one('#imgTagWrapperId')
                        if img_wrapper:
                            img = img_wrapper.select_one('img')
                            if img:
                                # Try data-old-hires first (high-res), then src
                                scraped_url = img.get('data-old-hires') or img.get('src')
                                if scraped_url and scraped_url.startswith('http'):
                                    product_image_cache[f"image_{asin}"] = {
                                        'image_url': scraped_url,
                                        'timestamp': now
                                    }
                                    results[asin] = {
                                        'image_url': scraped_url,
                                        'cached': False,
                                        'method': 'html_scraping'
                                    }
                                    found_image = True
                    
                    # Add delay between scraping attempts to avoid detection
                    if len(uncached_asins) > 1:
                        time.sleep(random.uniform(1, 2))
                        
                except Exception as e:
                    print(f"HTML scraping failed for {asin}: {str(e)}")
                
                # Fallback: Try Amazon Associates widget
                if not found_image:
                    try:
                        associate_url = f'https://ws-na.amazon-adsystem.com/widgets/q?_encoding=UTF8&ASIN={asin}&Format=_SL250_&ID=AsinImage&MarketPlace=US&ServiceVersion=20070822&WS=1'
                        response = requests.head(associate_url, timeout=5)
                        if response.status_code == 200:
                            product_image_cache[f"image_{asin}"] = {
                                'image_url': associate_url,
                                'timestamp': now
                            }
                            results[asin] = {
                                'image_url': associate_url,
                                'cached': False,
                                'method': 'amazon_associates'
                            }
                            found_image = True
                    except:
                        pass
                
                # If still no image, use placeholder
                if not found_image:
                    placeholder_url = f'https://via.placeholder.com/300x300/f0f0f0/666666?text={asin[:8]}'
                    results[asin] = {
                        'image_url': placeholder_url,
                        'cached': False,
                        'method': 'placeholder',
                        'error': 'Failed to find image'
                    }
                
            except Exception as e:
                print(f"Error processing {asin}: {str(e)}")
                placeholder_url = f'https://via.placeholder.com/300x300/ffcccc/cc0000?text=ERROR'
                results[asin] = {
                    'image_url': placeholder_url,
                    'cached': False,
                    'method': 'error_placeholder',
                    'error': str(e)
                }
        
        return jsonify({
            'results': results,
            'total_asins': len(asins),
            'cached_count': len(asins) - len(uncached_asins),
            'fetched_count': len(uncached_asins)
        })
        
    except Exception as e:
        return jsonify({'error': f'Batch image fetch failed: {str(e)}'}), 500

@app.route('/api/test-image-patterns/<asin>', methods=['GET'])
@login_required
def test_image_patterns(asin):
    """Test HTML scraping and fallback methods for debugging"""
    try:
        results = []
        
        # Test HTML scraping method (primary method)
        scraping_result = None
        try:
            amazon_url = f'https://www.amazon.com/dp/{asin}'
            scrape_headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }
            
            response = requests.get(amazon_url, headers=scrape_headers, timeout=10)
            if response.status_code == 200:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(response.content, 'html.parser')
                
                img_wrapper = soup.select_one('#imgTagWrapperId')
                if img_wrapper:
                    img = img_wrapper.select_one('img')
                    if img:
                        scraped_url = img.get('data-old-hires') or img.get('src')
                        if scraped_url and scraped_url.startswith('http'):
                            scraping_result = {
                                'url': scraped_url,
                                'method': 'html_scraping',
                                'selector': '#imgTagWrapperId img',
                                'attribute_used': 'data-old-hires' if img.get('data-old-hires') else 'src',
                                'valid_image': True
                            }
                        else:
                            scraping_result = {
                                'error': 'No valid image URL found in HTML',
                                'method': 'html_scraping_failed'
                            }
                    else:
                        scraping_result = {
                            'error': 'No img tag found in #imgTagWrapperId',
                            'method': 'html_scraping_failed'
                        }
                else:
                    scraping_result = {
                        'error': '#imgTagWrapperId not found',
                        'method': 'html_scraping_failed'
                    }
            else:
                scraping_result = {
                    'error': f'HTTP {response.status_code}',
                    'method': 'html_scraping_failed'
                }
        except Exception as e:
            scraping_result = {
                'error': str(e),
                'method': 'html_scraping_failed'
            }

        # Test Amazon Associates widget as fallback
        associate_result = None
        try:
            associate_url = f'https://ws-na.amazon-adsystem.com/widgets/q?_encoding=UTF8&ASIN={asin}&Format=_SL250_&ID=AsinImage&MarketPlace=US&ServiceVersion=20070822&WS=1'
            response = requests.head(associate_url, timeout=5)
            associate_result = {
                'url': associate_url,
                'status_code': response.status_code,
                'valid': response.status_code == 200,
                'method': 'amazon_associates'
            }
        except Exception as e:
            associate_result = {
                'error': str(e),
                'valid': False,
                'method': 'amazon_associates_failed'
            }

        return jsonify({
            'asin': asin,
            'html_scraping_result': scraping_result,
            'associate_widget_result': associate_result,
            'recommendation': 'HTML scraping is the primary method, Associates widget is fallback'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/product-image/<asin>/debug', methods=['GET'])
@login_required
def debug_product_image(asin):
    """Debug endpoint to see what selectors and URLs are found for a specific ASIN"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5'
        }
        
        response = fetch_amazon_page_with_retry(asin)
        if not response:
            return jsonify({
                'asin': asin,
                'error': 'Could not fetch Amazon page - likely rate limited or blocked'
            }), 500
        
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.content, 'html.parser')
        
        debug_info = {
            'asin': asin,
            'imgTagWrapperId_found': False,
            'imgTagWrapperId_images': [],
            'selectors_found': [],
            'all_images_found': [],
            'final_image': None
        }
        
        # First check specifically for imgTagWrapperId
        img_tag_wrapper = soup.select_one('#imgTagWrapperId')
        if img_tag_wrapper:
            debug_info['imgTagWrapperId_found'] = True
            img_elements = img_tag_wrapper.select('img')
            for img in img_elements[:3]:  # Limit to first 3
                img_info = {}
                attrs = ['data-old-hires', 'data-a-hires', 'data-zoom-hires', 'data-a-dynamic-image', 'src', 'data-src', 'data-lazy-src']
                for attr in attrs:
                    value = img.get(attr)
                    if value:
                        img_info[attr] = value[:200] + '...' if len(value) > 200 else value
                if img_info:
                    debug_info['imgTagWrapperId_images'].append(img_info)
        
        # Then check other selectors
        selectors = [
            '#landingImage',
            '#imgTagWrapperId img',
            'img[data-old-hires]',
            '.a-dynamic-image',
            '#imageBlock img',
            '#imageBlock_feature_div img',
            '.a-carousel-container img',
            '#altImages img',
            '.image img',
            '.imgTagWrapper img',
            '[data-action="main-image-click"] img'
        ]
        
        for selector in selectors:
            img_elements = soup.select(selector)
            if img_elements:
                selector_info = {
                    'selector': selector,
                    'count': len(img_elements),
                    'images': []
                }
                
                for img in img_elements[:3]:  # Limit to first 3 for debugging
                    img_info = {}
                    attrs = ['data-old-hires', 'data-a-hires', 'data-zoom-hires', 'data-a-dynamic-image', 'src', 'data-src', 'data-lazy-src']
                    for attr in attrs:
                        value = img.get(attr)
                        if value:
                            img_info[attr] = value[:100] + '...' if len(value) > 100 else value
                    
                    if img_info:
                        selector_info['images'].append(img_info)
                        debug_info['all_images_found'].append({
                            'selector': selector,
                            'attributes': img_info
                        })
                
                if selector_info['images']:
                    debug_info['selectors_found'].append(selector_info)
        
        return jsonify(debug_info)
        
    except Exception as e:
        return jsonify({
            'asin': asin,
            'error': f'Debug failed: {str(e)}'
        }), 500

@app.route('/api/test-image/<asin>', methods=['GET'])
@login_required  
def test_image_simple(asin):
    """Simple test endpoint to verify image URL construction works"""
    try:
        test_urls = [
            f'https://m.media-amazon.com/images/P/{asin}.01._SX300_SY300_.jpg',
            f'https://images-na.ssl-images-amazon.com/images/P/{asin}.01.LZZZZZZZ.jpg',
            f'https://m.media-amazon.com/images/P/{asin}.01._AC_SX300_.jpg'
        ]
        
        results = []
        headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}
        
        for url in test_urls:
            try:
                response = requests.head(url, timeout=5, headers=headers)
                results.append({
                    'url': url,
                    'status_code': response.status_code,
                    'working': response.status_code == 200
                })
            except Exception as e:
                results.append({
                    'url': url,
                    'status_code': None,
                    'working': False,
                    'error': str(e)
                })
        
        working_url = next((r['url'] for r in results if r['working']), None)
        
        return jsonify({
            'asin': asin,
            'test_results': results,
            'working_url': working_url,
            'success': working_url is not None
        })
        
    except Exception as e:
        return jsonify({
            'asin': asin,
            'error': f'Test failed: {str(e)}'
        }), 500

@app.route('/api/image-status', methods=['GET'])
@login_required
def get_image_status():
    """Get status of image caching and rate limiting"""
    global last_amazon_request_time, product_image_cache
    
    current_time = time.time()
    time_since_last = current_time - last_amazon_request_time
    
    return jsonify({
        'cache_size': len(product_image_cache),
        'last_request_ago_seconds': time_since_last,
        'min_interval_seconds': MIN_REQUEST_INTERVAL,
        'can_make_request_now': time_since_last >= MIN_REQUEST_INTERVAL,
        'cache_sample': list(product_image_cache.keys())[:5] if product_image_cache else [],
        'queue_size': len(image_queue),
        'queue_sample': image_queue[:5] if image_queue else []
    })

@app.route('/api/check-images', methods=['POST'])
@login_required
def check_images_ready():
    """Check if images are ready for given ASINs"""
    try:
        data = request.get_json()
        asins = data.get('asins', [])
        
        results = {}
        for asin in asins:
            cache_key = f"image_{asin}"
            if cache_key in product_image_cache:
                cached_data = product_image_cache[cache_key]
                cache_time = cached_data.get('timestamp')
                if cache_time and (datetime.now() - cache_time).total_seconds() < IMAGE_CACHE_EXPIRY_HOURS * 3600:
                    results[asin] = {
                        'ready': True,
                        'image_url': cached_data['image_url'],
                        'cached_since': cache_time.isoformat()
                    }
                    continue
            
            # Check if in queue
            with queue_lock:
                queue_position = image_queue.index(asin) + 1 if asin in image_queue else None
            
            results[asin] = {
                'ready': False,
                'in_queue': queue_position is not None,
                'queue_position': queue_position
            }
        
        return jsonify({
            'results': results,
            'total_cached': len(product_image_cache),
            'queue_size': len(image_queue)
        })
        
    except Exception as e:
        return jsonify({'error': f'Check failed: {str(e)}'}), 500

# eBay Lister API Endpoints
@app.route('/api/products/asin/<asin>', methods=['GET'])
@login_required
def get_product_by_asin(asin):
    """Get product information by ASIN for eBay listing creation using Sellerboard data"""
    try:
        # Validate ASIN format
        if not asin or len(asin) != 10:
            return jsonify({
                'success': False,
                'message': 'Invalid ASIN format. ASIN must be 10 characters.'
            }), 400
            
        # Get user's Discord ID for configuration lookup
        discord_id = session['discord_id']
        print(f"eBay Lister: Looking up ASIN {asin} for user {discord_id}")
        user_record = get_user_record(discord_id)
        
        if not user_record:
            print(f"eBay Lister: No user configuration found for {discord_id}")
            return jsonify({
                'success': False,
                'message': 'User configuration not found. Please complete your setup first.'
            }), 400
        
        # Get Sellerboard URLs
        orders_url = get_user_sellerboard_orders_url(user_record)
        stock_url = get_user_sellerboard_stock_url(user_record)
        
        print(f"eBay Lister: Orders URL configured: {bool(orders_url)}")
        print(f"eBay Lister: Stock URL configured: {bool(stock_url)}")
        
        if not orders_url or not stock_url:
            print(f"eBay Lister: Missing URLs - orders: {bool(orders_url)}, stock: {bool(stock_url)}")
            return jsonify({
                'success': False,
                'message': 'Sellerboard URLs not configured. Please set up your Sellerboard integration in Settings first.'
            }), 400
            
        # Use OrdersAnalysis to get real product data
        from orders_analysis import EnhancedOrdersAnalysis
        from datetime import date, timedelta
        import pytz
        
        # Get user timezone or default to UTC
        user_timezone = get_user_timezone(user_record) or 'UTC'
        target_date = date.today()
        
        # Define asin_upper outside the try block so it's available in except
        asin_upper = asin.upper()
        
        try:
            # Initialize with user's Sellerboard URLs
            print(f"eBay Lister: Initializing analyzer for ASIN {asin_upper}")
            analyzer = EnhancedOrdersAnalysis(orders_url, stock_url)
            
            # Get stock information (contains product details)
            print(f"eBay Lister: Downloading stock CSV from Sellerboard")
            stock_df = analyzer.download_csv(stock_url)
            print(f"eBay Lister: Stock CSV downloaded, shape: {stock_df.shape}")
            print(f"eBay Lister: Column names in stock CSV: {list(stock_df.columns)}")
            
            # Debug: Show first few rows to understand data structure
            if not stock_df.empty:
                # Convert first row to JSON-serializable format for debug output
                first_row_raw = stock_df.iloc[0].to_dict()
                first_row_safe = {}
                for key, value in first_row_raw.items():
                    try:
                        if hasattr(value, 'item'):  # numpy scalar
                            value = value.item()
                        elif str(type(value)).startswith('<class \'pandas.') or str(type(value)).startswith('<class \'numpy.'):
                            value = str(value)
                        first_row_safe[key] = value
                    except Exception:
                        first_row_safe[key] = str(value)
                print(f"eBay Lister: First row of data: {first_row_safe}")
            
            # Try to parse stock info, but handle errors gracefully
            try:
                stock_info = analyzer.get_stock_info(stock_df)
                print(f"eBay Lister: Processed {len(stock_info)} products from stock data")
            except ValueError as e:
                print(f"eBay Lister: Error parsing stock data: {e}")
                # Try to find ASIN column manually
                possible_asin_cols = [col for col in stock_df.columns if 'asin' in col.lower() or 'sku' in col.lower()]
                print(f"eBay Lister: Possible ASIN/SKU columns: {possible_asin_cols}")
                
                # If we can't find ASIN column, provide helpful error
                return jsonify({
                    'success': False,
                    'message': f'Could not find ASIN column in Sellerboard data. Available columns: {", ".join(stock_df.columns[:10])}... Please check your Sellerboard export format.',
                    'debug_info': {
                        'columns': list(stock_df.columns),
                        'possible_asin_columns': possible_asin_cols
                    }
                }), 400
            
            # Debug: Show sample ASINs for troubleshooting
            available_asins = list(stock_info.keys())[:10]  # First 10 ASINs
            print(f"eBay Lister: Sample ASINs in inventory: {available_asins}")
            
            # Debug: Check exact ASIN matching
            print(f"eBay Lister: Looking for ASIN '{asin_upper}' in stock_info keys")
            print(f"eBay Lister: Type of asin_upper: {type(asin_upper)}, Value: '{asin_upper}'")
            
            # Check different variations
            found = False
            matched_key = None
            for key in stock_info.keys():
                print(f"eBay Lister: Comparing '{asin_upper}' with key '{key}' (type: {type(key)})")
                if key == asin_upper:
                    found = True
                    matched_key = key
                    break
                # Also try case-insensitive match
                if key.upper() == asin_upper:
                    found = True
                    matched_key = key
                    print(f"eBay Lister: Found case-insensitive match: '{key}'")
                    break
                # Try stripping whitespace
                if key.strip() == asin_upper:
                    found = True
                    matched_key = key
                    print(f"eBay Lister: Found match after stripping: '{key}'")
                    break
            
            # Check if ASIN exists in stock data
            if not found:
                print(f"eBay Lister: ASIN {asin_upper} not found. Available ASINs count: {len(stock_info)}")
                # Show more detailed debug info
                print(f"eBay Lister: First 5 raw keys: {list(stock_info.keys())[:5]}")
                print(f"eBay Lister: First 5 keys repr: {[repr(k) for k in list(stock_info.keys())[:5]]}")
                
                return jsonify({
                    'success': False,
                    'message': f'ASIN {asin_upper} not found in your inventory. You have {len(stock_info)} products in your Sellerboard data. Sample ASINs: {", ".join(available_asins[:5])}',
                    'debug_info': {
                        'total_products': len(stock_info),
                        'sample_asins': available_asins[:10],
                        'searched_asin': asin_upper,
                        'exact_keys': [repr(k) for k in available_asins[:5]]  # Show exact representation
                    }
                }), 404
            
            # Use the matched key to get product info
            asin_to_use = matched_key if matched_key else asin_upper
            print(f"eBay Lister: Using key '{asin_to_use}' to access product data")
                
            # Get product information from stock data
            product_info = stock_info[asin_to_use]
            print(f"eBay Lister: Successfully retrieved product info for {asin_to_use}")
            
            # Try to get sales data for pricing context
            print(f"eBay Lister: Downloading orders CSV from Sellerboard")
            orders_df = analyzer.download_csv(orders_url)
            print(f"eBay Lister: Orders CSV downloaded, shape: {orders_df.shape}")
            print(f"eBay Lister: Processing orders for date range")
            orders_for_week = analyzer.get_orders_for_date_range(
                orders_df, 
                target_date - timedelta(days=7), 
                target_date, 
                user_timezone
            )
            print(f"eBay Lister: Found {len(orders_for_week)} orders in the past week")
            print(f"eBay Lister: Calculating ASIN sales counts")
            weekly_sales = analyzer.asin_sales_count(orders_for_week)
            print(f"eBay Lister: Calculated sales for {len(weekly_sales)} ASINs")
            
            # Extract available data from Sellerboard
            product_title = product_info.get('Title', f'Product {asin_upper}')
            
            # Get current stock and pricing info
            current_stock = 0
            try:
                stock_fields = ['FBA/FBM Stock', 'FBA stock', 'Inventory (FBA)', 'Stock', 'Current Stock']
                for field in stock_fields:
                    if field in product_info and product_info[field] is not None:
                        stock_val = str(product_info[field]).replace(',', '').strip()
                        if stock_val and stock_val.lower() not in ['nan', 'none', '']:
                            current_stock = int(float(stock_val))
                            print(f"eBay Lister: Found stock value {current_stock} in field '{field}'")
                            break
            except (ValueError, TypeError) as e:
                print(f"eBay Lister: Error parsing stock: {e}")
                current_stock = 0
            
            # Try to get pricing from recent sales or stock data
            estimated_price = '0.00'
            try:
                price_fields = ['Price', 'Current Price', 'Sale Price', 'Unit Price', 'Stock value']
                for field in price_fields:
                    if field in product_info and product_info[field] is not None:
                        price_val = str(product_info[field]).replace('$', '').replace(',', '').strip()
                        if price_val and price_val.lower() not in ['nan', 'none', '', '0', '0.0']:
                            # For stock value, calculate per-unit price
                            if field == 'Stock value' and current_stock > 0:
                                estimated_price = f"{float(price_val) / current_stock:.2f}"
                                print(f"eBay Lister: Calculated price ${estimated_price} from stock value")
                            else:
                                estimated_price = f"{float(price_val):.2f}"
                                print(f"eBay Lister: Found price ${estimated_price} in field '{field}'")
                            break
            except (ValueError, TypeError) as e:
                print(f"eBay Lister: Error parsing price: {e}")
                estimated_price = '0.00'
            
            # Get weekly sales for velocity context  
            weekly_sales_count = weekly_sales.get(asin_to_use, 0)
            
            # Build comprehensive product data
            product_data = {
                'asin': asin_upper,
                'title': product_title,
                'brand': 'Unknown Brand',  # Sellerboard doesn't typically include brand
                'category': 'General Merchandise',  # Generic category
                'price': estimated_price,
                'current_stock': current_stock,
                'weekly_sales': weekly_sales_count,
                'image_url': f'https://via.placeholder.com/300x300?text={asin_upper}',  # Placeholder since Sellerboard doesn't include images
                'dimensions': 'Not available from Sellerboard',
                'weight': 'Not available from Sellerboard',
                'description': f'{product_title} - High-quality product available through Amazon FBA. ASIN: {asin_upper}',
                'bullet_points': [
                    f'Product Title: {product_title}',
                    f'Current Stock: {current_stock} units',
                    f'Weekly Sales Velocity: {weekly_sales_count} units/week',
                    'Shipped via Amazon FBA for fast delivery',
                    'Professional seller with high ratings'
                ],
                'features': {
                    'ASIN': asin_upper,
                    'Current Stock': str(current_stock),
                    'Weekly Sales': str(weekly_sales_count),
                    'Data Source': 'Sellerboard Integration'
                },
                'sellerboard_data': {
                    'stock_info': {k: (v if v is not None and str(v).lower() != 'nan' else 'N/A') for k, v in product_info.items() if k not in ['Title']},  # Include all extra fields, clean NaN values
                    'weekly_sales': weekly_sales_count,
                    'data_freshness': 'Real-time from your Sellerboard account'
                }
            }
            
            print(f"eBay Lister: Returning successful product data for {asin_upper}")
            print(f"eBay Lister: Final product data keys: {list(product_data.keys())}")
            print(f"eBay Lister: Stock: {product_data['current_stock']}, Price: {product_data['price']}, Sales: {product_data['weekly_sales']}")
            return jsonify({
                'success': True,
                'product': product_data
            })
            
        except Exception as sellerboard_error:
            print(f"Sellerboard integration error: {sellerboard_error}")
            import traceback
            traceback.print_exc()
            
            # Fallback to basic mock data if Sellerboard fails
            print(f"eBay Lister: Falling back to mock data for ASIN {asin_upper}")
            mock_product_data = {
                'asin': asin_upper,
                'title': f'Product {asin_upper} (Fallback Data)',
                'brand': 'Unknown Brand',
                'category': 'General Merchandise',
                'price': '29.99',
                'current_stock': 0,
                'weekly_sales': 0,
                'image_url': f'https://via.placeholder.com/300x300?text={asin_upper}',
                'dimensions': 'Not available',
                'weight': 'Not available',
                'description': f'Product {asin_upper} - Sellerboard integration failed, using fallback data.',
                'bullet_points': [
                    f'ASIN: {asin_upper}',
                    'Sellerboard integration temporarily unavailable',
                    'Please check your Sellerboard URL configuration',
                    'Contact support if this persists'
                ],
                'features': {
                    'ASIN': asin_upper,
                    'Data Source': 'Fallback (Sellerboard Failed)'
                },
                'sellerboard_error': str(sellerboard_error)
            }
            
            return jsonify({
                'success': True,
                'product': mock_product_data,
                'warning': f'Sellerboard integration failed: {str(sellerboard_error)}'
            })
        
    except Exception as e:
        print(f"Error fetching product data for ASIN {asin}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Failed to fetch product data: {str(e)}. Check server logs for details.'
        }), 500

@app.route('/api/ebay/generate-listing', methods=['POST'])
@login_required
def generate_ebay_listing():
    """Generate eBay listing data from Amazon product information"""
    try:
        data = request.get_json()
        asin = data.get('asin')
        product_data = data.get('productData')
        
        if not asin or not product_data:
            return jsonify({
                'success': False,
                'message': 'Missing ASIN or product data'
            }), 400
            
        # Generate eBay-optimized listing
        ebay_title = f"{product_data['title'][:70]}..." if len(product_data['title']) > 70 else product_data['title']
        
        # Get additional data for enhanced description
        current_stock = product_data.get('current_stock', 0)
        weekly_sales = product_data.get('weekly_sales', 0)
        sellerboard_data = product_data.get('sellerboard_data', {})
        
        # Create description with HTML formatting for eBay using real Sellerboard data
        ebay_description = f"""
<div style="font-family: Arial, sans-serif; line-height: 1.6;">
    <h2>{product_data['title']}</h2>
    
    <h3>Product Features:</h3>
    <ul>
        {"".join(f"<li>{point}</li>" for point in product_data.get('bullet_points', []))}
    </ul>
    
    <h3>Product Details:</h3>
    <table border="1" cellpadding="5" cellspacing="0" style="border-collapse: collapse;">
        <tr><td><strong>ASIN:</strong></td><td>{asin}</td></tr>
        <tr><td><strong>Brand:</strong></td><td>{product_data.get('brand', 'Professional Brand')}</td></tr>
        <tr><td><strong>Current Stock:</strong></td><td>{current_stock} units available</td></tr>
        <tr><td><strong>Sales Velocity:</strong></td><td>{weekly_sales} units sold per week</td></tr>
        <tr><td><strong>Shipping:</strong></td><td>Fulfilled by Amazon (FBA)</td></tr>
    </table>
    
    <h3>About This Item:</h3>
    <p>{product_data.get('description', 'High-quality product with excellent features.')}</p>
    
    <h3>Why Buy From Us:</h3>
    <ul>
        <li>✅ Fast shipping via Amazon FBA network</li>
        <li>✅ Professional seller with high customer satisfaction</li>
        <li>✅ Authentic products - no counterfeits</li>
        <li>✅ Excellent customer service</li>
        {"<li>✅ High demand item - " + str(weekly_sales) + " sold weekly</li>" if weekly_sales > 0 else ""}
    </ul>
    
    <h3>Shipping & Returns:</h3>
    <p>Items ship quickly via Amazon's fulfillment network. Standard return policy applies.</p>
    
    <div style="text-align: center; margin-top: 20px; padding: 10px; background-color: #f0f0f0;">
        <p><strong>Thank you for your business!</strong></p>
        <p><em>Data sourced from Sellerboard analytics - {sellerboard_data.get('data_freshness', 'Live data')}</em></p>
    </div>
</div>
        """.strip()
        
        # Calculate suggested pricing (markup from Amazon price)
        try:
            base_price = float(product_data.get('price', '29.99'))
            # If price is 0 or very low, use a reasonable default
            if base_price <= 1.0:
                base_price = 29.99
                print(f"eBay Lister: Using default price ${base_price} as product price was too low")
        except (ValueError, TypeError):
            base_price = 29.99
            print(f"eBay Lister: Using default price ${base_price} due to price parsing error")
            
        suggested_price = round(base_price * 0.85, 2)  # Start at 85% for auction
        buy_it_now_price = round(base_price * 1.15, 2)  # 15% markup for BIN
        
        # Generate eBay category suggestion based on product category
        ebay_category = "Consumer Electronics > Portable Audio & Headphones"
        if 'phone' in product_data.get('category', '').lower():
            ebay_category = "Cell Phones & Accessories > Cell Phone Accessories"
        elif 'computer' in product_data.get('category', '').lower():
            ebay_category = "Computers/Tablets & Networking > Computer Components & Parts"
            
        listing_data = {
            'title': ebay_title,
            'description': ebay_description,
            'category': ebay_category,
            'condition': 'New',
            'suggestedPrice': suggested_price,
            'buyItNowPrice': buy_it_now_price,
            'shipping': 'Free Standard Shipping',
            'itemSpecifics': {
                'Brand': product_data.get('brand', 'Unbranded'),
                'Model': asin,
                'Type': 'Consumer Electronics',
                'Color': product_data.get('features', {}).get('Color', 'Black'),
                'Condition': 'New',
                'Country/Region of Manufacture': 'China'
            }
        }
        
        return jsonify({
            'success': True,
            'listing': listing_data
        })
        
    except Exception as e:
        print(f"Error generating eBay listing: {e}")
        return jsonify({
            'success': False,
            'message': 'Failed to generate eBay listing. Please try again.'
        }), 500

# Purchase Management Endpoints
@app.route('/api/purchases', methods=['GET'])
@login_required
def get_purchases():
    """Get all purchases with live Sellerboard data"""
    try:
        discord_id = session['discord_id']
        user_record = get_user_record(discord_id)
        
        if not user_record:
            return jsonify({
                'success': False,
                'message': 'User configuration not found'
            }), 400

        # Determine which user's purchases to fetch
        # For VAs/sub-users: show their parent user's purchases
        # For main users: show their own purchases
        target_user_id = discord_id
        
        if get_user_field(user_record, 'account.user_type') == 'subuser':
            # This is a VA/sub-user - get their parent's purchases
            parent_user = get_parent_user_record(discord_id)
            if parent_user:
                target_user_id = get_user_field(parent_user, 'identity.discord_id') or discord_id
                print(f"VA user {discord_id} fetching purchases for parent user {target_user_id}")
            else:
                print(f"Warning: VA user {discord_id} has no parent user found")
        
        print(f"Fetching purchases for user_id: {target_user_id} (original requester: {discord_id})")
        
        # Get purchases from S3
        all_purchases = get_purchases_config()
        print(f"Found {len(all_purchases)} total purchases in S3")
        
        # Filter purchases for the target user
        purchases = [p for p in all_purchases if p.get('user_id') == target_user_id]
        print(f"Found {len(purchases)} purchases for target user {target_user_id}")
        
        # Sort by created_at descending
        purchases.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        
        # Enrich with live Sellerboard data
        # For VAs, use parent user's Sellerboard configuration
        config_user = user_record
        if get_user_field(user_record, 'account.user_type') == 'subuser':
            parent_user = get_parent_user_record(discord_id)
            if parent_user:
                config_user = parent_user
                print(f"Using parent user's Sellerboard config for VA {discord_id}")
        
        orders_url = get_user_sellerboard_orders_url(config_user)
        stock_url = get_user_sellerboard_stock_url(config_user)
        
        if orders_url and stock_url:
            from orders_analysis import EnhancedOrdersAnalysis
            from datetime import date, timedelta
            
            try:
                analyzer = EnhancedOrdersAnalysis(orders_url, stock_url)
                
                # Get stock and sales data
                stock_df = analyzer.download_csv(stock_url)
                stock_info = analyzer.get_stock_info(stock_df)
                
                orders_df = analyzer.download_csv(orders_url)
                target_date = date.today()
                orders_for_month = analyzer.get_orders_for_date_range(
                    orders_df, 
                    target_date - timedelta(days=30), 
                    target_date, 
                    get_user_timezone(config_user) or 'UTC'
                )
                monthly_sales = analyzer.asin_sales_count(orders_for_month)
                
                # Update purchases with live data
                for purchase in purchases:
                    asin = extract_asin_from_url(purchase.get('sell_link', ''))
                    if asin and asin in stock_info:
                        stock_data = stock_info[asin]
                        purchase['current_stock'] = stock_data.get('FBA/FBM Stock', 0)
                        purchase['spm'] = monthly_sales.get(asin, 0)
                        purchase['asin'] = asin
                    
            except Exception as e:
                print(f"Error enriching purchase data: {e}")
                # Continue without enrichment
        
        return jsonify({
            'success': True,
            'purchases': purchases
        })
        
    except Exception as e:
        print(f"Error fetching purchases: {e}")
        return jsonify({
            'success': False,
            'message': 'Failed to fetch purchases'
        }), 500

@app.route('/api/purchases', methods=['POST'])
@login_required
def add_purchase():
    """Add a new purchase"""
    try:
        data = request.get_json()
        discord_id = session['discord_id']
        
        print(f"🔄 CREATING PURCHASE - User: {discord_id}")
        print(f"📝 Request data: {data}")
        
        # Extract ASIN from Amazon URL
        asin = extract_asin_from_url(data.get('sellLink', ''))
        print(f"🔍 Extracted ASIN: {asin}")
        
        # Get current purchases from S3
        all_purchases = get_purchases_config()
        print(f"📊 Current purchases count in S3: {len(all_purchases)}")
        
        # Generate new purchase ID
        purchase_id = max([p.get('id', 0) for p in all_purchases], default=0) + 1
        print(f"🆔 Generated purchase ID: {purchase_id}")
        
        # Create new purchase object
        from datetime import datetime
        new_purchase = {
            'id': purchase_id,
            'user_id': discord_id,
            'buy_link': data.get('buyLink'),
            'sell_link': data.get('sellLink'),
            'name': data.get('name'),
            'price': float(data.get('price', 0)),
            'target_quantity': int(data.get('targetQuantity', 0)),
            'notes': data.get('notes', ''),
            'asin': asin,
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat(),
            'purchased': False,
            'va_notes': ''
        }
        
        # Add to purchases list
        all_purchases.append(new_purchase)
        
        # Save to S3
        if update_purchases_config(all_purchases):
            print(f"✅ Purchase saved to S3 successfully")
            print(f"📊 New purchases count in S3: {len(all_purchases)}")
            
            return jsonify({
                'success': True,
                'purchase': new_purchase
            })
        else:
            print(f"❌ ERROR: Failed to save purchase to S3!")
            return jsonify({
                'success': False,
                'message': 'Failed to save purchase'
            }), 500
        
    except Exception as e:
        print(f"❌ Error adding purchase: {e}")
        import traceback
        print(f"❌ Full traceback: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'message': f'Failed to add purchase: {str(e)}'
        }), 500

@app.route('/api/purchases/<int:purchase_id>', methods=['PUT'])
@login_required
def update_purchase(purchase_id):
    """Update a purchase"""
    try:
        data = request.get_json()
        discord_id = session['discord_id']
        user_record = get_user_record(discord_id)
        
        # Determine which user owns the purchase we're updating
        # For VAs: they can update their parent user's purchases
        target_user_id = discord_id
        if get_user_field(user_record, 'account.user_type') == 'subuser':
            parent_user = get_parent_user_record(discord_id)
            if parent_user:
                target_user_id = get_user_field(parent_user, 'identity.discord_id') or discord_id
        
        # Get all purchases from S3
        all_purchases = get_purchases_config()
        
        # Find the purchase to update
        purchase_found = False
        allowed_fields = ['purchased', 'notes', 'target_quantity', 'va_notes']
        
        for purchase in all_purchases:
            if purchase.get('id') == purchase_id and purchase.get('user_id') == target_user_id:
                purchase_found = True
                
                # Update allowed fields
                for field in allowed_fields:
                    if field in data:
                        purchase[field] = data[field]
                
                # Update timestamp
                from datetime import datetime
                purchase['updated_at'] = datetime.utcnow().isoformat()
                break
        
        if not purchase_found:
            return jsonify({
                'success': False,
                'message': 'Purchase not found'
            }), 404
        
        # Save updated purchases to S3
        if update_purchases_config(all_purchases):
            return jsonify({
                'success': True,
                'message': 'Purchase updated successfully'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to save purchase updates'
            }), 500
        
    except Exception as e:
        print(f"Error updating purchase: {e}")
        return jsonify({
            'success': False,
            'message': 'Failed to update purchase'
        }), 500

def extract_asin_from_url(url):
    """Extract ASIN from Amazon URL"""
    if not url:
        return None
    
    import re
    match = re.search(r'/dp/([A-Z0-9]{10})', url)
    return match.group(1) if match else None

def migrate_purchases_to_s3():
    """Migrate existing purchases from SQLite to S3"""
    try:
        # Get existing purchases from S3
        existing_purchases = get_purchases_config()
        print(f"Found {len(existing_purchases)} existing purchases in S3")
        
        # Get all purchases from SQLite
        cursor.execute("SELECT * FROM purchases ORDER BY created_at DESC")
        sqlite_purchases = cursor.fetchall()
        print(f"Found {len(sqlite_purchases)} purchases in SQLite")
        
        # Convert SQLite purchases to S3 format
        migrated_count = 0
        for row in sqlite_purchases:
            purchase_dict = dict(zip([col[0] for col in cursor.description], row))
            
            # Check if this purchase already exists in S3 (by ID and user_id)
            purchase_exists = any(
                p.get('id') == purchase_dict.get('id') and 
                p.get('user_id') == purchase_dict.get('user_id')
                for p in existing_purchases
            )
            
            if not purchase_exists:
                # Ensure all required fields are present
                purchase_dict.setdefault('purchased', False)
                purchase_dict.setdefault('va_notes', '')
                purchase_dict.setdefault('updated_at', purchase_dict.get('created_at'))
                
                existing_purchases.append(purchase_dict)
                migrated_count += 1
        
        if migrated_count > 0:
            # Save all purchases to S3
            if update_purchases_config(existing_purchases):
                print(f"✅ Successfully migrated {migrated_count} purchases to S3")
                return True, f"Migrated {migrated_count} purchases"
            else:
                print(f"❌ Failed to save migrated purchases to S3")
                return False, "Failed to save to S3"
        else:
            print(f"ℹ️ No new purchases to migrate")
            return True, "No new purchases to migrate"
            
    except Exception as e:
        print(f"❌ Error during migration: {e}")
        return False, f"Migration error: {str(e)}"

@app.route('/api/purchases/migrate', methods=['POST'])
@login_required
def migrate_purchases():
    """Endpoint to trigger purchase migration from SQLite to S3"""
    try:
        discord_id = session['discord_id']
        
        # Only allow admin to trigger migration
        if discord_id != '712147636463075389':
            return jsonify({
                'success': False,
                'message': 'Unauthorized'
            }), 403
        
        success, message = migrate_purchases_to_s3()
        
        return jsonify({
            'success': success,
            'message': message
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Migration failed: {str(e)}'
        }), 500


@app.route('/api/debug/purchases', methods=['GET'])
@login_required  
def debug_purchases():
    """Debug endpoint to inspect purchases database directly"""
    try:
        discord_id = session['discord_id']
        user_record = get_user_record(discord_id)
        
        # Only allow admin users to access this debug endpoint
        if not user_record or discord_id != '712147636463075389':  # Admin Discord ID
            return jsonify({
                'success': False,
                'message': 'Access denied - admin only'
            }), 403
        
        debug_info = {}
        
        # Get total purchase count
        cursor.execute("SELECT COUNT(*) FROM purchases")
        debug_info['total_purchases'] = cursor.fetchone()[0]
        
        # Get purchases by user
        cursor.execute("SELECT user_id, COUNT(*) as count FROM purchases GROUP BY user_id")
        debug_info['purchases_by_user'] = dict(cursor.fetchall())
        
        # Get all purchases with basic info
        cursor.execute("SELECT id, user_id, name, created_at FROM purchases ORDER BY created_at DESC LIMIT 10")
        recent_purchases = []
        for row in cursor.fetchall():
            recent_purchases.append(dict(zip([col[0] for col in cursor.description], row)))
        debug_info['recent_purchases'] = recent_purchases
        
        # Get database file info
        import os
        db_path = os.path.abspath(DATABASE_FILE)
        debug_info['database_file'] = {
            'path': db_path,
            'exists': os.path.exists(db_path),
            'size': os.path.getsize(db_path) if os.path.exists(db_path) else 0
        }
        
        return jsonify({
            'success': True,
            'debug_info': debug_info
        })
        
    except Exception as e:
        print(f"Debug endpoint error: {e}")
        return jsonify({
            'success': False,
            'message': f'Debug error: {str(e)}'
        }), 500

# Database initialization for purchases table
def init_purchases_table():
    """Initialize the purchases table if it doesn't exist"""
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                buy_link TEXT,
                sell_link TEXT,
                name TEXT,
                price REAL DEFAULT 0,
                target_quantity INTEGER DEFAULT 0,
                purchased INTEGER DEFAULT 0,
                notes TEXT,
                va_notes TEXT,
                asin TEXT,
                current_stock INTEGER DEFAULT 0,
                spm INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes separately for SQLite
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_purchases_user_id ON purchases (user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_purchases_asin ON purchases (asin)")
        
        conn.commit()
        print("Purchases table initialized successfully")
    except Exception as e:
        print(f"Error initializing purchases table: {e}")

# Initialize purchases table on startup
init_purchases_table()

# Demo control endpoints
@app.route('/api/demo/status', methods=['GET'])
def demo_status():
    """Check demo mode status"""
    return jsonify({
        'demo_mode': DEMO_MODE,
        'environment': os.getenv('DEMO_MODE', 'false'),
        'test_restart': True  # This will confirm if restart picked up changes
    })

def clear_all_caches_for_demo_toggle():
    """Clear all caches when toggling demo mode to prevent stale data issues"""
    # Clear user config cache
    config_cache.clear()
    
    # Clear user session cache
    user_session_cache.clear()
    
    # Clear analytics cache
    analytics_cache.clear()
    
    # Clear file listing cache
    file_listing_cache.clear()
    
    # Clear flask session data to force re-authentication
    session.clear()

@app.route('/api/demo/toggle', methods=['POST'])
def toggle_demo_mode():
    """Toggle demo mode (for development/testing only)"""
    global DEMO_MODE
    
    # Only allow toggling in development
    if os.getenv('FLASK_ENV') == 'development' or os.getenv('ENVIRONMENT') == 'development':
        DEMO_MODE = not DEMO_MODE
        
        # Clear all caches when switching modes to prevent stale data
        clear_all_caches_for_demo_toggle()
        
        return jsonify({
            'demo_mode': DEMO_MODE,
            'message': f'Demo mode {"enabled" if DEMO_MODE else "disabled"}'
        })
    else:
        return jsonify({'error': 'Demo mode toggle not available in production'}), 403

@app.route('/api/demo/enable', methods=['POST'])
def enable_demo_mode():
    """Enable demo mode for demos"""
    global DEMO_MODE
    DEMO_MODE = True
    
    # Clear all caches when enabling demo mode
    clear_all_caches_for_demo_toggle()
    
    return jsonify({
        'demo_mode': True,
        'message': 'Demo mode enabled - all data is now simulated for demonstration purposes'
    })

@app.route('/api/demo/user', methods=['GET'])
def get_demo_user():
    """Get demo user data without authentication"""
    if not DEMO_MODE:
        return jsonify({'error': 'Demo mode not enabled'}), 403
    
    demo_users = get_dummy_users()
    demo_user = demo_users[0]
    return jsonify({
        'discord_id': get_user_discord_id(demo_user),
        'discord_username': get_user_field(demo_user, 'identity.discord_username') or demo_user.get('discord_username'),
        'email': get_user_field(demo_user, 'identity.email') or demo_user.get('email'),
        'profile_configured': True,
        'google_linked': True,
        'sheet_configured': True,
        'amazon_connected': True,
        'demo_mode': True,
        'user_type': get_user_field(demo_user, 'account.user_type') or 'main',
        'permissions': get_user_permissions(demo_user),
        'last_activity': demo_user.get('last_activity'),
        'timezone': 'America/New_York'
    })

@app.route('/api/analytics/inventory-age')
@login_required
def get_inventory_age_analysis():
    """Get comprehensive inventory age analysis"""
    print(f"DEBUG: inventory-age endpoint called by user: {session.get('discord_id', 'unknown')}")
    try:
        discord_id = session['discord_id']
        user_record = get_user_record(discord_id)
        
        # Store auth success info for debug endpoint
        from orders_analysis import _global_worksheet_debug
        _global_worksheet_debug['auth_attempt'] = {
            'discord_id': discord_id,
            'user_found': bool(user_record),
            'timestamp': datetime.now().isoformat()
        }
        
        if not user_record:
            return jsonify({'error': 'User not found'}), 404
        
        # Handle parent-child relationship for configuration
        config_user_record = user_record
        parent_user_id = user_record.get('parent_user_id')
        if parent_user_id:
            parent_record = get_user_record(parent_user_id)
            if parent_record:
                config_user_record = parent_record
        
        # Get current analytics data
        from orders_analysis import EnhancedOrdersAnalysis
        
        orders_url = get_user_sellerboard_orders_url(config_user_record)
        stock_url = get_user_sellerboard_stock_url(config_user_record)
        
        if not orders_url or not stock_url:
            _global_worksheet_debug['auth_attempt']['sellerboard_config'] = {
                'orders_url_configured': bool(orders_url),
                'stock_url_configured': bool(stock_url)
            }
            return jsonify({
                'error': 'Sellerboard URLs not configured',
                'message': 'Please configure your Sellerboard URLs in Settings to enable inventory age analysis.'
            }), 400
        
        # Get enhanced analytics
        from datetime import date
        target_date = date.today() - timedelta(days=1)  # Use yesterday's date for most recent complete data
        
        # Extract user timezone
        user_timezone = get_user_field(user_record, 'profile.timezone')
        
        # Debug: Check what settings we're passing
        # Force search_all_worksheets for inventory age analysis to get complete purchase history
        user_settings = {
            'access_token': (get_user_field(config_user_record, 'integrations.google.tokens') or {}).get('access_token'),
            'google_tokens': get_user_google_tokens(config_user_record) or {},  # Add the full google_tokens dict
            'sheet_id': get_user_field(config_user_record, 'files.sheet_id'),
            'worksheet_title': get_user_field(config_user_record, 'integrations.google.worksheet_title'),
            'column_mapping': get_user_column_mapping(config_user_record),
            'amazon_lead_time_days': get_user_field(config_user_record, 'settings.amazon_lead_time_days') or config_user_record.get('amazon_lead_time_days', 90),
            'search_all_worksheets': True,  # Force all worksheets for inventory age analysis
            'enable_source_links': True,  # Enable Google Sheets integration
            'discord_id': discord_id
        }
        
        print(f"DEBUG - Inventory Age Analysis user settings: sheet_id={bool(user_settings.get('sheet_id'))}, google_tokens={bool(get_user_field(config_user_record, 'integrations.google.tokens'))}")
        
        # Get COGS data directly from email for all products
        cogs_data = fetch_sellerboard_cogs_data_from_email(discord_id)
        
        if not cogs_data:
            return jsonify({
                'error': 'No COGS data available',
                'message': 'Unable to retrieve COGS data from Sellerboard emails. Please ensure Sellerboard automation emails are being received.'
            }), 500
        
        print(f"Using COGS file as primary data source: {cogs_data['filename']} with {cogs_data['total_products']} products")
        
        # Still need orders analysis for sales data
        from orders_analysis import OrdersAnalysis
        analyzer = OrdersAnalysis(orders_url=orders_url, stock_url=stock_url, cogs_url=None, discord_id=discord_id)
        analysis = analyzer.analyze(
            for_date=target_date,
            user_timezone=user_timezone,
            user_settings=user_settings,
            preserve_purchase_history=True  # Keep all purchase history for inventory age analysis
        )
        
        if not analysis:
            return jsonify({
                'error': 'No sales data available',
                'message': 'Unable to retrieve sales data for analysis.'
            }), 500
        
        # Initialize age analyzer
        age_analyzer = InventoryAgeAnalyzer()
        
        # Use both COGS and stock files strategically
        import pandas as pd
        cogs_df = pd.DataFrame(cogs_data['data'])
        
        # Filter COGS data to exclude hidden products
        asin_col = cogs_data['asin_column']
        
        # Check for Hide column and filter out hidden products
        hide_col = None
        for col in cogs_df.columns:
            if 'hide' in col.lower():
                hide_col = col
                break
        
        if hide_col:
            cogs_df_filtered = cogs_df[cogs_df[hide_col] != 'Yes']
            print(f"Filtered out {len(cogs_df) - len(cogs_df_filtered)} hidden products from COGS file")
        else:
            cogs_df_filtered = cogs_df
            print("No Hide column found in COGS file")
        
        # Get stock data from stock file for accurate stock quantities
        stock_df = analyzer.download_csv(stock_url)
        stock_info = analyzer.get_stock_info(stock_df)
        
        print(f"COGS file: {len(cogs_df_filtered)} products (after filtering)")
        print(f"Stock file: {len(stock_info)} products")
        
        # Use the enhanced_analytics that was already correctly created by OrdersAnalysis
        # (The previous code here was overwriting the correctly calculated enhanced_analytics from analysis)
        enhanced_analytics = analysis.get('enhanced_analytics', {}) if analysis else {}
        
        # Get other analysis data for compatibility
        restock_alerts = analysis.get('restock_alerts', {}) if analysis else {}
        purchase_insights = analysis.get('purchase_insights', {}) if analysis else {}
        
        print(f"Combined COGS + Stock data: {len(enhanced_analytics)} total products")
        in_stock_count = sum(1 for data in enhanced_analytics.values() if data['current_stock'] > 0)
        print(f"  - {in_stock_count} products with stock > 0")
        print(f"  - {len(enhanced_analytics) - in_stock_count} products out of stock or unknown")
        
        # Verify we have the same data structure as Smart Restock Recommendations
        print(f"DEBUG - Inventory age analysis:")
        print(f"  - enhanced_analytics: {len(enhanced_analytics)} products")
        print(f"  - restock_alerts: {len(restock_alerts)} products")
        
        # Compare current_stock values from both sources for first 3 products
        if enhanced_analytics and restock_alerts:
            print("DEBUG - Current stock comparison (enhanced_analytics vs restock_alerts):")
            common_asins = set(enhanced_analytics.keys()) & set(restock_alerts.keys())
            for i, asin in enumerate(list(common_asins)[:3]):
                enhanced_stock = enhanced_analytics[asin].get('restock', {}).get('current_stock', 'N/A')
                alert_stock = restock_alerts[asin].get('current_stock', 'N/A')
                print(f"  {asin}: enhanced={enhanced_stock}, alert={alert_stock}")
        print()
        
        # Download raw orders data for velocity inference using the same analyzer
        orders_df = analyzer.download_csv(orders_url)
        
        # Calculate velocity for each product and add to enhanced_analytics
        for asin in enhanced_analytics.keys():
            try:
                velocity_data = analyzer.calculate_enhanced_velocity(asin, orders_df, target_date, user_timezone)
                enhanced_analytics[asin]['velocity'] = velocity_data
                
                # Calculate restock data with monthly_purchase_adjustment
                stock_info_for_asin = stock_info.get(asin, {})
                restock_data = analyzer.calculate_optimal_restock_quantity(
                    asin, velocity_data, stock_info_for_asin, 
                    lead_time_days=90, purchase_analytics=purchase_insights
                )
                
                # Update restock data with monthly_purchase_adjustment
                enhanced_analytics[asin]['restock'].update({
                    'monthly_purchase_adjustment': restock_data.get('monthly_purchase_adjustment', 0),
                    'suggested_quantity': restock_data.get('suggested_quantity', 0)
                })
                
            except Exception as ve:
                print(f"Warning: Failed to calculate velocity/restock for {asin}: {ve}")
                enhanced_analytics[asin]['velocity'] = {'weighted_velocity': 0}
                enhanced_analytics[asin]['restock']['monthly_purchase_adjustment'] = 0
        
        # Debug: Show what stock values we're actually getting
        print(f"DEBUG - Using enhanced_analytics data (same analyzer as Smart Restock)")
        print(f"DEBUG - Sample stock values from enhanced_analytics:")
        for i, (asin, data) in enumerate(list(enhanced_analytics.items())[:5]):
            stock_value = data.get('restock', {}).get('current_stock', 'NOT_FOUND')
            print(f"  {asin}: {stock_value} units")
        
        age_analysis_source = enhanced_analytics
        
        # Perform age analysis using the same current_stock values as Smart Restock
        age_analysis = age_analyzer.analyze_inventory_age(
            enhanced_analytics=age_analysis_source,
            purchase_insights=purchase_insights,
            stock_data=stock_info,
            orders_data=orders_df
        )
        
        # Get products needing action
        action_items = age_analyzer.get_products_needing_action(age_analysis, enhanced_analytics)
        
        # Add action items to response
        age_analysis['action_items'] = action_items[:20]  # Top 20 items needing action
        age_analysis['total_action_items'] = len(action_items)
        
        # CRITICAL: Include enhanced_analytics so frontend can access stock values and product names
        age_analysis['enhanced_analytics'] = enhanced_analytics
        
        # Debug enhanced_analytics before JSON serialization
        sample_asins = ["B004ZAKHHM", "B00F99VIUS", "B009I4G5JO"]
        for asin in sample_asins:
            if asin in enhanced_analytics:
                stock_val = enhanced_analytics[asin].get('current_stock', 'NOT_FOUND')
                print(f"DEBUG final response - {asin}: current_stock = {stock_val}")
            else:
                print(f"DEBUG final response - {asin}: NOT FOUND in enhanced_analytics")
        
        # Debug: Log what we're returning
        print(f"DEBUG - Final response structure keys: {list(age_analysis.keys())}")
        print(f"DEBUG - Final response structure type: {type(age_analysis)}")
        if 'age_analysis' in age_analysis:
            print(f"DEBUG - Number of products in age_analysis: {len(age_analysis['age_analysis'])}")
            print(f"DEBUG - First 3 ASINs in age_analysis: {list(age_analysis['age_analysis'].keys())[:3]}")
        if 'summary' in age_analysis:
            print(f"DEBUG - Summary keys: {list(age_analysis['summary'].keys())}")
        
        # Debug: Log the actual JSON structure being returned
        import json
        
        # Sanitize the entire response to ensure JSON compatibility
        try:
            sanitized_age_analysis = sanitize_for_json(age_analysis)
            
            # Check response size after sanitization
            json_str = json.dumps(sanitized_age_analysis, indent=2)
            response_size = len(json_str)
            print(f"DEBUG - JSON response size after sanitization: {response_size} bytes")
            print(f"DEBUG - JSON response preview (first 500 chars): {json_str[:500]}")
            
            # Check if response is unexpectedly large
            if response_size > 50000:  # More than 50KB is suspicious for this endpoint
                print(f"WARNING - Response size is unusually large: {response_size} bytes")
                
                # Try to identify what's causing the large response
                for key, value in sanitized_age_analysis.items():
                    try:
                        key_size = len(json.dumps(value))
                        print(f"DEBUG - {key} size: {key_size} bytes")
                        if key_size > 10000:  # Log details for large sections
                            if isinstance(value, dict):
                                print(f"DEBUG - {key} contains {len(value)} items")
                            elif isinstance(value, list):
                                print(f"DEBUG - {key} contains {len(value)} items")
                    except Exception as e:
                        print(f"DEBUG - {key} serialization error: {str(e)}")
            
            # Final check before returning
            if 'age_analysis' not in sanitized_age_analysis:
                print(f"ERROR - Missing 'age_analysis' key in response. Keys found: {list(sanitized_age_analysis.keys())}")
            
            # Check if the response looks like an array (numeric keys)
            if all(key.isdigit() for key in list(str(k) for k in sanitized_age_analysis.keys())[:10]):
                print(f"ERROR - Response has numeric keys, suggesting DataFrame serialization!")
                print(f"First 10 keys: {list(sanitized_age_analysis.keys())[:10]}")
                return jsonify({
                    'error': 'Invalid response structure',
                    'message': 'Response contains array-like structure instead of expected format',
                    'debug_keys': list(sanitized_age_analysis.keys())[:10]
                }), 500
            
            # Try returning raw JSON response to bypass any jsonify issues
            json_string = json.dumps(sanitized_age_analysis)
            print(f"DEBUG - JSON string first 500 chars: {json_string[:500]}")
            print(f"DEBUG - JSON string length: {len(json_string)}")
            
            # Check if the JSON string looks correct
            parsed_check = json.loads(json_string)
            print(f"DEBUG - Parsed JSON keys: {list(parsed_check.keys())}")
            
            # If response is too large, try to reduce it
            if len(json_string) > 150000:  # 150KB threshold
                print("WARNING - Response too large, reducing data")
                
                # Keep only essential data for each product
                reduced_age_analysis = {}
                for asin, data in sanitized_age_analysis.get('age_analysis', {}).items():
                    reduced_age_analysis[asin] = {
                        'estimated_age_days': data.get('estimated_age_days'),
                        'age_category': data.get('age_category'),
                        'confidence_score': data.get('confidence_score'),
                        'recommendations': data.get('recommendations', [])[:1]  # Keep only first recommendation
                    }
                
                reduced_response = {
                    'age_analysis': reduced_age_analysis,
                    'summary': sanitized_age_analysis.get('summary'),
                    'age_categories': sanitized_age_analysis.get('age_categories'),
                    'generated_at': sanitized_age_analysis.get('generated_at'),
                    'total_action_items': sanitized_age_analysis.get('total_action_items'),
                    'enhanced_analytics': sanitized_age_analysis.get('enhanced_analytics'),  # Include for stock/names
                    'reduced': True  # Flag to indicate reduced response
                }
                
                json_string = json.dumps(reduced_response)
                print(f"DEBUG - Reduced JSON string length: {len(json_string)}")
            
            response = make_response(json_string)
            response.headers['Content-Type'] = 'application/json'
            return response
                        
        except ValueError as sanitize_error:
            print(f"ERROR - Data sanitization failed: {str(sanitize_error)}")
            return jsonify({
                'error': 'Response contains non-serializable data structures',
                'message': str(sanitize_error),
                'suggestion': 'Check for pandas DataFrames or other non-JSON types in the response data'
            }), 500
        except Exception as json_error:
            print(f"ERROR - JSON serialization failed: {str(json_error)}")
            # Try to debug what exactly is causing the serialization failure
            try:
                # Test each top-level key individually to identify the problematic data
                problematic_keys = []
                for key, value in age_analysis.items():
                    try:
                        json.dumps(value)
                    except Exception as key_error:
                        problematic_keys.append(f"{key}: {str(key_error)}")
                
                print(f"DEBUG - Problematic keys: {problematic_keys}")
                return jsonify({
                    'error': 'Response serialization failed',
                    'message': 'The response data contains non-serializable objects',
                    'problematic_keys': problematic_keys
                }), 500
            except Exception:
                return jsonify({
                    'error': 'Response serialization failed',
                    'message': 'The response data contains non-serializable objects'
                }), 500
        
    except Exception as e:
        import traceback
        print(f"Error in inventory age analysis: {e}")
        print(f"Traceback: {traceback.format_exc()}")
        
        # Store error info for debug endpoint
        from orders_analysis import _global_worksheet_debug
        _global_worksheet_debug['auth_endpoint_error'] = {
            'error': str(e),
            'error_type': type(e).__name__,
            'traceback': traceback.format_exc(),
            'timestamp': datetime.now().isoformat()
        }
        
        return jsonify({
            'error': str(e),
            'message': 'Failed to perform inventory age analysis',
            'traceback': traceback.format_exc(),
            'error_type': type(e).__name__
        }), 500

@app.route('/api/analytics/inventory-age/filter')
@login_required 
def filter_inventory_by_age():
    """Filter inventory by age categories"""
    try:
        discord_id = session['discord_id']
        categories = request.args.getlist('categories')  # e.g., ['aged', 'old', 'ancient']
        
        if not categories:
            return jsonify({'error': 'No age categories specified'}), 400
        
        # Get full age analysis (could be cached in future)
        # For now, redirect to main endpoint with filter parameter
        # This is a placeholder for a more optimized filtering endpoint
        
        return jsonify({
            'message': 'Use the main inventory-age endpoint and filter client-side for now',
            'requested_categories': categories
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/demo/analytics', methods=['GET'])
def get_demo_analytics():
    """Get demo analytics without authentication"""
    if not DEMO_MODE:
        return jsonify({'error': 'Demo mode not enabled'}), 403
    
    from datetime import date
    target_date = date.today() - timedelta(days=1)
    return jsonify(get_dummy_analytics_data(target_date))

@app.route('/api/debug/stock-analysis', methods=['GET'])
def debug_stock_analysis():
    """Debug endpoint to analyze stock data loading issues"""
    try:
        # Check if authenticated
        if 'discord_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
            
        discord_id = session['discord_id']
        user_record = get_user_record(discord_id)
        
        if not user_record:
            return jsonify({'error': 'User not found'}), 404
            
        # Handle parent-child relationship
        config_user_record = user_record
        parent_user_id = user_record.get('parent_user_id')
        if parent_user_id:
            parent_record = get_user_record(parent_user_id)
            if parent_record:
                config_user_record = parent_record
                
        # Get stock URL
        stock_url = get_user_sellerboard_stock_url(config_user_record)
        if not stock_url:
            return jsonify({'error': 'Stock URL not configured'}), 400
            
        # Load stock data
        from orders_analysis import OrdersAnalysis
        analyzer = OrdersAnalysis(orders_url="dummy", stock_url=stock_url)
        
        # Download stock CSV
        import pandas as pd
        stock_df = analyzer.download_csv(stock_url)
        
        # Get stock info
        stock_info = analyzer.get_stock_info(stock_df)
        
        # Analyze the data
        debug_info = {
            'stock_url_configured': bool(stock_url),
            'stock_df_shape': list(stock_df.shape) if stock_df is not None else None,
            'stock_df_columns': list(stock_df.columns) if stock_df is not None else None,
            'stock_info_count': len(stock_info),
            'sample_asins': {},
            'non_zero_stock_asins': [],
            'zero_stock_asins': [],
            'column_analysis': {}
        }
        
        # Check if FBA/FBM Stock column exists
        if stock_df is not None:
            fba_stock_columns = [col for col in stock_df.columns if 'stock' in col.lower()]
            debug_info['stock_related_columns'] = fba_stock_columns
            
            # Check specific column
            if 'FBA/FBM Stock' in stock_df.columns:
                debug_info['column_analysis']['FBA/FBM Stock'] = {
                    'exists': True,
                    'dtype': str(stock_df['FBA/FBM Stock'].dtype),
                    'sample_values': [float(x) if pd.notna(x) else None for x in stock_df['FBA/FBM Stock'].head(10)],
                    'unique_count': int(stock_df['FBA/FBM Stock'].nunique()),
                    'null_count': int(stock_df['FBA/FBM Stock'].isnull().sum())
                }
        
        # Sample some ASINs from stock_info
        for i, (asin, info) in enumerate(list(stock_info.items())[:10]):
            stock_val = info.get('FBA/FBM Stock', 'NOT FOUND')
            debug_info['sample_asins'][asin] = {
                'FBA/FBM Stock': float(stock_val) if isinstance(stock_val, (int, float)) and pd.notna(stock_val) else str(stock_val),
                'extracted_stock': float(analyzer.extract_current_stock(info, debug_asin=asin)),
                'all_columns': list(info.keys())[:5]  # First 5 columns
            }
            
        # Find ASINs with non-zero stock
        for asin, info in stock_info.items():
            stock = analyzer.extract_current_stock(info)
            if stock > 0:
                debug_info['non_zero_stock_asins'].append({
                    'asin': asin,
                    'stock': float(stock),
                    'title': info.get('Title', 'Unknown')[:50]
                })
            elif stock == 0:
                debug_info['zero_stock_asins'].append(asin)
                
        # Limit lists for response size
        debug_info['non_zero_stock_asins'] = debug_info['non_zero_stock_asins'][:20]
        debug_info['zero_stock_asins'] = debug_info['zero_stock_asins'][:20]
        debug_info['total_non_zero_stock'] = len([1 for a, i in stock_info.items() if analyzer.extract_current_stock(i) > 0])
        debug_info['total_zero_stock'] = len([1 for a, i in stock_info.items() if analyzer.extract_current_stock(i) == 0])
        
        return jsonify(debug_info)
        
    except Exception as e:
        import traceback
        return jsonify({
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

@app.route('/api/debug/all-product-analytics', methods=['GET'])
def debug_all_product_analytics():
    """Debug endpoint to analyze All Product Analytics data flow"""
    try:
        # Check authentication status
        auth_status = {
            'session_exists': 'discord_id' in session,
            'discord_id': session.get('discord_id', 'Not logged in'),
            'session_keys': list(session.keys())
        }
        # Try to get demo data structure
        demo_response = None
        try:
            import requests
            demo_response = requests.get('http://localhost:5000/api/demo/analytics/inventory-age').json()
        except Exception as e:
            demo_response = {'error': str(e)}
        
        # Try to get real endpoint worksheet debug info
        worksheet_debug = None
        try:
            # Import the global debug info
            from orders_analysis import _global_worksheet_debug
            if _global_worksheet_debug:
                worksheet_debug = _global_worksheet_debug.copy()
            else:
                worksheet_debug = {
                    'note': 'No recent worksheet processing found',
                    'instruction': 'Refresh All Product Analytics page while logged in to populate this data'
                }
        except Exception as e:
            worksheet_debug = {'error': str(e)}

        # Analyze the structure
        debug_info = {
            'auth_status': auth_status,
            'demo_endpoint_status': 'success' if 'age_analysis' in demo_response else 'failed',
            'demo_has_enhanced_analytics': 'enhanced_analytics' in demo_response,
            'demo_enhanced_analytics_sample': {},
            'demo_amount_ordered_values': {},
            'worksheet_debug_info': worksheet_debug,
            'search_all_worksheets_info': {
                'inventory_age_force_setting': True,
                'purchase_analytics_method': '_analyze_recent_2_months_purchases',
                'expected_behavior': 'Now searches ALL worksheets within last 2 months by date range instead of limiting to 2 worksheets'
            },
            'timestamp': datetime.now().isoformat()
        }
        
        if 'enhanced_analytics' in demo_response:
            ea = demo_response['enhanced_analytics']
            debug_info['demo_enhanced_analytics_count'] = len(ea)
            
            # Sample first 3 ASINs
            for asin in list(ea.keys())[:3]:
                asin_data = ea[asin]
                debug_info['demo_enhanced_analytics_sample'][asin] = {
                    'product_name': asin_data.get('product_name'),
                    'current_stock': asin_data.get('current_stock'),
                    'velocity_weighted': asin_data.get('velocity', {}).get('weighted_velocity'),
                    'restock_structure': list(asin_data.get('restock', {}).keys()),
                    'monthly_purchase_adjustment': asin_data.get('restock', {}).get('monthly_purchase_adjustment')
                }
                debug_info['demo_amount_ordered_values'][asin] = asin_data.get('restock', {}).get('monthly_purchase_adjustment', 'N/A')
        
        return jsonify(debug_info)
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        })

@app.route('/api/test/inventory-age-available', methods=['GET'])
def test_inventory_age_available():
    """Simple test endpoint to verify inventory-age routes are deployed"""
    return jsonify({
        'message': 'Inventory age endpoints are available',
        'routes_available': [
            '/api/analytics/inventory-age',
            '/api/demo/analytics/inventory-age',
            '/api/analytics/inventory-age/filter'
        ],
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/demo/analytics/inventory-age', methods=['GET'])
def get_demo_inventory_age_analysis():
    """Get demo inventory age analysis without authentication"""
    # Always allow demo data for inventory age analysis
    # if not DEMO_MODE:
    #     return jsonify({'error': 'Demo mode not enabled'}), 403
    
    # Generate demo inventory age data
    demo_asins = ['B08N5WRWNW', 'B07XJ8C8F7', 'B09KMXJQ9R', 'B08ABC123', 'B09DEF456', 'B07GHI789']
    
    demo_product_names = {
        'B08N5WRWNW': 'Wireless Bluetooth Earbuds Pro',
        'B07XJ8C8F7': 'Smart LED Strip Lights 16ft',
        'B09KMXJQ9R': 'USB-C Fast Charging Cable 6ft',
        'B08ABC123': 'Portable Power Bank 20000mAh',
        'B09DEF456': 'Laptop Stand Adjustable Aluminum',
        'B07GHI789': 'Gaming Mouse RGB Wireless'
    }
    
    age_categories = {
        'fresh': {'min': 0, 'max': 30, 'label': 'Fresh (0-30 days)', 'color': '#10b981'},
        'moderate': {'min': 31, 'max': 90, 'label': 'Moderate (31-90 days)', 'color': '#f59e0b'}, 
        'aged': {'min': 91, 'max': 180, 'label': 'Aged (91-180 days)', 'color': '#f97316'},
        'old': {'min': 181, 'max': 365, 'label': 'Old (181-365 days)', 'color': '#dc2626'},
        'ancient': {'min': 366, 'max': 999999, 'label': 'Ancient (365+ days)', 'color': '#7c2d12'}
    }
    
    import random
    age_analysis = {}
    categories_count = {cat: 0 for cat in age_categories.keys()}
    action_items = []
    
    for i, asin in enumerate(demo_asins):
        # Generate varied age data for demo
        if i == 0:  # Fresh
            age_days = random.randint(5, 25)
            category = 'fresh'
        elif i == 1:  # Moderate
            age_days = random.randint(40, 80)
            category = 'moderate'
        elif i == 2:  # Aged
            age_days = random.randint(120, 160)
            category = 'aged'
        elif i == 3:  # Old
            age_days = random.randint(220, 300)
            category = 'old'
        elif i == 4:  # Ancient
            age_days = random.randint(400, 500)
            category = 'ancient'
        else:
            age_days = random.randint(15, 200)
            category = 'moderate' if age_days < 90 else 'aged'
        
        categories_count[category] += 1
        
        recommendations = []
        if category == 'fresh':
            recommendations = ["✅ Fresh inventory - good restocking timing"]
        elif category == 'moderate':
            recommendations = ["⚠️ Monitor closely - consider sales acceleration tactics"]
        elif category == 'aged':
            recommendations = ["🟡 Consider discount promotions to move aged inventory", "📦 High aged stock - prioritize liquidation"]
        elif category == 'old':
            recommendations = ["🔴 Urgent: Implement aggressive pricing strategies", "💰 Consider bundling or promotional campaigns"]
        elif category == 'ancient':
            recommendations = ["🚨 Critical: Ancient inventory requires immediate action", "🏷️ Deep discount or clearance sale recommended"]
        
        age_analysis[asin] = {
            'estimated_age_days': age_days,
            'age_category': category,
            'confidence_score': random.uniform(0.6, 0.9),
            'data_sources': ['demo_purchase_data', 'demo_velocity_inference'],
            'age_range': {'min': age_days - 5, 'max': age_days + 5, 'variance': 10},
            'details': {
                'purchase_based_age': age_days + random.randint(-10, 10),
                'velocity_based_age': age_days + random.randint(-15, 15),
            },
            'recommendations': recommendations
        }
        
        # Create action items for aged/old/ancient inventory
        if category in ['aged', 'old', 'ancient']:
            urgency_scores = {'aged': 0.6, 'old': 0.8, 'ancient': 1.0}
            current_stock = random.randint(20, 200)
            velocity = random.uniform(0.5, 5.0)
            
            action_items.append({
                'asin': asin,
                'product_name': demo_product_names.get(asin, f'Demo Product {asin}'),
                'age_days': age_days,
                'age_category': category,
                'current_stock': current_stock,
                'velocity': velocity,
                'urgency_score': urgency_scores[category] + random.uniform(-0.1, 0.1),
                'estimated_value': current_stock * random.uniform(10, 50),
                'recommendations': recommendations,
                'days_to_sell': current_stock / velocity if velocity > 0 else 999999
            })
    
    # Sort action items by urgency
    action_items.sort(key=lambda x: x['urgency_score'], reverse=True)
    
    # Create enhanced_analytics for frontend compatibility
    enhanced_analytics = {}
    for asin in demo_asins:
        current_stock = random.randint(10, 200)
        enhanced_analytics[asin] = {
            'product_name': demo_product_names.get(asin, f'Demo Product {asin}'),
            'current_stock': current_stock,
            'velocity': {
                'weighted_velocity': random.uniform(0.5, 5.0)
            },
            'restock': {
                'current_stock': current_stock,
                'monthly_purchase_adjustment': random.randint(0, 50),
                'source': 'demo_data'
            }
        }
    
    return jsonify({
        'age_analysis': age_analysis,
        'summary': {
            'total_products': len(demo_asins),
            'products_with_age_data': len(demo_asins),
            'coverage_percentage': 100.0,
            'average_age_days': sum(data['estimated_age_days'] for data in age_analysis.values()) // len(age_analysis),
            'median_age_days': 120,
            'average_confidence': 0.75,
            'categories_breakdown': categories_count,
            'insights': [
                "⚠️ High percentage of aged inventory - consider liquidation strategies",
                "🚨 1 product with ancient inventory needs immediate attention",
                "📊 Good confidence in age estimates based on purchase tracking"
            ],
            'oldest_inventory_days': max(data['estimated_age_days'] for data in age_analysis.values()),
            'newest_inventory_days': min(data['estimated_age_days'] for data in age_analysis.values())
        },
        'age_categories': age_categories,
        'action_items': action_items[:20],
        'total_action_items': len(action_items),
        'generated_at': datetime.now().isoformat(),
        'demo_mode': True,
        'enhanced_analytics': enhanced_analytics
    })

@app.route('/api/demo/product-image/<asin>/simple', methods=['GET'])
def get_demo_product_image_simple(asin):
    """Simple demo product image endpoint without authentication"""
    if not DEMO_MODE:
        return jsonify({'error': 'Demo mode not enabled'}), 403
    
    # Return placeholder image URL
    placeholder_url = f"https://via.placeholder.com/200x200/4f46e5/ffffff?text={asin[:6]}"
    
    try:
        import requests
        img_response = requests.get(placeholder_url, timeout=5, stream=True)
        img_response.raise_for_status()
        
        response = make_response(img_response.content)
        response.headers['Content-Type'] = 'image/png'
        response.headers['Cache-Control'] = 'public, max-age=3600'
        return response
    except:
        return '', 404

@app.route('/api/demo/disable', methods=['POST'])
def disable_demo_mode():
    """Disable demo mode"""
    global DEMO_MODE
    DEMO_MODE = False
    
    # Clear all caches when disabling demo mode
    clear_all_caches_for_demo_toggle()
    
    return jsonify({
        'demo_mode': False,
        'message': 'Demo mode disabled - using real data'
    })

# ===== ADMIN USER GROUPS API ENDPOINTS =====

@app.route('/api/admin/user-features', methods=['GET'])
@admin_required  
def get_all_user_features():
    """Get all user feature access permissions"""
    try:
        # Get users from config (S3)
        users = get_users_config()
        
        # Get all user feature access from database
        cursor.execute('''
            SELECT discord_id, feature_key, has_access
            FROM user_feature_access
            WHERE has_access = 1
        ''')
        
        user_features = {}
        for user in users:
            user_features[get_user_discord_id(user)] = {}
            
        for row in cursor.fetchall():
            discord_id, feature_key, has_access = row
            if discord_id not in user_features:
                user_features[discord_id] = {}
            user_features[discord_id][feature_key] = bool(has_access)
        
        response = jsonify({'user_features': user_features})
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    except Exception as e:
        return jsonify({'error': f'Error fetching user features: {str(e)}'}), 500

@app.route('/api/admin/user-features', methods=['POST'])
@admin_required
def grant_user_feature_access():
    """Grant a user access to a specific feature"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        feature_key = data.get('feature_key')
        discord_id = session['discord_id']
        
        if not user_id or not feature_key:
            return jsonify({'error': 'User ID and feature key required'}), 400
        
        cursor.execute('''
            INSERT OR REPLACE INTO user_feature_access (discord_id, feature_key, has_access, granted_by)
            VALUES (?, ?, ?, ?)
        ''', (user_id, feature_key, True, discord_id))
        
        conn.commit()
        
        # Also store in S3 users.json for persistence
        users = get_users_config()
        for user in users:
            if get_user_field(user, 'identity.discord_id') == user_id:
                feature_perms = get_user_field(user, 'account.feature_permissions') or {}
                feature_perms[feature_key] = {
                    'has_access': True,
                    'granted_by': discord_id,
                    'granted_at': datetime.utcnow().isoformat()
                }
                set_user_field(user, 'account.feature_permissions', feature_perms)
                update_users_config(users)
                break
        
        return jsonify({'message': 'Feature access granted successfully'})
    except Exception as e:
        return jsonify({'error': f'Error granting feature access: {str(e)}'}), 500

@app.route('/api/admin/user-features/<user_id>/<feature_key>', methods=['DELETE'])
@admin_required
def revoke_user_feature_access(user_id, feature_key):
    """Revoke a user's access to a specific feature"""
    try:
        cursor.execute('''
            DELETE FROM user_feature_access 
            WHERE discord_id = ? AND feature_key = ?
        ''', (user_id, feature_key))
        
        conn.commit()
        
        # Also remove from S3 users.json for persistence
        users = get_users_config()
        for user in users:
            if get_user_field(user, 'identity.discord_id') == user_id:
                feature_perms = get_user_field(user, 'account.feature_permissions') or {}
                if feature_key in feature_perms:
                    del feature_perms[feature_key]
                    set_user_field(user, 'account.feature_permissions', feature_perms)
                    update_users_config(users)
                break
        
        return jsonify({'message': 'Feature access revoked successfully'})
    except Exception as e:
        return jsonify({'error': f'Error revoking feature access: {str(e)}'}), 500

@app.route('/api/admin/features/<feature_key>', methods=['PUT'])
@admin_required
def update_feature_settings(feature_key):
    """Update feature settings (beta status, etc)"""
    try:
        data = request.get_json()
        is_beta = data.get('is_beta')
        
        if is_beta is not None:
            cursor.execute('''
                UPDATE features SET is_beta = ? WHERE feature_key = ?
            ''', (is_beta, feature_key))
            conn.commit()
            
        return jsonify({'message': 'Feature settings updated successfully'})
    except Exception as e:
        return jsonify({'error': f'Error updating feature settings: {str(e)}'}), 500

# ===== USER GROUPS API ENDPOINTS =====

@app.route('/api/admin/groups', methods=['GET'])
@admin_required  
def get_all_groups():
    """Get all user groups"""
    try:
        cursor.execute('''
            SELECT group_key, group_name, description, created_by, created_at
            FROM user_groups
            ORDER BY group_name
        ''')
        
        groups = []
        for row in cursor.fetchall():
            group_key, group_name, description, created_by, created_at = row
            
            # Get member count
            cursor.execute('''
                SELECT COUNT(*) FROM user_group_members WHERE group_key = ?
            ''', (group_key,))
            member_count = cursor.fetchone()[0]
            
            groups.append({
                'group_key': group_key,
                'group_name': group_name,
                'description': description,
                'created_by': created_by,
                'created_at': created_at,
                'member_count': member_count
            })
        
        return jsonify({'groups': groups})
    except Exception as e:
        return jsonify({'error': f'Error fetching groups: {str(e)}'}), 500

@app.route('/api/admin/groups', methods=['POST'])
@admin_required
def create_group():
    """Create a new user group"""
    try:
        data = request.get_json()
        group_key = data.get('group_key')
        group_name = data.get('group_name')
        description = data.get('description', '')
        discord_id = session['discord_id']
        
        if not group_key or not group_name:
            return jsonify({'error': 'Group key and name required'}), 400
        
        cursor.execute('''
            INSERT INTO user_groups (group_key, group_name, description, created_by)
            VALUES (?, ?, ?, ?)
        ''', (group_key, group_name, description, discord_id))
        
        conn.commit()
        return jsonify({'message': 'Group created successfully'})
    except Exception as e:
        return jsonify({'error': f'Error creating group: {str(e)}'}), 500

@app.route('/api/admin/groups/<group_key>/members', methods=['GET'])
@admin_required
def get_group_members(group_key):
    """Get members of a specific group"""
    try:
        # Get all users from config
        users = get_users_config()
        users_dict = {get_user_discord_id(user): user for user in users}
        
        # Get group members from database
        cursor.execute('''
            SELECT discord_id, added_at
            FROM user_group_members
            WHERE group_key = ?
        ''', (group_key,))
        
        members = []
        for row in cursor.fetchall():
            discord_id, added_at = row
            if discord_id in users_dict:
                user = users_dict[discord_id]
                members.append({
                    'discord_id': discord_id,
                    'discord_username': user.get('discord_username', 'Unknown'),
                    'email': get_user_field(user, 'identity.email') or '',
                    'added_at': added_at
                })
        
        return jsonify({'members': members})
    except Exception as e:
        return jsonify({'error': f'Error fetching group members: {str(e)}'}), 500

@app.route('/api/admin/groups/<group_key>/members', methods=['POST'])
@admin_required
def add_group_member(group_key):
    """Add a user to a group"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        discord_id = session['discord_id']
        
        if not user_id:
            return jsonify({'error': 'User ID required'}), 400
        
        cursor.execute('''
            INSERT OR IGNORE INTO user_group_members (discord_id, group_key, added_by)
            VALUES (?, ?, ?)
        ''', (user_id, group_key, discord_id))
        
        conn.commit()
        return jsonify({'message': 'User added to group successfully'})
    except Exception as e:
        return jsonify({'error': f'Error adding user to group: {str(e)}'}), 500

@app.route('/api/admin/groups/<group_key>/members/<user_id>', methods=['DELETE'])
@admin_required
def remove_group_member(group_key, user_id):
    """Remove a user from a group"""
    try:
        cursor.execute('''
            DELETE FROM user_group_members 
            WHERE group_key = ? AND discord_id = ?
        ''', (group_key, user_id))
        
        conn.commit()
        return jsonify({'message': 'User removed from group successfully'})
    except Exception as e:
        return jsonify({'error': f'Error removing user from group: {str(e)}'}), 500

@app.route('/api/admin/groups/<group_key>/features', methods=['GET'])
@admin_required
def get_group_features(group_key):
    """Get feature access for a specific group"""
    try:
        cursor.execute('''
            SELECT feature_key, has_access, granted_at
            FROM group_feature_access
            WHERE group_key = ?
            ORDER BY feature_key
        ''', (group_key,))
        
        features = {}
        for row in cursor.fetchall():
            feature_key, has_access, granted_at = row
            features[feature_key] = {
                'has_access': bool(has_access),
                'granted_at': granted_at
            }
        
        return jsonify({'features': features})
    except Exception as e:
        return jsonify({'error': f'Error fetching group features: {str(e)}'}), 500

@app.route('/api/admin/groups/<group_key>/features', methods=['POST'])
@admin_required
def grant_group_feature_access(group_key):
    """Grant a group access to a specific feature"""
    try:
        data = request.get_json()
        feature_key = data.get('feature_key')
        discord_id = session['discord_id']
        
        if not feature_key:
            return jsonify({'error': 'Feature key required'}), 400
        
        cursor.execute('''
            INSERT OR REPLACE INTO group_feature_access (group_key, feature_key, has_access, granted_by)
            VALUES (?, ?, ?, ?)
        ''', (group_key, feature_key, True, discord_id))
        
        conn.commit()
        return jsonify({'message': 'Group feature access granted successfully'})
    except Exception as e:
        return jsonify({'error': f'Error granting group feature access: {str(e)}'}), 500

@app.route('/api/admin/groups/<group_key>/features/<feature_key>', methods=['DELETE'])
@admin_required
def revoke_group_feature_access(group_key, feature_key):
    """Revoke a group's access to a specific feature"""
    try:
        cursor.execute('''
            DELETE FROM group_feature_access 
            WHERE group_key = ? AND feature_key = ?
        ''', (group_key, feature_key))
        
        conn.commit()
        return jsonify({'message': 'Group feature access revoked successfully'})
    except Exception as e:
        return jsonify({'error': f'Error revoking group feature access: {str(e)}'}), 500

# ================================
# Email Monitoring API Endpoints
# ================================

@app.route('/api/email-monitoring/config', methods=['GET'])
@login_required
def get_email_monitoring_config():
    """Get user's email monitoring configuration from S3"""
    try:
        discord_id = session['discord_id']
        
        # Check if user has access to email monitoring feature
        if not has_feature_access(discord_id, 'email_monitoring'):
            return jsonify({'error': 'Access denied to email monitoring feature'}), 403
        
        configs = email_monitoring_manager.get_email_configs(discord_id)
        
        formatted_configs = []
        for config in configs:
            formatted_config = {
                'id': config.get('id'),
                'email_address': config.get('email_address'),
                'auth_type': config.get('auth_type', 'imap'),
                'is_active': config.get('is_active', True),
                'last_checked': config.get('last_checked')
            }
            
            # Add auth-specific fields
            if config.get('auth_type') != 'oauth':
                formatted_config.update({
                    'imap_server': config.get('imap_server'),
                    'imap_port': config.get('imap_port'),
                    'username': config.get('username')
                })
            
            formatted_configs.append(formatted_config)
        
        print(f"🔍 GET email configs for discord_id {discord_id}: found {len(formatted_configs)} configs")
        for config in formatted_configs:
            print(f"  - {config['email_address']} (auth_type: {config['auth_type']})")
        
        return jsonify({'configs': formatted_configs})
        
    except Exception as e:
        print(f"Error fetching email monitoring config: {e}")
        return jsonify({'error': 'Failed to fetch email monitoring configuration'}), 500

# Old IMAP endpoint removed - OAuth is now the only supported method

@app.route('/api/email-monitoring/rules', methods=['GET'])
@login_required
def get_email_monitoring_rules():
    """Get user's email monitoring rules from S3"""
    try:
        discord_id = session['discord_id']
        
        if not has_feature_access(discord_id, 'email_monitoring'):
            return jsonify({'error': 'Access denied to email monitoring feature'}), 403
        
        rules = email_monitoring_manager.get_monitoring_rules(discord_id, active_only=False)
        
        formatted_rules = []
        for rule in rules:
            formatted_rule = {
                'id': rule.get('id'),
                'rule_name': rule.get('rule_name'),
                'sender_filter': rule.get('sender_filter'),
                'subject_filter': rule.get('subject_filter'),
                'content_filter': rule.get('content_filter'),
                'is_active': rule.get('is_active', True)
            }
            formatted_rules.append(formatted_rule)
        
        print(f"📋 GET rules for discord_id {discord_id}: found {len(formatted_rules)} rules")
        for rule in formatted_rules:
            print(f"  - {rule['rule_name']} (ID: {rule['id']})")
        
        return jsonify({'rules': formatted_rules})
        
    except Exception as e:
        print(f"Error fetching email monitoring rules: {e}")
        return jsonify({'error': 'Failed to fetch email monitoring rules'}), 500

@app.route('/api/email-monitoring/rules', methods=['POST'])
@login_required
def create_email_monitoring_rule():
    """Create email monitoring rule in S3"""
    try:
        discord_id = session['discord_id']
        
        if not has_feature_access(discord_id, 'email_monitoring'):
            return jsonify({'error': 'Access denied to email monitoring feature'}), 403
        
        data = request.get_json()
        
        rule = {
            'rule_name': data.get('rule_name'),
            'sender_filter': data.get('sender_filter'),
            'subject_filter': data.get('subject_filter'),
            'content_filter': data.get('content_filter'),
            'is_active': data.get('is_active', True)
        }
        
        rule_id = email_monitoring_manager.add_monitoring_rule(discord_id, rule)
        
        if rule_id:
            return jsonify({'message': 'Email monitoring rule created successfully', 'rule_id': rule_id})
        else:
            return jsonify({'error': 'Failed to create rule'}), 500
        
    except Exception as e:
        print(f"Error creating email monitoring rule: {e}")
        return jsonify({'error': 'Failed to create email monitoring rule'}), 500

@app.route('/api/email-monitoring/rules/<rule_id>', methods=['DELETE'])
@login_required
def delete_email_monitoring_rule(rule_id):
    """Delete email monitoring rule from S3"""
    try:
        discord_id = session['discord_id']
        
        if not has_feature_access(discord_id, 'email_monitoring'):
            return jsonify({'error': 'Access denied to email monitoring feature'}), 403
        
        success = email_monitoring_manager.delete_monitoring_rule(discord_id, rule_id)
        
        if success:
            return jsonify({'message': 'Email monitoring rule deleted successfully'})
        else:
            return jsonify({'error': 'Rule not found'}), 404
            
    except Exception as e:
        print(f"Error deleting email monitoring rule: {e}")
        return jsonify({'error': 'Failed to delete email monitoring rule'}), 500

@app.route('/api/email-monitoring/quick-setup', methods=['POST'])
@login_required
def email_monitoring_quick_setup():
    """Quick setup for Yankee Candle email monitoring using S3"""
    try:
        discord_id = session['discord_id']
        
        if not has_feature_access(discord_id, 'email_monitoring'):
            return jsonify({'error': 'Access denied to email monitoring feature'}), 403
        
        from email_monitor_s3_general import create_yankee_candle_rule
        rule_id = create_yankee_candle_rule(discord_id)
        
        if rule_id:
            return jsonify({'message': 'Yankee Candle monitoring rule created successfully'})
        else:
            return jsonify({'error': 'Failed to create Yankee Candle rule'}), 500
            
    except Exception as e:
        print(f"Error in email monitoring quick setup: {e}")
        return jsonify({'error': 'Failed to create Yankee Candle rule'}), 500

@app.route('/api/email-monitoring/test', methods=['POST'])
@login_required
def test_email_connection():
    """Test email connection"""
    try:
        discord_id = session['discord_id']
        
        if not has_feature_access(discord_id, 'email_monitoring'):
            return jsonify({'error': 'Access denied to email monitoring feature'}), 403
        
        data = request.get_json()
        
        # Import required modules for email testing
        import imaplib
        import email
        
        try:
            # Test IMAP connection
            mail = imaplib.IMAP4_SSL(data['imap_server'], data.get('imap_port', 993))
            mail.login(data['username'], data['password'])
            mail.select('inbox')
            
            # Test search functionality
            result, messages = mail.search(None, 'ALL')
            message_count = len(messages[0].split()) if messages[0] else 0
            
            mail.logout()
            
            return jsonify({
                'success': True,
                'message': f'Connection successful! Found {message_count} messages in inbox.',
                'message_count': message_count
            })
            
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Connection failed: {str(e)}'
            }), 400
            
    except Exception as e:
        print(f"Error testing email connection: {e}")
        return jsonify({'error': 'Failed to test email connection'}), 500

# POST endpoint removed - only OAuth setup endpoint is used now

@app.route('/api/email-monitoring/status', methods=['GET'])
@login_required
def get_email_monitoring_status():
    """Get refund email monitoring service status from S3"""
    try:
        discord_id = session['discord_id']
        
        if not has_feature_access(discord_id, 'email_monitoring'):
            return jsonify({'error': 'Access denied to email monitoring feature'}), 403
        
        # Get configurations and rules from S3
        configs = email_monitoring_manager.get_email_configs(discord_id)
        rules = email_monitoring_manager.get_monitoring_rules(discord_id)
        recent_logs = email_monitoring_manager.get_recent_logs(discord_id, 10)
        
        # Count active items
        active_configs = len([c for c in configs if c.get('is_active')])
        active_rules = len([r for r in rules if r.get('is_active')])
        
        # Check if email monitoring service is running
        service_running = (email_monitor_instance is not None and 
                          email_monitor_instance.is_running and 
                          active_configs > 0 and active_rules > 0)
        
        # Format recent logs
        formatted_logs = []
        for log in recent_logs:
            formatted_logs.append({
                'id': log.get('id'),
                'timestamp': log.get('timestamp'),
                'subject': log.get('email_subject'),
                'sender': log.get('email_sender'),
                'email_body': log.get('email_body', ''),
                'webhook_sent': log.get('webhook_sent', False)
            })
        
        return jsonify({
            'active_configs': active_configs,
            'active_rules': active_rules,
            'recent_logs': formatted_logs,
            'service_running': service_running,
            'service_type': 'email_monitoring_s3'
        })
        
    except Exception as e:
        print(f"Error getting email monitoring status: {e}")
        return jsonify({'error': 'Failed to get email monitoring status'}), 500

@app.route('/api/email-monitoring/quick-setup', methods=['POST'])
@login_required
def quick_setup_yankee_candle():
    """Quick setup for Yankee Candle refund monitoring"""
    try:
        discord_id = session['discord_id']
        
        if not has_feature_access(discord_id, 'email_monitoring'):
            return jsonify({'error': 'Access denied to email monitoring feature'}), 403
        
        # Import the helper function
        import sys
        sys.path.append('.')
        from email_monitor_s3 import create_yankee_candle_rule
        
        # Note: webhook_url is no longer needed since we use system-wide webhooks
        print(f"🔧 Creating Yankee Candle rule for discord_id: {discord_id}")
        rule_id = create_yankee_candle_rule(discord_id)
        print(f"✅ Yankee Candle rule created with ID: {rule_id}")
        
        return jsonify({
            'message': 'Yankee Candle refund monitoring rule created successfully',
            'rule_id': rule_id,
            'rule_details': {
                'name': 'Yankee Candle Refund Alert',
                'sender_filter': 'reply@e.yankeecandle.com',
                'subject_filter': "Here's your refund!",
                'webhook': 'Uses system-wide admin webhook'
            }
        })
        
    except Exception as e:
        print(f"Error creating Yankee Candle rule: {e}")
        return jsonify({'error': 'Failed to create Yankee Candle monitoring rule'}), 500

@app.route('/api/email-monitoring/check-now', methods=['POST'])
@login_required
def check_emails_now():
    """Manually trigger email checking"""
    try:
        discord_id = session['discord_id']
        
        if not has_feature_access(discord_id, 'email_monitoring'):
            return jsonify({'error': 'Access denied to email monitoring feature'}), 403
        
        # Check if monitoring is running
        if not email_monitor_instance:
            return jsonify({'error': 'Email monitoring service is not running'}), 503
        
        # Run an email check cycle in a separate thread to avoid blocking
        # Manual checks do not send webhooks, only update activity logs
        check_thread = threading.Thread(
            target=lambda: email_monitor_instance.run_email_check_cycle(send_webhooks=False),
            daemon=True
        )
        check_thread.start()
        
        return jsonify({
            'message': 'Email check initiated (webhooks disabled for manual checks). Results will appear in the activity log shortly.',
            'check_interval_hours': email_monitor_instance.check_interval / 3600
        })
        
    except Exception as e:
        print(f"Error triggering email check: {e}")
        return jsonify({'error': 'Failed to trigger email check'}), 500

@app.route('/api/email-monitoring/debug', methods=['GET'])
@login_required
def debug_email_monitoring():
    """Debug endpoint to check email monitoring configuration"""
    try:
        discord_id = session['discord_id']
        
        if not has_feature_access(discord_id, 'email_monitoring'):
            return jsonify({'error': 'Access denied to email monitoring feature'}), 403
        
        local_conn = sqlite3.connect(DATABASE_FILE)
        local_cursor = local_conn.cursor()
        
        # Check email configurations
        local_cursor.execute('''
            SELECT discord_id, email_address, imap_server, imap_port, username, is_active, last_checked
            FROM email_monitoring 
            WHERE discord_id = ?
        ''', (discord_id,))
        
        configs = []
        for row in local_cursor.fetchall():
            configs.append({
                'discord_id': row[0],
                'email_address': row[1],
                'imap_server': row[2],
                'imap_port': row[3],
                'username': row[4],
                'is_active': bool(row[5]),
                'last_checked': row[6]
            })
        
        # Check monitoring rules
        local_cursor.execute('''
            SELECT id, rule_name, sender_filter, subject_filter, content_filter, webhook_url, is_active
            FROM email_monitoring_rules 
            WHERE discord_id = ?
        ''', (discord_id,))
        
        rules = []
        for row in local_cursor.fetchall():
            rules.append({
                'id': row[0],
                'rule_name': row[1],
                'sender_filter': row[2],
                'subject_filter': row[3],
                'content_filter': row[4],
                'webhook_url': row[5],
                'is_active': bool(row[6])
            })
        
        # Check recent logs
        local_cursor.execute('''
            SELECT created_at, rule_id, email_subject, email_sender, email_date, webhook_sent, webhook_response
            FROM email_monitoring_logs 
            WHERE discord_id = ?
            ORDER BY created_at DESC 
            LIMIT 10
        ''', (discord_id,))
        
        logs = []
        for row in local_cursor.fetchall():
            logs.append({
                'timestamp': row[0],
                'rule_id': row[1],
                'subject': row[2],
                'sender': row[3],
                'email_date': row[4],
                'webhook_sent': bool(row[5]),
                'webhook_response': row[6]
            })
        
        local_conn.close()
        
        return jsonify({
            'service_running': email_monitor_instance is not None,
            'configurations': configs,
            'rules': rules,
            'recent_logs': logs,
            'discord_id': discord_id
        })
        
    except Exception as e:
        print(f"Error in email monitoring debug: {e}")
        return jsonify({'error': f'Debug failed: {str(e)}'}), 500

@app.route('/api/email-monitoring/reset-password', methods=['POST'])
@login_required  
def reset_email_monitoring_password():
    """Reset/update password for email monitoring configuration"""
    try:
        discord_id = session['discord_id']
        
        if not has_feature_access(discord_id, 'email_monitoring'):
            return jsonify({'error': 'Access denied to email monitoring feature'}), 403
        
        data = request.get_json()
        email_address = data.get('email_address')
        new_password = data.get('password')
        
        if not email_address or not new_password:
            return jsonify({'error': 'Email address and password are required'}), 400
        
        # Encrypt the new password
        from email_monitor import email_cipher
        encrypted_password = email_cipher.encrypt(new_password.encode()).decode()
        
        local_conn = sqlite3.connect(DATABASE_FILE)
        local_cursor = local_conn.cursor()
        
        # Update the password for this user's configuration
        local_cursor.execute('''
            UPDATE email_monitoring 
            SET password_encrypted = ?
            WHERE discord_id = ? AND email_address = ?
        ''', (encrypted_password, discord_id, email_address))
        
        if local_cursor.rowcount == 0:
            local_conn.close()
            return jsonify({'error': 'Email configuration not found'}), 404
        
        local_conn.commit()
        local_conn.close()
        
        return jsonify({'message': 'Password updated successfully'})
        
    except Exception as e:
        print(f"Error resetting email monitoring password: {e}")
        return jsonify({'error': f'Failed to reset password: {str(e)}'}), 500

@app.route('/api/email-monitoring/oauth-url', methods=['GET'])
@login_required
def get_email_monitoring_oauth_url():
    """Get Gmail OAuth authorization URL for email monitoring"""
    try:
        # Generate state parameter for CSRF protection
        state = str(uuid.uuid4())
        session['email_oauth_state'] = state
        
        # Construct OAuth 2.0 authorization URL using the same redirect URI as other OAuth flows
        auth_url = (
            f"https://accounts.google.com/o/oauth2/v2/auth?"
            f"client_id={GOOGLE_CLIENT_ID}&"
            f"redirect_uri={urllib.parse.quote(GOOGLE_REDIRECT_URI)}&"
            f"scope=https://www.googleapis.com/auth/gmail.readonly&"
            f"response_type=code&"
            f"access_type=offline&"
            f"prompt=consent&"
            f"state=email_monitoring_{state}"
        )
        
        return jsonify({
            'auth_url': auth_url,
            'state': state
        })
    except Exception as e:
        print(f"Error generating OAuth URL: {e}")
        return jsonify({'error': 'Failed to generate authorization URL'}), 500

@app.route('/api/email-monitoring/oauth-setup', methods=['POST'])
@login_required
def setup_email_monitoring_oauth():
    """Complete OAuth setup for email monitoring and save to S3"""
    try:
        data = request.get_json()
        email_address = data.get('email_address')
        auth_code = data.get('auth_code')
        
        if not email_address or not auth_code:
            return jsonify({'error': 'Email address and authorization code are required'}), 400
            
        # Exchange authorization code for tokens
        token_data = {
            'client_id': GOOGLE_CLIENT_ID,
            'client_secret': GOOGLE_CLIENT_SECRET,
            'code': auth_code,
            'grant_type': 'authorization_code',
            'redirect_uri': GOOGLE_REDIRECT_URI
        }
        
        import requests
        token_response = requests.post('https://oauth2.googleapis.com/token', data=token_data)
        
        if not token_response.ok:
            print(f"Token exchange failed: {token_response.text}")
            return jsonify({'error': 'Failed to exchange authorization code for tokens'}), 400
            
        tokens = token_response.json()
        access_token = tokens.get('access_token')
        refresh_token = tokens.get('refresh_token')
        expires_in = tokens.get('expires_in', 3600)
        
        if not access_token:
            return jsonify({'error': 'No access token received'}), 400
            
        # Calculate token expiry
        from datetime import datetime, timedelta
        expires_at = (datetime.now() + timedelta(seconds=expires_in)).isoformat()
        
        # Save email monitoring configuration to S3
        discord_id = session['discord_id']
        
        email_config = {
            'email_address': email_address,
            'auth_type': 'oauth',
            'oauth_access_token': access_token,
            'oauth_refresh_token': refresh_token,
            'oauth_token_expires_at': expires_at,
            'is_active': True
        }
        
        success = email_monitoring_manager.add_email_config(discord_id, email_config)
        
        if success:
            print(f"✅ OAuth setup completed for {email_address} (discord_id: {discord_id})")
            return jsonify({'message': 'OAuth setup completed successfully'})
        else:
            return jsonify({'error': 'Failed to save email configuration'}), 500
        
    except Exception as e:
        print(f"Error setting up OAuth: {e}")
        return jsonify({'error': f'Failed to setup OAuth: {str(e)}'}), 500

@app.route('/api/admin/email-monitoring/webhook', methods=['GET'])
@admin_required
def get_email_monitoring_webhook():
    """Get system-wide email monitoring webhook configuration from S3"""
    try:
        webhook_config = email_monitoring_manager.get_system_webhook()
        
        if webhook_config:
            return jsonify({
                'configured': True,
                'config': {
                    'webhook_url': webhook_config['webhook_url'],
                    'description': webhook_config['description'],
                    'is_active': webhook_config['is_active'],
                    'include_body': webhook_config.get('include_body', False),
                    'created_at': webhook_config['created_at'],
                    'created_by': webhook_config['created_by']
                }
            })
        else:
            return jsonify({'configured': False})
            
    except Exception as e:
        print(f"Error getting email monitoring webhook: {e}")
        return jsonify({'error': 'Failed to get webhook configuration'}), 500

@app.route('/api/admin/email-monitoring/webhook', methods=['POST'])
@admin_required
def set_email_monitoring_webhook():
    """Set system-wide email monitoring webhook configuration in S3"""
    try:
        data = request.get_json()
        webhook_url = data.get('webhook_url')
        description = data.get('description', 'Default Webhook')
        include_body = data.get('include_body', False)
        
        if not webhook_url:
            return jsonify({'error': 'Webhook URL is required'}), 400
        
        success = email_monitoring_manager.set_system_webhook(
            webhook_url, description, session.get('discord_id', 'admin'), include_body
        )
        
        if success:
            print(f"✅ Webhook saved successfully: {webhook_url}")
            return jsonify({'message': 'Webhook configuration saved successfully'})
        else:
            return jsonify({'error': 'Failed to save webhook'}), 500
            
    except Exception as e:
        print(f"Error setting email monitoring webhook: {e}")
        return jsonify({'error': 'Failed to save webhook configuration'}), 500
        
        local_cursor.execute('''
            SELECT webhook_url, webhook_name, is_active, created_at, updated_at
            FROM email_monitoring_webhook_config
            WHERE is_active = 1
            ORDER BY created_at DESC
            LIMIT 1
        ''')
        
        row = local_cursor.fetchone()
        local_conn.close()
        
        if row:
            return jsonify({
                'configured': True,
                'config': {
                    'webhook_url': row[0],
                    'description': row[1],  # Frontend expects 'description' not 'webhook_name'
                    'is_active': bool(row[2]),
                    'created_at': row[3],
                    'updated_at': row[4]
                }
            })
        else:
            return jsonify({'configured': False})
            
    except Exception as e:
        print(f"Error getting email monitoring webhook config: {e}")
        return jsonify({'error': 'Failed to get webhook configuration'}), 500

# Duplicate webhook endpoint removed - using S3 version above

@app.route('/api/admin/email-monitoring/webhook/test', methods=['POST'])
@admin_required
def test_email_monitoring_webhook():
    """Test the email monitoring webhook"""
    try:
        data = request.get_json()
        webhook_url = data.get('webhook_url')
        
        if not webhook_url:
            return jsonify({'error': 'Webhook URL is required'}), 400
            
        # Send test payload - format for Discord webhooks
        if 'discord.com/api/webhooks' in webhook_url.lower():
            test_payload = {
                'content': '🧪 **Email Monitoring Test**',
                'embeds': [{
                    'title': 'Webhook Test Successful',
                    'description': 'This is a test notification from the email monitoring system',
                    'color': 5763719,  # Blue color
                    'timestamp': datetime.now().isoformat(),
                    'footer': {'text': 'Email Monitoring System'}
                }]
            }
        else:
            # Generic payload for other webhook types (Slack, custom, etc.)
            test_payload = {
                'type': 'test_notification',
                'message': 'This is a test notification from the email monitoring system',
                'timestamp': datetime.now().isoformat(),
                'test': True
            }
        
        response = requests.post(webhook_url, json=test_payload, timeout=10)
        response.raise_for_status()
        
        return jsonify({
            'message': f'Test successful! Webhook responded with status {response.status_code}'
        })
        
    except requests.exceptions.Timeout:
        return jsonify({'error': 'Webhook test timed out'}), 400
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'Webhook test failed: {str(e)}'}), 400
    except Exception as e:
        print(f"Error testing webhook: {e}")
        return jsonify({'error': 'Failed to test webhook'}), 500

@app.route('/api/admin/email-monitoring/webhook', methods=['DELETE'])
@admin_required
def delete_email_monitoring_webhook():
    """Delete the system-wide email monitoring webhook configuration"""
    try:
        local_conn = sqlite3.connect(DATABASE_FILE)
        local_cursor = local_conn.cursor()
        
        # Delete all webhook configurations
        local_cursor.execute('DELETE FROM email_monitoring_webhook_config')
        
        local_conn.commit()
        local_conn.close()
        
        return jsonify({'message': 'Webhook configuration deleted successfully'})
        
    except Exception as e:
        print(f"Error deleting email monitoring webhook: {e}")
        return jsonify({'error': 'Failed to delete webhook configuration'}), 500

@app.route('/api/email-monitoring/service-control', methods=['POST'])
@admin_required
def control_email_monitoring_service():
    """Admin endpoint to start/stop the email monitoring service"""
    try:
        data = request.get_json()
        action = data.get('action')  # 'start' or 'stop'
        
        if action == 'start':
            if email_monitor_thread and email_monitor_thread.is_alive():
                return jsonify({'message': 'Email monitoring service is already running'})
            
            start_email_monitoring()
            return jsonify({'message': 'Email monitoring service started'})
            
        elif action == 'stop':
            stop_email_monitoring()
            return jsonify({'message': 'Email monitoring service stopped'})
            
        else:
            return jsonify({'error': 'Invalid action. Use "start" or "stop"'}), 400
            
    except Exception as e:
        print(f"Error controlling email monitoring service: {e}")
        return jsonify({'error': f'Failed to {action} email monitoring service'}), 500

# ================================
# Discount Email Configuration API
# ================================

@app.route('/api/admin/discount-email/config', methods=['GET'])
@admin_required
def get_discount_email_config_status():
    """Get current discount opportunities email configuration"""
    try:
        # First check S3 configuration (matches the priority in other functions)
        s3_config = get_discount_email_config()
        if s3_config and s3_config.get('is_s3_config'):
            return jsonify({
                'configured': True,
                'config': {
                    'email_address': s3_config.get('email_address'),
                    'config_type': s3_config.get('config_type', 'gmail_oauth'),
                    'is_active': True,
                    'created_at': s3_config.get('created_at'),
                    'last_updated': s3_config.get('last_updated'),
                    'source': 'S3'
                }
            })
        
        # Fallback to database for backward compatibility
        local_conn = sqlite3.connect(DATABASE_FILE)
        local_cursor = local_conn.cursor()
        
        local_cursor.execute('''
            SELECT id, email_address, config_type, imap_server, imap_port, username, 
                   gmail_access_token, is_active, created_at, last_updated
            FROM discount_email_config
            WHERE is_active = 1
            ORDER BY created_at DESC
            LIMIT 1
        ''')
        
        row = local_cursor.fetchone()
        local_conn.close()
        
        if row:
            id_val, email, config_type, server, port, username, gmail_token, is_active, created, updated = row
            config_data = {
                'id': id_val,
                'email_address': email,
                'config_type': config_type or 'gmail_oauth',
                'is_active': bool(is_active),
                'created_at': created,
                'last_updated': updated
            }
            
            if config_type == 'imap':
                config_data.update({
                    'imap_server': server,
                    'imap_port': port,
                    'username': username
                })
            elif config_type == 'gmail_oauth':
                config_data.update({
                    'has_gmail_token': bool(gmail_token)
                })
            
            return jsonify({
                'configured': True,
                'config': config_data
            })
        else:
            return jsonify({'configured': False})
        
    except Exception as e:
        print(f"Error getting discount email config: {e}")
        return jsonify({'error': 'Failed to get discount email configuration'}), 500

@app.route('/api/admin/discount-email/config', methods=['POST'])
@admin_required
def update_discount_email_config():
    """Update discount opportunities email configuration - now saves to S3"""
    try:
        data = request.get_json()
        
        # Handle both IMAP and Gmail OAuth configurations
        if data.get('config_type') == 'gmail_oauth':
            required_fields = ['email_address', 'config_type']
        else:
            required_fields = ['email_address', 'imap_server', 'username', 'password', 'config_type']
        
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Get existing configuration to preserve format patterns
        existing_config = get_discount_email_config() or {}
        
        # Prepare configuration data for S3
        config_data = {
            'email_address': data['email_address'],
            'config_type': data.get('config_type', 'gmail_oauth'),
            'is_active': True,
            'created_by': session.get('discord_id'),
            'created_at': datetime.now().isoformat(),
            'last_updated': datetime.now().isoformat(),
            # Preserve existing format patterns
            'subject_pattern': existing_config.get('subject_pattern', r'\[([^\]]+)\]\s*Alert:\s*[^\(]*\(ASIN:\s*([B0-9A-Z]{10})\)'),
            'asin_pattern': existing_config.get('asin_pattern', r'\(ASIN:\s*([B0-9A-Z]{10})\)'),
            'retailer_pattern': existing_config.get('retailer_pattern', r'\[([^\]]+)\]\s*Alert:'),
            'sender_filter': existing_config.get('sender_filter', 'alert@distill.io')
        }
        
        if data.get('config_type') == 'imap':
            # Encrypt password for IMAP
            encrypted_password = email_cipher.encrypt(data['password'].encode()).decode()
            config_data.update({
                'imap_server': data['imap_server'],
                'imap_port': data.get('imap_port', 993),
                'username': data['username'],
                'password_encrypted': encrypted_password
            })
        elif data.get('config_type') == 'gmail_oauth':
            config_data.update({
                'gmail_email': data['email_address'],
                'tokens': data.get('tokens', {}),
                'connected_at': data.get('connected_at', datetime.now().isoformat())
            })
        
        # Save to S3
        success = save_discount_email_config(config_data)
        
        if not success:
            return jsonify({'error': 'Failed to save configuration to S3'}), 500
        
        # Clear cache to force refresh
        cache_key = f"config_discount_email_config"
        if cache_key in config_cache:
            del config_cache[cache_key]
            
        # Clear discount opportunities cache to force refresh with new email
        if 'discount_opportunities_cache' in globals():
            global discount_opportunities_cache
            discount_opportunities_cache = {}
        
        return jsonify({'message': 'Discount email configuration saved to S3 successfully'})
        
    except Exception as e:
        print(f"Error updating discount email config: {e}")
        return jsonify({'error': 'Failed to update discount email configuration'}), 500

@app.route('/api/admin/discount-email/test', methods=['POST'])
@admin_required
def test_discount_email_connection():
    """Test discount email connection"""
    try:
        data = request.get_json()
        
        # Import required modules
        import imaplib
        
        try:
            # Test IMAP connection
            mail = imaplib.IMAP4_SSL(data['imap_server'], data.get('imap_port', 993))
            mail.login(data['username'], data['password'])
            mail.select('inbox')
            
            # Search for discount-related emails
            result, messages = mail.search(None, 'SUBJECT "discount" OR SUBJECT "clearance" OR SUBJECT "sale"')
            discount_count = len(messages[0].split()) if messages[0] else 0
            
            mail.logout()
            
            return jsonify({
                'success': True,
                'message': f'Connection successful! Found {discount_count} potential discount emails.',
                'discount_count': discount_count
            })
            
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Connection failed: {str(e)}'
            }), 400
            
    except Exception as e:
        print(f"Error testing discount email connection: {e}")
        return jsonify({'error': 'Failed to test email connection'}), 500

@app.route('/api/admin/discount-email/clear-cache', methods=['POST'])
@admin_required
def clear_discount_cache():
    """Clear discount opportunities cache to force refresh"""
    try:
        # Clear the global cache
        if 'discount_opportunities_cache' in globals():
            global discount_opportunities_cache
            discount_opportunities_cache = {}
        
        # Clear database cache
        local_conn = sqlite3.connect(DATABASE_FILE)
        local_cursor = local_conn.cursor()
        
        local_cursor.execute('DELETE FROM discount_opportunities_cache')
        local_conn.commit()
        local_conn.close()
        
        return jsonify({'message': 'Discount opportunities cache cleared successfully'})
        
    except Exception as e:
        print(f"Error clearing discount cache: {e}")
        return jsonify({'error': 'Failed to clear cache'}), 500

@app.route('/api/admin/discount-email/gmail-oauth-url', methods=['POST'])
@admin_required
def get_discount_gmail_oauth_url():
    """Get Gmail OAuth URL for discount opportunities"""
    try:
        data = request.get_json()
        email_address = data.get('email_address')
        
        if not email_address:
            return jsonify({'error': 'Email address is required'}), 400
        
        # Store email in session for later use
        session['discount_email_setup'] = email_address
        
        # Generate OAuth URL for Gmail access
        google_auth_url = (
            f"https://accounts.google.com/o/oauth2/v2/auth"
            f"?client_id={GOOGLE_CLIENT_ID}"
            f"&redirect_uri={urllib.parse.quote(GOOGLE_REDIRECT_URI)}"
            f"&response_type=code"
            f"&scope=https://www.googleapis.com/auth/gmail.readonly"
            f"&access_type=offline"
            f"&prompt=consent"
            f"&state=discount_email_setup"  # Use state to identify this flow
        )
        
        return jsonify({
            'auth_url': google_auth_url,
            'message': 'Please complete OAuth authorization'
        })
        
    except Exception as e:
        print(f"Error setting up Gmail OAuth: {e}")
        return jsonify({'error': 'Failed to setup Gmail OAuth'}), 500

@app.route('/api/admin/discount-email/complete-oauth', methods=['POST'])
@admin_required
def complete_discount_gmail_oauth():
    """Complete Gmail OAuth setup for discount opportunities"""
    try:
        data = request.get_json()
        code = data.get('code')
        state = data.get('state')
        
        if not code:
            return jsonify({'error': 'Authorization code required'}), 400
        
        # Verify this is for discount email setup
        if state != 'discount_email_setup':
            return jsonify({'error': 'Invalid state parameter'}), 400
            
        # Get email from session
        email_address = session.get('discount_email_setup')
        if not email_address:
            return jsonify({'error': 'Email address not found in session'}), 400
        
        # Exchange code for tokens
        token_url = "https://oauth2.googleapis.com/token"
        payload = {
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code"
        }
        
        token_response = requests.post(token_url, data=payload)
        token_response.raise_for_status()
        tokens = token_response.json()
        
        access_token = tokens['access_token']
        refresh_token = tokens.get('refresh_token')
        expires_in = tokens.get('expires_in', 3600)
        
        # Calculate expiration time
        from datetime import datetime, timedelta
        expires_at = datetime.now() + timedelta(seconds=expires_in)
        
        # Save to S3 only (persistent across redeploys)
        config_data = {
            'email_address': email_address,
            'config_type': 'gmail_oauth',
            'tokens': {
                'access_token': access_token,
                'refresh_token': refresh_token,
                'token_expires_at': expires_at.isoformat()
            },
            'connected_at': datetime.now().isoformat(),
            'connected_by': session.get('discord_id', 'admin'),
            'is_active': True,
            # Default patterns for Distill alerts
            'subject_pattern': r'\[([^\]]+)\]\s*Alert:\s*[^\(]*\(ASIN:\s*([B0-9A-Z]{10})\)',
            'asin_pattern': r'\b(B[0-9A-Z]{9})\b',  # Use flexible pattern
            'retailer_pattern': r'\[([^\]]+)\]\s*Alert:',
            'sender_filter': 'alert@distill.io'
        }
        
        # Save to S3
        if not save_discount_email_config(config_data):
            return jsonify({'error': 'Failed to save configuration'}), 500
        
        # Clear any cached discount email config
        cache_key = f"config_discount_email_config"
        if cache_key in config_cache:
            del config_cache[cache_key]
        
        # Clean up session
        session.pop('discount_email_setup', None)
        
        return jsonify({
            'success': True,
            'message': 'Gmail OAuth setup completed successfully',
            'email': email_address
        })
        
    except Exception as e:
        print(f"Error completing Gmail OAuth: {e}")
        return jsonify({'error': f'Failed to complete OAuth setup: {str(e)}'}), 500

@app.route('/api/admin/discount-email/format-patterns', methods=['GET'])
@admin_required
def get_discount_email_format_patterns():
    """Get current discount email format patterns"""
    try:
        # Get config directly from S3/database without circular dependency
        discount_config = get_discount_email_config()
        
        # Return default patterns if no config exists
        patterns = {
            'subject_pattern': r'\[([^\]]+)\]\s*Alert:\s*[^\(]*\(ASIN:\s*([B0-9A-Z]{10})\)',
            'asin_pattern': r'\(ASIN:\s*([B0-9A-Z]{10})\)',
            'retailer_pattern': r'\[([^\]]+)\]\s*Alert:',
            'sender_filter': 'alert@distill.io'
        }
        
        # Override with saved patterns if config exists
        if discount_config and isinstance(discount_config, dict):
            patterns.update({
                'subject_pattern': discount_config.get('subject_pattern', patterns['subject_pattern']),
                'asin_pattern': discount_config.get('asin_pattern', patterns['asin_pattern']),
                'retailer_pattern': discount_config.get('retailer_pattern', patterns['retailer_pattern']),
                'sender_filter': discount_config.get('sender_filter', patterns['sender_filter'])
            })
            
        return jsonify(patterns)
        
    except Exception as e:
        print(f"Error getting format patterns: {e}")
        # Return defaults if there's an error
        return jsonify({
            'subject_pattern': r'\[([^\]]+)\]\s*Alert:\s*[^\(]*\(ASIN:\s*([B0-9A-Z]{10})\)',
            'asin_pattern': r'\(ASIN:\s*([B0-9A-Z]{10})\)',
            'retailer_pattern': r'\[([^\]]+)\]\s*Alert:',
            'sender_filter': 'alert@distill.io'
        })

def convert_template_to_regex(template):
    """Convert user-friendly template to regex pattern"""
    import re
    
    # Escape special regex characters except our placeholders
    escaped = re.escape(template)
    
    # Replace escaped placeholders with regex patterns
    replacements = {
        r'\\\{RETAILER\\\}': r'([^\]\\(\\)]+)',  # Capture group for retailer
        r'\\\{ASIN\\\}': r'([B0-9A-Z]{10})',     # Capture group for ASIN  
        r'\\\{NOTE\\\}': r'([^\\)]+)',           # Capture group for note content
        r'\\\{[^\\}]+\\\}': r'[^\\(\\)\\s]+'     # Any other placeholder becomes non-capturing
    }
    
    for placeholder, regex in replacements.items():
        escaped = re.sub(placeholder, regex, escaped)
    
    return escaped

def extract_patterns_from_template(template):
    """Extract individual patterns for ASIN and retailer from template"""
    import re
    
    # Convert template to regex
    subject_regex = convert_template_to_regex(template)
    
    # ASIN pattern is always the same
    asin_pattern = r'\(ASIN:\s*([B0-9A-Z]{10})\)'
    
    # Retailer pattern based on template structure
    if template.startswith('[{RETAILER}]'):
        retailer_pattern = r'\[([^\]]+)\]'
    else:
        retailer_pattern = r'([^:\s\(\)]+)'
    
    return subject_regex, asin_pattern, retailer_pattern

@app.route('/api/admin/discount-email/format-patterns', methods=['PUT'])
@admin_required
def update_discount_email_format_patterns():
    """Update discount email format patterns"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        # Check if using template format or direct regex
        if data.get('email_template'):
            # Convert template to regex patterns
            try:
                subject_pattern, asin_pattern, retailer_pattern = extract_patterns_from_template(data['email_template'])
                sender_filter = data.get('sender_filter', 'alert@distill.io')
                
                # Store the original template for display
                template = data['email_template']
            except Exception as e:
                return jsonify({'error': f'Invalid template format: {str(e)}'}), 400
        else:
            # Use direct regex patterns (fallback for advanced users)
            subject_pattern = data.get('subject_pattern', r'\[([^\]]+)\]\s*Alert:\s*[^\(]*\(ASIN:\s*([B0-9A-Z]{10})\)')
            asin_pattern = data.get('asin_pattern', r'\(ASIN:\s*([B0-9A-Z]{10})\)')
            retailer_pattern = data.get('retailer_pattern', r'\[([^\]]+)\]\s*Alert:')
            sender_filter = data.get('sender_filter', 'alert@distill.io')
            template = None
        
        # Validate regex patterns
        import re
        try:
            re.compile(subject_pattern)
            re.compile(asin_pattern) 
            re.compile(retailer_pattern)
        except re.error as e:
            return jsonify({'error': f'Invalid regex pattern: {str(e)}'}), 400
        
        # Get existing config or create new one
        existing_config = get_discount_email_config() or {}
        
        # Prepare config data
        config_data = {
            'subject_pattern': subject_pattern,
            'asin_pattern': asin_pattern,
            'retailer_pattern': retailer_pattern,
            'sender_filter': sender_filter,
            'config_type': 'pattern_config'
        }
        
        # Add template if provided for user-friendly display
        if template:
            config_data['email_template'] = template
        
        # Preserve existing email configuration if it exists
        if existing_config:
            config_data.update({
                'email_address': existing_config.get('email_address'),
                'gmail_email': existing_config.get('gmail_email'),
                'connected_at': existing_config.get('connected_at'),
                'tokens': existing_config.get('tokens')
            })
        
        # Save to S3
        success = save_discount_email_config(config_data)
        
        if not success:
            return jsonify({'error': 'Failed to save configuration to S3'}), 500
            
        return jsonify({
            'success': True,
            'message': 'Format patterns updated successfully in S3',
            'patterns': {
                'subject_pattern': subject_pattern,
                'asin_pattern': asin_pattern,
                'retailer_pattern': retailer_pattern,
                'sender_filter': sender_filter
            }
        })
        
    except Exception as e:
        print(f"Error updating format patterns: {e}")
        return jsonify({'error': f'Failed to update format patterns: {str(e)}'}), 500

@app.route('/api/admin/discount-email/test-patterns', methods=['POST'])
@admin_required 
def test_discount_email_patterns():
    """Test format patterns against sample email subjects"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        # Get patterns from request or use current config
        patterns = data.get('patterns', {})
        test_subjects = data.get('test_subjects', [
            '[Lowes] Alert: Lowes (ASIN: B0093OG4PE) (Note: Mobile)',
            '[Vitacost] Alert: Vitacost 2C (ASIN: B0012NW4RQ) (Note: N/A)',
            '[Walmart] Alert: Walmart (ASIN: B0017TF1E8) (Note: Testing)'
        ])
        
        # Get current patterns if not provided
        if not patterns:
            discount_config = get_discount_email_config()
            patterns = {
                'subject_pattern': discount_config.get('subject_pattern', r'\[([^\]]+)\]\s*Alert:\s*[^\(]*\(ASIN:\s*([B0-9A-Z]{10})\)'),
                'asin_pattern': discount_config.get('asin_pattern', r'\(ASIN:\s*([B0-9A-Z]{10})\)'),
                'retailer_pattern': discount_config.get('retailer_pattern', r'\[([^\]]+)\]\s*Alert:'),
                'sender_filter': discount_config.get('sender_filter', 'alert@distill.io')
            } if discount_config else {}
        
        results = []
        import re
        
        for subject in test_subjects:
            result = {
                'subject': subject,
                'asin': None,
                'retailer': None,
                'matches': {}
            }
            
            # Test ASIN pattern
            try:
                asin_match = re.search(patterns.get('asin_pattern', ''), subject, re.IGNORECASE)
                if asin_match:
                    result['asin'] = asin_match.group(1)
                    result['matches']['asin'] = True
                else:
                    result['matches']['asin'] = False
            except:
                result['matches']['asin'] = 'error'
                
            # Test retailer pattern  
            try:
                retailer_match = re.search(patterns.get('retailer_pattern', ''), subject, re.IGNORECASE)
                if retailer_match:
                    result['retailer'] = retailer_match.group(1)
                    result['matches']['retailer'] = True
                else:
                    result['matches']['retailer'] = False
            except:
                result['matches']['retailer'] = 'error'
                
            results.append(result)
        
        return jsonify({
            'success': True,
            'test_results': results,
            'patterns_used': patterns
        })
        
    except Exception as e:
        print(f"Error testing patterns: {e}")
        return jsonify({'error': f'Failed to test patterns: {str(e)}'}), 500


if __name__ == '__main__':
    try:
        # Production configuration for Railway
        port = int(os.environ.get('PORT', 5000))
        debug_mode = os.environ.get('FLASK_ENV') == 'development'
        
        pass  # Debug print removed
        pass  # Debug print removed
        
        # Check critical environment variables
        critical_vars = ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'CONFIG_S3_BUCKET']
        missing_vars = [var for var in critical_vars if not os.environ.get(var)]
        
        if missing_vars:
            pass  # Debug print removed
            pass  # Debug print removed
        else:
            pass  # All environment variables are set
        
        # Railway expects the app to be available on 0.0.0.0 and the PORT env var
        pass  # Debug print removed
        app.run(
            host='0.0.0.0', 
            port=port, 
            debug=debug_mode,
            threaded=True,  # Enable threading for better concurrency
            use_reloader=False  # Disable reloader in production
        )
        
    except Exception as e:
        pass  # Debug print removed
        import traceback
        traceback.print_exc()
        raise