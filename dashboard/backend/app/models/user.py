"""
User Model

Handles all user-related database operations
"""

import json
import logging
from datetime import datetime
from typing import Dict, Optional, List, Any

from app.models import db
from app.utils.errors import NotFoundError, ValidationError
from app.utils.encryption import encrypt_token, decrypt_token

logger = logging.getLogger(__name__)


class User:
    """User model for database operations"""
    
    @staticmethod
    def get_by_discord_id(discord_id: str) -> Optional[Dict[str, Any]]:
        """Get user by Discord ID"""
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE discord_id = ?', (discord_id,))
            row = cursor.fetchone()
            
            if row:
                return dict(row)
            return None
    
    @staticmethod
    def create(user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new user"""
        required_fields = ['discord_id', 'username']
        missing_fields = [field for field in required_fields if field not in user_data]
        if missing_fields:
            raise ValidationError(f"Missing required fields: {', '.join(missing_fields)}")
        
        # Encrypt sensitive tokens
        if 'access_token' in user_data and user_data['access_token']:
            user_data['access_token'] = encrypt_token(user_data['access_token'])
        if 'refresh_token' in user_data and user_data['refresh_token']:
            user_data['refresh_token'] = encrypt_token(user_data['refresh_token'])
        
        # Convert dict fields to JSON
        json_fields = ['google_tokens', 'gmail_tokens', 'column_mapping']
        for field in json_fields:
            if field in user_data and isinstance(user_data[field], dict):
                user_data[field] = json.dumps(user_data[field])
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Build dynamic insert query
            fields = list(user_data.keys())
            placeholders = ['?' for _ in fields]
            query = f'''
                INSERT INTO users ({', '.join(fields)})
                VALUES ({', '.join(placeholders)})
            '''
            
            cursor.execute(query, list(user_data.values()))
            
            logger.info(f"Created new user: {user_data['discord_id']}")
            
            return User.get_by_discord_id(user_data['discord_id'])
    
    @staticmethod
    def update(discord_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update user data"""
        user = User.get_by_discord_id(discord_id)
        if not user:
            raise NotFoundError(f"User {discord_id} not found")
        
        # Encrypt sensitive tokens
        if 'access_token' in update_data and update_data['access_token']:
            update_data['access_token'] = encrypt_token(update_data['access_token'])
        if 'refresh_token' in update_data and update_data['refresh_token']:
            update_data['refresh_token'] = encrypt_token(update_data['refresh_token'])
        
        # Convert dict fields to JSON
        json_fields = ['google_tokens', 'gmail_tokens', 'column_mapping']
        for field in json_fields:
            if field in update_data and isinstance(update_data[field], dict):
                update_data[field] = json.dumps(update_data[field])
        
        # Add updated_at timestamp
        update_data['updated_at'] = datetime.now()
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Build dynamic update query
            set_clauses = [f"{field} = ?" for field in update_data.keys()]
            query = f'''
                UPDATE users
                SET {', '.join(set_clauses)}
                WHERE discord_id = ?
            '''
            
            values = list(update_data.values()) + [discord_id]
            cursor.execute(query, values)
            
            logger.info(f"Updated user: {discord_id}")
            
            return User.get_by_discord_id(discord_id)
    
    @staticmethod
    def delete(discord_id: str) -> bool:
        """Delete a user"""
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM users WHERE discord_id = ?', (discord_id,))
            
            if cursor.rowcount > 0:
                logger.info(f"Deleted user: {discord_id}")
                return True
            
            return False
    
    @staticmethod
    def get_all(user_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all users, optionally filtered by type"""
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            if user_type:
                cursor.execute('SELECT * FROM users WHERE user_type = ?', (user_type,))
            else:
                cursor.execute('SELECT * FROM users')
            
            return [dict(row) for row in cursor.fetchall()]
    
    @staticmethod
    def get_subusers(parent_id: str) -> List[Dict[str, Any]]:
        """Get all subusers for a parent user"""
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM users 
                WHERE parent_user_id = ? AND user_type IN ('subuser', 'va')
            ''', (parent_id,))
            
            return [dict(row) for row in cursor.fetchall()]
    
    @staticmethod
    def verify_ownership(user_id: str, resource_user_id: str) -> bool:
        """Verify if a user owns a resource or is authorized to access it"""
        # User can access their own resources
        if user_id == resource_user_id:
            return True
        
        # Check if user is a parent of the resource owner
        resource_user = User.get_by_discord_id(resource_user_id)
        if resource_user and resource_user.get('parent_user_id') == user_id:
            return True
        
        # Check if user is a subuser of the resource owner
        user = User.get_by_discord_id(user_id)
        if user and user.get('parent_user_id') == resource_user_id:
            return True
        
        return False
    
    @staticmethod
    def get_decrypted_tokens(discord_id: str) -> Dict[str, Any]:
        """Get user with decrypted tokens"""
        user = User.get_by_discord_id(discord_id)
        if not user:
            return None
        
        # Decrypt tokens
        if user.get('access_token'):
            try:
                user['access_token'] = decrypt_token(user['access_token'])
            except Exception as e:
                logger.error(f"Failed to decrypt access token: {e}")
                user['access_token'] = None
        
        if user.get('refresh_token'):
            try:
                user['refresh_token'] = decrypt_token(user['refresh_token'])
            except Exception as e:
                logger.error(f"Failed to decrypt refresh token: {e}")
                user['refresh_token'] = None
        
        # Parse JSON fields
        json_fields = ['google_tokens', 'gmail_tokens', 'column_mapping']
        for field in json_fields:
            if user.get(field) and isinstance(user[field], str):
                try:
                    user[field] = json.loads(user[field])
                except json.JSONDecodeError:
                    user[field] = {}
        
        return user