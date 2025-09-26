"""EchoMi AI Model - Flask Application Factory"""

from flask import Flask
from flask_cors import CORS
import logging
import os

def create_app(config_name='development'):
    """Create and configure Flask application"""
    
    app = Flask(__name__)
    
    # Basic configuration
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-for-hackathon')
    app.config['DEBUG'] = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    
    # Enable CORS for frontend integration
    CORS(app)
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Register blueprints (will add as we implement)
    from ..routes import health_bp
    app.register_blueprint(health_bp, url_prefix='/api')
    
    app.logger.info("🚀 EchoMi AI Model started successfully!")
    
    return app