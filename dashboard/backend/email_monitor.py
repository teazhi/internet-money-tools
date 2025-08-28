#!/usr/bin/env python3
"""
Email Monitoring Service for Yankee Candle Refunds
Monitors IMAP emails and sends webhook notifications when matching emails are found.
"""

import imaplib
import email
import sqlite3
import time
import json
import requests
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
import os
import threading
from email.header import decode_header

# Configuration
DATABASE_FILE = 'app_data.db'
CHECK_INTERVAL = int(os.getenv('EMAIL_CHECK_INTERVAL', '86400'))  # Default 24 hours (86400 seconds)
BATCH_SIZE = 50  # Process emails in batches

# Initialize encryption
ENCRYPTION_KEY = os.getenv('EMAIL_ENCRYPTION_KEY')
if not ENCRYPTION_KEY:
    ENCRYPTION_KEY = Fernet.generate_key()
    print("⚠️  Warning: Using auto-generated encryption key. Set EMAIL_ENCRYPTION_KEY environment variable for production.")

email_cipher = Fernet(ENCRYPTION_KEY)

class EmailMonitor:
    def __init__(self):
        self.running = False
        self.last_check_times = {}
    
    def decrypt_password(self, encrypted_password):
        """Decrypt stored email password"""
        try:
            return email_cipher.decrypt(encrypted_password.encode()).decode()
        except Exception as e:
            print(f"Error decrypting password: {e}")
            return None
    
    def get_active_configurations(self):
        """Get all active email monitoring configurations"""
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT discord_id, email_address, auth_type, imap_server, imap_port, username, 
                   password_encrypted, oauth_access_token, oauth_refresh_token, oauth_token_expires_at, last_checked
            FROM email_monitoring 
            WHERE is_active = 1
        ''')
        
        configs = cursor.fetchall()
        conn.close()
        return configs
    
    def get_user_rules(self, discord_id):
        """Get active monitoring rules for a user"""
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, rule_name, sender_filter, subject_filter, content_filter
            FROM email_monitoring_rules 
            WHERE discord_id = ? AND is_active = 1
        ''', (discord_id,))
        
        rules = cursor.fetchall()
        conn.close()
        return rules
    
    def update_last_checked(self, discord_id, email_address):
        """Update the last checked timestamp for an email configuration"""
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE email_monitoring 
            SET last_checked = CURRENT_TIMESTAMP 
            WHERE discord_id = ? AND email_address = ?
        ''', (discord_id, email_address))
        
        conn.commit()
        conn.close()
    
    def log_email_match(self, discord_id, rule_id, email_subject, email_sender, email_date, webhook_sent, webhook_response):
        """Log when an email matches a rule"""
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO email_monitoring_logs 
            (discord_id, rule_id, email_subject, email_sender, email_date, webhook_sent, webhook_response)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (discord_id, rule_id, email_subject, email_sender, email_date, webhook_sent, webhook_response))
        
        conn.commit()
        conn.close()
    
    def decode_email_header(self, header):
        """Decode email header properly handling encoding"""
        if not header:
            return ""
        
        decoded_headers = decode_header(header)
        header_string = ""
        
        for decoded_string, encoding in decoded_headers:
            if isinstance(decoded_string, bytes):
                try:
                    if encoding:
                        header_string += decoded_string.decode(encoding)
                    else:
                        header_string += decoded_string.decode('utf-8', errors='ignore')
                except (UnicodeDecodeError, LookupError):
                    header_string += decoded_string.decode('utf-8', errors='ignore')
            else:
                header_string += decoded_string
        
        return header_string
    
    def matches_rule(self, email_msg, rule):
        """Check if an email matches a monitoring rule"""
        _, rule_name, sender_filter, subject_filter, content_filter = rule
        
        # Get email components
        sender = self.decode_email_header(email_msg.get('From', ''))
        subject = self.decode_email_header(email_msg.get('Subject', ''))
        
        # Get email body
        body = ""
        try:
            if email_msg.is_multipart():
                for part in email_msg.walk():
                    if part.get_content_type() == "text/plain":
                        charset = part.get_content_charset() or 'utf-8'
                        body += part.get_payload(decode=True).decode(charset, errors='ignore')
            else:
                charset = email_msg.get_content_charset() or 'utf-8'
                body = email_msg.get_payload(decode=True).decode(charset, errors='ignore')
        except Exception as e:
            print(f"Error extracting email body: {e}")
            body = ""
        
        # Check filters
        if sender_filter and sender_filter.lower() not in sender.lower():
            return False
        
        if subject_filter and subject_filter.lower() not in subject.lower():
            return False
        
        if content_filter and content_filter.lower() not in body.lower():
            return False
        
        return True, sender, subject, body
    
    def send_webhook(self, webhook_url, email_data):
        """Send webhook notification"""
        try:
            # Format payload for Discord webhooks
            if 'discord.com/api/webhooks' in webhook_url.lower():
                preview = email_data['body'][:500] + "..." if len(email_data['body']) > 500 else email_data['body']
                payload = {
                    'content': '📧 **New Email Match Found**',
                    'embeds': [{
                        'title': email_data['subject'],
                        'description': f"**From:** {email_data['sender']}\n**Date:** {email_data['date']}\n\n**Preview:**\n{preview}",
                        'color': 3066993,  # Green color
                        'timestamp': datetime.now().isoformat(),
                        'footer': {'text': 'Email Monitoring System'}
                    }]
                }
            else:
                # Generic payload for other webhook types (Slack, custom, etc.)
                payload = {
                    'type': 'email_notification',
                    'timestamp': datetime.now().isoformat(),
                    'email': {
                        'sender': email_data['sender'],
                        'subject': email_data['subject'],
                        'date': email_data['date'],
                        'preview': email_data['body'][:500] + "..." if len(email_data['body']) > 500 else email_data['body']
                    }
                }
            
            response = requests.post(webhook_url, json=payload, timeout=30)
            response.raise_for_status()
            
            return True, f"Success: {response.status_code}"
            
        except Exception as e:
            return False, f"Error: {str(e)}"
    
    def check_email_account(self, config):
        """Check a single email account for new messages"""
        # Unpack all fields (including new OAuth fields)
        discord_id, email_address, auth_type, imap_server, imap_port, username, encrypted_password, oauth_access_token, oauth_refresh_token, oauth_token_expires_at, last_checked = config
        
        if auth_type == 'oauth':
            # Use Gmail API with OAuth
            return self.check_email_account_oauth(discord_id, email_address, oauth_access_token, oauth_refresh_token, oauth_token_expires_at, last_checked)
        else:
            # Use IMAP authentication
            password = self.decrypt_password(encrypted_password)
            if not password:
                print(f"Failed to decrypt password for {email_address}")
                return
            
            return self.check_email_account_imap(discord_id, email_address, imap_server, imap_port, username, password, last_checked)
    
    def get_system_webhook_url(self):
        """Get the system-wide webhook URL"""
        try:
            conn = sqlite3.connect(DATABASE_FILE)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT webhook_url 
                FROM email_monitoring_webhook_config
                WHERE is_active = 1
                ORDER BY created_at DESC
                LIMIT 1
            ''')
            
            row = cursor.fetchone()
            conn.close()
            
            return row[0] if row else None
        except Exception as e:
            print(f"Error getting system webhook: {e}")
            return None
    
    def check_email_account_oauth(self, discord_id, email_address, access_token, refresh_token, token_expires_at, last_checked):
        """Check email account using Gmail API OAuth"""
        try:
            print(f"Checking {email_address} using Gmail API OAuth")
            
            # Create mock user record for Gmail API calls
            user_record = {
                'google_tokens': {
                    'access_token': access_token,
                    'refresh_token': refresh_token,
                    'expires_at': token_expires_at
                }
            }
            
            # Import Gmail API functions from main app
            import sys
            import importlib
            app_module = sys.modules.get('__main__') or sys.modules.get('app')
            if app_module:
                search_gmail_messages = getattr(app_module, 'search_gmail_messages', None)
                get_gmail_message = getattr(app_module, 'get_gmail_message', None)
                
                if not search_gmail_messages or not get_gmail_message:
                    print(f"Gmail API functions not available")
                    return
                
                # Search for emails from the last few days
                days_back = 2  # Check last 2 days
                from datetime import datetime, timedelta
                cutoff_date = datetime.now() - timedelta(days=days_back)
                
                # Build search query
                query = f'after:{cutoff_date.strftime("%Y/%m/%d")}'
                
                print(f"Gmail API search query: {query}")
                
                # Search for messages
                messages = search_gmail_messages(user_record, query, max_results=50)
                
                if not messages or not messages.get('messages'):
                    print(f"No emails found in Gmail for {email_address}")
                    self.update_last_checked(discord_id, email_address)
                    return
                
                # Get user's monitoring rules
                rules = self.get_user_rules(discord_id)
                if not rules:
                    print(f"No active rules found for user {discord_id}")
                    self.update_last_checked(discord_id, email_address)
                    return
                
                # Get system webhook URL
                webhook_url = self.get_system_webhook_url()
                if not webhook_url:
                    print(f"No system webhook configured")
                    return
                
                matches_found = 0
                
                # Process each message
                for message in messages['messages'][:50]:  # Limit to 50 for performance
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
                        
                        # Get email body
                        html_content = self.extract_email_content(email_data.get('payload', {}))
                        
                        # Check against each rule
                        for rule in rules:
                            rule_id = rule[0]
                            
                            match_result = self.matches_rule_oauth(subject, sender, html_content, rule)
                            if match_result:
                                print(f"🎯 Email match found! Rule: {rule[1]}, Subject: {subject}")
                                
                                # Send webhook
                                email_webhook_data = {
                                    'sender': sender,
                                    'subject': subject,
                                    'date': date_received,
                                    'body': html_content[:500] + "..." if len(html_content) > 500 else html_content
                                }
                                
                                webhook_sent, webhook_response = self.send_webhook(webhook_url, email_webhook_data)
                                
                                # Log the match
                                self.log_email_match(
                                    discord_id, rule_id, subject, sender, 
                                    date_received, webhook_sent, webhook_response
                                )
                                
                                matches_found += 1
                                
                                if webhook_sent:
                                    print(f"✅ Webhook sent successfully for rule {rule[1]}")
                                else:
                                    print(f"❌ Webhook failed for rule {rule[1]}: {webhook_response}")
                    
                    except Exception as e:
                        print(f"Error processing Gmail message {message_id}: {e}")
                        continue
                
                print(f"Processed Gmail messages for {email_address}, found {matches_found} matches")
                self.update_last_checked(discord_id, email_address)
                
            else:
                print(f"Cannot access Gmail API functions")
                
        except Exception as e:
            print(f"Error checking Gmail account {email_address}: {e}")
    
    def extract_email_content(self, payload):
        """Extract HTML/text content from Gmail API payload"""
        try:
            if payload.get('mimeType') == 'text/html':
                data = payload.get('body', {}).get('data', '')
                if data:
                    import base64
                    return base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
            
            if payload.get('mimeType') == 'text/plain':
                data = payload.get('body', {}).get('data', '')
                if data:
                    import base64
                    plain_text = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                    return f"<div>{plain_text}</div>"
            
            # Check multipart messages
            for part in payload.get('parts', []):
                result = self.extract_email_content(part)
                if result:
                    return result
            
            return "<div>No content</div>"
        except Exception as e:
            print(f"Error extracting email content: {e}")
            return "<div>Content extraction failed</div>"
    
    def matches_rule_oauth(self, subject, sender, body, rule):
        """Check if email matches rule (OAuth version)"""
        _, rule_name, sender_filter, subject_filter, content_filter = rule[:5]
        
        # Check filters
        if sender_filter and sender_filter.lower() not in sender.lower():
            return False
        
        if subject_filter and subject_filter.lower() not in subject.lower():
            return False
        
        if content_filter and content_filter.lower() not in body.lower():
            return False
        
        return True
    
    def check_email_account_imap(self, discord_id, email_address, imap_server, imap_port, username, password, last_checked):
        """Check email account using IMAP"""
        try:
            # Connect to IMAP server
            mail = imaplib.IMAP4_SSL(imap_server, imap_port)
            mail.login(username, password)
            mail.select('inbox')
            
            # Calculate search criteria based on last check
            search_criteria = 'ALL'
            if last_checked:
                # Convert last_checked to datetime and search for emails after that
                try:
                    last_check_dt = datetime.fromisoformat(last_checked.replace('Z', '+00:00'))
                    # For daily checks, look back 2 days to ensure we don't miss anything
                    two_days_ago = (datetime.now() - timedelta(days=2)).strftime('%d-%b-%Y')
                    search_criteria = f'SINCE "{two_days_ago}"'
                except:
                    # If parsing fails, search all emails from last 2 days
                    two_days_ago = (datetime.now() - timedelta(days=2)).strftime('%d-%b-%Y')
                    search_criteria = f'SINCE "{two_days_ago}"'
            else:
                # First time checking - check last 2 days
                two_days_ago = (datetime.now() - timedelta(days=2)).strftime('%d-%b-%Y')
                search_criteria = f'SINCE "{two_days_ago}"'
            
            print(f"Checking {email_address} with criteria: {search_criteria}")
            
            # Search for emails
            result, messages = mail.search(None, search_criteria)
            if result != 'OK':
                print(f"Search failed for {email_address}")
                return
            
            email_ids = messages[0].split()
            if not email_ids:
                print(f"No new emails found for {email_address}")
                self.update_last_checked(discord_id, email_address)
                return
            
            print(f"Found {len(email_ids)} emails to check for {email_address}")
            
            # Get user's monitoring rules
            rules = self.get_user_rules(discord_id)
            if not rules:
                print(f"No active rules found for user {discord_id}")
                self.update_last_checked(discord_id, email_address)
                return
            
            # Get system webhook URL
            webhook_url = self.get_system_webhook_url()
            if not webhook_url:
                print(f"No system webhook configured, skipping notifications")
                return
            
            # Check each email against rules
            matches_found = 0
            for email_id in email_ids[-BATCH_SIZE:]:  # Process latest emails first
                try:
                    # Fetch email
                    result, msg_data = mail.fetch(email_id, '(RFC822)')
                    if result != 'OK':
                        continue
                    
                    email_msg = email.message_from_bytes(msg_data[0][1])
                    email_date = email_msg.get('Date', '')
                    
                    # Check against each rule
                    for rule in rules:
                        rule_id = rule[0]
                        
                        match_result = self.matches_rule(email_msg, rule)
                        if match_result and isinstance(match_result, tuple):
                            matches, sender, subject, body = match_result
                            
                            if matches:
                                print(f"🎯 Email match found! Rule: {rule[1]}, Subject: {subject}")
                                
                                # Send webhook using system webhook
                                email_data = {
                                    'sender': sender,
                                    'subject': subject,
                                    'date': email_date,
                                    'body': body
                                }
                                
                                webhook_sent, webhook_response = self.send_webhook(webhook_url, email_data)
                                
                                # Log the match
                                self.log_email_match(
                                    discord_id, rule_id, subject, sender, 
                                    email_date, webhook_sent, webhook_response
                                )
                                
                                matches_found += 1
                                
                                if webhook_sent:
                                    print(f"✅ Webhook sent successfully for rule {rule[1]}")
                                else:
                                    print(f"❌ Webhook failed for rule {rule[1]}: {webhook_response}")
                
                except Exception as e:
                    print(f"Error processing email {email_id}: {e}")
                    continue
            
            print(f"Processed {len(email_ids)} emails for {email_address}, found {matches_found} matches")
            
            # Update last checked time
            self.update_last_checked(discord_id, email_address)
            
        except Exception as e:
            print(f"Error checking email account {email_address}: {e}")
        
        finally:
            try:
                mail.logout()
            except:
                pass
    
    def run_monitoring_cycle(self):
        """Run one complete monitoring cycle"""
        print(f"🔄 Starting email monitoring cycle at {datetime.now()}")
        
        configs = self.get_active_configurations()
        if not configs:
            print("No active email monitoring configurations found")
            return
        
        print(f"Found {len(configs)} active email configurations")
        
        # Process each email configuration
        for config in configs:
            try:
                self.check_email_account(config)
                # Small delay between accounts to avoid rate limiting
                time.sleep(2)
            except Exception as e:
                print(f"Error processing email config: {e}")
                continue
        
        print(f"✅ Email monitoring cycle completed at {datetime.now()}")
    
    def start(self):
        """Start the email monitoring service"""
        print("🚀 Starting Email Monitoring Service")
        hours = CHECK_INTERVAL / 3600
        if hours >= 24:
            days = hours / 24
            print(f"Check interval: {days:.0f} day{'s' if days != 1 else ''}")
        else:
            print(f"Check interval: {hours:.1f} hours")
        
        self.running = True
        
        while self.running:
            try:
                self.run_monitoring_cycle()
                
                # Wait for next cycle
                for _ in range(CHECK_INTERVAL):
                    if not self.running:
                        break
                    time.sleep(1)
                    
            except KeyboardInterrupt:
                print("\n🛑 Keyboard interrupt received, stopping...")
                self.running = False
                break
            except Exception as e:
                print(f"❌ Error in monitoring loop: {e}")
                # Wait a bit before retrying
                time.sleep(30)
        
        print("Email monitoring service stopped")
    
    def stop(self):
        """Stop the email monitoring service"""
        print("Stopping email monitoring service...")
        self.running = False

def create_yankee_candle_rule(discord_id, webhook_url=None):
    """Helper function to create the specific Yankee Candle refund rule"""
    try:
        print(f"📝 Creating Yankee Candle rule for {discord_id}")
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        # Check if rule already exists
        cursor.execute('''
            SELECT id FROM email_monitoring_rules 
            WHERE discord_id = ? AND rule_name = ?
        ''', (discord_id, 'Yankee Candle Refund Alert'))
        
        existing_rule = cursor.fetchone()
        
        if existing_rule:
            print(f"📝 Rule already exists with ID {existing_rule[0]}, updating...")
            cursor.execute('''
                UPDATE email_monitoring_rules 
                SET sender_filter = ?, subject_filter = ?, content_filter = ?, is_active = ?
                WHERE discord_id = ? AND rule_name = ?
            ''', (
                'reply@e.yankeecandle.com',
                "Here's your refund!",
                None,
                True,
                discord_id,
                'Yankee Candle Refund Alert'
            ))
            rule_id = existing_rule[0]
        else:
            print(f"📝 Creating new rule...")
            cursor.execute('''
                INSERT INTO email_monitoring_rules 
                (discord_id, rule_name, sender_filter, subject_filter, content_filter, is_active)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                discord_id,
                'Yankee Candle Refund Alert',
                'reply@e.yankeecandle.com',
                "Here's your refund!",
                None,  # No content filter needed
                True
            ))
            rule_id = cursor.lastrowid
        
        conn.commit()
        conn.close()
        
        print(f"✅ Successfully created Yankee Candle rule with ID {rule_id}")
        return rule_id
    
    except Exception as e:
        print(f"❌ Error creating Yankee Candle rule: {e}")
        if 'conn' in locals():
            conn.close()
        raise e

if __name__ == '__main__':
    # Create and start the email monitor
    monitor = EmailMonitor()
    
    try:
        monitor.start()
    except KeyboardInterrupt:
        print("\nShutting down email monitor...")
    finally:
        monitor.stop()