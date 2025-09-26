"""Simple Flask application entry point for hackathon"""

import sys
import os

# Add the app directory to Python path
app_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, app_dir)

try:
    from flask import Flask
    from flask_cors import CORS
    FLASK_AVAILABLE = True
except ImportError:
    print("⚠️  Flask not installed. Installing required packages...")
    print("Run: pip install flask flask-cors")
    FLASK_AVAILABLE = False
    sys.exit(1)

def create_app():
    """Create Flask application"""
    
    from app.config.config import config, Config
    
    app = Flask(__name__)
    
    # Load configuration
    config_name = os.getenv('FLASK_CONFIG', 'development')
    app.config.from_object(config[config_name])
    
    # Initialize configuration
    Config.init_app(app)
    
    # Enable CORS for frontend integration
    CORS(app)
    
    # Import and register blueprints
    from app.routes.health import health_bp
    app.register_blueprint(health_bp, url_prefix='/api')
    
    @app.route('/')
    def home():
        return {
            'message': '🤖 EchoMi AI Model - Hackathon Edition',
            'version': Config.VERSION,
            'mock_mode': Config.MOCK_MODE,
            'endpoints': {
                'health': '/api/health',
                'status': '/api/status', 
                'ping': '/api/ping'
            }
        }
    
    return app

if __name__ == '__main__':
    if FLASK_AVAILABLE:
        app = create_app()
        port = int(os.getenv('PORT', 5000))
        print(f"🚀 Starting EchoMi AI Model on port {port}")
        print(f"🔗 Access at: http://localhost:{port}")
        print(f"💊 Health check: http://localhost:{port}/api/health")
        app.run(host='0.0.0.0', port=port, debug=True)