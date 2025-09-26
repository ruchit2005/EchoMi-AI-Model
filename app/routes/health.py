"""Health check and status endpoints"""

from flask import Blueprint, jsonify
import time
import sys
import os
from ..config.config import Config

health_bp = Blueprint('health', __name__)

@health_bp.route('/health', methods=['GET'])
def health_check():
    """Basic health check endpoint"""
    
    return jsonify({
        'status': 'healthy',
        'timestamp': time.time(),
        'app_name': Config.APP_NAME,
        'version': Config.VERSION,
        'mock_mode': Config.MOCK_MODE,
        'python_version': sys.version,
        'uptime': 'Just started'
    }), 200

@health_bp.route('/status', methods=['GET'])
def status_check():
    """Detailed status information"""
    
    return jsonify({
        'application': {
            'name': Config.APP_NAME,
            'version': Config.VERSION,
            'debug': Config.DEBUG,
            'mock_mode': Config.MOCK_MODE
        },
        'system': {
            'python_version': sys.version,
            'platform': sys.platform,
            'cwd': os.getcwd()
        },
        'services': {
            'openai': 'mock' if Config.MOCK_MODE else 'not_configured',
            'maps': 'mock' if Config.MOCK_MODE else 'not_configured', 
            'notifications': 'mock' if Config.MOCK_MODE else 'not_configured',
            'otp': 'mock' if Config.MOCK_MODE else 'not_configured'
        },
        'timestamp': time.time()
    }), 200

@health_bp.route('/ping', methods=['GET'])
def ping():
    """Simple ping endpoint"""
    return jsonify({'message': 'pong', 'timestamp': time.time()}), 200