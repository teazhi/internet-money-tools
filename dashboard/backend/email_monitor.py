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
CHECK_INTERVAL = int(os.getenv('EMAIL_CHECK_INTERVAL', '7200'))  # Default 2 hours (7200 seconds)
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
            SELECT discord_id, email_address, imap_server, imap_port, username, password_encrypted, last_checked
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
            SELECT id, rule_name, sender_filter, subject_filter, content_filter, webhook_url
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
        _, rule_name, sender_filter, subject_filter, content_filter, webhook_url = rule
        
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
        discord_id, email_address, imap_server, imap_port, username, encrypted_password, last_checked = config
        
        password = self.decrypt_password(encrypted_password)
        if not password:
            print(f"Failed to decrypt password for {email_address}")
            return
        
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
                    since_date = last_check_dt.strftime('%d-%b-%Y')
                    search_criteria = f'SINCE "{since_date}"'
                except:
                    # If parsing fails, search all emails from last 24 hours
                    yesterday = (datetime.now() - timedelta(days=1)).strftime('%d-%b-%Y')
                    search_criteria = f'SINCE "{yesterday}"'
            else:
                # First time checking - only check last 24 hours
                yesterday = (datetime.now() - timedelta(days=1)).strftime('%d-%b-%Y')
                search_criteria = f'SINCE "{yesterday}"'
            
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
                                
                                # Send webhook
                                webhook_url = rule[5]
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
        print(f"Check interval: {CHECK_INTERVAL} seconds")
        
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

def create_yankee_candle_rule(discord_id, webhook_url):
    """Helper function to create the specific Yankee Candle refund rule"""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT OR REPLACE INTO email_monitoring_rules 
        (discord_id, rule_name, sender_filter, subject_filter, content_filter, webhook_url, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        discord_id,
        'Yankee Candle Refund Alert',
        'reply@e.yankeecandle.com',
        "Here's your refund!",
        None,  # No content filter needed
        webhook_url,
        True
    ))
    
    conn.commit()
    rule_id = cursor.lastrowid
    conn.close()
    
    return rule_id

if __name__ == '__main__':
    # Create and start the email monitor
    monitor = EmailMonitor()
    
    try:
        monitor.start()
    except KeyboardInterrupt:
        print("\nShutting down email monitor...")
    finally:
        monitor.stop()