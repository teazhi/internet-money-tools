from flask import Flask, request, jsonify, session, redirect, url_for, send_from_directory
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

# Load environment variables
try:
    load_dotenv()
    print("[INIT] Environment variables loaded")
except Exception as e:
    print(f"[INIT WARNING] Failed to load .env file: {e}")

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'development-key-change-in-production')
print("[INIT] Flask app initialized")

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
    "https://internet-money-tools.vercel.app",  # Add Vercel frontend
    "https://internet-money-tools-git-main-teazhis-projects.vercel.app",  # Vercel preview URLs
    "https://internet-money-tools-dfqzt1xy0-teazhis-projects.vercel.app"  # Vercel deployment URLs
]
if os.environ.get('FRONTEND_URL'):
    allowed_origins.append(os.environ.get('FRONTEND_URL'))
if os.environ.get('RAILWAY_STATIC_URL'):
    allowed_origins.append(f"https://{os.environ.get('RAILWAY_STATIC_URL')}")

try:
    CORS(app, supports_credentials=True, origins=allowed_origins)
    print("[INIT] CORS configured")
except Exception as e:
    print(f"[INIT ERROR] CORS configuration failed: {e}")
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

# Email Configuration (for invitations)
SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
SMTP_EMAIL = os.getenv('SMTP_EMAIL')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')

# Google OAuth Configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")

def get_s3_client():
    return boto3.client(
        's3',
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    )

def get_users_config():
    s3_client = get_s3_client()
    try:
        response = s3_client.get_object(Bucket=CONFIG_S3_BUCKET, Key=USERS_CONFIG_KEY)
        config_data = json.loads(response['Body'].read().decode('utf-8'))
        return config_data.get("users", [])
    except Exception as e:
        print(f"Error fetching users config: {e}")
        return []

def update_users_config(users):
    s3_client = get_s3_client()
    config_data = json.dumps({"users": users}, indent=2)
    
    print(f"[UPDATE CONFIG] About to save {len(users)} users to S3")
    print(f"[UPDATE CONFIG] S3 Bucket: {CONFIG_S3_BUCKET}")
    print(f"[UPDATE CONFIG] S3 Key: {USERS_CONFIG_KEY}")
    print(f"[UPDATE CONFIG] Config data preview: {config_data[:500]}...")
    
    try:
        result = s3_client.put_object(
            Bucket=CONFIG_S3_BUCKET, 
            Key=USERS_CONFIG_KEY, 
            Body=config_data,
            ContentType='application/json'
        )
        print(f"[UPDATE CONFIG] S3 put_object result: {result}")
        print("Users configuration updated successfully.")
        
        # Verify the save by reading it back immediately
        try:
            verify_response = s3_client.get_object(Bucket=CONFIG_S3_BUCKET, Key=USERS_CONFIG_KEY)
            verify_data = json.loads(verify_response['Body'].read().decode('utf-8'))
            print(f"[UPDATE CONFIG] Verification: read back {len(verify_data.get('users', []))} users")
        except Exception as verify_error:
            print(f"[UPDATE CONFIG] Verification failed: {verify_error}")
        
        return True
    except Exception as e:
        print(f"[UPDATE CONFIG] Error updating users config: {e}")
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
        print(f"Error reading invitations config: {e}")
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
        print(f"Error updating invitations config: {e}")
        return False

def send_invitation_email(email, invitation_token, invited_by):
    """Send invitation email to user"""
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        print("SMTP credentials not configured")
        return False
    
    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_EMAIL
        msg['To'] = email
        msg['Subject'] = "You're invited to builders+ Dashboard"
        
        invitation_url = f"https://internet-money-tools.vercel.app/login?invitation={invitation_token}"
        
        body = f"""
        <html>
        <body>
            <h2>You're invited to builders+ Dashboard!</h2>
            <p>Hi there!</p>
            <p>{invited_by} has invited you to join the builders+ Amazon Seller Dashboard.</p>
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
            <p>Best regards,<br>builders+ Team</p>
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
        print(f"Error sending invitation email: {e}")
        return False

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        print(f"[Auth Check] Session data: {dict(session)}")
        print(f"[Auth Check] Discord ID in session: {'discord_id' in session}")
        if 'discord_id' not in session:
            print(f"[Auth Check] Authentication failed - no discord_id in session")
            return jsonify({'error': 'Authentication required'}), 401
        print(f"[Auth Check] Authentication successful for user: {session['discord_id']}")
        return f(*args, **kwargs)
    return decorated_function

def is_admin_user(discord_id):
    """Check if a Discord ID is an admin"""
    return discord_id == '1278565917206249503'

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
    print(f"[DEBUG] Discord OAuth redirect URI being used: {DISCORD_REDIRECT_URI}")
    
    # Get invitation token from query parameters
    invitation_token = request.args.get('invitation')
    print(f"[Discord Auth] Invitation token received: {invitation_token}")
    state_param = f"&state={invitation_token}" if invitation_token else ""
    print(f"[Discord Auth] State parameter: {state_param}")
    
    discord_auth_url = (
        f"https://discord.com/api/oauth2/authorize"
        f"?client_id={DISCORD_CLIENT_ID}"
        f"&redirect_uri={urllib.parse.quote(DISCORD_REDIRECT_URI)}"
        f"&response_type=code"
        f"&scope=identify"
        f"{state_param}"
    )
    print(f"[DEBUG] Full Discord auth URL: {discord_auth_url}")
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
    
    # If user doesn't exist, check for invitation
    if not existing_user:
        invitation_token = request.args.get('state')  # Discord passes our state parameter back
        print(f"[Discord Callback] Invitation token from state: {invitation_token}")
        print(f"[Discord Callback] Full callback args: {dict(request.args)}")
        
        if not invitation_token:
            print(f"[Discord Callback] No invitation token found, redirecting to no_invitation error")
            return redirect("https://internet-money-tools.vercel.app/login?error=no_invitation")
        
        # Validate invitation token
        invitations = get_invitations_config()
        print(f"[Discord Callback] Checking {len(invitations)} invitations for token: {invitation_token}")
        valid_invitation = None
        for inv in invitations:
            print(f"[Discord Callback] Checking invitation: token={inv['token']}, status={inv['status']}, created={inv['created_at']}")
            if inv['token'] == invitation_token and inv['status'] == 'pending':
                # Check if invitation is not expired (7 days)
                try:
                    # Parse created_at timestamp (strip any timezone suffix for consistency)
                    created_at_str = inv['created_at'].replace('Z', '').replace('+00:00', '')
                    invitation_date = datetime.fromisoformat(created_at_str)
                    # Use UTC for both comparisons to avoid timezone issues
                    current_time = datetime.utcnow()
                    time_diff = current_time - invitation_date
                    print(f"[Discord Callback] Invitation age: {time_diff}, expires after 7 days")
                    if time_diff < timedelta(days=7):
                        valid_invitation = inv
                        print(f"[Discord Callback] Found valid invitation for email: {inv['email']}")
                        break
                    else:
                        print(f"[Discord Callback] Invitation expired ({time_diff} old)")
                except Exception as date_error:
                    print(f"[Discord Callback] Date parsing error: {date_error}, treating as valid for now")
                    # If date parsing fails, allow the invitation (fallback)
                    valid_invitation = inv
                    print(f"[Discord Callback] Found valid invitation for email: {inv['email']} (date parse fallback)")
                    break
            else:
                print(f"[Discord Callback] Invitation mismatch: token={inv['token'] == invitation_token}, status={inv['status'] == 'pending'}")
        
        if not valid_invitation:
            print(f"[Discord Callback] No valid invitation found, redirecting to invalid_invitation error")
            return redirect("https://internet-money-tools.vercel.app/login?error=invalid_invitation")
        
        # Mark invitation as used
        valid_invitation['status'] = 'accepted'
        valid_invitation['discord_id'] = discord_id
        valid_invitation['discord_username'] = discord_username
        valid_invitation['accepted_at'] = datetime.now().isoformat()
        update_invitations_config(invitations)
    
    session['discord_id'] = discord_id
    session['discord_username'] = discord_username
    session['discord_avatar'] = user_data.get('avatar')
    
    print(f"[DEBUG] Session set with discord_id: {session['discord_id']}")
    print(f"[DEBUG] Full session data: {dict(session)}")
    
    # Save Discord username to user record for admin panel
    try:
        users = get_users_config()
        discord_id = session['discord_id']
        user_record = next((u for u in users if u.get("discord_id") == discord_id), None)
        
        if user_record is None:
            user_record = {"discord_id": discord_id}
            users.append(user_record)
        
        # Update Discord username and last activity in permanent record
        user_record['discord_username'] = user_data['username']
        user_record['last_activity'] = datetime.now().isoformat()
        update_users_config(users)
        print(f"[DEBUG] Updated user record with Discord username: {user_data['username']}")
    except Exception as e:
        print(f"[DEBUG] Failed to update user record: {e}")
    
    # FORCE redirect to Vercel frontend - UPDATED
    frontend_url = "https://internet-money-tools.vercel.app/dashboard"
    print(f"[DEBUG] Discord callback redirecting to: {frontend_url}")
    
    # Dynamic redirect based on environment (backup)
    # if os.environ.get('FRONTEND_URL'):
    #     frontend_url = f"{os.environ.get('FRONTEND_URL')}/dashboard"
    
    return redirect(frontend_url)

@app.route('/auth/logout')
def logout():
    session.clear()
    return jsonify({'message': 'Logged out successfully'})

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
    
    # Debug logging
    if admin_impersonating:
        print(f"[API USER] Impersonation mode - returning data for: {discord_id}")
        print(f"[API USER] User record found: {user_record is not None}")
        if user_record:
            print(f"[API USER] User has google_tokens: {user_record.get('google_tokens') is not None}")
            print(f"[API USER] User has sheet_id: {user_record.get('sheet_id') is not None}")
    
    response_data = {
        'discord_id': discord_id,
        'discord_username': session.get('discord_username'),
        'discord_avatar': session.get('discord_avatar'),
        'is_admin': is_admin_user(discord_id),
        'profile_configured': user_record is not None,
        'google_linked': user_record and user_record.get('google_tokens') is not None,
        'sheet_configured': user_record and user_record.get('sheet_id') is not None,
        'user_record': user_record if user_record else None
    }
    
    # Add impersonation info if applicable
    if admin_impersonating:
        response_data['admin_impersonating'] = True
        response_data['original_admin_id'] = admin_impersonating['original_discord_id']
        response_data['original_admin_username'] = admin_impersonating['original_discord_username']
        print(f"[API USER] Returning impersonated user data: {response_data['discord_username']}")
    
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
        "scope": "https://www.googleapis.com/auth/spreadsheets.readonly https://www.googleapis.com/auth/drive.readonly",
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

@app.route('/api/debug/stock-columns')
@login_required
def debug_stock_columns():
    """Debug endpoint to check stock data columns"""
    try:
        print("[DEBUG] Testing stock columns endpoint")
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
        print(f"[DEBUG] Stock columns: {columns}")
        
        # Get sample data from first row
        if len(stock_df) > 0:
            sample_row = stock_df.iloc[0].to_dict()
            print(f"[DEBUG] Sample row data: {sample_row}")
            
            # Look for source-like columns
            source_columns = [col for col in columns if 'source' in col.lower() or 'link' in col.lower() or 'url' in col.lower()]
            print(f"[DEBUG] Potential source columns: {source_columns}")
            
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
        print(f"[DEBUG] Error in stock columns debug: {str(e)}")
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
        print(f"[DEBUG COGS] Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/analytics/orders')
@login_required
def get_orders_analytics():
    try:
        print(f"[Dashboard Analytics] User session: {session.get('discord_id', 'Not logged in')}")
        print(f"[Dashboard Analytics] Request headers: {dict(request.headers)}")
        print(f"[Dashboard Analytics] Session keys: {list(session.keys())}")
        
        # Import the orders analysis class (copied to backend directory)
        from orders_analysis import OrdersAnalysis
        
        # Get user's timezone preference first and update last activity
        discord_id = session['discord_id']
        user_record = get_user_record(discord_id)
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
                print(f"[DEBUG] Failed to update last activity: {e}")
        
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
                    print(f"[Dashboard Analytics] Using user timezone: {user_timezone}")
                except pytz.UnknownTimeZoneError:
                    now = datetime.now()
                    print(f"[Dashboard Analytics] Invalid timezone {user_timezone}, using system time")
            else:
                now = datetime.now()
                print(f"[Dashboard Analytics] No timezone set, using system time")
            
            # Show yesterday's data until 11:59 PM today, then show today's data
            if now.hour == 23 and now.minute == 59:
                # At 11:59 PM, switch to today's data
                target_date = now.date()
                print(f"[Dashboard Analytics] Switching to today's data at 11:59 PM {user_timezone or 'system timezone'}")
            else:
                # Show yesterday's complete data throughout the day
                target_date = now.date() - timedelta(days=1)
                print(f"[Dashboard Analytics] Showing yesterday's data (will switch at 11:59 PM {user_timezone or 'system timezone'})")
        
        print(f"[Dashboard Analytics] Fetching data for date: {target_date}")
        print(f"[Dashboard Analytics] About to call OrdersAnalysis")
        
        # Get user's custom URLs if configured
        discord_id = session['discord_id']
        user_record = get_user_record(discord_id)
        
        orders_url = None
        stock_url = None
        if user_record:
            orders_url = user_record.get('sellerboard_orders_url')
            stock_url = user_record.get('sellerboard_stock_url')
        
        # Require user to have configured their own URLs
        if not orders_url or not stock_url:
            return jsonify({
                'error': 'Report URLs not configured',
                'message': 'Please configure your Sellerboard report URLs in Settings before accessing analytics.',
                'requires_setup': True,
                'report_date': target_date.isoformat(),
                'is_yesterday': target_date == (date.today() - timedelta(days=1))
            }), 400
        
        print(f"[Dashboard Analytics] Using user-configured URLs")
        print(f"[Dashboard Analytics] Orders URL: {orders_url[:50]}..." if orders_url else "No orders URL")
        print(f"[Dashboard Analytics] Stock URL: {stock_url[:50]}..." if stock_url else "No stock URL")
        
        try:
            print(f"[Dashboard Analytics] Initializing OrdersAnalysis...")
            analyzer = OrdersAnalysis(orders_url=orders_url, stock_url=stock_url)
            print(f"[Dashboard Analytics] OrdersAnalysis initialized, starting analysis...")
            # Prepare user settings for COGS data fetching
            user_settings = {
                'enable_source_links': user_record.get('enable_source_links', False),
                'search_all_worksheets': user_record.get('search_all_worksheets', False),
                'sheet_id': user_record.get('sheet_id'),
                'worksheet_title': user_record.get('worksheet_title'),
                'google_tokens': user_record.get('google_tokens', {}),
                'column_mapping': user_record.get('column_mapping', {})
            }
            
            analysis = analyzer.analyze(target_date, user_timezone=user_timezone, user_settings=user_settings)
            print(f"[Dashboard Analytics] Analysis completed successfully")
            print(f"[Dashboard Analytics] Low stock items found: {len(analysis.get('low_stock', {}))}")
            print(f"[Dashboard Analytics] Restock priority items: {len(analysis.get('restock_priority', {}))}")
            print(f"[Dashboard Analytics] Today's sales items: {len(analysis.get('today_sales', {}))}")
            print(f"[Dashboard Analytics] Enhanced analytics items: {len(analysis.get('enhanced_analytics', {}))}")
            print(f"[Dashboard Analytics] Restock alerts: {len(analysis.get('restock_alerts', {}))}")
            print(f"[Dashboard Analytics] Critical alerts: {len(analysis.get('critical_alerts', []))}")
            
            # Debug: Show sample enhanced analytics data
            if analysis.get('enhanced_analytics'):
                sample_asin = list(analysis['enhanced_analytics'].keys())[0]
                sample_data = analysis['enhanced_analytics'][sample_asin]
                print(f"[DEBUG] Sample enhanced analytics for {sample_asin}:")
                print(f"[DEBUG]   velocity: {sample_data.get('velocity', {})}")
                print(f"[DEBUG]   priority: {sample_data.get('priority', {})}")
                print(f"[DEBUG]   restock: {sample_data.get('restock', {})}")
        except Exception as analysis_error:
            print(f"[Dashboard Analytics] Enhanced analysis failed: {analysis_error}")
            print(f"[Dashboard Analytics] Error type: {type(analysis_error).__name__}")
            import traceback
            print(f"[Dashboard Analytics] Full traceback:")
            traceback.print_exc()
            print(f"[Dashboard Analytics] Falling back to basic analytics...")
            
            # Fallback to basic analytics structure
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
                'error': f'Enhanced analytics failed: {str(analysis_error)}',
                'fallback_mode': True
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
        analysis['is_yesterday'] = target_date == (date.today() - timedelta(days=1))
        analysis['user_timezone'] = user_timezone
        
        print(f"[Dashboard Analytics] Successfully fetched data with {len(analysis.get('today_sales', {}))} products")
        print(f"[Dashboard Analytics] Final analysis keys: {list(analysis.keys())}")
        print(f"[Dashboard Analytics] today_sales in analysis: {'today_sales' in analysis}")
        print(f"[Dashboard Analytics] today_sales value: {analysis.get('today_sales')}")
        
        response = jsonify(analysis)
        response.headers['Content-Type'] = 'application/json'
        return response
        
    except Exception as e:
        print(f"[Dashboard Analytics] Error getting analytics data: {e}")
        import traceback
        print(f"[Dashboard Analytics] Full traceback: {traceback.format_exc()}")
        
        # Return error with more details for debugging
        return jsonify({
            'error': f'Failed to fetch analytics data: {str(e)}',
            'report_date': (date.today() - timedelta(days=1)).isoformat(),
            'is_yesterday': True,
            'debug_info': {
                'error_type': type(e).__name__,
                'traceback': traceback.format_exc()
            }
        }), 500

def allowed_file(filename):
    """Check if file extension is allowed"""
    ALLOWED_EXTENSIONS = {'csv', 'xlsx', 'xlsm', 'xls'}
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/api/upload/sellerboard', methods=['POST'])
@login_required
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
        
        # Create user-specific filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        user_filename = f"{discord_id}_{timestamp}_{filename}"
        
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
        
        # Update user record with uploaded file info
        users = get_users_config()
        user_record = next((u for u in users if u.get("discord_id") == discord_id), None)
        
        if user_record is None:
            user_record = {"discord_id": discord_id}
            users.append(user_record)
        
        # Store file information
        if 'uploaded_files' not in user_record:
            user_record['uploaded_files'] = []
        
        # File type management: Keep one of each type (sellerboard and listing loader)
        # Determine file type based on filename and extension
        filename_lower = filename.lower()
        
        if '.xlsm' in filename_lower or 'listing' in filename_lower or 'loader' in filename_lower:
            file_type_category = 'listing_loader'
        elif '.xlsx' in filename_lower or 'sellerboard' in filename_lower or 'sb' in filename_lower:
            file_type_category = 'sellerboard'
        else:
            # Default to sellerboard for .csv and unrecognized files
            file_type_category = 'sellerboard'
        
        file_info = {
            'filename': filename,
            's3_key': s3_key,
            'upload_date': datetime.now().isoformat(),
            'file_size': len(file_content),
            'file_type': file.content_type,
            'file_type_category': file_type_category
        }
        
        # Remove any existing files of the same type
        files_to_delete = []
        remaining_files = []
        
        for existing_file in user_record['uploaded_files']:
            existing_type = existing_file.get('file_type_category', 'sellerboard')
            if existing_type == file_type_category:
                files_to_delete.append(existing_file)
            else:
                remaining_files.append(existing_file)
        
        # Delete old files of same type from S3
        for old_file in files_to_delete:
            try:
                s3_client.delete_object(Bucket=CONFIG_S3_BUCKET, Key=old_file['s3_key'])
                print(f"Deleted old {file_type_category} file: {old_file['filename']}")
            except Exception as e:
                print(f"Error deleting old file {old_file['s3_key']}: {e}")
        
        # Update the files list (keep other type + new file)
        user_record['uploaded_files'] = remaining_files
        user_record['uploaded_files'].append(file_info)
        
        if update_users_config(users):
            return jsonify({
                'message': 'File uploaded successfully',
                'file_info': file_info
            })
        else:
            return jsonify({'error': 'Failed to update user configuration'}), 500
            
    except Exception as e:
        print(f"Upload error: {e}")
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500

@app.route('/api/files/sellerboard', methods=['GET'])
@login_required
def list_sellerboard_files():
    """List user's uploaded files"""
    try:
        discord_id = session['discord_id']
        user_record = get_user_record(discord_id)
        
        if not user_record or 'uploaded_files' not in user_record:
            return jsonify({'files': []})
        
        return jsonify({'files': user_record['uploaded_files']})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/migrate-all-files', methods=['POST'])
@login_required
def migrate_all_user_files():
    """Admin endpoint to migrate all existing files to proper directory structure"""
    try:
        discord_id = session['discord_id']
        
        # Check if user has admin permissions (you can adjust this logic)
        if discord_id != '1278565917206249503':  # Your Discord ID
            return jsonify({'error': 'Unauthorized'}), 403
        
        s3_client = get_s3_client()
        users = get_users_config()
        
        # Known user mappings
        user_mappings = {
            'oscar': '1208551911976861737',
            'tevin': '1278565917206249503', 
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
                
                # Skip system files
                if s3_key in ['users.json', 'command_permissions.json', 'amznUploadConfig.json', 'config.json']:
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
                                    'upload_date': obj.get('LastModified', datetime.now()).isoformat(),
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
                    
                    # Check if filename contains user identifier or matches known patterns
                    filename = key.lower()
                    user_record_info = user_record
                    
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
                    
                    # Use LastModified as upload date
                    upload_date = obj.get('LastModified', datetime.now()).isoformat()
                    
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
                    
                    user_record['uploaded_files'].append(file_info)
                    migrated_files.append(file_info)
            
            # Update users config
            users = get_users_config()
            for i, user in enumerate(users):
                if user.get('discord_id') == discord_id:
                    users[i] = user_record
                    break
            
            update_users_config(users)
            
            return jsonify({
                'message': f'Successfully migrated {len(migrated_files)} files',
                'migrated_files': migrated_files
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
        file_key = unquote(file_key)  # Decode URL encoding
        print(f"[DEBUG] Delete request from user {discord_id} for file: {file_key}")
        
        users = get_users_config()
        user_record = next((u for u in users if u.get("discord_id") == discord_id), None)
        
        if not user_record or 'uploaded_files' not in user_record:
            print(f"[DEBUG] No user record or uploaded_files for {discord_id}")
            return jsonify({'error': 'File not found'}), 404
        
        # Find and remove the file
        file_to_delete = None
        for i, file_info in enumerate(user_record['uploaded_files']):
            if file_info['s3_key'] == file_key:
                file_to_delete = user_record['uploaded_files'].pop(i)
                print(f"[DEBUG] Found file to delete: {file_info}")
                break
        
        if not file_to_delete:
            print(f"[DEBUG] File not found in user's uploaded_files. Available keys: {[f['s3_key'] for f in user_record['uploaded_files']]}")
            return jsonify({'error': 'File not found'}), 404
        
        # Delete from S3
        s3_client = get_s3_client()
        print(f"[DEBUG] Deleting from S3: bucket={CONFIG_S3_BUCKET}, key={file_key}")
        s3_client.delete_object(Bucket=CONFIG_S3_BUCKET, Key=file_key)
        print(f"[DEBUG] S3 deletion successful")
        
        # Update user config
        if update_users_config(users):
            print(f"[DEBUG] User config updated successfully")
            response = jsonify({'message': 'File deleted successfully'})
            response.headers.add('Access-Control-Allow-Origin', request.headers.get('Origin', '*'))
            response.headers.add('Access-Control-Allow-Credentials', 'true')
            return response
        else:
            print(f"[DEBUG] Failed to update user config")
            return jsonify({'error': 'Failed to update configuration'}), 500
            
    except Exception as e:
        print(f"[DEBUG] Delete error: {e}")
        return jsonify({'error': str(e)}), 500

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
        active_users = sum(1 for u in users if 
                          u.get('email') and 
                          u.get('google_tokens') and 
                          u.get('sheet_id'))
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
        print(f"[ADMIN UPDATE] Received request for user_id: {user_id}")
        print(f"[ADMIN UPDATE] Request data: {data}")
        
        users = get_users_config()
        
        # Find user in the users list (not just get a reference)
        user_index = None
        for i, u in enumerate(users):
            if str(u.get("discord_id")) == str(user_id):
                user_index = i
                break
        
        if user_index is None:
            print(f"[ADMIN UPDATE] User not found in users list: {user_id}")
            return jsonify({'error': 'User not found'}), 404
        
        user_record = users[user_index]
        print(f"[ADMIN UPDATE] Found user record at index {user_index}: {user_record.get('discord_username', 'Unknown')}")
        print(f"[ADMIN UPDATE] Before update - enable_source_links: {user_record.get('enable_source_links')}")
        print(f"[ADMIN UPDATE] Before update - search_all_worksheets: {user_record.get('search_all_worksheets')}")
        
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
                print(f"[ADMIN UPDATE] Updated {field}: {old_value} -> {data[field]}")
        
        print(f"[ADMIN UPDATE] After update - enable_source_links: {users[user_index].get('enable_source_links')}")
        print(f"[ADMIN UPDATE] After update - search_all_worksheets: {users[user_index].get('search_all_worksheets')}")
        print(f"[ADMIN UPDATE] About to save users list with {len(users)} users")
        
        # Save changes
        if update_users_config(users):
            print(f"[ADMIN UPDATE] Successfully saved user config")
            return jsonify({'message': 'User updated successfully'})
        else:
            print(f"[ADMIN UPDATE] Failed to save user config")
            return jsonify({'error': 'Failed to update user'}), 500
            
    except Exception as e:
        print(f"[ADMIN UPDATE] Exception: {e}")
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
        print(f"[ADMIN IMPERSONATE] Starting impersonation for user_id: {user_id}")
        
        # Find the user
        user_record = get_user_record(user_id)
        if not user_record:
            print(f"[ADMIN IMPERSONATE] User not found: {user_id}")
            return jsonify({'error': 'User not found'}), 404
        
        print(f"[ADMIN IMPERSONATE] Found user record: {user_record.get('discord_username', 'Unknown')}")
        print(f"[ADMIN IMPERSONATE] User has profile: {user_record is not None}")
        print(f"[ADMIN IMPERSONATE] User has google_tokens: {user_record.get('google_tokens') is not None}")
        print(f"[ADMIN IMPERSONATE] User has sheet_id: {user_record.get('sheet_id') is not None}")
        
        # Store original admin session
        session['admin_impersonating'] = {
            'original_discord_id': session['discord_id'],
            'original_discord_username': session['discord_username'],
            'target_user_id': user_id
        }
        
        # Temporarily switch session to target user
        session['discord_id'] = user_record['discord_id']
        session['discord_username'] = user_record.get('discord_username', 'Unknown User')
        
        print(f"[ADMIN IMPERSONATE] Session updated - now impersonating: {session['discord_id']}")
        
        return jsonify({
            'message': f'Now viewing as {user_record.get("discord_username", "Unknown User")}',
            'impersonating': True,
            'target_user': {
                'discord_id': user_record['discord_id'],
                'discord_username': user_record.get('discord_username', 'Unknown User')
            }
        })
        
    except Exception as e:
        print(f"[ADMIN IMPERSONATE] Error: {e}")
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
        print(f"[ADMIN STOP IMPERSONATE] Error: {e}")
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
        <title>builders+ Dashboard</title>
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
            <h1>🚀 builders+ Dashboard</h1>
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
        frontend_url = "https://internet-money-tools.vercel.app/dashboard"
    
    return jsonify({
        'redirect_url': frontend_url,
        'frontend_env': os.environ.get('FRONTEND_URL'),
        'railway_env': os.environ.get('RAILWAY_STATIC_URL'),
        'message': f'Would redirect to: {frontend_url}'
    })

@app.route('/test/redirect')
def test_redirect():
    """Test actual redirect behavior"""
    return redirect("https://internet-money-tools.vercel.app/dashboard")

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
            print(f"[SCRIPT CONFIG] Error reading amznUploadConfig: {e}")
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
            print(f"[SCRIPT CONFIG] Error reading config.json: {e}")
            configs['config'] = {
                'last_processed_date': '',
                'status': 'not_found',
                'error': str(e)
            }
        
        return jsonify(configs)
        
    except Exception as e:
        print(f"[SCRIPT CONFIG] Error fetching script configs: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/script-configs', methods=['POST'])
@admin_required
def update_script_configs():
    """Update script configuration in S3"""
    try:
        data = request.json
        s3_client = get_s3_client()
        results = {}
        
        print(f"[SCRIPT CONFIG] Updating configs: {data}")
        
        # Update amznUploadConfig if provided
        if 'amznUploadConfig' in data:
            try:
                # Convert date to datetime with time set to start of day
                date_str = data['amznUploadConfig']['last_processed_date']
                if date_str:
                    # Parse date and set time to 00:00:00
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                    iso_datetime = date_obj.strftime('%Y-%m-%dT00:00:00Z')
                else:
                    iso_datetime = ''
                
                new_config = {
                    'last_processed_date': iso_datetime
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
                print(f"[SCRIPT CONFIG] Updated amznUploadConfig: {new_config}")
                
            except Exception as e:
                print(f"[SCRIPT CONFIG] Error updating amznUploadConfig: {e}")
                results['amznUploadConfig'] = {
                    'status': 'error',
                    'error': str(e)
                }
        
        # Update config.json if provided
        if 'config' in data:
            try:
                # Convert date to datetime with time set to start of day
                date_str = data['config']['last_processed_date']
                if date_str:
                    # Parse date and set time to 00:00:00
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                    iso_datetime = date_obj.strftime('%Y-%m-%dT00:00:00Z')
                else:
                    iso_datetime = ''
                
                new_config = {
                    'last_processed_date': iso_datetime
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
                print(f"[SCRIPT CONFIG] Updated config.json: {new_config}")
                
            except Exception as e:
                print(f"[SCRIPT CONFIG] Error updating config.json: {e}")
                results['config'] = {
                    'status': 'error',
                    'error': str(e)
                }
        
        return jsonify({
            'message': 'Script configurations updated',
            'results': results
        })
        
    except Exception as e:
        print(f"[SCRIPT CONFIG] Error updating script configs: {e}")
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
        
        print(f"[SCRIPT TRIGGER] Triggering {script_type} Lambda function")
        
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
            print(f"[SCRIPT TRIGGER] AWS Region: {aws_region}")
            print(f"[SCRIPT TRIGGER] AWS Access Key configured: {'Yes' if aws_access_key else 'No'}")
            print(f"[SCRIPT TRIGGER] Lambda function name: {lambda_name}")
            
            lambda_client = boto3.client(
                'lambda',
                aws_access_key_id=aws_access_key,
                aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
                region_name=aws_region
            )
            
            # Test if Lambda function exists first
            try:
                lambda_client.get_function(FunctionName=lambda_name)
                print(f"[SCRIPT TRIGGER] Lambda function {lambda_name} exists")
            except lambda_client.exceptions.ResourceNotFoundException:
                print(f"[SCRIPT TRIGGER] ERROR: Lambda function {lambda_name} not found")
                return jsonify({
                    'error': f'Lambda function {lambda_name} not found. Please check the function name and region.'
                }), 404
            except Exception as get_error:
                print(f"[SCRIPT TRIGGER] ERROR checking Lambda function existence: {get_error}")
                return jsonify({
                    'error': f'Failed to verify Lambda function {lambda_name}: {str(get_error)}'
                }), 500
            
            response = lambda_client.invoke(
                FunctionName=lambda_name,
                InvocationType='Event',  # Async invocation
                Payload=json.dumps({})
            )
            print(f"[SCRIPT TRIGGER] Successfully invoked Lambda function {lambda_name}")
            print(f"[SCRIPT TRIGGER] Lambda response StatusCode: {response.get('StatusCode')}")
            
            return jsonify({
                'message': f'{script_type} Lambda function ({lambda_name}) invoked successfully',
                'script_type': script_type,
                'lambda_name': lambda_name,
                'lambda_invoked': True,
                'status_code': response.get('StatusCode')
            })
            
        except Exception as lambda_error:
            print(f"[SCRIPT TRIGGER] Failed to invoke Lambda {lambda_name}: {lambda_error}")
            return jsonify({
                'error': f'Failed to invoke Lambda function {lambda_name}: {str(lambda_error)}'
            }), 500
            
    except Exception as e:
        print(f"[SCRIPT TRIGGER] Error: {e}")
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
            region_name='us-east-1'  # Adjust to your Lambda region
        )
        
        # Calculate time range
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours)
        
        start_timestamp = int(start_time.timestamp() * 1000)
        end_timestamp = int(end_time.timestamp() * 1000)
        
        print(f"[LAMBDA LOGS] Fetching logs for {function_name} from {start_time} to {end_time}")
        
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
        print(f"[LAMBDA LOGS] Error: {e}")
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

@app.route('/status', methods=['GET'])
def status():
    """Ultra-simple status check"""
    return 'OK'

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
        
        print(f"[STARTUP] Starting Flask app on port {port}, debug={debug_mode}")
        print(f"[STARTUP] Environment variables: PORT={os.environ.get('PORT')}, FLASK_ENV={os.environ.get('FLASK_ENV')}")
        print(f"[STARTUP] Host: 0.0.0.0, Port: {port}")
        
        # Check critical environment variables
        critical_vars = ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'CONFIG_S3_BUCKET']
        missing_vars = [var for var in critical_vars if not os.environ.get(var)]
        
        if missing_vars:
            print(f"[STARTUP WARNING] Missing environment variables: {missing_vars}")
            print(f"[STARTUP WARNING] Some features may not work properly")
        else:
            print(f"[STARTUP] All critical environment variables are set")
        
        # Railway expects the app to be available on 0.0.0.0 and the PORT env var
        print(f"[STARTUP] Starting Flask server...")
        app.run(
            host='0.0.0.0', 
            port=port, 
            debug=debug_mode,
            threaded=True,  # Enable threading for better concurrency
            use_reloader=False  # Disable reloader in production
        )
        
    except Exception as e:
        print(f"[STARTUP ERROR] Failed to start Flask app: {e}")
        import traceback
        traceback.print_exc()
        raise