# Basic configuration management for hackathon
import os
import logging

class Config:
    """Base configuration"""
    
    # Flask settings
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-for-hackathon')
    DEBUG = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    
    # Application settings
    APP_NAME = "EchoMi AI Model"
    VERSION = "1.0.0-hackathon"
    
    # Mock mode for testing without external services
    MOCK_MODE = os.getenv('MOCK_MODE', 'True').lower() == 'true'
    
    # Logging configuration
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    
    @staticmethod
    def init_app(app):
        """Initialize app with configuration"""
        
        # Configure logging
        log_level = getattr(logging, Config.LOG_LEVEL.upper())
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        app.logger.info(f"🔧 {Config.APP_NAME} v{Config.VERSION} configured")
        app.logger.info(f"🧪 Mock mode: {'ON' if Config.MOCK_MODE else 'OFF'}")

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    
class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}