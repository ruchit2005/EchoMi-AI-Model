"""Conversation API routes matching original.py flow"""

from flask import Blueprint, request, jsonify
import uuid
from ..config.config import Config
from ..services.conversation_handler import ConversationHandler
from ..utils.text_processing import detect_user_intent

conversation_bp = Blueprint('conversation', __name__)

# Initialize conversation handler
config = Config()
conversation_handler = ConversationHandler(config)

def handle_sms_reprocessing(data):
    """Handle SMS reprocessing requests from backend"""
    try:
        call_sid = data.get("call_sid")
        sms_data = data.get("sms_data", [])
        
        print(f"📨 [SMS REPROCESS] Processing {len(sms_data)} SMS messages for call {call_sid}")
        
        # Use conversation handler to process the SMS data
        result = conversation_handler.handle_sms_reprocessing(data, sms_data, call_sid)
        
        return jsonify(result)
        
    except Exception as e:
        print(f"❌ [SMS REPROCESS] Error: {str(e)}")
        return jsonify({
            "response_text": "I'm sorry, I had trouble processing your SMS messages. Could you try again?",
            "requires_sms": False,
            "conversation_stage": "error",
            "error": str(e)
        }), 500

@conversation_bp.route('/generate', methods=['POST'])
def generate():
    """
    Main endpoint that handles conversation flow with SMS integration
    Supports both regular conversation and SMS reprocessing
    """
    try:
        data = request.get_json(force=True)
        
        # Check if this is a reprocessing request from backend
        if data.get("requires_reprocessing"):
            return handle_sms_reprocessing(data)
        
        # Regular conversation flow
        new_message = data.get("new_message", "").strip()
        caller_role = data.get("caller_role", "unknown")
        history = data.get("history", []) or []
        stage = data.get("conversation_stage", "start")
        response_language = data.get("response_language", "en")
        call_sid = data.get("call_sid", str(uuid.uuid4()))
        
        collected_info = data.get("collected_info", {}) or {}
        firebase_uid = data.get("firebaseUid")
        caller_id = data.get("caller_id")
        
        if firebase_uid:
            collected_info['firebaseUid'] = firebase_uid
        
        if not new_message: 
            return jsonify({"error": "'new_message' is required"}), 400
        
        # Auto-identify caller role if not provided or unknown
        if caller_role == "unknown" and stage == "start":
            identified_role = conversation_handler.identify_caller_role(new_message)
            caller_role = identified_role
            print(f"[System]: Identified role as '{caller_role}'")
        
        print(f"🎯 Role={caller_role} | Intent={detect_user_intent(new_message)} | Stage: {stage}")
        
        # Handle conversation logic based on role
        if caller_role == "delivery": 
            # Check if this is an OTP request that needs SMS integration
            intent = detect_user_intent(new_message)
            otp_stages = ["asking_otp_company", "asking_order_id", "providing_otp", "otp_provided", "requesting_sms_otp"]
            
            if intent == "requesting_otp" or stage in otp_stages:
                # Use SMS integration format for OTP requests
                response_data = conversation_handler.handle_otp_request_logic(
                    new_message, stage, collected_info, response_language, call_sid, history
                )
                return jsonify(response_data)
            else:
                # Use legacy format for non-OTP delivery conversations
                response_text, new_stage, updated_info, action = conversation_handler.handle_delivery_logic(
                    new_message, stage, collected_info, caller_id, response_language
                )
                
                # Check if the action requires SMS integration
                if action.get("type") == "REQUEST_SMS_OTP":
                    # Trigger SMS integration
                    company = action.get("company", "delivery")
                    waiting_message = f"I'll check your recent messages for the {company} OTP. Please give me a moment." if response_language == 'en' else f"मैं आपके हाल के संदेशों में {company} का OTP खोज रहा हूँ। कृपया एक क्षण प्रतीक्षा करें।"
                    
                    return jsonify({
                        "response_text": waiting_message,
                        "requires_sms": True,
                        "call_sid": call_sid,
                        "conversation_stage": "checking_sms",
                        "intent": "fetch_otp",
                        "company_requested": company,
                        "updated_history": history + [
                            {"role": "user", "content": new_message},
                            {"role": "assistant", "content": waiting_message}
                        ],
                        "collected_info": updated_info
                    })
                
                return jsonify({
                    "response_text": response_text,
                    "requires_sms": False,
                    "conversation_stage": new_stage,
                    "collected_info": updated_info,
                    "action": action,
                    "call_sid": call_sid
                })
        else: 
            # For unknown callers, use legacy format for now
            response_text, new_stage, updated_info, action = conversation_handler.handle_unknown_logic(
                new_message, stage, collected_info, caller_id, response_language
            )
            
            # Convert to new format for consistency
            return jsonify({
                "response_text": response_text,
                "requires_sms": False,
                "conversation_stage": new_stage,
                "collected_info": updated_info,
                "action": action,
                "call_sid": call_sid,
                "updated_history": history + [
                    {"role": "user", "content": new_message},
                    {"role": "assistant", "content": response_text}
                ]
            })
        
        print(new_stage)
        
        intent = detect_user_intent(new_message)
        
        # Handle OTP action - fetch OTP immediately if needed (matches original)
        if action.get("type") == "PROVIDE_OTP":
            intent = "provide_otp"
            
            # Try to get OTP details from updated_info
            firebase_uid = updated_info.get('firebaseUid', 'demo-user')
            company = updated_info.get('company')
            order_id = updated_info.get('order_id')
            
            if all([firebase_uid, company, order_id]):
                otp_result = conversation_handler.otp_service.fetch_otp(firebase_uid, company, order_id)
                
                if otp_result["success"]:
                    from ..utils.text_processing import format_otp_for_speech
                    formatted_otp = format_otp_for_speech(otp_result["otp"])
                    response_text = f"Here's your OTP for {company}: {formatted_otp}"
                    
                    # Update action with actual OTP
                    action.update({
                        "otp": otp_result["otp"],
                        "formatted_otp": formatted_otp,
                        "otp_retrieved": True
                    })
                else:
                    response_text = f"I'm having trouble getting your OTP for {company}. Please try again."
                    action["otp_error"] = otp_result.get("error", "Unknown error")

        updated_history = history + [
            {"role": "user", "parts": [new_message]}, 
            {"role": "model", "parts": [response_text]}
        ]
        
        # Generate summary if call is ending
        conversation_summary = None
        if new_stage == "end_of_call" or intent == "ending_conversation":
            conversation_summary = conversation_handler.generate_conversation_summary(updated_history, updated_info)
        
        print(f"🎯 Role={caller_role} | Intent={intent} | Stage: {stage} -> {new_stage}")
        
        response_data = {
            "response_text": response_text, 
            "language": response_language,  # NEW: Return the language used
            "updated_history": updated_history, 
            "intent": intent, 
            "stage": new_stage, 
            "caller_role": caller_role,  # Include the identified/provided role
            "collected_info": updated_info, 
            "action": action 
        }
        
        # Include summary if generated
        if conversation_summary:
            response_data["conversation_summary"] = conversation_summary
        
        return jsonify(response_data)
        
    except Exception as e:
        print(f"❌ [GENERATE ERROR] {e}")
        return jsonify({
            "error": "Internal server error",
            "details": str(e) if config.DEBUG else None
        }), 500

@conversation_bp.route('/api/get-otp', methods=['POST'])
def get_otp_direct():
    """
    Direct OTP endpoint - use as fallback or for external integrations (matches original)
    """
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ["firebaseUid", "company", "orderId"]
        missing_fields = [field for field in required_fields if not data.get(field)]
        
        if missing_fields:
            return jsonify({
                "success": False,
                "error": f"Missing required parameters: {', '.join(missing_fields)}"
            }), 400
        
        firebase_uid = data.get("firebaseUid")
        company = data.get("company")
        order_id = data.get("orderId")
        
        print(f"📱 [DIRECT OTP] Request for {company} order {order_id}")
        
        # Check if order exists in local wallet and is approved
        order_data = conversation_handler.order_wallet.get(order_id)
        if order_data and order_data.get("status") != "approved":
            return jsonify({
                "success": False,
                "error": f"Order status is {order_data.get('status', 'unknown')}. Only approved orders can get OTP.",
                "speech_text": "The delivery hasn't been approved yet. Please wait for approval."
            }), 403
        
        # Fetch OTP from service
        otp_result = conversation_handler.otp_service.fetch_otp(firebase_uid, company, order_id)
        
        if otp_result["success"]:
            from ..utils.text_processing import format_otp_for_speech
            formatted_otp = format_otp_for_speech(otp_result["otp"])
            
            # Mark order as completed in local wallet
            if order_id in conversation_handler.order_wallet:
                conversation_handler.order_wallet[order_id]["status"] = "completed"
            
            return jsonify({
                "success": True,
                "otp": otp_result["otp"],
                "formatted_otp": formatted_otp,
                "speech_text": f"Here's your OTP for {company}: {formatted_otp}"
            })
        else:
            return jsonify({
                "success": False,
                "error": otp_result.get("error", "Could not retrieve OTP"),
                "speech_text": f"Sorry, I couldn't get the OTP for {company}. {otp_result.get('error', 'Please try again.')}"
            })
        
    except Exception as e:
        print(f"❌ [DIRECT OTP ERROR] {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "speech_text": "I'm having trouble getting your OTP right now."
        }), 500

@conversation_bp.route('/api/conversation-summary', methods=['POST'])
def get_conversation_summary():
    """
    Endpoint to generate conversation summary (matches original)
    """
    try:
        data = request.get_json()
        
        conversation_history = data.get("history", [])
        collected_info = data.get("collected_info", {})
        call_duration = data.get("call_duration")  # Optional
        
        if not conversation_history:
            return jsonify({
                "success": False,
                "error": "No conversation history provided"
            }), 400
        
        summary = conversation_handler.generate_conversation_summary(conversation_history, collected_info)
        
        from datetime import datetime
        response_data = {
            "success": True,
            "summary": summary,
            "conversation_length": len(conversation_history),
            "timestamp": datetime.now().isoformat()
        }
        
        # Add call duration if provided
        if call_duration:
            response_data["call_duration"] = call_duration
        
        # Add key details from collected_info
        if collected_info:
            response_data["call_details"] = {
                "company": collected_info.get("company"),
                "caller_name": collected_info.get("name"),
                "final_stage": collected_info.get("stage"),
                "otp_provided": any("OTP" in str(msg.get("parts", [])) for msg in conversation_history if msg.get("role") == "model")
            }
        
        return jsonify(response_data)
        
    except Exception as e:
        print(f"❌ [CONVERSATION SUMMARY ERROR] {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@conversation_bp.route('/add-order', methods=['POST'])
def add_order():
    """Secure endpoint to add order details to the wallet (matches original)"""
    data = request.get_json()
    
    # For demo purposes, we'll skip the secret key check in mock mode
    if not config.MOCK_MODE:
        app_secret_key = getattr(config, 'APP_SECRET_KEY', None)
        if not data or data.get("secret_key") != app_secret_key:
            return jsonify({"error": "Unauthorized"}), 401
    
    company = data.get("company", "").title()
    otp = data.get("otp")
    tracking_id = data.get("tracking_id")

    if not (company and otp):
        return jsonify({"error": "Missing 'company' or 'otp'"}), 400

    order_id = str(uuid.uuid4())
    order_data = {"company": company, "otp": otp, "status": "pending"}
    if tracking_id:
        order_data["tracking_id"] = tracking_id.replace(" ", "").upper()

    conversation_handler.order_wallet[order_id] = order_data
    print(f"✅ Order added [{order_id}] for {company}")
    return jsonify({"success": True, "order_id": order_id})

@conversation_bp.route('/list-orders', methods=['GET'])
def list_orders():
    """Debug endpoint to see current orders in wallet (matches original)"""
    return jsonify({
        "orders": conversation_handler.order_wallet,
        "count": len(conversation_handler.order_wallet)
    })

@conversation_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'services': {
            'openai': 'mock' if config.MOCK_MODE else 'real',
            'maps': 'mock' if config.MOCK_MODE else 'real',
            'otp': 'mock' if config.MOCK_MODE else 'real'
        },
        'order_count': len(conversation_handler.order_wallet)
    })