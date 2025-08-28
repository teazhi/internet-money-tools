#!/usr/bin/env python3
"""
Migration script to move OAuth tokens from users.json to database
This will clean up the architecture by separating user profile data from email monitoring data.
"""

import sqlite3
import json
import sys
import os
from datetime import datetime

# Import app functions
sys.path.append('.')
from app import get_users_config, update_users_config

DATABASE_FILE = 'app_data.db'

def migrate_oauth_tokens():
    """Move OAuth tokens from users.json to email_monitoring table"""
    print("🔄 Starting OAuth token migration...")
    
    # Get current users config
    try:
        users = get_users_config()
        print(f"Found {len(users)} users in users.json")
    except Exception as e:
        print(f"❌ Failed to load users config: {e}")
        return False
    
    # Connect to database
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    migrations_made = 0
    tokens_removed = 0
    
    for user in users:
        discord_id = user.get('discord_id')
        google_tokens = user.get('google_tokens')
        
        if not discord_id or not google_tokens:
            continue
            
        print(f"\n👤 Processing user {discord_id}")
        
        # Check if this user has email monitoring configurations
        cursor.execute('''
            SELECT id, email_address FROM email_monitoring 
            WHERE discord_id = ? AND auth_type = 'oauth'
        ''', (discord_id,))
        
        email_configs = cursor.fetchall()
        
        if email_configs:
            print(f"  📧 Found {len(email_configs)} email configurations")
            
            # Update each email config with the OAuth tokens from users.json
            for config_id, email_address in email_configs:
                access_token = google_tokens.get('access_token')
                refresh_token = google_tokens.get('refresh_token')  
                expires_at = google_tokens.get('expires_at')
                
                if access_token and refresh_token:
                    cursor.execute('''
                        UPDATE email_monitoring 
                        SET oauth_access_token = ?, 
                            oauth_refresh_token = ?, 
                            oauth_token_expires_at = ?
                        WHERE id = ?
                    ''', (access_token, refresh_token, expires_at, config_id))
                    
                    print(f"  ✅ Migrated OAuth tokens for {email_address}")
                    migrations_made += 1
        
        # Remove google_tokens from user object to clean up users.json
        if 'google_tokens' in user:
            del user['google_tokens']
            tokens_removed += 1
            print(f"  🗑️  Removed google_tokens from users.json")
    
    # Commit database changes
    conn.commit()
    conn.close()
    
    # Update users.json without the OAuth tokens
    if tokens_removed > 0:
        try:
            update_users_config(users)
            print(f"\n✅ Updated users.json - removed {tokens_removed} google_tokens entries")
        except Exception as e:
            print(f"\n❌ Failed to update users.json: {e}")
            return False
    
    print(f"\n🎉 Migration completed!")
    print(f"  - Migrated {migrations_made} email configurations")
    print(f"  - Cleaned up {tokens_removed} users.json entries")
    print(f"  - OAuth tokens now properly stored in database")
    
    return True

def verify_migration():
    """Verify the migration worked correctly"""
    print("\n🔍 Verifying migration...")
    
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    # Check database tokens
    cursor.execute('''
        SELECT discord_id, email_address, oauth_access_token, oauth_refresh_token 
        FROM email_monitoring 
        WHERE auth_type = 'oauth'
    ''')
    
    db_configs = cursor.fetchall()
    print(f"Database: {len(db_configs)} OAuth configurations found")
    
    for discord_id, email, access_token, refresh_token in db_configs:
        token_status = "✅ Valid tokens" if (access_token and len(access_token) > 50) else "❌ Invalid/missing tokens"
        print(f"  {email}: {token_status}")
    
    conn.close()
    
    # Check users.json
    try:
        users = get_users_config()
        users_with_tokens = [u for u in users if u.get('google_tokens')]
        print(f"users.json: {len(users_with_tokens)} users still have google_tokens (should be 0)")
        
        if len(users_with_tokens) == 0:
            print("✅ users.json cleaned up successfully")
        else:
            print("⚠️  Some users still have google_tokens in users.json")
            
    except Exception as e:
        print(f"❌ Failed to verify users.json: {e}")

if __name__ == '__main__':
    print("OAuth Token Migration Tool")
    print("=" * 50)
    
    # Ask for confirmation
    response = input("This will move OAuth tokens from users.json to database. Continue? (y/N): ")
    if response.lower() != 'y':
        print("Migration cancelled")
        sys.exit(0)
    
    # Run migration
    success = migrate_oauth_tokens()
    
    if success:
        verify_migration()
        print("\n🎯 Next Steps:")
        print("1. Complete OAuth setup in frontend to get real tokens")  
        print("2. Test email monitoring - it should now find matches")
        print("3. users.json is now cleaner and focused on user profile data")
    else:
        print("\n❌ Migration failed - check errors above")