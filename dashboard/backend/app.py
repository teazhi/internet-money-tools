from flask import Flask, request, jsonify, session, redirect, url_for, send_from_directory, make_response
from flask_cors import CORS
import os
import json
import requests
import boto3
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

# Load environment variables
try:
    load_dotenv()
    pass  # Environment variables loaded
except Exception as e:
    pass  # Failed to load .env file

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

def get_users_config():
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
    
    # Check specific permission
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
                    user_record['permissions'] = valid_invitation.get('permissions', ['sellerboard_upload'])
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
        "scope": "https://www.googleapis.com/auth/spreadsheets.readonly https://www.googleapis.com/auth/drive.readonly https://www.googleapis.com/auth/gmail.readonly",
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

@app.route('/api/google/spreadsheets')
@login_required
def list_spreadsheets():
    discord_id = session['discord_id']
    user_record = get_user_record(discord_id)
    
    if not user_record or not user_record.get('google_tokens'):
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
        
        files = safe_google_api_call(user_record, api_call)
        return jsonify({'spreadsheets': files})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/google/worksheets/<spreadsheet_id>')
@login_required
def list_worksheets(spreadsheet_id):
    discord_id = session['discord_id']
    user_record = get_user_record(discord_id)
    
    if not user_record or not user_record.get('google_tokens'):
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
        
        worksheets = safe_google_api_call(user_record, api_call)
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
    
    if not user_record or not user_record.get('google_tokens'):
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
        
        headers = safe_google_api_call(user_record, api_call)
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
        headers = safe_google_api_call(user_record, api_call)
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
        
        stock_url = user_record.get('sellerboard_stock_url')
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
        # Process dashboard analytics request
        
        # Try SP-API first, fallback to Sellerboard if needed
        
        # Get user's timezone preference first and update last activity
        discord_id = session['discord_id']
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
        
        # Update last activity for analytics access
        if user_record:
            try:
                users = get_users_config()
                for user in users:
                    if user.get("discord_id") == discord_id:
                        user['last_activity'] = datetime.now().isoformat()
                        if 'discord_username' in session:
                            user['discord_username'] = session['discord_username']
                        break
                update_users_config(users)
            except Exception as e:
                # Failed to update last activity
                pass
        
        # Get query parameter for date, default to yesterday until 11:59 PM
        target_date_str = request.args.get('date')
        if target_date_str:
            try:
                target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
            except ValueError:
                return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
        else:
            # Default to UTC if no timezone set
            if user_timezone:
                try:
                    tz = pytz.timezone(user_timezone)
                    now = datetime.now(tz)
                    pass  # Debug print removed
                except pytz.UnknownTimeZoneError:
                    now = datetime.now()
                    pass  # Debug print removed
            else:
                now = datetime.now()
            
            # Show yesterday's data until 11:59 PM today, then show today's data
            if now.hour == 23 and now.minute == 59:
                # At 11:59 PM, switch to today's data
                target_date = now.date()
                pass  # Debug print removed
            else:
                # Show yesterday's complete data throughout the day
                target_date = now.date() - timedelta(days=1)
        
        
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
        
        
        pass  # Debug print removed
        pass  # Debug print removed
        
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

@app.route('/api/upload/sellerboard', methods=['POST'])
@permission_required('sellerboard_upload')
def upload_sellerboard_file():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'Invalid file type. Allowed: CSV, XLSX, XLSM, XLS'}), 400
        
        discord_id = session['discord_id']
        filename = secure_filename(file.filename)
        
        # Determine target user (for sub-users, upload to parent's account)
        current_user = get_user_record(discord_id)
        if current_user and current_user.get('user_type') == 'subuser':
            target_user_id = current_user.get('parent_user_id')
            uploaded_by = discord_id  # Track who actually uploaded
        else:
            target_user_id = discord_id
            uploaded_by = discord_id
        
        # Create user-specific filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        user_filename = f"{target_user_id}_{timestamp}_{filename}"
        
        # Upload to S3
        s3_client = get_s3_client()
        file_content = file.read()
        
        # Upload to S3 with user-specific key
        s3_key = f"sellerboard_files/{user_filename}"
        s3_client.put_object(
            Bucket=CONFIG_S3_BUCKET,
            Key=s3_key,
            Body=file_content,
            ContentType=file.content_type
        )
        
        # Update target user record with uploaded file info
        users = get_users_config()
        user_record = next((u for u in users if u.get("discord_id") == target_user_id), None)
        
        if user_record is None:
            user_record = {"discord_id": target_user_id}
            users.append(user_record)
        
        # Store file information
        if 'uploaded_files' not in user_record:
            user_record['uploaded_files'] = []
        
        # File type management: Keep one of each type (sellerboard and listing loader)
        # Determine file type based on filename using standardized function
        file_type_category = determine_file_type_category(filename)
        
        # Default to sellerboard for 'other' category files (CSV and unrecognized files)
        if file_type_category == 'other':
            file_type_category = 'sellerboard'
        
        file_info = {
            'filename': filename,
            's3_key': s3_key,
            'upload_date': datetime.utcnow().isoformat() + 'Z',  # Use UTC with Z suffix
            'file_size': len(file_content),
            'file_type': file.content_type,
            'file_type_category': file_type_category,
            'uploaded_by': uploaded_by  # Track who uploaded the file
        }
        
        # Clean up old files of the same type using the new S3-based cleanup
        cleanup_result = cleanup_old_files_on_upload(target_user_id, file_type_category, s3_key)
        
        # Note: We no longer maintain the uploaded_files array in user records
        # since we now get files directly from S3 using proper discord_id filtering
        # This ensures each user only sees their own files
        
        # Always return success since we no longer depend on user config updates for file management
        success_message = 'File uploaded successfully'
        if cleanup_result['deleted_count'] > 0:
            success_message += f' (replaced {cleanup_result["deleted_count"]} old file{"s" if cleanup_result["deleted_count"] > 1 else ""})'
        
        return jsonify({
            'message': success_message,
            'file_info': file_info,
            'cleanup_result': cleanup_result
        })
            
    except Exception as e:
        pass  # Debug print removed
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500

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

@app.route('/api/files/sellerboard', methods=['GET'])
@login_required
def list_sellerboard_files():
    """List user's uploaded files - now with proper discord_id filtering"""
    try:
        discord_id = session['discord_id']
        
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

@app.route('/api/files/cleanup-duplicates', methods=['POST'])
@login_required
def cleanup_user_duplicates():
    """Clean up duplicate files for the current user, keeping only the latest of each type"""
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

@app.route('/api/admin/migrate-all-files', methods=['POST'])
@login_required
def migrate_all_user_files():
    """Admin endpoint to migrate all existing files to proper directory structure"""
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
    """Remove _updated files from user records - these are script outputs, not user files"""
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

@app.route('/api/files/migrate', methods=['POST'])
@login_required
def migrate_existing_files():
    """Migrate existing S3 files to user records"""
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

@app.route('/api/files/status', methods=['GET'])
@login_required
def files_upload_status():
    """Check if user has uploaded both required file types"""
    try:
        discord_id = session['discord_id']
        user_record = get_user_record(discord_id)
        
        if not user_record or 'uploaded_files' not in user_record:
            return jsonify({
                'has_sellerboard': False,
                'has_listing_loader': False,
                'files_complete': False
            })
        
        uploaded_files = user_record['uploaded_files']
        has_sellerboard = any(f.get('file_type_category') == 'sellerboard' for f in uploaded_files)
        has_listing_loader = any(f.get('file_type_category') == 'listing_loader' for f in uploaded_files)
        
        return jsonify({
            'has_sellerboard': has_sellerboard,
            'has_listing_loader': has_listing_loader,
            'files_complete': has_sellerboard and has_listing_loader
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/files/sellerboard/<path:file_key>', methods=['DELETE', 'OPTIONS'])
def delete_sellerboard_file(file_key):
    """Delete a specific Sellerboard file"""
    # Handle preflight OPTIONS request
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers.add('Access-Control-Allow-Origin', request.headers.get('Origin', '*'))
        response.headers.add('Access-Control-Allow-Methods', 'DELETE, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        return response
    
    # Apply login check only for non-OPTIONS requests
    if not session.get('discord_id'):
        return jsonify({'error': 'Authentication required'}), 401
    
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

@app.route('/api/invite-subuser', methods=['POST'])
@login_required
def invite_subuser():
    """Invite a sub-user/VA with specific permissions"""
    try:
        data = request.json
        email = data.get('email')
        permissions = data.get('permissions', ['sellerboard_upload'])  # Default to sellerboard upload permission
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
            # Validate permissions
            valid_permissions = ['sellerboard_upload', 'reimbursements_analysis', 'all']
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

@app.route('/api/discount-opportunities/analyze', methods=['POST'])
@login_required
def analyze_discount_opportunities():
    """Analyze discount opportunities from Distill.io email alerts against user's inventory"""
    try:
        data = request.get_json() or {}
        retailer_filter = data.get('retailer', '')
        
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
        
        # Get user's inventory analysis
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
            
        except Exception as e:
            return jsonify({
                'opportunities': [],
                'message': f'Failed to generate analytics: {str(e)}'
            }), 500
        
        # Fetch recent Distill.io email alerts
        email_alerts = fetch_discount_email_alerts()
        
        # Fetch source links CSV for ASIN matching
        csv_url = 'https://docs.google.com/spreadsheets/d/e/2PACX-1vRz7iEc-6eA4pfImWfSs_qVyUWHmqDw8ET1PTWugLpqDHU6txhwyG9lCMA65Z9AHf-6lcvCcvbE4MPT/pub?output=csv'
        response = requests.get(csv_url, timeout=30)
        response.raise_for_status()
        
        csv_data = StringIO(response.text)
        source_df = pd.read_csv(csv_data)
        
        opportunities = []
        
        # Process email alerts
        for email_alert in email_alerts:
            retailer = email_alert['retailer']
            asin = email_alert['asin']
            
            # Skip if retailer filter is specified and doesn't match
            if retailer_filter and retailer_filter.lower() not in retailer.lower():
                continue
            
            # Check if this ASIN is in user's inventory and needs restocking
            if asin in enhanced_analytics:
                inventory_data = enhanced_analytics[asin]
                restock_data = inventory_data.get('restock', {})
                
                # Apply same restock logic as Smart Restock recommendations
                current_stock = restock_data.get('current_stock', 0)
                suggested_quantity = restock_data.get('suggested_quantity', 0)
                days_left = restock_data.get('days_left', float('inf'))
                
                # Only include if restocking is actually needed (same as Smart Restock filter)
                if suggested_quantity > 0:
                    # Look for source link in CSV data
                    source_link = None
                    asin_mask = source_df.astype(str).apply(
                        lambda x: x.str.contains(asin, case=False, na=False)
                    ).any(axis=1)
                    
                    if asin_mask.any():
                        matching_rows = source_df[asin_mask]
                        if len(matching_rows) > 0:
                            # Look for URL/link columns
                            for col in matching_rows.columns:
                                if any(keyword in col.lower() for keyword in ['url', 'link', 'source']):
                                    potential_link = matching_rows.iloc[0][col]
                                    if pd.notna(potential_link) and str(potential_link).startswith('http'):
                                        source_link = str(potential_link)
                                        break
                    
                    # Extract special promotional text for Vitacost
                    promo_message = None
                    if retailer.lower() == 'vitacost':
                        html_content = email_alert.get('html_content', '')
                        promo_message = extract_vitacost_promo_message(html_content)
                    
                    opportunity = {
                        'asin': asin,
                        'retailer': retailer,
                        'product_name': inventory_data.get('product_name', ''),
                        'current_stock': current_stock,
                        'suggested_quantity': suggested_quantity,
                        'days_left': days_left,
                        'velocity': inventory_data.get('velocity', {}).get('weighted_velocity', 0),
                        'source_link': source_link,
                        'promo_message': promo_message,
                        'note': email_alert.get('note'),
                        'alert_time': email_alert['alert_time'],
                        'priority_score': calculate_opportunity_priority(inventory_data, days_left, suggested_quantity),
                        'restock_priority': inventory_data.get('priority', {}).get('category', 'normal')
                    }
                    opportunities.append(opportunity)
        
        # Sort by priority score
        opportunities.sort(key=lambda x: x['priority_score'], reverse=True)
        
        return jsonify({
            'opportunities': opportunities,
            'total_alerts_processed': len(email_alerts),
            'matched_products': len(opportunities),
            'retailer_filter': retailer_filter,
            'analyzed_at': datetime.now(pytz.UTC).isoformat(),
            'message': f'Found {len(opportunities)} discount opportunities for products that need restocking'
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Error analyzing opportunities: {str(e)}'}), 500

@app.route('/api/retailer-leads/worksheets', methods=['GET'])
@login_required
def get_available_worksheets():
    """Get all available worksheets from the Google Sheet"""
    try:
        # First, try to get worksheets by testing the provided CSV URL structure
        base_csv_url = 'https://docs.google.com/spreadsheets/d/e/2PACX-1vRz7iEc-6eA4pfImWfSs_qVyUWHmqDw8ET1PTWugLpqDHU6txhwyG9lCMA65Z9AHf-6lcvCcvbE4MPT/pub?gid={}&single=true&output=csv'
        
        # Test the known GID to see if it works
        test_url = base_csv_url.format('1832463061')
        
        response = requests.get(test_url, timeout=30)
        response.raise_for_status()
        
        if response.text and not response.text.startswith('<HTML>'):
            # CSV is working, now we need to find all worksheet GIDs
            # Since we can't easily discover all GIDs, we'll use a predefined list of common worksheet names
            # that correspond to typical retailer worksheets
            
            worksheets = [
                'Kohls - Flat',
                'Walmart', 
                'Target',
                'Costco',
                'Sam\'s Club',
                'BJ\'s',
                'Home Depot', 
                'Lowe\'s',
                'Walgreens',
                'CVS',
                'Best Buy',
                'Macy\'s',
                'Nordstrom',
                'Dick\'s Sporting Goods',
                'Bed Bath & Beyond',
                'Amazon',
                'Wayfair',
                'Overstock'
            ]
            
            return jsonify({
                'worksheets': worksheets,
                'total': len(worksheets),
                'note': 'Using predefined worksheet list'
            })
        else:
            raise Exception("CSV URL returned HTML instead of CSV")
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        
        # Fallback to Google Sheets API if available
        try:
            discord_id = session['discord_id']
            user = get_user_record(discord_id)
            
            # Get user config for analytics
            config_user_record = user
            if user and user.get('user_type') == 'subuser':
                parent_user_id = user.get('parent_user_id')
                if parent_user_id:
                    parent_record = get_user_record(parent_user_id)
                    if parent_record:
                        config_user_record = parent_record
            
            # Check if user has Google tokens
            if config_user_record and config_user_record.get('google_tokens'):
                # Get the Google Sheet ID from the CSV URL
                sheet_id = '1eY-3tjEgrtqchhBHqfdkYqpKl8xO7bKx-A1h8Lxrq7M'
                
                # Use existing function to get worksheet titles
                worksheet_titles = fetch_all_sheet_titles_for_user({
                    'google_tokens': config_user_record['google_tokens'],
                    'sheet_id': sheet_id
                })
                
                return jsonify({
                    'worksheets': worksheet_titles,
                    'total': len(worksheet_titles),
                    'note': 'Using Google Sheets API'
                })
        except:
            pass
        
        return jsonify({'error': f'Error fetching worksheets: {str(e)}'}), 500

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
        
        print(f"DEBUG: Using orders_url: {orders_url[:50]}..." if orders_url else "DEBUG: No orders_url")
        print(f"DEBUG: Using stock_url: {stock_url[:50]}..." if stock_url else "DEBUG: No stock_url")
        print(f"DEBUG: User timezone: {user_timezone}")
        
        # Quick test if URLs are accessible
        if orders_url:
            try:
                import requests
                test_response = requests.head(orders_url, timeout=10)
                print(f"DEBUG: Orders URL status: {test_response.status_code}")
            except Exception as e:
                print(f"DEBUG: Orders URL test failed: {str(e)}")
                
        if stock_url:
            try:
                import requests
                test_response = requests.head(stock_url, timeout=10)
                print(f"DEBUG: Stock URL status: {test_response.status_code}")
            except Exception as e:
                print(f"DEBUG: Stock URL test failed: {str(e)}")
        
        from datetime import datetime
        import pytz
        from orders_analysis import OrdersAnalysis
        
        tz = pytz.timezone(user_timezone)
        today = datetime.now(tz).date()
        
        try:
            print(f"DEBUG: Starting OrdersAnalysis with orders_url: {orders_url is not None}, stock_url: {stock_url is not None}")
            orders_analysis = OrdersAnalysis(orders_url, stock_url)
            print(f"DEBUG: OrdersAnalysis created successfully")
            
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
            print(f"DEBUG: Analysis completed")
            
            enhanced_analytics = analysis.get('enhanced_analytics', {})
            print(f"DEBUG: Full analysis keys: {list(analysis.keys()) if analysis else 'None'}")
            print(f"DEBUG: Enhanced analytics type and length: {type(enhanced_analytics)}, {len(enhanced_analytics) if enhanced_analytics else 0}")
            
            # Check if we're getting fallback/basic mode
            if analysis.get('basic_mode'):
                print(f"DEBUG: WARNING - Analysis is in basic/fallback mode")
                print(f"DEBUG: Basic mode message: {analysis.get('message', 'No message')}")
                return jsonify({
                    'error': 'Analytics in fallback mode',
                    'message': f'OrdersAnalysis fell back to basic mode: {analysis.get("message", "Unknown reason")}'
                }), 500
        except Exception as e:
            print(f"DEBUG: Exception in OrdersAnalysis: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({
                'error': 'Failed to fetch inventory data',
                'message': f'Failed to generate analytics: {str(e)}'
            }), 500
        
        # Map worksheet names to their GIDs (worksheet IDs)
        # You'll need to provide the GIDs for other worksheets
        worksheet_gid_map = {
            'Kohls - Flat': '1832463061',
            'Kohls': '1832463061',  # Alias
            # Add more worksheets here with their respective GIDs
            # 'Walmart': 'WALMART_GID_HERE',
            # 'Target': 'TARGET_GID_HERE',
            # etc.
        }
        
        # Get the GID for the selected worksheet
        gid = worksheet_gid_map.get(worksheet, '1832463061')  # Default to Kohls if not found
        
        # Build the CSV URL with the specific GID
        csv_url = f'https://docs.google.com/spreadsheets/d/e/2PACX-1vRz7iEc-6eA4pfImWfSs_qVyUWHmqDw8ET1PTWugLpqDHU6txhwyG9lCMA65Z9AHf-6lcvCcvbE4MPT/pub?gid={gid}&single=true&output=csv'
        
        try:
            # Make request with redirect following
            response = requests.get(csv_url, timeout=30, allow_redirects=True)
            response.raise_for_status()
            
            # Check if we got valid CSV data
            if response.text.startswith('<HTML>'):
                raise Exception("Received HTML instead of CSV")
            
            csv_data = StringIO(response.text)
            source_df = pd.read_csv(csv_data)
            
            # For now, this CSV represents the selected worksheet
            # In the future, we could map worksheet names to different GIDs
            worksheet_df = source_df.copy()
            
            if worksheet_df.empty:
                return jsonify({
                    'error': f'No data found for: {worksheet}',
                    'message': f'The worksheet "{worksheet}" appears to be empty'
                }), 404
                
        except Exception as e:
            print(f"Error fetching CSV data: {e}")
            return jsonify({
                'error': f'Failed to fetch data for: {worksheet}',
                'message': f'Could not load worksheet data: {str(e)}'
            }), 500
        
        recommendations = []
        
        # Debug: Add inventory info to response for debugging
        debug_info = {
            'total_asins_in_inventory': len(enhanced_analytics),
            'sample_asins': list(enhanced_analytics.keys())[:10],
            'basic_mode': analysis.get('basic_mode', False),
            'analysis_keys': list(analysis.keys()) if analysis else []
        }
        
        # If we have ASINs, include a good sample for debugging
        if len(enhanced_analytics) <= 50:
            debug_info['all_inventory_asins'] = list(enhanced_analytics.keys())
        else:
            debug_info['sample_inventory_asins_extended'] = list(enhanced_analytics.keys())[:30]
            
        # Check if B014UM9N3I is in enhanced analytics
        target_asin = 'B014UM9N3I'
        debug_info['target_asin_in_inventory'] = target_asin in enhanced_analytics
        if target_asin not in enhanced_analytics:
            # Look for similar ASINs in inventory
            similar_in_inventory = [k for k in enhanced_analytics.keys() if 'B014' in k.upper()]
            debug_info['similar_b014_asins_in_inventory'] = similar_in_inventory
            
        print(f"DEBUG: Enhanced analytics contains {len(enhanced_analytics)} ASINs")
        print(f"DEBUG: All ASINs in inventory: {list(enhanced_analytics.keys())}")
        
        # If we have very few ASINs, show them all with their structure
        if len(enhanced_analytics) <= 5:
            print(f"DEBUG: Enhanced analytics structure (showing all {len(enhanced_analytics)} items):")
            for key, value in enhanced_analytics.items():
                if isinstance(value, dict):
                    print(f"  {key}: {list(value.keys())}")
                    # Show nested structure for first item
                    if key == list(enhanced_analytics.keys())[0]:
                        for subkey, subvalue in value.items():
                            if isinstance(subvalue, dict):
                                print(f"    {subkey}: {list(subvalue.keys())}")
                else:
                    print(f"  {key}: {type(value)} - not dict")
        else:
            print(f"DEBUG: Sample ASINs in inventory: {list(enhanced_analytics.keys())[:10]}")
            print(f"DEBUG: Enhanced analytics structure sample:")
            for i, (key, value) in enumerate(enhanced_analytics.items()):
                if i < 3:  # Show first 3 items
                    print(f"  {key}: {type(value)} - {list(value.keys()) if isinstance(value, dict) else 'not dict'}")
                else:
                    break
        
        # Debug: Show what ASINs are in the worksheet
        worksheet_asins = []
        for _, row in worksheet_df.iterrows():
            raw_asin = str(row.get('ASIN', '')).strip()
            if raw_asin and raw_asin != 'nan':
                worksheet_asins.append(raw_asin.upper())
        
        print(f"DEBUG: Worksheet contains {len(worksheet_asins)} ASINs")
        print(f"DEBUG: First 10 ASINs in worksheet: {worksheet_asins[:10]}")
        
        # Check for our specific ASIN
        target_asin = 'B014UM9N3I'
        if target_asin in worksheet_asins:
            print(f"DEBUG: SPECIAL - {target_asin} found in worksheet ASINs")
        else:
            print(f"DEBUG: SPECIAL - {target_asin} NOT found in worksheet ASINs")
            # Look for similar ASINs
            similar = [asin for asin in worksheet_asins if 'B014' in asin]
            if similar:
                print(f"  - Similar ASINs with B014: {similar}")
        
        # Analyze each lead
        for _, row in worksheet_df.iterrows():
            asin = str(row.get('ASIN', '')).strip().upper()  # Normalize to uppercase
            if not asin or asin == 'nan' or asin == 'NAN':
                continue
                
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
            
            # Debug: Log lookup results  
            found_in_inventory = bool(inventory_data)
            print(f"DEBUG: ASIN {asin} found in inventory: {found_in_inventory}")
            
            # Special debug for the specific missing ASIN
            if asin == 'B014UM9N3I':
                print(f"DEBUG: SPECIAL - Checking B014UM9N3I specifically:")
                print(f"  - Raw ASIN from worksheet: '{asin}'")
                print(f"  - Length: {len(asin)}")
                print(f"  - Looking for uppercase: {asin in enhanced_analytics}")
                print(f"  - Looking for lowercase: {asin.lower() in enhanced_analytics}")
                
                # Check for exact matches and similar matches
                exact_matches = [k for k in enhanced_analytics.keys() if k == asin]
                similar_matches = [k for k in enhanced_analytics.keys() if 'B014UM9N3I' in k.upper()]
                close_matches = [k for k in enhanced_analytics.keys() if 'B014' in k.upper()]
                
                print(f"  - Exact matches: {exact_matches}")
                print(f"  - Similar matches (containing B014UM9N3I): {similar_matches}")
                print(f"  - Close matches (containing B014): {close_matches}")
                
                # Check character by character comparison with close matches
                if close_matches:
                    for close_match in close_matches[:3]:  # Check first 3
                        print(f"  - Comparing '{asin}' vs '{close_match}':")
                        print(f"    - Same length: {len(asin) == len(close_match)}")
                        print(f"    - Character comparison: {[c1 == c2 for c1, c2 in zip(asin, close_match)]}")
                        if asin != close_match:
                            print(f"    - Differences: {[(i, c1, c2) for i, (c1, c2) in enumerate(zip(asin, close_match)) if c1 != c2]}")
                
                if asin in enhanced_analytics:
                    print(f"  - Found data keys: {enhanced_analytics[asin].keys()}")
                elif asin.lower() in enhanced_analytics:
                    print(f"  - Found lowercase data keys: {enhanced_analytics[asin.lower()].keys()}")
            
            # Get retailer name for this specific row
            retailer_name = extract_retailer_from_url(source_link) if source_link else 'Unknown'
            
            recommendation = {
                'asin': asin,
                'retailer': retailer_name,
                'worksheet': worksheet,
                'source_link': source_link,
                'in_inventory': bool(inventory_data),
                'recommendation': 'SKIP',
                'reason': '',
                'priority_score': 0
            }
            
            if inventory_data:
                # Product is in inventory - check if needs restocking
                restock_data = inventory_data.get('restock', {})
                velocity_data = inventory_data.get('velocity', {})
                priority_data = inventory_data.get('priority', {})
                
                current_stock = restock_data.get('current_stock', 0)
                suggested_quantity = restock_data.get('suggested_quantity', 0)
                velocity = velocity_data.get('weighted_velocity', 0)  # Use the same velocity as Smart Restock
                
                # Get additional data
                cogs_data = inventory_data.get('cogs_data', {})
                cogs = cogs_data.get('cogs', 0)
                last_price = inventory_data.get('stock_info', {}).get('Price', 0)
                
                # Use the same logic as Smart Restock: check priority category
                priority_category = priority_data.get('category', 'low')
                priority_score = priority_data.get('score', 0)
                
                # Apply EXACT same logic as Smart Restock
                if suggested_quantity > 0:
                    # Check if it's in a restock alert category (same as Smart Restock)
                    alert_categories = ['critical_immediate', 'critical_very_soon', 'urgent_restock', 'moderate_restock']
                    
                    if priority_category in alert_categories:
                        recommendation['recommendation'] = 'BUY - RESTOCK'
                        recommendation['reason'] = f'Smart Restock Alert: {priority_data.get("reasoning", "Needs restocking")}'
                        recommendation['priority_score'] = priority_score
                    else:
                        recommendation['recommendation'] = 'MONITOR'
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
                # Product not in inventory - recommend as new opportunity
                recommendation['recommendation'] = 'BUY - NEW'
                recommendation['reason'] = 'Not in inventory - potential new product'
                recommendation['priority_score'] = 50  # Medium priority for new products
            
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
            'analyzed_at': datetime.now(pytz.UTC).isoformat(),
            'debug_info': debug_info  # Add debug information to the response
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Error analyzing retailer leads: {str(e)}'}), 500

def fetch_discount_email_alerts():
    """Fetch recent Distill.io email alerts from admin-configured Gmail using Gmail API"""
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
        
        # Get admin user record for Gmail access
        admin_user_record = None
        users = get_users_config()
        for user in users:
            if user.get('email') == monitor_email and user.get('google_tokens'):
                admin_user_record = user
                break
        
        if not admin_user_record:
            print(f"No admin user found with email {monitor_email} and Google tokens")
            # Return mock data if admin not configured with Gmail
            return fetch_mock_discount_alerts()
        
        # Build Gmail search query
        # Search for emails from Distill.io in the last N days
        # No keyword filtering needed - Distill.io already filters relevant emails
        from datetime import datetime, timedelta
        import pytz
        
        days_back = get_discount_email_days_back()
        cutoff_date = datetime.now(pytz.UTC) - timedelta(days=days_back)
        date_str = cutoff_date.strftime('%Y/%m/%d')
        
        # Create search query for Gmail
        # No need to filter by keywords since Distill.io already filters relevant emails
        query = f'from:{DISCOUNT_SENDER_EMAIL} after:{date_str}'
        
        print(f"Gmail search query: {query}")
        
        # Search for messages
        search_results = search_gmail_messages(admin_user_record, query, max_results=100)
        if not search_results:
            print("No search results from Gmail API")
            return fetch_mock_discount_alerts()
        
        messages = search_results.get('messages', [])
        if not messages:
            print("No messages found in search results")
            return fetch_mock_discount_alerts()
        
        print(f"Found {len(messages)} messages from Gmail search")
        
        email_alerts = []
        
        # Process each message
        for message_info in messages[:50]:  # Limit to 50 most recent
            message_id = message_info.get('id')
            if not message_id:
                continue
                
            # Get full message details
            message_data = get_gmail_message(admin_user_record, message_id)
            if not message_data:
                continue
            
            # Extract email content
            email_content = extract_email_content(message_data)
            if not email_content:
                continue
            
            # Verify sender is from Distill.io
            sender = email_content.get('sender', '')
            if DISCOUNT_SENDER_EMAIL not in sender:
                continue
            
            # Parse email subject to extract retailer and ASIN
            subject = email_content.get('subject', '')
            parsed_alert = parse_distill_email_subject(subject)
            
            if parsed_alert:
                # Convert Gmail date to ISO format
                gmail_date = email_content.get('date', '')
                iso_date = convert_gmail_date_to_iso(gmail_date)
                
                email_alerts.append({
                    'retailer': parsed_alert['retailer'],
                    'asin': parsed_alert['asin'],
                    'note': parsed_alert.get('note'),
                    'subject': subject,
                    'html_content': email_content.get('html_content', ''),
                    'alert_time': iso_date,
                    'message_id': message_id
                })
        
        print(f"Processed {len(email_alerts)} discount email alerts")
        
        # Sort by alert time (newest first)
        email_alerts.sort(key=lambda x: x['alert_time'], reverse=True)
        
        return email_alerts
        
    except Exception as e:
        print(f"Error fetching discount email alerts: {e}")
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

def parse_distill_email_subject(subject):
    """Parse Distill.io email subject to extract retailer, ASIN, and notes"""
    import re
    
    # Pattern to match: Retailer (ASIN: XXXXXXXXXX) (Note: additional info)
    # Example: Walmart (ASIN: B07D83HV1M) (Note: Amazon is two pack)
    pattern = r'([A-Za-z]+)\s*\(ASIN:\s*([B-Z][0-9A-Z]{9})\)(?:\s*\(Note:\s*([^)]+)\))?'
    match = re.search(pattern, subject)
    
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
    
    retailers = ['vitacost', 'walmart', 'target', 'amazon', 'costco', 'sam']
    
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


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({'error': 'Not found', 'path': request.path}), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    return jsonify({'error': 'Internal server error'}), 500

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