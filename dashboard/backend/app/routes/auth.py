"""
Authentication Routes

Handles Discord OAuth and user authentication
"""

from flask import Blueprint, request, redirect, url_for, session, jsonify
import requests
import logging
from urllib.parse import urlencode

from app.models.user import User
from app.utils.errors import APIError, AuthenticationError
from app.middleware.auth import login_required
from app.config import Config

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/discord/login')
def discord_login():
    """Initiate Discord OAuth flow"""
    try:
        discord_auth_url = "https://discord.com/api/oauth2/authorize"
        params = {
            'client_id': Config.DISCORD_CLIENT_ID,
            'redirect_uri': Config.DISCORD_REDIRECT_URI,
            'response_type': 'code',
            'scope': 'identify email guilds.members.read'
        }
        
        auth_url = f"{discord_auth_url}?{urlencode(params)}"
        return redirect(auth_url)
        
    except Exception as e:
        logger.error(f"Discord login error: {e}")
        raise APIError("Failed to initiate Discord login")


@auth_bp.route('/discord/callback')
def discord_callback():
    """Handle Discord OAuth callback"""
    try:
        code = request.args.get('code')
        if not code:
            raise AuthenticationError("No authorization code received")
        
        # Exchange code for access token
        token_data = _exchange_code_for_token(code)
        access_token = token_data['access_token']
        
        # Get user info from Discord
        user_info = _get_discord_user_info(access_token)
        
        # Check if user is in the required guild
        if not _verify_guild_membership(access_token, user_info['id']):
            raise AuthenticationError("Access denied: Not a member of required Discord server")
        
        # Create or update user
        user_data = {
            'discord_id': user_info['id'],
            'username': user_info['username'],
            'email': user_info.get('email'),
            'avatar': user_info.get('avatar'),
            'access_token': access_token,
            'refresh_token': token_data.get('refresh_token')
        }
        
        existing_user = User.get_by_discord_id(user_info['id'])
        if existing_user:
            user = User.update(user_info['id'], user_data)
        else:
            user = User.create(user_data)
        
        # Set session
        session['discord_id'] = user['discord_id']
        session['username'] = user['username']
        session.permanent = True
        
        logger.info(f"User {user['username']} logged in successfully")
        
        # Redirect to frontend
        return redirect(f"{request.host_url}#/dashboard")
        
    except APIError:
        raise
    except Exception as e:
        logger.error(f"Discord callback error: {e}")
        raise APIError("Authentication failed")


@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    """Logout user"""
    username = session.get('username', 'Unknown')
    session.clear()
    
    logger.info(f"User {username} logged out")
    
    return jsonify({'message': 'Logged out successfully'})


@auth_bp.route('/user')
@login_required
def get_current_user():
    """Get current authenticated user info"""
    user = User.get_decrypted_tokens(session['discord_id'])
    if not user:
        raise AuthenticationError("User not found")
    
    # Remove sensitive data before sending to frontend
    safe_user = {
        'discord_id': user['discord_id'],
        'username': user['username'],
        'email': user['email'],
        'avatar': user['avatar'],
        'user_tier': user.get('user_tier', 'basic'),
        'user_type': user.get('user_type', 'user'),
        'parent_user_id': user.get('parent_user_id'),
        'enable_source_links': bool(user.get('enable_source_links')),
        'search_all_worksheets': bool(user.get('search_all_worksheets')),
        'created_at': user.get('created_at'),
        'updated_at': user.get('updated_at')
    }
    
    return jsonify(safe_user)


def _exchange_code_for_token(code):
    """Exchange authorization code for access token"""
    token_url = "https://discord.com/api/oauth2/token"
    
    data = {
        'client_id': Config.DISCORD_CLIENT_ID,
        'client_secret': Config.DISCORD_CLIENT_SECRET,
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': Config.DISCORD_REDIRECT_URI
    }
    
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    
    response = requests.post(token_url, data=data, headers=headers, timeout=10)
    response.raise_for_status()
    
    return response.json()


def _get_discord_user_info(access_token):
    """Get user information from Discord API"""
    headers = {'Authorization': f'Bearer {access_token}'}
    
    response = requests.get('https://discord.com/api/users/@me', headers=headers, timeout=10)
    response.raise_for_status()
    
    return response.json()


def _verify_guild_membership(access_token, user_id):
    """Verify user is member of required guild"""
    if not Config.DISCORD_GUILD_ID:
        return True  # Skip verification if no guild ID configured
    
    headers = {'Authorization': f'Bearer {access_token}'}
    
    try:
        # Get user's guilds
        response = requests.get('https://discord.com/api/users/@me/guilds', headers=headers, timeout=10)
        response.raise_for_status()
        
        guilds = response.json()
        guild_ids = [guild['id'] for guild in guilds]
        
        return Config.DISCORD_GUILD_ID in guild_ids
        
    except Exception as e:
        logger.warning(f"Failed to verify guild membership: {e}")
        return True  # Allow access if verification fails