"""
Internet Money Tools Dashboard Application Package

This package contains the refactored backend application with proper
separation of concerns and modular architecture.
"""

from flask import Flask
from flask_cors import CORS
import os
from datetime import timedelta
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def create_app(config_name='production'):
    """Application factory pattern for Flask app creation"""
    app = Flask(__name__)
    
    # Load configuration
    from app.config import config
    config_class = config.get(config_name, config['default'])
    app.config.from_object(config_class)
    
    # Configure session
    app.secret_key = os.getenv('FLASK_SECRET_KEY', 'development-key-change-in-production')
    app.config['SESSION_TYPE'] = 'filesystem'
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
    app.config['SESSION_COOKIE_SECURE'] = True
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    
    # Initialize extensions
    initialize_extensions(app)
    
    # Register blueprints
    register_blueprints(app)
    
    # Register error handlers
    register_error_handlers(app)
    
    # Initialize database
    with app.app_context():
        from app.models import init_db
        init_db()
    
    logger.info(f"Application created in {config_name} mode")
    
    return app


def initialize_extensions(app):
    """Initialize Flask extensions"""
    # CORS
    allowed_origins = os.getenv('CORS_ALLOWED_ORIGINS', '').split(',')
    if not allowed_origins or allowed_origins == ['']:
        allowed_origins = ["http://localhost:3000", "http://localhost:3001"]
    
    CORS(app, 
         resources={r"/api/*": {"origins": allowed_origins}},
         supports_credentials=True,
         allow_headers=["Content-Type", "Authorization"],
         methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])


def register_blueprints(app):
    """Register all application blueprints"""
    from app.routes.auth import auth_bp
    from app.routes.user import user_bp
    from app.routes.analytics import analytics_bp
    from app.routes.purchases import purchases_bp
    from app.routes.admin import admin_bp
    from app.routes.integrations import integrations_bp
    
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(user_bp, url_prefix='/api/user')
    app.register_blueprint(analytics_bp, url_prefix='/api/analytics')
    app.register_blueprint(purchases_bp, url_prefix='/api/purchases')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')
    app.register_blueprint(integrations_bp, url_prefix='/api/integrations')


def register_error_handlers(app):
    """Register application error handlers"""
    from app.utils.errors import register_error_handlers as register
    register(app)