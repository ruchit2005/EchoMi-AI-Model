"""Health check and status endpoints"""

from flask import Blueprint, jsonify
import time
import sys
import os
from ..config.config import Config
from ..models import HealthStatus, ServiceStatus

health_bp = Blueprint('health', __name__)

@health_bp.route('/health', methods=['GET'])
def health_check():
    """Basic health check endpoint with Pydantic model"""
    
    health_data = HealthStatus(
        status='healthy',
        timestamp=time.time(),
        app_name=Config.APP_NAME,
        version=Config.VERSION,
        mock_mode=False
    )
    
    return jsonify(health_data.model_dump()), 200

@health_bp.route('/status', methods=['GET'])
def status_check():
    """Detailed status information"""
    
    return jsonify({
        'application': {
            'name': Config.APP_NAME,
            'version': Config.VERSION,
            'debug': Config.DEBUG
        },
        'system': {
            'python_version': sys.version,
            'platform': sys.platform,
            'cwd': os.getcwd()
        },
        'services': {
            'openai': 'configured' if Config.OPENAI_API_KEY else 'not_configured',
            'maps': 'configured' if Config.GOOGLE_MAPS_API_KEY else 'not_configured', 
            'notifications': 'configured' if Config.INTERNAL_API_KEY else 'not_configured',
            'otp': 'configured'
        },
        'timestamp': time.time()
    }), 200

@health_bp.route('/ping', methods=['GET'])
def ping():
    """Simple ping endpoint"""
    return jsonify({'message': 'pong', 'timestamp': time.time()}), 200

@health_bp.route('/models/test', methods=['GET'])
def test_models():
    """Test endpoint to validate Pydantic models"""
    from datetime import datetime
    from ..models import (
        ConversationRequest, ConversationResponse, ConversationState,
        CallerType, ConversationStage, UserIntent, ConversationAction,
        OrderData, OrderStatus, LocationData
    )
    
    # Test ConversationRequest
    test_request = ConversationRequest(
        message="Hello, I need help with delivery",
        caller_type=CallerType.DELIVERY_PERSON,
        caller_id="test_caller_123"
    )
    
    # Test ConversationResponse  
    test_response = ConversationResponse(
        response="Hello! I can help you with your delivery. What do you need?",
        action=ConversationAction.ASK_FOR_INFO,
        stage=ConversationStage.PROCESSING_REQUEST,
        caller_type=CallerType.DELIVERY_PERSON,
        intent=UserIntent.GREETING,
        confidence=0.95,
        session_id="session_123"
    )
    
    # Test OrderData
    test_order = OrderData(
        order_id="ORDER_123",
        company="Swiggy",
        tracking_id="TRACK_456",
        status=OrderStatus.PENDING
    )
    
    # Test LocationData
    test_location = LocationData(
        name="Pizza Hut",
        address="123 Main Street, City",
        latitude=12.9716,
        longitude=77.5946
    )
    
    return jsonify({
        'message': 'All Pydantic models working correctly!',
        'test_data': {
            'conversation_request': test_request.model_dump(),
            'conversation_response': test_response.model_dump(),
            'order_data': test_order.model_dump(),
            'location_data': test_location.model_dump()
        },
        'timestamp': time.time()
    }), 200