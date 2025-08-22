from flask import Flask, request, jsonify, session, redirect, url_for, send_from_directory, make_response
from flask_cors import CORS
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

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'development-key-change-in-production')
# Flask app initialized

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
    """Generate dummy users for demo purposes"""
    return [
        {
            "discord_id": "123456789012345678",
            "discord_username": "DemoUser#1234",
            "email": "demo@example.com",
            "va_name": "Demo VA",
            "user_type": "main",
            "profile_configured": True,
            "google_linked": True,
            "sheet_configured": True,
            "permissions": ["all"],
            "sellerboard_orders_url": "https://demo.sellerboard.com/orders",
            "sellerboard_stock_url": "https://demo.sellerboard.com/stock",
            "sheet_id": "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms",
            "google_tokens": {
                "access_token": "dummy_access_token",
                "refresh_token": "dummy_refresh_token",
                "token_uri": "https://oauth2.googleapis.com/token",
                "client_id": "dummy_client_id",
                "client_secret": "dummy_client_secret"
            },
            "uploaded_files": [
                {
                    "filename": "orders_2024_01.csv",
                    "upload_date": "2024-01-15T10:30:00Z",
                    "file_size": 2048000,
                    "s3_key": "demo/orders_2024_01.csv"
                },
                {
                    "filename": "inventory_snapshot.xlsx",
                    "upload_date": "2024-01-10T14:20:00Z",
                    "file_size": 1024000,
                    "s3_key": "demo/inventory_snapshot.xlsx"
                }
            ],
            "last_activity": (datetime.utcnow() - timedelta(hours=2)).isoformat(),
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": (datetime.utcnow() - timedelta(days=1)).isoformat()
        },
        {
            "discord_id": "234567890123456789",
            "discord_username": "AdminDemo#5678",
            "email": "admin@example.com",
            "user_type": "admin",
            "profile_configured": True,
            "google_linked": True,
            "sheet_configured": True,
            "permissions": ["all"],
            "sellerboard_orders_url": "https://demo.sellerboard.com/admin/orders",
            "sellerboard_stock_url": "https://demo.sellerboard.com/admin/stock",
            "sheet_id": "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms",
            "last_activity": (datetime.utcnow() - timedelta(minutes=30)).isoformat(),
            "created_at": "2023-12-01T00:00:00Z",
            "updated_at": datetime.utcnow().isoformat()
        },
        {
            "discord_id": "345678901234567890",
            "discord_username": "VAUser#9012",
            "email": "va@example.com",
            "va_name": "Virtual Assistant",
            "user_type": "subuser",
            "parent_user_id": "123456789012345678",
            "profile_configured": True,
            "permissions": ["reimbursements_analysis"],
            "last_activity": (datetime.utcnow() - timedelta(hours=1)).isoformat(),
            "created_at": "2024-01-05T00:00:00Z",
            "updated_at": (datetime.utcnow() - timedelta(hours=6)).isoformat()
        }
    ]

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
    
    s3_client = get_s3_client()
    try:
        response = s3_client.get_object(Bucket=CONFIG_S3_BUCKET, Key=USERS_CONFIG_KEY)
        config_data = json.loads(response['Body'].read().decode('utf-8'))
        users = config_data.get("users", [])
        
        # Validate and fix token data for all users to prevent NoneType arithmetic errors
        for user in users:
            if user.get("google_tokens"):
                user["google_tokens"] = validate_and_fix_token_data(user["google_tokens"])
        
        return users
    except Exception as e:
        pass  # Error fetching users config
        return []

def update_users_config(users):
    s3_client = get_s3_client()
    config_data = json.dumps({"users": users}, indent=2)
    
    # About to save users to S3
    
    try:
        result = s3_client.put_object(
            Bucket=CONFIG_S3_BUCKET, 
            Key=USERS_CONFIG_KEY, 
            Body=config_data,
            ContentType='application/json'
        )
        # Users configuration updated successfully
        
        # Verify the save by reading it back immediately
        try:
            verify_response = s3_client.get_object(Bucket=CONFIG_S3_BUCKET, Key=USERS_CONFIG_KEY)
            verify_data = json.loads(verify_response['Body'].read().decode('utf-8'))
            pass  # Verification successful
        except Exception as verify_error:
            pass  # Verification failed
        
        return True
    except Exception as e:
        pass  # Error updating users config
        import traceback
        traceback.print_exc()
        return False

def get_invitations_config():
    """Get invitations configuration from S3"""
    try:
        s3_client = get_s3_client()
        response = s3_client.get_object(Bucket=CONFIG_S3_BUCKET, Key=INVITATIONS_CONFIG_KEY)
        return json.loads(response['Body'].read().decode('utf-8'))
    except s3_client.exceptions.NoSuchKey:
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
        return True
    except Exception as e:
        pass  # Error updating invitations config
        return False

def get_discount_monitoring_config():
    """Get discount monitoring configuration from S3"""
    s3_client = get_s3_client()
    try:
        response = s3_client.get_object(Bucket=CONFIG_S3_BUCKET, Key=DISCOUNT_MONITORING_CONFIG_KEY)
        config_data = json.loads(response['Body'].read().decode('utf-8'))
        return config_data
    except Exception as e:
        # Return default config if not found
        return {
            'days_back': 7,  # Default to 7 days
            'enabled': bool(DISCOUNT_MONITOR_EMAIL),
            'last_updated': None
        }

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
        return True
    except Exception as e:
        print(f"Error updating discount monitoring config: {e}")
        return False

def get_discount_email_days_back():
    """Get the current days back setting for discount email checking"""
    config = get_discount_monitoring_config()
    env_days = int(os.getenv('DISCOUNT_EMAIL_DAYS_BACK', '7'))
    
    # Prefer config over environment variable, but fallback to env if not set
    return config.get('days_back', env_days)

def get_purchases_config():
    """Get purchases configuration from S3"""
    if DEMO_MODE:
        return []
    
    s3_client = get_s3_client()
    try:
        response = s3_client.get_object(Bucket=CONFIG_S3_BUCKET, Key=PURCHASES_CONFIG_KEY)
        data = json.loads(response['Body'].read().decode('utf-8'))
        return data.get('purchases', [])
    except s3_client.exceptions.NoSuchKey:
        return []
    except Exception as e:
        print(f"Error fetching purchases config: {e}")
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
        return True
    except Exception as e:
        print(f"Error updating purchases config: {e}")
        return False

def send_invitation_email(email, invitation_token, invited_by):
    """Send invitation email to user"""
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        pass  # SMTP credentials not configured
        return False
    
    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_EMAIL
        msg['To'] = email
        msg['Subject'] = "You're invited to DMS Dashboard"
        
        invitation_url = f"https://dms-amazon.vercel.app/login?invitation={invitation_token}"
        
        body = f"""
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
        
        msg.attach(MIMEText(body, 'html'))
        
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_EMAIL, SMTP_PASSWORD)
        text = msg.as_string()
        server.sendmail(SMTP_EMAIL, email, text)
        server.quit()
        
        return True
    except Exception as e:
        pass  # Error sending invitation email
        return False

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
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
    
    user_permissions = user_record.get('permissions', [])
    user_type = user_record.get('user_type', 'main')
    
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
    if not sub_user or sub_user.get('user_type') != 'subuser':
        return None
    
    parent_id = sub_user.get('parent_user_id')
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
    """Get feature launches configuration from S3"""
    s3_client = get_s3_client()
    try:
        response = s3_client.get_object(Bucket=CONFIG_S3_BUCKET, Key='feature_config.json')
        config_data = json.loads(response['Body'].read().decode('utf-8'))
        return config_data.get('feature_launches', {}), config_data.get('user_permissions', {})
    except Exception as e:
        return {}, {}

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
            discord_id = user.get('discord_id')
            user_feature_perms = user.get('feature_permissions', {})
            
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
    
    # Try to find user with either string or integer ID
    user = next((u for u in users if str(u.get("discord_id")) == discord_id_str), None)
    if not user and discord_id_int is not None:
        user = next((u for u in users if u.get("discord_id") == discord_id_int), None)
    
    # If found, normalize the discord_id to string in the record
    if user and str(user.get("discord_id")) != discord_id_str:
        user["discord_id"] = discord_id_str
    
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
    refresh_token = user_record["google_tokens"].get("refresh_token")
    if not refresh_token:
        raise Exception("No refresh_token found. User must re-link Google account.")

    token_url = "https://oauth2.googleapis.com/token"
    payload = {
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token"
    }
    resp = requests.post(token_url, data=payload)
    resp.raise_for_status()
    new_tokens = resp.json()
    
    if "refresh_token" not in new_tokens:
        new_tokens["refresh_token"] = refresh_token

    # Validate and fix token data to prevent NoneType arithmetic errors
    new_tokens = validate_and_fix_token_data(new_tokens)

    user_record["google_tokens"].update(new_tokens)
    users = get_users_config()
    update_users_config(users)
    return new_tokens["access_token"]

def safe_google_api_call(user_record, api_call_func):
    access_token = user_record["google_tokens"]["access_token"]
    try:
        return api_call_func(access_token)
    except Exception as e:
        if "401" in str(e) or "Invalid Credentials" in str(e):
            new_access = refresh_google_token(user_record)
            return api_call_func(new_access)
        else:
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
    existing_user = next((u for u in users if u.get("discord_id") == discord_id), None)
    
    # Check for invitation token from state parameter (runs for both new and existing users)
    invitation_token = request.args.get('state')  # Discord passes our state parameter back
    # Process Discord callback with invitation token
    
    # If user doesn't exist, check for invitation requirement (for new users only)
    if not existing_user:
        if not invitation_token:
            pass  # No invitation token found for new user
            return redirect("https://dms-amazon.vercel.app/login?error=no_invitation")
        
        # Validate invitation token for new users
        invitations = get_invitations_config()
        # Check invitations for valid token
        valid_invitation = None
        for inv in invitations:
            pass  # Check invitation validity
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
                        valid_invitation = inv
                        pass  # Found valid invitation
                        break
                    else:
                        pass  # Invitation expired
                except Exception as date_error:
                    pass  # Date parsing error, treating as valid
                    # If date parsing fails, allow the invitation (fallback)
                    valid_invitation = inv
                    pass  # Found valid invitation (date parse fallback)
                    break
            else:
                pass  # Invitation mismatch
        
        if not valid_invitation:
            pass  # No valid invitation found
            return redirect("https://dms-amazon.vercel.app/login?error=invalid_invitation")
        
        # Clean up the invitation only after successful validation
        # Clean up invitation token after successful validation
        invitations = [inv for inv in invitations if inv['token'] != invitation_token]
        update_invitations_config(invitations)
        # Removed accepted invitation from list
    
    session['discord_id'] = discord_id
    session['discord_username'] = discord_username
    session['discord_avatar'] = user_data.get('avatar')
    
    # Session configured with Discord ID
    
    # Save Discord username to user record for admin panel
    try:
        users = get_users_config()
        discord_id = session['discord_id']
        user_record = next((u for u in users if u.get("discord_id") == discord_id), None)
        
        if user_record is None:
            user_record = {"discord_id": discord_id}
            
            # Check if this is a sub-user invitation
            if 'valid_invitation' in locals() and valid_invitation:
                if valid_invitation.get('user_type') == 'subuser':
                    user_record['user_type'] = 'subuser'
                    user_record['parent_user_id'] = valid_invitation.get('parent_user_id')
                    user_record['permissions'] = valid_invitation.get('permissions', ['reimbursements_analysis'])
                    user_record['va_name'] = valid_invitation.get('va_name', '')
                    user_record['email'] = valid_invitation.get('email')
                else:
                    user_record['user_type'] = 'main'
                    user_record['permissions'] = ['all']  # Main users have all permissions
            else:
                user_record['user_type'] = 'main'
                user_record['permissions'] = ['all']  # Main users have all permissions
                
            users.append(user_record)
        
        # Update Discord username and last activity in permanent record
        user_record['discord_username'] = user_data['username']
        user_record['last_activity'] = datetime.now().isoformat()
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
            if user['discord_id'] == discord_id:
                user['amazon_refresh_token'] = encrypted_token
                user['amazon_selling_partner_id'] = selling_partner_id
                user['amazon_connected_at'] = datetime.now().isoformat()
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
            if user['discord_id'] == discord_id:
                # Remove Amazon credentials
                user.pop('amazon_refresh_token', None)
                user.pop('amazon_selling_partner_id', None)
                user.pop('amazon_connected_at', None)
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
        
        if user_record and user_record.get('user_type') == 'subuser':
            parent_user = get_parent_user_record(discord_id)
            if parent_user:
                amazon_connected = parent_user.get('amazon_refresh_token') is not None
                amazon_connected_at = parent_user.get('amazon_connected_at')
                selling_partner_id = parent_user.get('amazon_selling_partner_id')
        else:
            if user_record:
                amazon_connected = user_record.get('amazon_refresh_token') is not None
                amazon_connected_at = user_record.get('amazon_connected_at')
                selling_partner_id = user_record.get('amazon_selling_partner_id')
        
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

@app.route('/api/user')
@login_required
def get_user():
    discord_id = session['discord_id']
    
    # In demo mode, return the demo user
    if DEMO_MODE:
        demo_users = get_dummy_users()
        demo_user = demo_users[0]  # Use first demo user
        return jsonify({
            'discord_id': demo_user['discord_id'],
            'discord_username': demo_user['discord_username'],
            'email': demo_user['email'],
            'profile_configured': True,
            'google_linked': True,
            'sheet_configured': True,
            'amazon_connected': True,
            'demo_mode': True,
            'user_type': demo_user.get('user_type', 'main'),
            'permissions': demo_user.get('permissions', ['all']),
            'last_activity': demo_user.get('last_activity'),
            'timezone': 'America/New_York'
        })
    
    user_record = get_user_record(discord_id)
    
    # Check if we're in admin impersonation mode
    admin_impersonating = session.get('admin_impersonating')
    
    # For subusers, check parent's configuration status
    if user_record and user_record.get('user_type') == 'subuser':
        parent_user = get_parent_user_record(discord_id)
        profile_configured = (parent_user is not None and 
                            parent_user.get('email') and 
                            parent_user.get('sellerboard_orders_url') and 
                            parent_user.get('sellerboard_stock_url'))
        google_linked = parent_user and parent_user.get('google_tokens') is not None
        sheet_configured = parent_user and parent_user.get('sheet_id') is not None
    else:
        # For main users, check their own configuration
        profile_configured = (user_record is not None and 
                            user_record.get('email') and 
                            user_record.get('sellerboard_orders_url') and 
                            user_record.get('sellerboard_stock_url'))
        google_linked = user_record and user_record.get('google_tokens') is not None
        sheet_configured = user_record and user_record.get('sheet_id') is not None

    # Check Amazon connection status
    amazon_connected = False
    amazon_connected_at = None
    if user_record and user_record.get('user_type') == 'subuser':
        parent_user = get_parent_user_record(discord_id)
        amazon_connected = parent_user and parent_user.get('amazon_refresh_token') is not None
        amazon_connected_at = parent_user.get('amazon_connected_at') if parent_user else None
    else:
        amazon_connected = user_record and user_record.get('amazon_refresh_token') is not None
        amazon_connected_at = user_record.get('amazon_connected_at') if user_record else None

    response_data = {
        'discord_id': discord_id,
        'discord_username': session.get('discord_username'),
        'discord_avatar': session.get('discord_avatar'),
        'user_type': user_record.get('user_type', 'main') if user_record else 'main',
        'permissions': user_record.get('permissions', ['all']) if user_record else ['all'],
        'parent_user_id': user_record.get('parent_user_id') if user_record else None,
        'va_name': user_record.get('va_name') if user_record else None,
        'is_admin': is_admin_user(discord_id),
        'profile_configured': profile_configured,
        'google_linked': google_linked,
        'sheet_configured': sheet_configured,
        'amazon_connected': amazon_connected,
        'amazon_connected_at': amazon_connected_at,
        'user_record': user_record if user_record else None
    }
    
    # Add impersonation info if applicable
    if admin_impersonating:
        response_data['admin_impersonating'] = True
        response_data['original_admin_id'] = admin_impersonating['original_discord_id']
        response_data['original_admin_username'] = admin_impersonating['original_discord_username']
        # Return impersonated user data
    
    return jsonify(response_data)

@app.route('/api/user/profile', methods=['POST'])
@login_required
def update_profile():
    discord_id = session['discord_id']
    data = request.json
    
    users = get_users_config()
    user_record = next((u for u in users if u.get("discord_id") == discord_id), None)
    
    if user_record is None:
        user_record = {"discord_id": discord_id}
        users.append(user_record)
    
    # Check if user is a subuser - they can only update their timezone
    if user_record.get('user_type') == 'subuser':
        # Only allow timezone updates for subusers
        if 'timezone' in data:
            user_record['timezone'] = data['timezone']
        user_record['last_activity'] = datetime.now().isoformat()
        if 'discord_username' in session:
            user_record['discord_username'] = session['discord_username']
        
        if update_users_config(users):
            return jsonify({'message': 'Timezone updated successfully'})
        else:
            return jsonify({'error': 'Failed to update timezone'}), 500
    
    # For main users, allow all updates
    # Always update Discord username and last activity from session when available
    if 'discord_username' in session:
        user_record['discord_username'] = session['discord_username']
    user_record['last_activity'] = datetime.now().isoformat()
    
    # Update user profile fields
    if 'email' in data:
        user_record['email'] = data['email']
    if 'run_scripts' in data:
        user_record['run_scripts'] = data['run_scripts']
    if 'run_prep_center' in data:
        user_record['run_prep_center'] = data['run_prep_center']
    # Note: listing_loader_key and sb_file_key are now deprecated
    # Files are automatically detected from uploaded_files array
    if 'sellerboard_orders_url' in data:
        user_record['sellerboard_orders_url'] = data['sellerboard_orders_url']
    if 'sellerboard_stock_url' in data:
        user_record['sellerboard_stock_url'] = data['sellerboard_stock_url']
    if 'sellerboard_cogs_url' in data:
        user_record['sellerboard_cogs_url'] = data['sellerboard_cogs_url']
    if 'timezone' in data:
        user_record['timezone'] = data['timezone']
    if 'enable_source_links' in data:
        user_record['enable_source_links'] = data['enable_source_links']
    if 'search_all_worksheets' in data:
        user_record['search_all_worksheets'] = data['search_all_worksheets']
    if 'disable_sp_api' in data:
        user_record['disable_sp_api'] = data['disable_sp_api']
    if 'amazon_lead_time_days' in data:
        # Validate lead time is within reasonable bounds
        lead_time = data['amazon_lead_time_days']
        try:
            lead_time_int = int(lead_time)
            if 30 <= lead_time_int <= 180:
                user_record['amazon_lead_time_days'] = lead_time_int
            else:
                return jsonify({'error': 'Amazon lead time must be between 30 and 180 days'}), 400
        except (ValueError, TypeError):
            return jsonify({'error': 'Amazon lead time must be a valid number between 30 and 180 days'}), 400
    
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
        user_record = next((u for u in users if u.get("discord_id") == discord_id), None)
        
        if user_record is None:
            user_record = {"discord_id": discord_id, "google_tokens": {}}
            users.append(user_record)
        
        old_tokens = user_record.get("google_tokens", {})
        if "refresh_token" not in tokens and "refresh_token" in old_tokens:
            tokens["refresh_token"] = old_tokens["refresh_token"]
        
        user_record["google_tokens"] = tokens
        
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
    user_record = next((u for u in users if u.get("discord_id") == discord_id), None)
    
    if not user_record:
        return jsonify({'error': 'User not found'}), 404
    
    # Remove Google tokens and sheet configuration
    user_record.pop('google_tokens', None)
    user_record.pop('sheet_id', None)
    user_record.pop('worksheet_title', None)
    user_record.pop('column_mapping', None)
    
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
    admin_config = get_admin_gmail_config()
    
    if admin_config and admin_config.get('tokens'):
        return jsonify({
            'connected': True,
            'gmail_email': admin_config.get('gmail_email', 'Unknown'),
            'message': 'System-wide discount monitoring Gmail is connected',
            'connected_at': admin_config.get('connected_at'),
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
    if user_record and user_record.get('user_type') == 'subuser':
        parent_user_id = user_record.get('parent_user_id')
        if parent_user_id:
            parent_record = get_user_record(parent_user_id)
            if parent_record:
                config_user_record = parent_record
    
    if not config_user_record.get('google_tokens'):
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
    if user_record and user_record.get('user_type') == 'subuser':
        parent_user_id = user_record.get('parent_user_id')
        if parent_user_id:
            parent_record = get_user_record(parent_user_id)
            if parent_record:
                config_user_record = parent_record
    
    if not config_user_record.get('google_tokens'):
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
    user_record = next((u for u in users if u.get("discord_id") == discord_id), None)
    
    if not user_record:
        return jsonify({'error': 'User profile not found'}), 404
    
    user_record['sheet_id'] = spreadsheet_id
    user_record['worksheet_title'] = worksheet_title
    user_record['column_mapping'] = column_mapping
    
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
    if user_record and user_record.get('user_type') == 'subuser':
        parent_user_id = user_record.get('parent_user_id')
        if parent_user_id:
            parent_record = get_user_record(parent_user_id)
            if parent_record:
                config_user_record = parent_record
    
    if not config_user_record.get('google_tokens'):
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

def search_gmail_messages(user_record, query, max_results=50):
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
    if user_record.get('discount_gmail_tokens'):
        print("[DEBUG] Using discount-specific Gmail tokens")
        return refresh_discount_gmail_token(user_record)
    
    # Priority 2: Fall back to regular Google tokens
    if user_record.get('google_tokens'):
        print("[DEBUG] Using regular Google tokens as fallback")
        return refresh_google_token(user_record)
    
    print("[DEBUG] No Gmail tokens available")
    return None

def refresh_discount_gmail_token(user_record):
    """Refresh discount monitoring specific Gmail tokens"""
    discount_tokens = user_record.get('discount_gmail_tokens', {})
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
            user_record['discount_gmail_tokens'] = discount_tokens
            
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
def get_admin_gmail_config():
    """Get system-wide admin Gmail configuration"""
    try:
        # Try to load from S3 or file system
        config_bucket = CONFIG_S3_BUCKET
        if config_bucket:
            try:
                s3 = boto3.client('s3', 
                    aws_access_key_id=AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=AWS_SECRET_ACCESS_KEY
                )
                
                response = s3.get_object(Bucket=config_bucket, Key='admin_gmail_config.json')
                config_data = json.loads(response['Body'].read())
                return config_data
            except ClientError as e:
                if e.response['Error']['Code'] == 'NoSuchKey':
                    return None
                else:
                    raise
        else:
            # Local file fallback
            config_file = 'admin_gmail_config.json'
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    return json.load(f)
            return None
    except Exception as e:
        print(f"Error loading admin Gmail config: {e}")
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

def search_gmail_messages_admin(query, max_results=50):
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
        if user_record and user_record.get('user_type') == 'subuser':
            parent_user_id = user_record.get('parent_user_id')
            if parent_user_id:
                parent_record = get_user_record(parent_user_id)
                if parent_record:
                    config_user_record = parent_record
        
        stock_url = config_user_record.get('sellerboard_stock_url')
        if not stock_url:
            return jsonify({'error': 'Stock URL not configured'}), 400
        
        from orders_analysis import EnhancedOrdersAnalysis
        analyzer = EnhancedOrdersAnalysis(orders_url="dummy", stock_url=stock_url)
        stock_df = analyzer.download_csv(stock_url)
        
        columns = list(stock_df.columns)
        # Stock columns retrieved
        
        # Get sample data from first row
        if len(stock_df) > 0:
            sample_row = stock_df.iloc[0].to_dict()
            # Sample row data retrieved
            
            # Look for source-like columns
            source_columns = [col for col in columns if 'source' in col.lower() or 'link' in col.lower() or 'url' in col.lower()]
            # Source columns identified
            
            return jsonify({
                'columns': columns,
                'sample_data': sample_row,
                'potential_source_columns': source_columns,
                'total_rows': len(stock_df)
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
            'enable_source_links': user_record.get('enable_source_links', False),
            'sheet_id': bool(user_record.get('sheet_id')),
            'worksheet_title': bool(user_record.get('worksheet_title')),
            'google_tokens': bool(user_record.get('google_tokens', {}).get('refresh_token')),
            'column_mapping': user_record.get('column_mapping', {}),
            'sellerboard_orders_url': bool(user_record.get('sellerboard_orders_url')),
            'sellerboard_stock_url': bool(user_record.get('sellerboard_stock_url')),
            'user_configured': bool(user_record.get('sheet_id') and user_record.get('worksheet_title'))
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
            user_timezone = user_record.get('timezone') if user_record else None
            
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
        if user_record and user_record.get('user_type') == 'subuser':
            parent_user_id = user_record.get('parent_user_id')
            if parent_user_id:
                parent_record = get_user_record(parent_user_id)
                if parent_record:
                    config_user_record = parent_record
        
        user_timezone = user_record.get('timezone') if user_record else None
        
        # Update last activity for analytics access (only if not updated recently)
        if user_record:
            try:
                last_activity = user_record.get('last_activity')
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
                    users = get_users_config()
                    for user in users:
                        if user.get("discord_id") == discord_id:
                            user['last_activity'] = datetime.now().isoformat()
                            if 'discord_username' in session:
                                user['discord_username'] = session['discord_username']
                            break
                    update_users_config(users)
            except Exception as e:
                # Failed to update last activity - not critical
                pass
        
        # Target date already processed above
        
        
        # Check if user is admin and SP-API should be attempted
        is_admin = is_admin_user(discord_id)
        disable_sp_api = config_user_record.get('disable_sp_api', False) if config_user_record else False
        
        if is_admin and not disable_sp_api:
            pass  # Debug print removed
            try:
                from sp_api_client import create_sp_api_client
                from sp_api_analytics import create_sp_api_analytics
                
                # Try to get user's Amazon refresh token first, fallback to environment
                encrypted_token = user_record.get('amazon_refresh_token') if user_record else None
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
                marketplace_id = user_record.get('marketplace_id', 'ATVPDKIKX0DER')  # Default to US
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
                    orders_url = config_user_record.get('sellerboard_orders_url') if config_user_record else None
                    stock_url = config_user_record.get('sellerboard_stock_url') if config_user_record else None
                    
                    if not orders_url or not stock_url:
                        return jsonify({
                            'error': 'Admin SP-API failed and no Sellerboard URLs configured. Please configure Sellerboard URLs in Settings.',
                            'status': 'configuration_required'
                        }), 400
                    
                    # Use Sellerboard data
                    analyzer = OrdersAnalysis(
                        orders_url=orders_url,
                        stock_url=stock_url,
                        target_date=target_date,
                        user_timezone=user_timezone
                    )
                    
                    analysis = analyzer.analyze()
                    
                except Exception as sellerboard_error:
                    pass  # Debug print removed
                    return jsonify({
                        'error': f'Both SP-API and Sellerboard analysis failed: {str(sellerboard_error)}',
                        'sp_api_error': str(sp_api_error),
                        'sellerboard_error': str(sellerboard_error)
                    }), 500
        elif is_admin and disable_sp_api:
            pass  # Debug print removed
            # Admin user with SP-API disabled - use Sellerboard
            try:
                from orders_analysis import OrdersAnalysis
                
                # Get user's configured Sellerboard URLs
                orders_url = config_user_record.get('sellerboard_orders_url') if config_user_record else None
                stock_url = config_user_record.get('sellerboard_stock_url') if config_user_record else None
                
                if not orders_url or not stock_url:
                    return jsonify({
                        'error': 'SP-API disabled and no Sellerboard URLs configured',
                        'message': 'Please configure Sellerboard report URLs in Settings or re-enable SP-API.',
                        'requires_setup': True,
                        'report_date': target_date.isoformat(),
                        'is_yesterday': is_date_yesterday(target_date, user_timezone)
                    }), 400
                
                pass  # Debug print removed
                analyzer = OrdersAnalysis(orders_url=orders_url, stock_url=stock_url)
                
                # Prepare user settings for COGS data fetching
                user_settings = {
                    'enable_source_links': config_user_record.get('enable_source_links', False),
                    'search_all_worksheets': config_user_record.get('search_all_worksheets', False),
                    'sheet_id': config_user_record.get('sheet_id'),
                    'worksheet_title': config_user_record.get('worksheet_title'),
                    'google_tokens': config_user_record.get('google_tokens', {}),
                    'column_mapping': config_user_record.get('column_mapping', {}),
                    'amazon_lead_time_days': config_user_record.get('amazon_lead_time_days', 90)
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
                orders_url = config_user_record.get('sellerboard_orders_url') if config_user_record else None
                stock_url = config_user_record.get('sellerboard_stock_url') if config_user_record else None
                
                if not orders_url or not stock_url:
                    return jsonify({
                        'error': 'Sellerboard URLs not configured',
                        'message': 'Please configure Sellerboard report URLs in Settings.',
                        'requires_setup': True,
                        'report_date': target_date.isoformat(),
                        'is_yesterday': is_date_yesterday(target_date, user_timezone)
                    }), 400
                
                pass  # Debug print removed
                analyzer = OrdersAnalysis(orders_url=orders_url, stock_url=stock_url)
                
                # Prepare user settings for COGS data fetching
                user_settings = {
                    'enable_source_links': config_user_record.get('enable_source_links', False),
                    'search_all_worksheets': config_user_record.get('search_all_worksheets', False),
                    'sheet_id': config_user_record.get('sheet_id'),
                    'worksheet_title': config_user_record.get('worksheet_title'),
                    'google_tokens': config_user_record.get('google_tokens', {}),
                    'column_mapping': config_user_record.get('column_mapping', {}),
                    'amazon_lead_time_days': config_user_record.get('amazon_lead_time_days', 90)
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
                            if user.get('discord_id') == matched_user:
                                if 'uploaded_files' not in user:
                                    user['uploaded_files'] = []
                                
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
                                user['uploaded_files'] = [
                                    f for f in user['uploaded_files'] 
                                    if f.get('file_type_category') != file_type_category
                                ]
                                
                                user['uploaded_files'].append(file_info)
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
            if 'uploaded_files' not in user:
                continue
                
            original_count = len(user['uploaded_files'])
            user['uploaded_files'] = [
                f for f in user['uploaded_files'] 
                if '_updated.' not in f.get('filename', '') and '_updated.' not in f.get('s3_key', '')
            ]
            removed_count = original_count - len(user['uploaded_files'])
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
            if user.get("discord_id") == discord_id:
                user_record = user
                user_index = i
                break
        
        if not user_record:
            return jsonify({'error': 'User not found'}), 404
        
        if 'uploaded_files' not in user_record:
            return jsonify({'message': 'No files to clean up', 'removed_count': 0})
        
        # Remove _updated files from uploaded_files
        original_count = len(user_record['uploaded_files'])
        user_record['uploaded_files'] = [
            f for f in user_record['uploaded_files'] 
            if '_updated.' not in f.get('filename', '') and '_updated.' not in f.get('s3_key', '')
        ]
        removed_count = original_count - len(user_record['uploaded_files'])
        
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
        if 'uploaded_files' not in user_record:
            user_record['uploaded_files'] = []
        
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
                        if user_record_info.get('email'):
                            email_username = user_record_info['email'].split('@')[0].lower()
                            if email_username in filename:
                                all_objects.append(obj)
                        
                        # Also check deprecated listing_loader_key field
                        if user_record_info.get('listing_loader_key'):
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
                already_exists = any(f['s3_key'] == s3_key for f in user_record['uploaded_files'])
                
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
                user_record['uploaded_files'] = [
                    f for f in user_record['uploaded_files'] 
                    if f.get('file_type_category') != file_type
                ]
            
            # Add the most recent file of each type
            for file_info in files_by_type.values():
                user_record['uploaded_files'].append(file_info)
            
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
                if user.get('discord_id') == discord_id:
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
        user_record = next((u for u in users if u.get("discord_id") == discord_id), None)
        
        if not user_record or 'uploaded_files' not in user_record:
            pass  # Debug print removed
            return jsonify({'error': 'User record not found'}), 404
        
        pass  # Debug print removed
        pass  # Debug print removed
        # Find and remove the file - try multiple matching strategies
        file_to_delete = None
        file_index = None
        
        # Strategy 1: Exact match
        for i, file_info in enumerate(user_record['uploaded_files']):
            if file_info.get('s3_key') == file_key:
                file_to_delete = file_info
                file_index = i
                pass  # Debug print removed
                break
        
        # Strategy 2: Try without URL decoding if exact match failed
        if not file_to_delete:
            for i, file_info in enumerate(user_record['uploaded_files']):
                if file_info.get('s3_key') == original_file_key:
                    file_to_delete = file_info
                    file_index = i
                    file_key = original_file_key  # Use original for S3 deletion
                    pass  # Debug print removed
                    break
        
        # Strategy 3: Try partial match (in case of encoding differences)
        if not file_to_delete:
            for i, file_info in enumerate(user_record['uploaded_files']):
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
                    'available_keys': [f.get('s3_key') for f in user_record['uploaded_files']]
                }
            }), 404
        
        # Remove file from user record
        user_record['uploaded_files'].pop(file_index)
        
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
        
        # Add derived status fields for each user
        for user in users:
            user['profile_configured'] = bool(user.get('email'))
            user['google_linked'] = bool(user.get('google_tokens'))
            user['sheet_configured'] = bool(user.get('sheet_id'))
            
        return jsonify({'users': users})
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
                          u.get('user_type') == 'subuser' or  # Subusers are always active
                          (u.get('email') and u.get('google_tokens') and u.get('sheet_id')))  # Main users need full setup
        
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
            if str(u.get("discord_id")) == str(user_id):
                user_index = i
                break
        
        if user_index is None:
            pass  # Debug print removed
            return jsonify({'error': 'User not found'}), 404
        
        user_record = users[user_index]
        pass  # Debug print removed
        pass  # Debug print removed
        
        # Update allowed fields directly in the users list
        allowed_fields = [
            'email', 'run_scripts', 'run_prep_center', 
            'sellerboard_orders_url', 'sellerboard_stock_url',
            'enable_source_links', 'search_all_worksheets'
        ]
        
        for field in allowed_fields:
            if field in data:
                old_value = user_record.get(field)
                users[user_index][field] = data[field]
        
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
            if str(user.get("discord_id")) == user_id_str:
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
            return jsonify({'message': f'User {deleted_user.get("discord_username", user_id)} deleted successfully'})
        else:
            return jsonify({'error': 'Failed to delete user'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
        session['discord_id'] = user_record['discord_id']
        session['discord_username'] = user_record.get('discord_username', 'Unknown User')
        
        
        return jsonify({
            'message': f'Now viewing as {user_record.get("discord_username", "Unknown User")}',
            'impersonating': True,
            'target_user': {
                'discord_id': user_record['discord_id'],
                'discord_username': user_record.get('discord_username', 'Unknown User')
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
            'user_has_cogs_url': bool(user_record and user_record.get('sellerboard_cogs_url')) if user_record else False,
            'cogs_url_preview': user_record.get('sellerboard_cogs_url', '')[:50] + '...' if user_record and user_record.get('sellerboard_cogs_url') else None
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
            if not user.get('discord_id'):
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
        existing_user = next((u for u in users if u.get('email') == email), None)
        
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
            if send_invitation_email(email, invitation_token, session.get('discord_username', 'Admin')):
                return jsonify({'message': 'Invitation sent successfully', 'invitation': invitation})
            else:
                return jsonify({'message': 'Invitation created but email failed to send', 'invitation': invitation})
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
        existing_user = next((u for u in users if u.get('email') == email), None)
        
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
            if send_invitation_email(email, invitation_token, inviter_name):
                return jsonify({'message': 'Sub-user invitation sent successfully', 'invitation': invitation})
            else:
                return jsonify({'message': 'Invitation created but email failed to send', 'invitation': invitation})
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
        
        # Find all sub-users for this parent
        subusers = [
            {
                'discord_id': user.get('discord_id'),
                'discord_username': user.get('discord_username'),
                'va_name': user.get('va_name'),
                'email': user.get('email'),
                'permissions': user.get('permissions', []),
                'last_activity': user.get('last_activity'),
                'user_type': user.get('user_type')
            }
            for user in users 
            if user.get('user_type') == 'subuser' and user.get('parent_user_id') == discord_id
        ]
        
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
                user_exists = any(u.get('email') == inv.get('email') for u in users)
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
            if user.get('discord_id') == subuser_id and user.get('parent_user_id') == discord_id:
                subuser_index = i
                break
        
        if subuser_index is None:
            return jsonify({'error': 'Sub-user not found or not authorized'}), 404
        
        # Update the sub-user's information
        if 'va_name' in data:
            users[subuser_index]['va_name'] = data['va_name']
        
        if 'permissions' in data:
            # Validate permissions - include all feature keys the main user has access to
            main_user_features = get_user_features(discord_id)
            valid_feature_keys = [key for key, info in main_user_features.items() if info.get('has_access')]
            
            # Include basic permissions
            basic_permissions = ['reimbursements_analysis', 'all']
            valid_permissions = basic_permissions + valid_feature_keys
            
            # Filter to only valid permissions
            permissions = [p for p in data['permissions'] if p in valid_permissions]
            users[subuser_index]['permissions'] = permissions
        
        # Update last modified timestamp
        users[subuser_index]['updated_at'] = datetime.utcnow().isoformat()
        
        if update_users_config(users):
            return jsonify({
                'success': True, 
                'message': 'Sub-user updated successfully',
                'subuser': {
                    'discord_id': users[subuser_index]['discord_id'],
                    'va_name': users[subuser_index].get('va_name'),
                    'permissions': users[subuser_index]['permissions'],
                    'updated_at': users[subuser_index]['updated_at']
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
        subuser = next((u for u in users if u.get('discord_id') == subuser_id and u.get('parent_user_id') == discord_id), None)
        
        if not subuser:
            return jsonify({'error': 'Sub-user not found or not authorized'}), 404
        
        # Remove the sub-user
        users = [u for u in users if not (u.get('discord_id') == subuser_id and u.get('parent_user_id') == discord_id)]
        
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
        if not user_record.get('enable_source_links'):
            return jsonify({
                'sources': [],
                'message': 'Source links are not enabled. Enable them in Settings to see purchase sources.'
            })
        
        # Get user's Google Sheet settings
        sheet_id = user_record.get('sheet_id')
        worksheet_title = user_record.get('worksheet_title')
        google_tokens = user_record.get('google_tokens', {})
        column_mapping = user_record.get('column_mapping', {})
        
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
        if user_record.get('search_all_worksheets'):
            cogs_data = analyzer.fetch_all_worksheets_cogs_data(
                google_tokens.get('access_token'),
                sheet_id
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
    access_token = user_record["google_tokens"]["access_token"]
    # Try one request; if 401, refresh and retry
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{user_record['sheet_id']}?fields=sheets(properties(title))"
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
    
    sheet_id = user_record["sheet_id"]
    access_token = user_record["google_tokens"]["access_token"]
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

def refresh_google_token(user_record):
    """
    Refresh the Google access token for a user record.
    Updates the user record and returns the new access token.
    """
    refresh_token = user_record["google_tokens"].get("refresh_token")
    if not refresh_token:
        raise Exception("No refresh_token found. User must re-link Google account.")

    token_url = "https://oauth2.googleapis.com/token"
    payload = {
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token"
    }
    resp = requests.post(token_url, data=payload)
    resp.raise_for_status()
    new_tokens = resp.json()
    
    # Keep the old refresh_token if Google didn't return a new one
    if "refresh_token" not in new_tokens:
        new_tokens["refresh_token"] = refresh_token

    # Update the user record
    user_record["google_tokens"].update(new_tokens)
    
    # Update the users config
    users = get_users_config()
    for i, user in enumerate(users):
        if user.get("discord_id") == user_record.get("discord_id"):
            users[i] = user_record
            break
    update_users_config(users)
    
    return new_tokens["access_token"]

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
        if user_record.get('user_type') == 'subuser':
            config_user = get_parent_user_record(discord_id)
            if not config_user:
                return jsonify({'error': 'Parent user not found'}), 404
        else:
            config_user = user_record
        
        # Check if Google Sheet is configured
        if not config_user.get('sheet_id') or not config_user.get('google_tokens'):
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
            print(f"[DEBUG] Returning cached discount opportunities from database for user {discord_id}")
            return jsonify(cached_opportunities)
        
        # Log environment configuration
        print(f"[DEBUG] DISCOUNT_MONITOR_EMAIL: {DISCOUNT_MONITOR_EMAIL}")
        print(f"[DEBUG] DISCOUNT_SENDER_EMAIL: {DISCOUNT_SENDER_EMAIL}")
        print(f"[DEBUG] Days back: {get_discount_email_days_back()}")
        user = get_user_record(discord_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get user config for analytics
        config_user_record = user
        if user and user.get('user_type') == 'subuser':
            parent_user_id = user.get('parent_user_id')
            if parent_user_id:
                parent_record = get_user_record(parent_user_id)
                if parent_record:
                    config_user_record = parent_record
        
        # Get the user's timezone
        user_timezone = user.get('timezone') if user else None
        
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
        if analytics_cache_key in analytics_cache:
            cache_entry = analytics_cache[analytics_cache_key]
            if datetime.now() - cache_entry['timestamp'] < timedelta(hours=24):
                print(f"[DEBUG] Using cached enhanced analytics")
                enhanced_analytics = cache_entry['data']
        
        if enhanced_analytics is None:
            print(f"[DEBUG] Generating fresh enhanced analytics (this may take a moment)")
            try:
                from orders_analysis import EnhancedOrdersAnalysis
                
                orders_url = config_user_record.get('sellerboard_orders_url')
                stock_url = config_user_record.get('sellerboard_stock_url')
                
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
                        'enable_source_links': config_user_record.get('enable_source_links', False),
                        'search_all_worksheets': config_user_record.get('search_all_worksheets', False),
                        'disable_sp_api': config_user_record.get('disable_sp_api', False),
                        'amazon_lead_time_days': config_user_record.get('amazon_lead_time_days', 90),
                        'discord_id': discord_id
                    }
                )
                
                if not analysis or not analysis.get('enhanced_analytics'):
                    return jsonify({
                        'opportunities': [],
                        'message': 'No inventory data available for analysis'
                    })
                    
                enhanced_analytics = analysis['enhanced_analytics']
                
                # Cache the enhanced analytics
                analytics_cache[analytics_cache_key] = {
                    'data': enhanced_analytics,
                    'timestamp': datetime.now()
                }
                print(f"[DEBUG] Cached enhanced analytics for 10 minutes")
                
            except Exception as e:
                print(f"[ERROR] Failed to generate analytics: {str(e)}")
                return jsonify({
                    'opportunities': [],
                    'message': f'Failed to generate analytics: {str(e)}'
                }), 500
        
        # Fetch recent email alerts
        email_alerts = fetch_discount_email_alerts()
        
        # Fetch source links CSV for ASIN matching with caching
        csv_cache_key = "source_links_csv"
        source_df = None
        
        if csv_cache_key in analytics_cache:
            cache_entry = analytics_cache[csv_cache_key]
            # Cache CSV for 24 hours for daily use
            if datetime.now() - cache_entry['timestamp'] < timedelta(hours=24):
                print(f"[DEBUG] Using cached CSV data")
                source_df = cache_entry['data']
        
        if source_df is None:
            print(f"[DEBUG] Fetching fresh CSV data")
            try:
                csv_url = 'https://docs.google.com/spreadsheets/d/e/2PACX-1vRz7iEc-6eA4pfImWfSs_qVyUWHmqDw8ET1PTWugLpqDHU6txhwyG9lCMA65Z9AHf-6lcvCcvbE4MPT/pub?output=csv'
                response = requests.get(csv_url, timeout=10)  # Further reduced timeout
                response.raise_for_status()
                
                csv_data = StringIO(response.text)
                source_df = pd.read_csv(csv_data)
                
                # Cache the DataFrame
                analytics_cache[csv_cache_key] = {
                    'data': source_df,
                    'timestamp': datetime.now()
                }
            except Exception as e:
                print(f"[WARNING] Failed to fetch CSV data: {str(e)}, continuing without source links")
                source_df = pd.DataFrame()  # Empty DataFrame
        
        # Pre-process CSV data for faster ASIN lookups
        print(f"[DEBUG] Pre-processing CSV data for faster lookups")
        asin_to_source_link = {}
        if source_df is not None and not source_df.empty:
            for _, row in source_df.iterrows():
                # Look for ASINs in any column
                for col in source_df.columns:
                    cell_value = str(row[col]) if pd.notna(row[col]) else ""
                    # Simple ASIN detection (10 characters starting with B)
                    if len(cell_value) == 10 and cell_value.startswith('B'):
                        # Look for URL/link columns in this row
                        for link_col in source_df.columns:
                            if any(keyword in link_col.lower() for keyword in ['url', 'link', 'source']):
                                potential_link = str(row[link_col]) if pd.notna(row[link_col]) else ""
                                if potential_link.startswith('http'):
                                    asin_to_source_link[cell_value.upper()] = potential_link
                                    break
        
        print(f"[DEBUG] Pre-processed {len(asin_to_source_link)} ASIN-to-source mappings")
        opportunities = []
        
        print(f"[DEBUG] Processing {len(email_alerts)} email alerts against inventory")
        print(f"[DEBUG] User has {len(enhanced_analytics)} ASINs in inventory")
        if enhanced_analytics:
            print(f"[DEBUG] Sample inventory ASINs: {list(enhanced_analytics.keys())[:5]}")
        
        # Process email alerts using multithreading
        def process_email_alert(email_alert):
            """Process a single email alert and return opportunity data"""
            retailer = email_alert['retailer']
            asin = email_alert['asin']
            
            # Skip if retailer filter is specified and doesn't match
            if retailer_filter and retailer_filter.lower() not in retailer.lower():
                return None
            
            # Check if this ASIN is in user's inventory
            if asin in enhanced_analytics:
                inventory_data = enhanced_analytics[asin]
                restock_data = inventory_data.get('restock', {})
                
                # Get restock information
                current_stock = restock_data.get('current_stock', 0)
                suggested_quantity = restock_data.get('suggested_quantity', 0)
                days_left = restock_data.get('days_left', None)
                
                # Determine if restocking is needed
                needs_restock = suggested_quantity > 0
                
                # Fast lookup for source link using pre-processed dictionary
                source_link = asin_to_source_link.get(asin.upper())
                
                # Extract special promotional text for Vitacost
                promo_message = None
                if retailer.lower() == 'vitacost':
                    html_content = email_alert.get('html_content', '')
                    promo_message = extract_vitacost_promo_message(html_content)
                
                # Determine status based on restock need
                if needs_restock:
                    status = 'Restock Needed'
                    priority_score = calculate_opportunity_priority(inventory_data, days_left, suggested_quantity)
                else:
                    status = 'Not Needed'
                    priority_score = 0  # Lower priority for items not needed
                
                opportunity = {
                    'asin': asin,
                    'retailer': retailer,
                    'product_name': inventory_data.get('product_name', ''),
                    'current_stock': current_stock,
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
        print(f"[DEBUG] Using {max_workers} threads to process {len(email_alerts)} alerts")
        
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
        
        print(f"[DEBUG] Final opportunities count: {len(opportunities)}")
        print(f"[DEBUG] Breakdown - Restock Needed: {restock_needed_count}, Not Needed: {not_needed_count}, Not Tracked: {not_tracked_count}")
        
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
        print(f"[DEBUG] Cached discount opportunities in database for user {discord_id}")
        
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
            ('lambda_deployment', 'Lambda Deployment', 'AWS Lambda function deployment', True)
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
        
        print("[DEBUG] Feature flags system initialized with user groups")
        
    except Exception as e:
        print(f"Error initializing feature flags: {e}")

def has_feature_access(discord_id, feature_key):
    """Check if user has access to a specific feature (individual or group-based)"""
    try:
        # Admin always has access to everything
        user = get_user_record(discord_id)
        if user and user.get('discord_id') == '712147636463075389':  # Admin discord ID
            return True
            
        # If user is a subuser, check parent's access instead
        if user and user.get('user_type') == 'subuser':
            parent_user_id = user.get('parent_user_id')
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
            if user and 'feature_permissions' in user:
                user_perm = user['feature_permissions'].get(feature_key, {})
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
        user_features = {}
        
        # Get all features
        cursor.execute('SELECT feature_key, feature_name, description, is_beta FROM features')
        all_features = cursor.fetchall()
        
        for feature_key, name, description, is_beta in all_features:
            # has_feature_access already handles subuser logic
            has_access = has_feature_access(discord_id, feature_key)
            user_features[feature_key] = {
                'name': name,
                'description': description,
                'is_beta': bool(is_beta),
                'has_access': has_access
            }
        
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
        
        cursor.execute('''
            SELECT f.feature_key, f.feature_name, f.description, f.is_beta,
                   fl.is_public, fl.launched_at, fl.launch_notes
            FROM features f
            LEFT JOIN feature_launches fl ON f.feature_key = fl.feature_key
            ORDER BY f.feature_name
        ''')
        
        features = []
        for row in cursor.fetchall():
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
        
        # Try both approaches: first the simple orders_report.py approach, then the complex one
        try:
            # Simple approach first - exactly like orders_report.py
            simple_response = requests.get(cogs_url, timeout=30)
            if simple_response.status_code == 200:
                response = simple_response
            else:
                # Fall back to complex approach
                raise requests.exceptions.HTTPError(response=simple_response)
        except:
            # Create a session to handle cookies properly (same as orders_analysis.py)
            session = requests.Session()
            
            # Add headers that might be expected by Sellerboard (same as orders_analysis.py)
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/csv,application/csv,text/plain,*/*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
            }
            
            # Try the complex approach with allow_redirects=True
            response = session.get(cogs_url, timeout=30, allow_redirects=True, headers=headers)
        
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

        # Security check: Ensure we're not mixing impersonation data
        if 'admin_impersonating' in session:
            target_user_id = session['admin_impersonating'].get('target_user_id')
            if str(discord_id) != str(target_user_id):
                return jsonify({"error": "Session impersonation mismatch"}), 403

        # Get user config for Google access (use parent config for subusers)
        config_user_record = user_record
        if user_record and user_record.get('user_type') == 'subuser':
            parent_user_id = user_record.get('parent_user_id')
            if parent_user_id:
                parent_record = get_user_record(parent_user_id)
                if parent_record:
                    config_user_record = parent_record

        # Get the Google Sheet settings for purchase data
        sheet_id = config_user_record.get('sheet_id')
        google_tokens = config_user_record.get('google_tokens', {})
        column_mapping = config_user_record.get('column_mapping', {})
        
        # Check for Sellerboard COGS URL - prioritize this over Google Sheets for inventory data
        sellerboard_cogs_url = config_user_record.get('sellerboard_cogs_url')
        
        if sellerboard_cogs_url:
            # Try to use Sellerboard COGS data as the inventory source
            try:
                inventory_data = fetch_sellerboard_cogs_data(sellerboard_cogs_url)
                
                # Still need Google Sheets for purchase data
                if not sheet_id or not google_tokens.get('access_token'):
                    return jsonify({"error": "Google Sheet not configured. Please set up Google Sheets in Settings for purchase data."}), 400
                    
            except Exception as e:
                # Fall back to Google Sheets approach instead of failing
                inventory_data = None
                if not sheet_id or not google_tokens.get('access_token'):
                    return jsonify({
                        "error": f"COGS data unavailable ({str(e)[:100]}...) and Google Sheet not configured. Please either fix the COGS URL or set up Google Sheets in Settings.",
                        "cogs_error": str(e)
                    }), 400
        else:
            # Fallback to original logic
            if not sheet_id or not google_tokens.get('access_token'):
                return jsonify({"error": "Google Sheet not configured. Please set up Google Sheets in Settings first."}), 400

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
        sellerboard_url = config_user_record.get('sellerboard_stock_url')
        if not sellerboard_url:
            return jsonify({"error": "Sellerboard stock URL not configured"}), 400

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
        if user and user.get('user_type') == 'subuser':
            parent_user_id = user.get('parent_user_id')
            if parent_user_id:
                parent_record = get_user_record(parent_user_id)
                if parent_record:
                    config_user_record = parent_record
        
        # Check if user has Google tokens
        if not config_user_record.get('google_tokens'):
            return jsonify({'worksheets': ['Unknown', 'Other', 'Misc', 'No Source']})
        
        try:
            # Get Google access token
            google_tokens = config_user_record.get('google_tokens', {})
            
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
        if user and user.get('user_type') == 'subuser':
            parent_user_id = user.get('parent_user_id')
            if parent_user_id:
                parent_record = get_user_record(parent_user_id)
                if parent_record:
                    config_user_record = parent_record
        
        # Check if user has Google tokens
        if not config_user_record.get('google_tokens'):
            return jsonify({
                'error': 'Google account not linked',
                'worksheets': ['All Leads']  # Fallback option
            })
            
        sheet_id = '1Q5weSRaRd7r1zdiA2bwWwcWIwP6pxplGYmY7k9a3aqw'  # Your leads sheet ID
        
        # Get Google access token
        google_tokens = config_user_record.get('google_tokens', {})
        
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
        if user and user.get('user_type') == 'subuser':
            parent_user_id = user.get('parent_user_id')
            if parent_user_id:
                parent_record = get_user_record(parent_user_id)
                if parent_record:
                    config_user_record = parent_record
        
        orders_url = config_user_record.get('sellerboard_orders_url')
        stock_url = config_user_record.get('sellerboard_stock_url')
        
        if not orders_url or not stock_url:
            return jsonify({'error': 'Sellerboard URLs not configured'}), 400
            
        from datetime import datetime
        import pytz
        from orders_analysis import OrdersAnalysis
        
        user_timezone = config_user_record.get('timezone', 'America/New_York')
        tz = pytz.timezone(user_timezone)
        today = datetime.now(tz).date()
        
        orders_analysis = OrdersAnalysis(orders_url, stock_url)
        analysis = orders_analysis.analyze(
            for_date=today,
            user_timezone=user_timezone,
            user_settings={
                'enable_source_links': config_user_record.get('enable_source_links', False),
                'search_all_worksheets': config_user_record.get('search_all_worksheets', False),
                'disable_sp_api': config_user_record.get('disable_sp_api', False),
                'amazon_lead_time_days': config_user_record.get('amazon_lead_time_days', 90),
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
        if user and user.get('user_type') == 'subuser':
            parent_user_id = user.get('parent_user_id')
            if parent_user_id:
                parent_record = get_user_record(parent_user_id)
                if parent_record:
                    config_user_record = parent_record
        
        # Check if user has necessary configurations
        if not config_user_record.get('sellerboard_orders_url') or not config_user_record.get('sellerboard_stock_url'):
            return jsonify({
                'error': 'Sellerboard URLs not configured',
                'message': 'Please configure your Sellerboard URLs in Settings first'
            }), 400
        
        # Get current inventory analysis
        orders_url = config_user_record.get('sellerboard_orders_url')
        stock_url = config_user_record.get('sellerboard_stock_url')
        user_timezone = config_user_record.get('timezone', 'America/New_York')
        
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
                    'enable_source_links': config_user_record.get('enable_source_links', False),
                    'search_all_worksheets': config_user_record.get('search_all_worksheets', False),
                    'disable_sp_api': config_user_record.get('disable_sp_api', False),
                    'amazon_lead_time_days': config_user_record.get('amazon_lead_time_days', 90),
                    'discord_id': discord_id,
                    # Add Google Sheet settings for purchase analytics (same as Smart Restock)
                    'sheet_id': config_user_record.get('sheet_id'),
                    'worksheet_title': config_user_record.get('worksheet_title'), 
                    'google_tokens': config_user_record.get('google_tokens', {}),
                    'column_mapping': config_user_record.get('column_mapping', {})
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
        if not config_user_record.get('google_tokens'):
            return jsonify({
                'error': 'Google account not linked',
                'message': 'Please link your Google account in Settings to access the leads sheet'
            }), 400
            
        try:
            # Get Google access token - use the refresh_google_token function from app.py
            discord_id_temp = discord_id  # Store temporarily
            google_tokens = config_user_record.get('google_tokens', {})
            
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
        if user and user.get('user_type') == 'subuser':
            parent_user_id = user.get('parent_user_id')
            if parent_user_id:
                parent_record = get_user_record(parent_user_id)
                if parent_record:
                    config_user_record = parent_record
        
        # Check if user has configured their leads sheet
        user_sheet_id = config_user_record.get('sheet_id')
        user_worksheet_title = config_user_record.get('worksheet_title')
        
        if not user_sheet_id or not user_worksheet_title:
            return jsonify({
                'error': 'Leads sheet not configured',
                'message': 'Please configure your leads sheet in Settings first'
            }), 400
        
        # Check if user has Google tokens for API access
        if not config_user_record.get('google_tokens'):
            return jsonify({
                'error': 'Google account not linked',
                'message': 'Please link your Google account in Settings to access the leads sheet'
            }), 400
        
        # Get Google access token
        google_tokens = config_user_record.get('google_tokens', {})
        
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
            column_mapping = config_user_record.get('column_mapping', {})
            
            # Check if user has search_all_worksheets enabled
            search_all_worksheets = config_user_record.get('search_all_worksheets', True)  # Default to True
            
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
    """Fetch recent email alerts from admin-configured Gmail using Gmail API"""
    try:
        monitor_email = DISCOUNT_MONITOR_EMAIL
        if not monitor_email:
            # Return mock data if no email configured
            return [
                {
                    'retailer': 'Vitacost',
                    'asin': 'B07XVTRJKX',
                    'subject': 'Vitacost Alert: B07XVTRJKX',
                    'html_content': '''<div id="m_731648639157524744topPromoMessages">== $10 off orders $50+ ==</div>
                                      <p id="m_7316486391575247445featuredDiscount">Free shipping on orders $49+</p>''',
                    'alert_time': '2025-08-09T19:53:00Z'
                },
                {
                    'retailer': 'Walmart', 
                    'asin': 'B08NDRQR5K',
                    'subject': 'Walmart Alert: B08NDRQR5K',
                    'html_content': '<div>Special promotion available</div>',
                    'alert_time': '2025-08-09T18:30:00Z'
                }
            ]
        
        # Get system-wide discount monitoring Gmail access
        print(f"[DEBUG] Checking system-wide discount monitoring Gmail access...")
        
        # Try to get admin Gmail tokens from system config
        admin_gmail_config = get_admin_gmail_config()
        
        if not admin_gmail_config or not admin_gmail_config.get('tokens'):
            print(f"[DEBUG] No system-wide discount monitoring Gmail configured")
            print(f"[DEBUG] Admin needs to connect Gmail for discount monitoring")
            # Return mock data if admin Gmail not configured
            return fetch_mock_discount_alerts()
        
        print(f"[DEBUG] ✅ FOUND SYSTEM-WIDE DISCOUNT GMAIL CONFIG")
        print(f"[DEBUG] Connected Gmail: {admin_gmail_config.get('gmail_email', 'Unknown')}")
        print(f"[DEBUG] All users will use this Gmail source for discount opportunities")
        
        # Build Gmail search query
        # Search for emails from alert service in the last N days
        # No keyword filtering needed - alerts are already filtered for relevance
        from datetime import datetime, timedelta
        import pytz
        
        days_back = get_discount_email_days_back()
        cutoff_date = datetime.now(pytz.UTC) - timedelta(days=days_back)
        
        # Try different date formats for Gmail
        date_str_slash = cutoff_date.strftime('%Y/%m/%d')
        date_str_dash = cutoff_date.strftime('%Y-%m-%d')
        
        print(f"[DEBUG] Cutoff date (UTC): {cutoff_date}")
        print(f"[DEBUG] Date string (slash): {date_str_slash}")
        print(f"[DEBUG] Date string (dash): {date_str_dash}")
        
        # Also show current time for debugging
        now_utc = datetime.now(pytz.UTC)
        print(f"[DEBUG] Current time (UTC): {now_utc}")
        print(f"[DEBUG] Timezone info - Looking for emails newer than {cutoff_date}")
        
        # Create search query for Gmail - try with dash format first
        query = f'from:{DISCOUNT_SENDER_EMAIL} after:{date_str_dash}'
        
        print(f"Gmail search query: {query}")
        
        # First, test basic Gmail API access with a simple query
        print("[DEBUG] Testing basic Gmail API access...")
        print(f"[DEBUG] About to search system-wide Gmail for discount monitoring")
        
        # Try to get the Gmail profile to verify which account we're accessing
        try:
            # Get admin Gmail access token
            access_token = get_admin_gmail_token()
            if access_token:
                import requests
                profile_response = requests.get(
                    'https://gmail.googleapis.com/gmail/v1/users/me/profile',
                    headers={'Authorization': f'Bearer {access_token}'}
                )
                if profile_response.status_code == 200:
                    profile_data = profile_response.json()
                    gmail_email = profile_data.get('emailAddress')
                    print(f"[DEBUG] 🔍 ACTUALLY SEARCHING GMAIL ACCOUNT: {gmail_email}")
                    print(f"[DEBUG] Total messages in account: {profile_data.get('messagesTotal', 'Unknown')}")
                else:
                    print(f"[DEBUG] Could not get Gmail profile: {profile_response.status_code}")
        except Exception as e:
            print(f"[DEBUG] Error getting Gmail profile: {e}")
        
        basic_query = 'is:inbox'
        basic_results = search_gmail_messages_admin(basic_query, max_results=5)
        if basic_results and basic_results.get('messages'):
            print(f"[DEBUG] Gmail API working - found {len(basic_results['messages'])} inbox messages")
        else:
            print("[DEBUG] Gmail API issue - no inbox messages found")
        
        # Search for messages using admin Gmail access
        search_results = search_gmail_messages_admin(query, max_results=100)
        
        # If dash format doesn't work, try slash format
        if not search_results or not search_results.get('messages'):
            print(f"[DEBUG] Dash format failed, trying slash format")
            query_slash = f'from:{DISCOUNT_SENDER_EMAIL} after:{date_str_slash}'
            print(f"[DEBUG] Slash query: {query_slash}")
            search_results = search_gmail_messages_admin(query_slash, max_results=100)
        
        # If both formats fail, try with 'newer_than:' syntax
        if not search_results or not search_results.get('messages'):
            print(f"[DEBUG] Both date formats failed, trying newer_than syntax")
            query_newer = f'from:{DISCOUNT_SENDER_EMAIL} newer_than:{days_back}d'
            print(f"[DEBUG] Newer_than query: {query_newer}")
            search_results = search_gmail_messages_admin(query_newer, max_results=100)
        
        # Check if we got results with date filtering
        messages = search_results.get('messages', []) if search_results else []
        
        # If no messages found with date filtering, try without date filter
        if not messages:
            print("[DEBUG] No messages found with date filtering, fetching all Distill emails...")
            
            # Fetch all Distill emails without date filter, then filter client-side
            no_date_query = f'from:{DISCOUNT_SENDER_EMAIL}'
            print(f"[DEBUG] Searching without date filter: {no_date_query}")
            search_results = search_gmail_messages_admin(no_date_query, max_results=100)
            
            if not search_results:
                print("[DEBUG] No Distill emails found at all")
                return fetch_mock_discount_alerts()
            
            messages = search_results.get('messages', [])
            if not messages:
                print("[DEBUG] No messages in search results even without date filter")
                return fetch_mock_discount_alerts()
            
            print(f"[DEBUG] Found {len(messages)} Distill emails total, will filter by date client-side")
        
        
        print(f"Found {len(messages)} messages from Gmail search")
        
        email_alerts = []
        processed_count = 0
        date_filtered_count = 0
        
        # Process each message
        for message_info in messages[:50]:  # Limit to 50 most recent
            message_id = message_info.get('id')
            if not message_id:
                continue
                
            # Get full message details
            message_data = get_gmail_message_admin(message_id)
            if not message_data:
                continue
            
            # Extract email content
            email_content = extract_email_content(message_data)
            if not email_content:
                continue
            
            processed_count += 1
            
            # Verify sender is from alert service
            sender = email_content.get('sender', '')
            if DISCOUNT_SENDER_EMAIL not in sender:
                continue
            
            # Convert Gmail date to ISO format and check if within date range
            gmail_date = email_content.get('date', '')
            iso_date = convert_gmail_date_to_iso(gmail_date)
            
            # Client-side date filtering
            try:
                from email.utils import parsedate_to_datetime
                if gmail_date:
                    email_datetime = parsedate_to_datetime(gmail_date)
                    if email_datetime < cutoff_date:
                        print(f"[DEBUG] Filtering out email from {email_datetime} (before cutoff {cutoff_date})")
                        date_filtered_count += 1
                        continue
                    else:
                        print(f"[DEBUG] Including email from {email_datetime} (after cutoff {cutoff_date})")
            except Exception as e:
                print(f"[DEBUG] Date parsing error for {gmail_date}: {e}")
                # Include email if we can't parse the date
            
            # Parse email subject to extract retailer and ASIN
            subject = email_content.get('subject', '')
            print(f"[DEBUG] Parsing subject: {subject}")
            parsed_alert = parse_email_subject(subject)
            
            if parsed_alert:
                print(f"[DEBUG] Successfully parsed - Retailer: {parsed_alert['retailer']}, ASIN: {parsed_alert['asin']}")
                email_alerts.append({
                    'retailer': parsed_alert['retailer'],
                    'asin': parsed_alert['asin'],
                    'note': parsed_alert.get('note'),
                    'subject': subject,
                    'html_content': email_content.get('html_content', ''),
                    'alert_time': iso_date,
                    'message_id': message_id
                })
            else:
                print(f"[DEBUG] Could not parse subject: {subject}")
                # Try to extract ASIN from email body if subject parsing fails
                html_content = email_content.get('html_content', '')
                text_content = email_content.get('text_content', '')
                
                # Look for ASIN pattern in content
                import re
                asin_pattern = r'[B-Z][0-9A-Z]{9}'
                
                # Try HTML content first
                asin_match = re.search(asin_pattern, html_content)
                if not asin_match and text_content:
                    asin_match = re.search(asin_pattern, text_content)
                
                if asin_match:
                    asin = asin_match.group()
                    print(f"[DEBUG] Found ASIN in email body: {asin}")
                    
                    # Try to identify retailer from subject or content
                    retailer = "Unknown"
                    subject_lower = subject.lower()
                    for potential_retailer in ['walmart', 'target', 'vitacost', 'lowes', 'home depot', 'cvs', 'amazon']:
                        if potential_retailer in subject_lower or potential_retailer in html_content.lower():
                            retailer = potential_retailer.title()
                            break
                    
                    email_alerts.append({
                        'retailer': retailer,
                        'asin': asin,
                        'note': f"From subject: {subject[:50]}...",
                        'subject': subject,
                        'html_content': html_content,
                        'alert_time': iso_date,
                        'message_id': message_id
                    })
                    print(f"[DEBUG] Created fallback alert - Retailer: {retailer}, ASIN: {asin}")
                else:
                    print(f"[DEBUG] No ASIN found in email body either")
        
        print(f"[DEBUG] Processed {processed_count} emails, filtered out {date_filtered_count} by date")
        
        print(f"Processed {len(email_alerts)} email alerts")
        
        # Sort by alert time (newest first)
        email_alerts.sort(key=lambda x: x['alert_time'], reverse=True)
        
        return email_alerts
        
    except Exception as e:
        print(f"Error fetching email alerts: {e}")
        import traceback
        traceback.print_exc()
        # Return mock data on error
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
                if user.get('email') == DISCOUNT_MONITOR_EMAIL:
                    admin_user = user
                    break
            
            if admin_user:
                debug_info['gmail_access'] = {
                    'user_found': True,
                    'has_google_tokens': bool(admin_user.get('google_tokens')),
                    'google_linked': admin_user.get('google_linked', False),
                    'tokens_keys': list(admin_user.get('google_tokens', {}).keys()) if admin_user.get('google_tokens') else []
                }
                
                # Try Gmail search
                if admin_user.get('google_tokens'):
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
                if user.get('email') == DISCOUNT_MONITOR_EMAIL and user.get('google_tokens'):
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
            if user.get('email') == DISCOUNT_MONITOR_EMAIL and user.get('google_tokens'):
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
        if user.get('email') == monitor_email:
            user_found = True
            user_has_tokens = bool(user.get('google_tokens'))
            results['user_info'] = {
                'discord_id': user.get('discord_id'),
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
            for email in [u.get('email', 'No email') for u in users]
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
MIN_REQUEST_INTERVAL = 5.0  # Much longer interval - 5 seconds between requests

import time
import random
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

# Create a persistent session for Amazon requests with better anti-detection
amazon_session = None
session_last_used = 0
SESSION_TIMEOUT = 300  # 5 minutes

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
        orders_url = user_record.get('sellerboard_orders_url')
        stock_url = user_record.get('sellerboard_stock_url')
        
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
        user_timezone = user_record.get('timezone', 'UTC')
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
                print(f"eBay Lister: First row of data: {stock_df.iloc[0].to_dict()}")
            
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
        
        if user_record.get('user_type') == 'subuser':
            # This is a VA/sub-user - get their parent's purchases
            parent_user = get_parent_user_record(discord_id)
            if parent_user:
                target_user_id = parent_user.get('discord_id', discord_id)
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
        if user_record.get('user_type') == 'subuser':
            parent_user = get_parent_user_record(discord_id)
            if parent_user:
                config_user = parent_user
                print(f"Using parent user's Sellerboard config for VA {discord_id}")
        
        orders_url = config_user.get('sellerboard_orders_url')
        stock_url = config_user.get('sellerboard_stock_url')
        
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
                    config_user.get('timezone', 'UTC')
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
        if user_record.get('user_type') == 'subuser':
            parent_user = get_parent_user_record(discord_id)
            if parent_user:
                target_user_id = parent_user.get('discord_id', discord_id)
        
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

@app.route('/api/debug/source-links', methods=['GET'])
@login_required
def debug_source_links():
    """Debug endpoint to check discount opportunities source link processing"""
    try:
        discord_id = session['discord_id']
        user_record = get_user_record(discord_id)
        
        if not user_record:
            return jsonify({'error': 'User record not found'}), 404
        
        # Check source links settings
        enable_source_links = user_record.get('enable_source_links', False)
        sheet_configured = bool(user_record.get('sheet_id') and user_record.get('worksheet_title'))
        
        # Fetch email alerts
        email_alerts = fetch_discount_email_alerts()
        
        # Fetch source CSV if enabled - use same logic as main function
        source_df = None
        asin_to_source_link = {}
        csv_error = None
        
        # Try to fetch CSV data
        csv_url = None
        csv_data_preview = None
        
        if enable_source_links:
            try:
                print(f"[DEBUG] Attempting to fetch CSV data for debug...")
                # Use the same hardcoded CSV URL as the main function
                csv_url = 'https://docs.google.com/spreadsheets/d/e/2PACX-1vRz7iEc-6eA4pfImWfSs_qVyUWHmqDw8ET1PTWugLpqDHU6txhwyG9lCMA65Z9AHf-6lcvCcvbE4MPT/pub?output=csv'
                response = requests.get(csv_url, timeout=10)
                response.raise_for_status()
                
                from io import StringIO
                import pandas as pd
                source_df = pd.read_csv(StringIO(response.text))
                
                print(f"[DEBUG] CSV fetched successfully, rows: {len(source_df)}, columns: {list(source_df.columns)}")
                
                # Get preview of first few rows for debugging
                if not source_df.empty:
                    csv_data_preview = source_df.head(3).to_dict('records')
                
                # Process source links like the main function does
                if source_df is not None and not source_df.empty:
                    for _, row in source_df.iterrows():
                        for col in source_df.columns:
                            cell_value = str(row[col]) if pd.notna(row[col]) else ""
                            if len(cell_value) == 10 and cell_value.isalnum():  # ASIN pattern
                                for link_col in source_df.columns:
                                    if any(keyword in link_col.lower() for keyword in ['url', 'link', 'source']):
                                        potential_link = str(row[link_col]) if pd.notna(row[link_col]) else ""
                                        if potential_link.startswith('http'):
                                            asin_to_source_link[cell_value.upper()] = potential_link
                                            print(f"[DEBUG] Found mapping: {cell_value.upper()} -> {potential_link}")
                                            break
                
                print(f"[DEBUG] Total ASIN mappings created: {len(asin_to_source_link)}")
                
            except Exception as e:
                csv_error = str(e)
                print(f"[DEBUG] CSV fetch error: {csv_error}")
        else:
            csv_error = "Source links are disabled in user settings"
        
        # Sample a few opportunities to show their source link status
        sample_opportunities = []
        for i, alert in enumerate(email_alerts[:5]):  # First 5 alerts
            asin = alert.get('asin', 'N/A')
            source_link = asin_to_source_link.get(asin.upper()) if asin != 'N/A' else None
            
            sample_opportunities.append({
                'asin': asin,
                'retailer': alert.get('retailer', 'N/A'),
                'has_source_link': bool(source_link),
                'source_link': source_link,
                'alert_note': alert.get('note', 'N/A')
            })
        
        return jsonify({
            'debug_info': {
                'enable_source_links': enable_source_links,
                'sheet_configured': sheet_configured,
                'sheet_id': user_record.get('sheet_id'),
                'worksheet_title': user_record.get('worksheet_title'),
                'google_tokens_present': bool(user_record.get('google_tokens', {}).get('refresh_token')),
                'csv_error': csv_error,
                'csv_url': csv_url,
                'csv_rows_found': len(source_df) if source_df is not None else 0,
                'csv_columns': list(source_df.columns) if source_df is not None and not source_df.empty else [],
                'asin_to_source_mappings': len(asin_to_source_link),
                'total_email_alerts': len(email_alerts)
            },
            'sample_opportunities': sample_opportunities,
            'first_few_source_mappings': dict(list(asin_to_source_link.items())[:5]) if asin_to_source_link else {},
            'csv_data_preview': csv_data_preview[:3] if csv_data_preview else []
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

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
        'environment': os.getenv('DEMO_MODE', 'false')
    })

@app.route('/api/demo/toggle', methods=['POST'])
def toggle_demo_mode():
    """Toggle demo mode (for development/testing only)"""
    global DEMO_MODE
    
    # Only allow toggling in development
    if os.getenv('FLASK_ENV') == 'development' or os.getenv('ENVIRONMENT') == 'development':
        DEMO_MODE = not DEMO_MODE
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
    return jsonify({
        'demo_mode': True,
        'message': 'Demo mode enabled - all data is now simulated for demonstration purposes'
    })

@app.route('/api/demo/disable', methods=['POST'])
def disable_demo_mode():
    """Disable demo mode"""
    global DEMO_MODE
    DEMO_MODE = False
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
            user_features[user['discord_id']] = {}
            
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
            if user.get('discord_id') == user_id:
                if 'feature_permissions' not in user:
                    user['feature_permissions'] = {}
                user['feature_permissions'][feature_key] = {
                    'has_access': True,
                    'granted_by': discord_id,
                    'granted_at': datetime.utcnow().isoformat()
                }
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
            if user.get('discord_id') == user_id:
                if 'feature_permissions' in user and feature_key in user['feature_permissions']:
                    del user['feature_permissions'][feature_key]
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
        users_dict = {user['discord_id']: user for user in users}
        
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
                    'email': user.get('email', ''),
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