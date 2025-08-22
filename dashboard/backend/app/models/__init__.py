"""
Database Models and Operations

This module contains all database models and operations
"""

import sqlite3
import os
import logging
from contextlib import contextmanager
from datetime import datetime
import json

logger = logging.getLogger(__name__)


class DatabaseConnection:
    """Database connection manager with context manager support"""
    
    def __init__(self, db_path=None):
        self.db_path = db_path or os.getenv('DATABASE_PATH', 'dashboard.db')
        self._ensure_database_exists()
    
    def _ensure_database_exists(self):
        """Ensure the database file exists"""
        if not os.path.exists(self.db_path):
            logger.info(f"Creating new database at {self.db_path}")
            self.init_db()
    
    @contextmanager
    def get_connection(self):
        """Get a database connection with automatic cleanup"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {str(e)}")
            raise
        finally:
            conn.close()
    
    def init_db(self):
        """Initialize the database with all required tables"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Users table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    discord_id TEXT PRIMARY KEY,
                    username TEXT,
                    email TEXT,
                    avatar TEXT,
                    access_token TEXT,
                    refresh_token TEXT,
                    google_tokens TEXT,
                    gmail_tokens TEXT,
                    cogs_url TEXT,
                    google_sheet_url TEXT,
                    sheet_id TEXT,
                    worksheet_title TEXT,
                    column_mapping TEXT,
                    keepa_api_key TEXT,
                    user_tier TEXT DEFAULT 'basic',
                    user_type TEXT DEFAULT 'user',
                    parent_user_id TEXT,
                    enable_source_links INTEGER DEFAULT 0,
                    search_all_worksheets INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (parent_user_id) REFERENCES users (discord_id)
                )
            ''')
            
            # Feature flags table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS feature_flags (
                    flag_name TEXT PRIMARY KEY,
                    enabled INTEGER DEFAULT 0,
                    user_groups TEXT,
                    rollout_percentage INTEGER DEFAULT 0,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # User features table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_features (
                    discord_id TEXT,
                    feature_name TEXT,
                    enabled INTEGER DEFAULT 0,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (discord_id, feature_name),
                    FOREIGN KEY (discord_id) REFERENCES users (discord_id)
                )
            ''')
            
            # Analytics cache table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS analytics_cache (
                    cache_key TEXT PRIMARY KEY,
                    data TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP
                )
            ''')
            
            # Product images cache table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS product_images (
                    asin TEXT PRIMARY KEY,
                    image_url TEXT,
                    title TEXT,
                    method TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Purchases table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS purchases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    asin TEXT NOT NULL,
                    product_name TEXT,
                    quantity INTEGER NOT NULL,
                    unit_cost REAL NOT NULL,
                    total_cost REAL NOT NULL,
                    supplier_name TEXT,
                    supplier_link TEXT,
                    status TEXT DEFAULT 'pending',
                    assigned_to TEXT,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (discord_id),
                    FOREIGN KEY (assigned_to) REFERENCES users (discord_id)
                )
            ''')
            
            # Create indexes for better performance
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_purchases_user_id ON purchases(user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_purchases_status ON purchases(status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_purchases_asin ON purchases(asin)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_analytics_cache_expires ON analytics_cache(expires_at)')
            
            logger.info("Database initialized successfully")


# Global database instance
db = DatabaseConnection()


def init_db():
    """Initialize the database (called from app factory)"""
    db.init_db()


def get_db():
    """Get database connection for use in routes"""
    return db.get_connection()