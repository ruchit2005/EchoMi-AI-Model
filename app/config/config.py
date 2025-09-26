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
    MOCK_MODE = os.getenv('MOCK_MODE', 'False').lower() == 'true'
    
    # API Keys (only used when MOCK_MODE=False)
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    GOOGLE_MAPS_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY')
    
    # SMS/Call service API keys
    SMS_API_KEY = os.getenv('SMS_API_KEY')  # MSG91 or similar
    CALL_API_KEY = os.getenv('CALL_API_KEY')  # Twilio or similar
    
    # Twilio specific (if using Twilio for calls)
    TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
    TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER')
    
    # Service configuration
    ENABLE_REAL_SMS = os.getenv('ENABLE_REAL_SMS', 'False').lower() == 'true'
    ENABLE_REAL_CALLS = os.getenv('ENABLE_REAL_CALLS', 'False').lower() == 'true'
    
    # Backend Integration
    NODEJS_BACKEND_URL = os.getenv('NODEJS_BACKEND_URL', 'http://localhost:3000')
    INTERNAL_API_KEY = os.getenv('INTERNAL_API_KEY')
    
    # Notification Settings
    OWNER_PHONE_NUMBER = os.getenv('OWNER_PHONE_NUMBER')
    
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