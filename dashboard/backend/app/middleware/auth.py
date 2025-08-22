"""
Authentication Middleware

Handles user authentication and authorization
"""

from functools import wraps
from flask import session, request, jsonify
import logging

from app.models.user import User
from app.utils.errors import AuthenticationError, AuthorizationError

logger = logging.getLogger(__name__)


def login_required(f):
    """Decorator to require user login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'discord_id' not in session:
            raise AuthenticationError("Authentication required")
        
        # Verify user still exists
        user = User.get_by_discord_id(session['discord_id'])
        if not user:
            session.clear()
            raise AuthenticationError("User not found")
        
        return f(*args, **kwargs)
    
    return decorated_function


def admin_required(f):
    """Decorator to require admin privileges"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'discord_id' not in session:
            raise AuthenticationError("Authentication required")
        
        user = User.get_by_discord_id(session['discord_id'])
        if not user:
            session.clear()
            raise AuthenticationError("User not found")
        
        if user.get('user_tier') != 'admin':
            raise AuthorizationError("Admin privileges required")
        
        return f(*args, **kwargs)
    
    return decorated_function


def owner_or_admin_required(f):
    """Decorator to require resource ownership or admin privileges"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'discord_id' not in session:
            raise AuthenticationError("Authentication required")
        
        user = User.get_by_discord_id(session['discord_id'])
        if not user:
            session.clear()
            raise AuthenticationError("User not found")
        
        # Admin can access everything
        if user.get('user_tier') == 'admin':
            return f(*args, **kwargs)
        
        # For resource-specific endpoints, check ownership
        # This can be customized per endpoint
        resource_user_id = kwargs.get('user_id') or request.view_args.get('user_id')
        if resource_user_id:
            if not User.verify_ownership(session['discord_id'], resource_user_id):
                raise AuthorizationError("Access denied")
        
        return f(*args, **kwargs)
    
    return decorated_function


def get_current_user():
    """Get the current authenticated user"""
    if 'discord_id' not in session:
        return None
    
    return User.get_decrypted_tokens(session['discord_id'])


def is_admin():
    """Check if current user is admin"""
    user = get_current_user()
    return user and user.get('user_tier') == 'admin'


def is_demo_mode():
    """Check if application is in demo mode"""
    import os
    return os.getenv('DEMO_MODE', 'false').lower() == 'true'


def demo_data_required(f):
    """Decorator to return demo data in demo mode"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if is_demo_mode():
            # Return demo data based on endpoint
            from app.services.demo_data import get_demo_data
            endpoint = request.endpoint
            demo_data = get_demo_data(endpoint)
            if demo_data:
                return jsonify(demo_data)
        
        return f(*args, **kwargs)
    
    return decorated_function