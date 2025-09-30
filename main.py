"""
EchoMi AI Model - Main Flask Application
Modular version matching original.py flow exactly
"""

from flask import Flask, jsonify
from flask_cors import CORS
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from app.config.config import Config
from app.routes.conversation import conversation_bp
from app.routes.admin import admin_bp
from app.routes.health import health_bp
from app.routes.call_summary import call_summary_bp

def create_app():
    """Create and configure Flask application"""
    app = Flask(__name__)
    
    # Load configuration
    config = Config()
    app.config.from_object(config)
    
    # Enable CORS
    CORS(app)
    
    # Register blueprints
    app.register_blueprint(conversation_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(call_summary_bp)
    
    # Health check route
    @app.route('/health', methods=['GET'])
    def health():
        return jsonify({
            "status": "healthy",
            "openai_configured": bool(config.OPENAI_API_KEY),
            "google_maps_configured": bool(config.GOOGLE_MAPS_API_KEY),
            "nodejs_backend_configured": bool(config.NODEJS_BACKEND_URL),
            "internal_api_configured": bool(config.INTERNAL_API_KEY)
        })
    
    @app.route('/', methods=['GET'])
    def root():
        return jsonify({
            "message": "EchoMi AI Model API",
            "version": config.VERSION,
            "mode": "mock" if config.MOCK_MODE else "production",
            "endpoints": [
                "/health",
                "/generate",
                "/api/get-otp",
                "/add-order",
                "/list-orders",
                "/api/test/all",
                "/api/test/examples",
                "/api/test/role-identification",
                "/api/test/unknown-caller-complete", 
                "/api/test/urgent-caller",
                "/api/test/name-extraction",
                "/api/test/enhanced-unknown-caller",
                "/api/test/followup-triggers",
                "/api/test/ai-followup-questions",
                "/api/test/phone-extraction",
                "/api/test/language-detection",
                "/api/test/hindi-delivery-flow", 
                "/api/test/english-delivery-flow",
                "/api/test/unknown-caller-multilingual",
                "/api/test/generate-endpoint-test",
                "/api/test/template-verification",
                "/api/admin/configure-backend",
                "/api/admin/test-backend",
                "/api/admin/backend-status",
                "/api/admin/update-config",
                "/api/status"
            ]
        })
    
    # API status endpoint for debugging services
    @app.route('/api/status', methods=['GET'])  
    def get_api_status():
        """Get detailed API and service status"""
        try:
            from app.services.conversation_handler import ConversationHandler
            from datetime import datetime
            
            handler = ConversationHandler(config)
            
            status = {
                'app_name': config.APP_NAME,
                'version': config.VERSION,
                'mock_mode': config.MOCK_MODE,
                'services': handler.service_factory.get_service_status(),
                'api_keys': {
                    'openai': bool(config.OPENAI_API_KEY),
                    'google_maps': bool(config.GOOGLE_MAPS_API_KEY),
                    'sms': bool(getattr(config, 'SMS_API_KEY', None)),
                    'call': bool(getattr(config, 'CALL_API_KEY', None))
                },
                'endpoints': [
                    '/health',
                    '/generate', 
                    '/api/get-otp',
                    '/add-order',
                    '/list-orders',
                    '/api/test/all',
                    '/api/test/examples',
                    '/api/test/role-identification',
                    '/api/test/unknown-caller-complete',
                    '/api/test/urgent-caller', 
                    '/api/test/name-extraction',
                    '/api/test/enhanced-unknown-caller',
                    '/api/test/followup-triggers',
                    '/api/test/ai-followup-questions',
                    '/api/test/phone-extraction',
                    '/api/test/language-detection',
                    '/api/test/hindi-delivery-flow',
                    '/api/test/english-delivery-flow', 
                    '/api/test/unknown-caller-multilingual',
                    '/api/test/generate-endpoint-test',
                    '/api/test/template-verification',
                    '/api/admin/configure-backend',
                    '/api/admin/test-backend', 
                    '/api/admin/backend-status',
                    '/api/admin/update-config',
                    '/api/status'
                ],
                'timestamp': datetime.now().isoformat()
            }
            
            return jsonify(status)
        except Exception as e:
            from datetime import datetime
            return jsonify({
                'error': f'Failed to get status: {str(e)}',
                'timestamp': datetime.now().isoformat()
            }), 500
    
    return app

if __name__ == '__main__':
    app = create_app()
    
    # Print startup information
    config = Config()
    print("🚀 Starting EchoMi AI Model Flask API...")
    print(f"📍 Mode: Production")
    print(f"🗝️ OpenAI API: {'✅' if config.OPENAI_API_KEY else '❌'}")
    print(f"🗺️ Google Maps API: {'✅' if config.GOOGLE_MAPS_API_KEY else '❌'}")
    print(f"📱 Node.js Backend: {config.NODEJS_BACKEND_URL}")
    print(f"🔐 Notification System: {'✅' if config.INTERNAL_API_KEY and config.OWNER_PHONE_NUMBER else '❌'}")
    
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=config.DEBUG
    )