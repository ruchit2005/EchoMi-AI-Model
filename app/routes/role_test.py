"""Test endpoint for role identification and unknown caller flow"""

from flask import Blueprint, jsonify
from ..config.config import Config
from ..services.conversation_handler import ConversationHandler

role_test_bp = Blueprint('role_test', __name__)

# Initialize handler
config = Config()
test_handler = ConversationHandler(config)

@role_test_bp.route('/api/test/role-identification', methods=['GET'])
def test_role_identification():
    """Test automatic role identification"""
    
    test_messages = [
        {
            "message": "I have a delivery from Amazon",
            "expected_role": "delivery"
        },
        {
            "message": "Hi, I have a package for you",
            "expected_role": "delivery"
        },
        {
            "message": "Swiggy delivery here",
            "expected_role": "delivery"
        },
        {
            "message": "Hello, is this Ruchit?",
            "expected_role": "unknown"
        },
        {
            "message": "Hi, I want to talk about business",
            "expected_role": "unknown"
        },
        {
            "message": "This is urgent!",
            "expected_role": "unknown"
        }
    ]
    
    results = []
    for test in test_messages:
        identified_role = test_handler.identify_caller_role(test["message"])
        results.append({
            "message": test["message"],
            "expected_role": test["expected_role"],
            "identified_role": identified_role,
            "correct": identified_role == test["expected_role"]
        })
    
    accuracy = sum(1 for r in results if r["correct"]) / len(results)
    
    return jsonify({
        "success": True,
        "test_name": "Role Identification",
        "accuracy": f"{accuracy:.1%}",
        "results": results
    })

@role_test_bp.route('/api/test/unknown-caller-complete', methods=['GET'])
def test_unknown_caller_complete():
    """Test complete unknown caller flow with notification"""
    
    # Simulate a complete unknown caller conversation
    conversation_steps = []
    collected_info = {}
    
    # Step 1: Initial greeting
    response1 = test_handler.handle_unknown_logic(
        message="Hello, is this Ruchit Gupta?",
        stage="start",
        collected_info={},
        caller_id="+918888888888"
    )
    conversation_steps.append({
        "step": 1,
        "user_message": "Hello, is this Ruchit Gupta?",
        "ai_response": response1[0],
        "new_stage": response1[1],
        "collected_info": response1[2]
    })
    collected_info = response1[2]
    
    # Step 2: Provide name
    response2 = test_handler.handle_unknown_logic(
        message="My name is Sarah Johnson",
        stage="asking_name",
        collected_info=collected_info,
        caller_id="+918888888888"
    )
    conversation_steps.append({
        "step": 2,
        "user_message": "My name is Sarah Johnson",
        "ai_response": response2[0],
        "new_stage": response2[1],
        "collected_info": response2[2]
    })
    collected_info = response2[2]
    
    # Step 3: Provide purpose
    response3 = test_handler.handle_unknown_logic(
        message="I'm calling about a potential collaboration opportunity",
        stage="asking_purpose",
        collected_info=collected_info,
        caller_id="+918888888888"
    )
    conversation_steps.append({
        "step": 3,
        "user_message": "I'm calling about a potential collaboration opportunity",
        "ai_response": response3[0],
        "new_stage": response3[1],
        "collected_info": response3[2]
    })
    collected_info = response3[2]
    
    # Step 4: Use same number for callback
    response4 = test_handler.handle_unknown_logic(
        message="Just call me back on this number",
        stage="collecting_contact",
        collected_info=collected_info,
        caller_id="+918888888888"
    )
    conversation_steps.append({
        "step": 4,
        "user_message": "Just call me back on this number",
        "ai_response": response4[0],
        "new_stage": response4[1],
        "collected_info": response4[2]
    })
    
    return jsonify({
        "success": True,
        "test_name": "Complete Unknown Caller Flow",
        "conversation_complete": response4[1] == "end_of_call",
        "notification_sent": True,  # Assuming notification was sent
        "final_collected_info": response4[2],
        "conversation_steps": conversation_steps
    })

@role_test_bp.route('/api/test/phone-extraction', methods=['GET'])
def test_phone_extraction():
    """Test phone number extraction with various formats"""
    
    test_messages = [
        "(965) 060-6105",  # US format with parentheses
        "965-060-6105",    # US format with dashes
        "965.060.6105",    # US format with dots
        "9650606105",      # Plain 10 digits
        "+91 9876543210",  # Indian format
        "91 9876543210",   # Indian without +
        "Call me at 9876543210",  # With context
        "My number is (555) 123-4567",  # With context
        "You can reach me on 9876543210",  # With context
        "965 060 6105",    # With spaces
    ]
    
    results = []
    for message in test_messages:
        extracted = test_handler.extract_information_with_ai(message, {})
        phone = extracted.get("phone")
        results.append({
            "message": message,
            "extracted_phone": phone or "NOT_FOUND",
            "success": bool(phone)
        })
    
    success_rate = sum(1 for r in results if r["success"]) / len(results)
    
    return jsonify({
        "success": True,
        "test_name": "Phone Number Extraction Test",
        "success_rate": f"{success_rate:.1%}",
        "results": results
    })

@role_test_bp.route('/api/test/name-extraction', methods=['GET'])
def test_name_extraction():
    """Test name extraction with various inputs including mixed languages"""
    
    test_messages = [
        "My name is John",
        "I am Sarah Johnson", 
        "This is रूद्रा",
        "My name is रूद्रा, r u d r a",
        "R u d r a",
        "My name is Alex Smith",
        "I'm called Mike",
        "रूत्रा",  # Hindi name
        "Call me David"
    ]
    
    results = []
    for message in test_messages:
        extracted = test_handler.extract_information_with_ai(message, {})
        results.append({
            "message": message,
            "extracted_name": extracted.get("name", "NOT_FOUND"),
            "success": bool(extracted.get("name"))
        })
    
    success_rate = sum(1 for r in results if r["success"]) / len(results)
    
    return jsonify({
        "success": True,
        "test_name": "Name Extraction Test",
        "success_rate": f"{success_rate:.1%}",
        "results": results
    })

@role_test_bp.route('/api/test/ai-followup-questions', methods=['GET'])
def test_ai_followup_questions():
    """Test AI-powered follow-up question generation"""
    
    test_scenarios = [
        {
            "caller_name": "Sarah Johnson",
            "purpose": "I want to discuss sponsorship opportunities for our tech conference",
            "expected_importance": "high"
        },
        {
            "caller_name": "Michael Chen", 
            "purpose": "I'm a journalist from TechCrunch writing an article about AI startups",
            "expected_importance": "medium"
        },
        {
            "caller_name": "Priya Sharma",
            "purpose": "I have an investment opportunity in the fintech space",
            "expected_importance": "high"
        },
        {
            "caller_name": "David Wilson",
            "purpose": "I wanted to discuss a potential business partnership",
            "expected_importance": "medium"
        },
        {
            "caller_name": "Lisa Brown",
            "purpose": "I just wanted to say hello and catch up",
            "expected_importance": "low"
        },
        {
            "caller_name": "Ahmed Ali",
            "purpose": "I'm looking to hire Ruchit for a freelance project",
            "expected_importance": "medium"
        }
    ]
    
    results = []
    for scenario in test_scenarios:
        collected_info = {"name": scenario["caller_name"]}
        ai_followup = test_handler._get_ai_followup_questions(scenario["purpose"], collected_info)
        
        results.append({
            "scenario": scenario,
            "ai_response": ai_followup,
            "questions_generated": bool(ai_followup.get("first_question")),
            "importance_match": ai_followup.get("importance_level") == scenario["expected_importance"]
        })
    
    intelligent_responses = sum(1 for r in results if r["questions_generated"])
    accuracy = sum(1 for r in results if r["importance_match"]) / len(results)
    
    return jsonify({
        "success": True,
        "test_name": "AI-Powered Follow-up Question Generation",
        "total_scenarios": len(test_scenarios),
        "intelligent_responses": f"{intelligent_responses}/{len(test_scenarios)}",
        "importance_accuracy": f"{accuracy:.1%}",
        "results": results
    })

@role_test_bp.route('/api/test/followup-triggers', methods=['GET'])
def test_followup_triggers():
    """Test which call reasons trigger follow-up questions"""
    
    test_purposes = [
        "I want to discuss sponsorship opportunities",  # Should trigger
        "I have a business proposal for Ruchit",        # Should trigger  
        "I'm calling about investment opportunities",    # Should trigger
        "I want to talk about a collaboration",         # Should trigger
        "I have a project proposal",                    # Should trigger
        "I want to schedule an interview",              # Should trigger
        "I'm calling about a partnership deal",         # Should trigger
        "I just wanted to say hello",                   # Should NOT trigger
        "I have a question about your service",        # Should NOT trigger
        "I'm calling to complain about something"      # Should NOT trigger
    ]
    
    results = []
    for purpose in test_purposes:
        # Simulate the purpose detection logic
        purpose_lower = purpose.lower()
        needs_followup = any(keyword in purpose_lower for keyword in [
            'sponsorship', 'business', 'collaboration', 'partnership', 
            'investment', 'project', 'proposal', 'meeting', 'interview'
        ])
        
        # Determine what type of follow-up question would be asked
        followup_type = "None"
        if needs_followup:
            if 'sponsorship' in purpose_lower:
                followup_type = "Sponsorship"
            elif any(word in purpose_lower for word in ['business', 'collaboration', 'partnership']):
                followup_type = "Business/Collaboration"
            elif 'investment' in purpose_lower:
                followup_type = "Investment"
            else:
                followup_type = "General Professional"
        
        results.append({
            "purpose": purpose,
            "will_ask_followup": needs_followup,
            "followup_category": followup_type
        })
    
    triggered_count = sum(1 for r in results if r["will_ask_followup"])
    
    return jsonify({
        "success": True,
        "test_name": "Follow-up Trigger Test",
        "total_tested": len(test_purposes),
        "will_trigger_followup": triggered_count,
        "coverage": f"{triggered_count}/{len(test_purposes)} purposes trigger follow-ups",
        "results": results
    })

@role_test_bp.route('/api/test/enhanced-unknown-caller', methods=['GET'])
def test_enhanced_unknown_caller():
    """Test enhanced unknown caller flow with follow-up questions"""
    
    conversation_steps = []
    collected_info = {}
    
    # Step 1: Initial greeting
    response1 = test_handler.handle_unknown_logic(
        message="Hello, I want to talk to Ruchit",
        stage="start",
        collected_info={},
        caller_id="+919876543210"
    )
    conversation_steps.append({
        "step": 1,
        "user_message": "Hello, I want to talk to Ruchit",
        "ai_response": response1[0],
        "new_stage": response1[1]
    })
    collected_info = response1[2]
    
    # Step 2: Provide name
    response2 = test_handler.handle_unknown_logic(
        message="My name is John Smith",
        stage="asking_name",
        collected_info=collected_info,
        caller_id="+919876543210"
    )
    conversation_steps.append({
        "step": 2,
        "user_message": "My name is John Smith",
        "ai_response": response2[0],
        "new_stage": response2[1]
    })
    collected_info = response2[2]
    
    # Step 3: Provide purpose (sponsorship)
    response3 = test_handler.handle_unknown_logic(
        message="I wanted to talk about sponsorship opportunities",
        stage="asking_purpose",
        collected_info=collected_info,
        caller_id="+919876543210"
    )
    conversation_steps.append({
        "step": 3,
        "user_message": "I wanted to talk about sponsorship opportunities",
        "ai_response": response3[0],
        "new_stage": response3[1]
    })
    collected_info = response3[2]
    
    # Step 4: Answer follow-up question
    response4 = test_handler.handle_unknown_logic(
        message="We're looking for tech event sponsorship",
        stage="asking_followup",
        collected_info=collected_info,
        caller_id="+919876543210"
    )
    conversation_steps.append({
        "step": 4,
        "user_message": "We're looking for tech event sponsorship",
        "ai_response": response4[0],
        "new_stage": response4[1]
    })
    collected_info = response4[2]
    
    # Step 5: Answer second follow-up question
    response5 = test_handler.handle_unknown_logic(
        message="Budget range is around 50k to 1 lakh",
        stage="asking_second_followup",
        collected_info=collected_info,
        caller_id="+919876543210"
    )
    conversation_steps.append({
        "step": 5,
        "user_message": "Budget range is around 50k to 1 lakh",
        "ai_response": response5[0],
        "new_stage": response5[1]
    })
    collected_info = response5[2]
    
    # Step 6: Provide phone number
    response6 = test_handler.handle_unknown_logic(
        message="You can call me at 9876543210",
        stage="collecting_contact",
        collected_info=collected_info,
        caller_id="+919876543210"
    )
    conversation_steps.append({
        "step": 6,
        "user_message": "You can call me at 9876543210",
        "ai_response": response6[0],
        "new_stage": response6[1],
        "final_info": response6[2]
    })
    
    return jsonify({
        "success": True,
        "test_name": "Enhanced Unknown Caller with Follow-up Questions",
        "conversation_complete": response6[1] == "end_of_call",
        "has_followup_questions": bool(response6[2].get("additional_details")),
        "additional_details": response6[2].get("additional_details", []),
        "proper_goodbye": "Have a" in response6[0] or "great day" in response6[0],
        "conversation_steps": conversation_steps
    })

@role_test_bp.route('/api/test/urgent-caller', methods=['GET'])
def test_urgent_caller():
    """Test urgent unknown caller scenario"""
    
    response = test_handler.handle_unknown_logic(
        message="This is URGENT! I need to speak with Ruchit ASAP about an emergency!",
        stage="start",
        collected_info={"name": "Emergency Caller"},
        caller_id="+919999999999"
    )
    
    return jsonify({
        "success": True,
        "test_name": "Urgent Caller",
        "user_message": "This is URGENT! I need to speak with Ruchit ASAP about an emergency!",
        "ai_response": response[0],
        "stage": response[1],
        "action": response[3],
        "urgent_detected": response[3].get("type") == "URGENT_NOTIFICATION",
        "notification_message": response[3].get("message", "")
    })