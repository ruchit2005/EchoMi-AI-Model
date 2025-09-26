"""Test endpoints and validation for EchoMi AI Model"""

from flask import Blueprint, request, jsonify
import json
from ..config.config import Config
from ..services.conversation_handler import ConversationHandler

test_bp = Blueprint('test', __name__)

# Initialize test handler
config = Config()
test_handler = ConversationHandler(config)

@test_bp.route('/api/test/delivery-flow', methods=['POST'])
def test_delivery_flow():
    """Test complete delivery conversation flow"""
    try:
        # Step 1: Initial delivery message
        step1_response = test_handler.handle_delivery_logic(
            message="I have a delivery from Amazon",
            stage="start",
            collected_info={"firebaseUid": "test-user-123"},
            caller_id=None
        )
        
        # Step 2: Ask for directions
        step2_response = test_handler.handle_delivery_logic(
            message="I need help getting there",
            stage="asking_location_help", 
            collected_info={
                "firebaseUid": "test-user-123",
                "company": "Amazon"
            },
            caller_id=None
        )
        
        # Step 3: Provide current location
        step3_response = test_handler.handle_delivery_logic(
            message="I am at Koramangala metro station",
            stage="getting_current_location",
            collected_info={
                "firebaseUid": "test-user-123", 
                "company": "Amazon"
            },
            caller_id=None
        )
        
        # Step 4: Arrived and need OTP
        step4_response = test_handler.handle_delivery_logic(
            message="I have arrived at the location",
            stage="traveling_to_location",
            collected_info={
                "firebaseUid": "test-user-123",
                "company": "Amazon"
            },
            caller_id=None
        )
        
        # Step 5: Confirm OTP needed
        step5_response = test_handler.handle_delivery_logic(
            message="Yes, I need the OTP",
            stage="asking_if_otp_needed",
            collected_info={
                "firebaseUid": "test-user-123",
                "company": "Amazon",
                "order_id": list(test_handler.order_wallet.keys())[0] if test_handler.order_wallet else "demo-order"
            },
            caller_id=None
        )
        
        return jsonify({
            "success": True,
            "test_name": "Complete Delivery Flow",
            "steps": {
                "step1_initial_delivery": {
                    "input": "I have a delivery from Amazon",
                    "response": step1_response[0],
                    "stage": step1_response[1]
                },
                "step2_ask_directions": {
                    "input": "I need help getting there", 
                    "response": step2_response[0],
                    "stage": step2_response[1]
                },
                "step3_provide_location": {
                    "input": "I am at Koramangala metro station",
                    "response": step3_response[0], 
                    "stage": step3_response[1]
                },
                "step4_arrived": {
                    "input": "I have arrived at the location",
                    "response": step4_response[0],
                    "stage": step4_response[1]
                },
                "step5_get_otp": {
                    "input": "Yes, I need the OTP",
                    "response": step5_response[0],
                    "stage": step5_response[1]
                }
            },
            "orders_created": len(test_handler.order_wallet)
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@test_bp.route('/api/test/otp-flow', methods=['POST'])
def test_otp_flow():
    """Test OTP request flow specifically"""
    try:
        # Test direct OTP request
        otp_response = test_handler.handle_otp_request_logic(
            message="I need the OTP for Amazon delivery",
            stage="providing_otp",
            collected_info={
                "firebaseUid": "test-user-123",
                "company": "Amazon"
            }
        )
        
        return jsonify({
            "success": True,
            "test_name": "OTP Request Flow",
            "input": "I need the OTP for Amazon delivery",
            "response": otp_response[0],
            "stage": otp_response[1],
            "collected_info": otp_response[2]
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@test_bp.route('/api/test/unknown-caller', methods=['POST']) 
def test_unknown_caller():
    """Test unknown caller flow"""
    try:
        # Step 1: Initial greeting
        step1_response = test_handler.handle_unknown_logic(
            message="Hello",
            stage="start",
            collected_info={},
            caller_id="unknown-123"
        )
        
        # Step 2: Provide name
        step2_response = test_handler.handle_unknown_logic(
            message="My name is John",
            stage="asking_name",
            collected_info={},
            caller_id="unknown-123"
        )
        
        # Step 3: Provide purpose
        step3_response = test_handler.handle_unknown_logic(
            message="I want to discuss a business proposal",
            stage="asking_purpose", 
            collected_info={"name": "John"},
            caller_id="unknown-123"
        )
        
        # Step 4: Provide phone
        step4_response = test_handler.handle_unknown_logic(
            message="You can call me back at 9876543210",
            stage="collecting_contact",
            collected_info={"name": "John", "purpose": "I want to discuss a business proposal"},
            caller_id="unknown-123"
        )
        
        return jsonify({
            "success": True,
            "test_name": "Unknown Caller Flow",
            "steps": {
                "step1_greeting": {
                    "input": "Hello",
                    "response": step1_response[0],
                    "stage": step1_response[1]
                },
                "step2_name": {
                    "input": "My name is John", 
                    "response": step2_response[0],
                    "stage": step2_response[1]
                },
                "step3_purpose": {
                    "input": "I want to discuss a business proposal",
                    "response": step3_response[0],
                    "stage": step3_response[1]
                },
                "step4_phone": {
                    "input": "You can call me back at 9876543210",
                    "response": step4_response[0],
                    "stage": step4_response[1],
                    "final_info": step4_response[2]
                }
            }
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@test_bp.route('/api/test/intent-detection', methods=['POST'])
def test_intent_detection():
    """Test intent detection capabilities"""
    from ..utils.text_processing import detect_user_intent
    
    test_messages = [
        "I have a delivery from Amazon",
        "I need the OTP",
        "Can you give me directions?", 
        "I am at Koramangala metro station",
        "Yes, I need help",
        "No, I don't need anything",
        "Thank you, bye",
        "This is urgent"
    ]
    
    results = []
    for message in test_messages:
        intent = detect_user_intent(message)
        results.append({
            "message": message,
            "detected_intent": intent
        })
    
    return jsonify({
        "success": True,
        "test_name": "Intent Detection",
        "results": results
    })

@test_bp.route('/api/test/services', methods=['GET'])
def test_services():
    """Test all mock services"""
    try:
        # Test Maps Service
        maps_result = test_handler.maps_service.geocode_location("Koramangala")
        
        # Test OTP Service  
        otp_result = test_handler.otp_service.fetch_otp("test-user", "Amazon", "test-order")
        
        # Test OpenAI Service
        ai_result = test_handler.openai_service.extract_information_with_ai(
            "My name is John from Amazon delivery", 
            {}
        )
        
        return jsonify({
            "success": True,
            "test_name": "Mock Services Test",
            "services": {
                "maps_service": {
                    "input": "Koramangala",
                    "output": maps_result[:2] if maps_result else None,  # First 2 results
                    "status": "working" if maps_result else "failed"
                },
                "otp_service": {
                    "input": {"user": "test-user", "company": "Amazon", "order": "test-order"},
                    "output": otp_result,
                    "status": "working" if otp_result.get("success") else "failed"
                },
                "openai_service": {
                    "input": "My name is John from Amazon delivery",
                    "output": ai_result,
                    "status": "working" if ai_result else "failed"
                }
            }
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@test_bp.route('/api/test/all', methods=['GET'])
def run_all_tests():
    """Run all tests at once"""
    try:
        results = {}
        
        # Test 1: Delivery Flow
        try:
            response = test_handler.handle_delivery_logic(
                "I have Amazon delivery", "start", {"firebaseUid": "test"}, None
            )
            results["delivery_flow"] = {
                "status": "passed",
                "response": response[0][:100] + "..." if len(response[0]) > 100 else response[0]
            }
        except Exception as e:
            results["delivery_flow"] = {"status": "failed", "error": str(e)}
        
        # Test 2: OTP Flow
        try:
            response = test_handler.handle_otp_request_logic(
                "I need OTP", "providing_otp", {"company": "Amazon", "firebaseUid": "test"}
            )
            results["otp_flow"] = {
                "status": "passed", 
                "response": response[0][:100] + "..." if len(response[0]) > 100 else response[0]
            }
        except Exception as e:
            results["otp_flow"] = {"status": "failed", "error": str(e)}
        
        # Test 3: Services
        try:
            maps_test = test_handler.maps_service.geocode_location("Test Location")
            otp_test = test_handler.otp_service.fetch_otp("test", "Amazon", "order123")
            results["services"] = {
                "status": "passed",
                "maps_working": bool(maps_test),
                "otp_working": otp_test.get("success", False)
            }
        except Exception as e:
            results["services"] = {"status": "failed", "error": str(e)}
        
        # Calculate overall status
        passed_tests = sum(1 for test in results.values() if test.get("status") == "passed")
        total_tests = len(results)
        
        return jsonify({
            "success": True,
            "summary": {
                "total_tests": total_tests,
                "passed": passed_tests,
                "failed": total_tests - passed_tests,
                "success_rate": f"{(passed_tests/total_tests)*100:.1f}%"
            },
            "detailed_results": results
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@test_bp.route('/api/test/examples', methods=['GET'])
def get_test_examples():
    """Get example requests for testing"""
    return jsonify({
        "success": True,
        "examples": {
            "delivery_conversation_start": {
                "url": "POST /generate",
                "payload": {
                    "new_message": "I have a delivery from Amazon",
                    "caller_role": "delivery",
                    "conversation_stage": "start",
                    "firebaseUid": "test-user-123",
                    "history": []
                }
            },
            "ask_for_directions": {
                "url": "POST /generate", 
                "payload": {
                    "new_message": "I need help getting there",
                    "caller_role": "delivery",
                    "conversation_stage": "asking_location_help",
                    "collected_info": {
                        "firebaseUid": "test-user-123",
                        "company": "Amazon"
                    },
                    "history": []
                }
            },
            "provide_location": {
                "url": "POST /generate",
                "payload": {
                    "new_message": "I am at Koramangala metro station",
                    "caller_role": "delivery", 
                    "conversation_stage": "getting_current_location",
                    "collected_info": {
                        "firebaseUid": "test-user-123",
                        "company": "Amazon"
                    },
                    "history": []
                }
            },
            "request_otp": {
                "url": "POST /generate",
                "payload": {
                    "new_message": "Yes, I need the OTP",
                    "caller_role": "delivery",
                    "conversation_stage": "asking_if_otp_needed", 
                    "collected_info": {
                        "firebaseUid": "test-user-123",
                        "company": "Amazon"
                    },
                    "history": []
                }
            },
            "direct_otp_request": {
                "url": "POST /api/get-otp",
                "payload": {
                    "firebaseUid": "test-user-123",
                    "company": "Amazon",
                    "orderId": "demo-order-123"
                }
            },
            "unknown_caller": {
                "url": "POST /generate",
                "payload": {
                    "new_message": "Hello, I want to speak to Ruchit",
                    "caller_role": "unknown",
                    "conversation_stage": "start",
                    "history": []
                }
            }
        }
    })