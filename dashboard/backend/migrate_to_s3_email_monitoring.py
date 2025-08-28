#!/usr/bin/env python3
"""
Migration script to move email monitoring data from SQLite to S3

This will:
1. Read all data from SQLite email monitoring tables
2. Transform it to the new S3 JSON structure
3. Save to email_monitoring.json in S3
4. Verify the migration
"""

import sqlite3
import sys
import os
from datetime import datetime

# Add current directory to path
sys.path.append('.')

from email_monitoring_s3 import email_monitoring_manager

DATABASE_FILE = 'app_data.db'

def migrate_sqlite_to_s3():
    """Migrate all email monitoring data from SQLite to S3"""
    print("🚀 Starting migration from SQLite to S3...")
    
    # Connect to SQLite database
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        print(f"✅ Connected to {DATABASE_FILE}")
    except Exception as e:
        print(f"❌ Failed to connect to SQLite: {e}")
        return False
    
    migration_stats = {
        'email_configs': 0,
        'monitoring_rules': 0,
        'activity_logs': 0,
        'webhook_configs': 0,
        'users_processed': set()
    }
    
    try:
        # 1. Migrate System Webhook Configuration
        print("\n📡 Migrating system webhook configuration...")
        cursor.execute('''
            SELECT webhook_url, webhook_name, created_by, created_at
            FROM email_monitoring_webhook_config 
            WHERE is_active = 1
            ORDER BY created_at DESC
            LIMIT 1
        ''')
        
        webhook_row = cursor.fetchone()
        if webhook_row:
            webhook_url, webhook_name, created_by, created_at = webhook_row
            success = email_monitoring_manager.set_system_webhook(
                webhook_url, webhook_name, created_by
            )
            if success:
                print(f"  ✅ Migrated system webhook: {webhook_url[:50]}...")
                migration_stats['webhook_configs'] = 1
        
        # 2. Migrate Email Configurations
        print("\n📧 Migrating email configurations...")
        cursor.execute('''
            SELECT discord_id, email_address, auth_type, imap_server, imap_port, username, 
                   password_encrypted, oauth_access_token, oauth_refresh_token, 
                   oauth_token_expires_at, is_active, last_checked
            FROM email_monitoring
        ''')
        
        email_configs = cursor.fetchall()
        print(f"  Found {len(email_configs)} email configurations")
        
        for config_row in email_configs:
            (discord_id, email_address, auth_type, imap_server, imap_port, username,
             password_encrypted, oauth_access_token, oauth_refresh_token,
             oauth_token_expires_at, is_active, last_checked) = config_row
            
            # Build email config object
            email_config = {
                "email_address": email_address,
                "auth_type": auth_type or "imap",
                "is_active": bool(is_active),
                "last_checked": last_checked
            }
            
            # Add auth-specific fields
            if auth_type == "oauth":
                email_config.update({
                    "oauth_access_token": oauth_access_token,
                    "oauth_refresh_token": oauth_refresh_token,
                    "oauth_token_expires_at": oauth_token_expires_at
                })
            else:
                email_config.update({
                    "imap_server": imap_server,
                    "imap_port": imap_port,
                    "username": username,
                    "password_encrypted": password_encrypted
                })
            
            # Save to S3
            success = email_monitoring_manager.add_email_config(discord_id, email_config)
            if success:
                migration_stats['email_configs'] += 1
                migration_stats['users_processed'].add(discord_id)
                print(f"  ✅ Migrated config: {email_address} for user {discord_id}")
        
        # 3. Migrate Monitoring Rules
        print("\n📋 Migrating monitoring rules...")
        cursor.execute('''
            SELECT discord_id, rule_name, sender_filter, subject_filter, 
                   content_filter, is_active
            FROM email_monitoring_rules
        ''')
        
        rules = cursor.fetchall()
        print(f"  Found {len(rules)} monitoring rules")
        
        for rule_row in rules:
            (discord_id, rule_name, sender_filter, subject_filter, 
             content_filter, is_active) = rule_row
            
            rule = {
                "rule_name": rule_name,
                "sender_filter": sender_filter,
                "subject_filter": subject_filter,
                "content_filter": content_filter,
                "is_active": bool(is_active)
            }
            
            rule_id = email_monitoring_manager.add_monitoring_rule(discord_id, rule)
            if rule_id:
                migration_stats['monitoring_rules'] += 1
                migration_stats['users_processed'].add(discord_id)
                print(f"  ✅ Migrated rule: {rule_name} for user {discord_id}")
        
        # 4. Migrate Activity Logs
        print("\n📊 Migrating activity logs...")
        cursor.execute('''
            SELECT discord_id, rule_id, email_subject, email_sender, email_date,
                   webhook_sent, webhook_response, created_at
            FROM email_monitoring_logs
            ORDER BY created_at DESC
            LIMIT 10000
        ''')
        
        logs = cursor.fetchall()
        print(f"  Found {len(logs)} activity logs")
        
        for log_row in logs:
            (discord_id, rule_id, email_subject, email_sender, email_date,
             webhook_sent, webhook_response, created_at) = log_row
            
            success = email_monitoring_manager.log_email_match(
                discord_id, str(rule_id), email_subject, email_sender,
                email_date, bool(webhook_sent), webhook_response
            )
            if success:
                migration_stats['activity_logs'] += 1
                migration_stats['users_processed'].add(discord_id)
        
        print(f"  ✅ Migrated {migration_stats['activity_logs']} activity logs")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False
    
    finally:
        conn.close()
    
    # Print migration summary
    print(f"\n🎉 Migration completed successfully!")
    print(f"  📧 Email configurations: {migration_stats['email_configs']}")
    print(f"  📋 Monitoring rules: {migration_stats['monitoring_rules']}")
    print(f"  📊 Activity logs: {migration_stats['activity_logs']}")
    print(f"  📡 Webhook configs: {migration_stats['webhook_configs']}")
    print(f"  👥 Users processed: {len(migration_stats['users_processed'])}")
    
    return True

def verify_migration():
    """Verify the migration worked correctly"""
    print("\n🔍 Verifying migration...")
    
    # Get stats from S3
    stats = email_monitoring_manager.get_stats()
    
    print(f"S3 Email Monitoring Stats:")
    print(f"  👥 Users: {stats['total_users']}")
    print(f"  📧 Configurations: {stats['total_configurations']} ({stats['active_configurations']} active)")
    print(f"  📋 Rules: {stats['total_rules']}")
    print(f"  📊 Logs: {stats['total_logs']}")
    print(f"  📡 Webhook: {'✅ Configured' if stats['system_webhook_configured'] else '❌ Not configured'}")
    
    # Test some operations
    print(f"\n🧪 Testing S3 operations...")
    
    # Test getting system webhook
    webhook = email_monitoring_manager.get_system_webhook()
    if webhook:
        print(f"  ✅ System webhook accessible: {webhook['webhook_url'][:30]}...")
    
    # Test getting active configs
    active_configs = email_monitoring_manager.get_all_active_configs()
    print(f"  ✅ Active configs accessible: {len(active_configs)} found")
    
    # Test getting recent logs
    recent_logs = email_monitoring_manager.get_all_recent_logs(10)
    print(f"  ✅ Recent logs accessible: {len(recent_logs)} found")
    
    print(f"\n✅ Migration verification completed!")

def backup_sqlite_data():
    """Create a backup of SQLite email monitoring data before migration"""
    print("💾 Creating SQLite backup...")
    
    try:
        import shutil
        backup_file = f"email_monitoring_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        shutil.copy2(DATABASE_FILE, backup_file)
        print(f"  ✅ Backup created: {backup_file}")
        return backup_file
    except Exception as e:
        print(f"  ⚠️  Backup failed: {e}")
        return None

if __name__ == '__main__':
    print("Email Monitoring SQLite → S3 Migration")
    print("=" * 50)
    
    # Check if SQLite database exists
    if not os.path.exists(DATABASE_FILE):
        print(f"❌ SQLite database not found: {DATABASE_FILE}")
        sys.exit(1)
    
    # Ask for confirmation
    print("This will migrate all email monitoring data from SQLite to S3.")
    print("The SQLite data will remain unchanged (read-only migration).")
    response = input("\nContinue with migration? (y/N): ")
    if response.lower() != 'y':
        print("Migration cancelled")
        sys.exit(0)
    
    # Create backup
    backup_file = backup_sqlite_data()
    
    # Run migration
    success = migrate_sqlite_to_s3()
    
    if success:
        verify_migration()
        print(f"\n🎯 Next Steps:")
        print(f"1. Update Flask app to use email_monitoring_s3.py")
        print(f"2. Test all email monitoring functionality")
        print(f"3. Remove SQLite email monitoring tables once confirmed working")
        if backup_file:
            print(f"4. SQLite backup saved as: {backup_file}")
    else:
        print(f"\n❌ Migration failed - check errors above")
        if backup_file:
            print(f"SQLite backup available: {backup_file}")