"""Conversation handler matching original.py flow exactly"""

import uuid
from typing import Dict, Any, Tuple, Optional
from ..utils.text_processing import detect_user_intent, format_otp_for_speech, format_number_for_speech
from ..utils.language_utils import get_response_templates, get_language_config, format_mixed_text
from .service_factory import ServiceFactory
from .delivery_guidance_service import DeliveryGuidanceService

class ConversationHandler:
    """Main conversation handler that matches original.py logic"""
    
    def __init__(self, config):
        self.config = config
        self.service_factory = ServiceFactory(config)
        
        # Get services from factory
        self.openai_service = self.service_factory.openai_service
        self.maps_service = self.service_factory.maps_service
        self.otp_service = self.service_factory.otp_service
        self.notification_service = self.service_factory.notification_service
        
        # Initialize delivery guidance service
        self.delivery_guide = DeliveryGuidanceService(config)
        
        # ORDER_WALLET equivalent - stores pending orders
        self.order_wallet = {}
    
    def identify_caller_role(self, message: str) -> str:
        """Identify if the caller is delivery person or unknown (matches original.py logic)"""
        message_lower = message.lower().strip()
        
        # Check for delivery-related keywords
        delivery_keywords = [
            'delivery', 'parcel', 'package', 'amazon', 'flipkart', 
            'swiggy', 'zomato', 'zepto', 'bluedart', 'myntra',
            'courier', 'order', 'shipped'
        ]
        
        # If the message contains delivery keywords, it's likely a delivery person
        if any(keyword in message_lower for keyword in delivery_keywords):
            return 'delivery'
        
        # Otherwise, treat as unknown caller
        return 'unknown'
    
    def handle_delivery_logic(self, message: str, stage: str, collected_info: Dict[str, Any], caller_id=None, response_language: str = "en") -> Tuple[str, str, Dict[str, Any], Dict[str, Any]]:
        """
        Enhanced delivery logic with proper conversational flow matching original.py:
        1. "How may I assist?" 
        2. Caller: "I have delivery from Amazon"
        3. AI: "Do you need help getting here or are you here?"
        4. If help needed -> provide directions
        5. When reached -> "Do you need OTP?"
        """
        intent = detect_user_intent(message)
        action = {}
        templates = get_response_templates(response_language)
        
        print(f"\n--- [DELIVERY LOGIC] START ---")
        print(f"--- [DELIVERY LOGIC] Stage: {stage}, Intent: {intent}, Language: {response_language} ---")
        print(f"--- [DELIVERY LOGIC] Message: '{message}' ---")
        print(f"--- [DELIVERY LOGIC] Current collected_info: {collected_info} ---")
        
        # Store language in collected_info for consistency
        collected_info["language"] = response_language
        
        # Enhanced OTP request detection - check for Hindi patterns too
        message_lower = message.lower().strip()
        is_otp_request = (intent == "requesting_otp" or 
                         any(phrase in message_lower for phrase in ["otp चाहिए", "ओटीपी चाहिए", "code चाहिए", "चाहिए otp"]))
        
        # Handle OTP requests at any stage
        if is_otp_request:
            print("--- [DELIVERY LOGIC] OTP request detected, redirecting ---")
            return self.handle_direct_otp_request(message, stage, collected_info, response_language)
        
        # Check if we're in an OTP-specific flow
        if stage in ["asking_otp_company", "asking_order_id", "providing_otp", "otp_provided"]:
            return self.handle_direct_otp_request(message, stage, collected_info, response_language)
        
        # Stage 1: Initial greeting - "How may I assist?"
        if stage == "start":
            print("--- [DELIVERY LOGIC] Initial greeting stage ---")
            
            # Check if this is already a delivery message
            if intent == "initial_delivery" or any(k in message.lower() for k in ["delivery", "parcel", "package"]):
                # Extract company information
                extracted_info = self.extract_information_with_ai(message, collected_info)
                collected_info.update(extracted_info)
                company = collected_info.get("company")
                
                if company:
                    # Move to asking if they need directions
                    print(f"--- [DELIVERY LOGIC] Company '{company}' identified, asking for location help ---")
                    response = templates['delivery_help'].replace("{company}", company) if response_language == 'hi' else f"Hi! I see you have a delivery from {company}. Do you need help getting here, or are you already here?"
                    return response, "asking_location_help", collected_info, action
                else:
                    # Ask for company first
                    response = "धन्यवाद! आपकी डिलीवरी के लिए मैं आपकी मदद कर सकता हूँ। यह किस कंपनी से है?" if response_language == 'hi' else "Hi! I can help with your delivery. Which company is this delivery from?"
                    return response, "asking_company_first", collected_info, action
            elif any(greeting in message.lower() for greeting in ["hello", "hi", "hey", "namaste", "नमस्ते"]):
                # Handle greetings - wait for more context instead of going to unknown
                response = "नमस्ते! मैं आपकी कैसे मदद कर सकता हूँ?" if response_language == 'hi' else "Hello! How can I help you today?"
                return response, "waiting_for_context", collected_info, action
            else:
                # Generic greeting
                return templates['greeting'], "initial_greeting", collected_info, action
        
        # Stage 1.5: Waiting for context after greeting
        if stage == "waiting_for_context":
            # Check if this is a delivery message
            if intent == "initial_delivery" or any(k in message.lower() for k in ["delivery", "parcel", "package"]):
                # Extract company information
                extracted_info = self.extract_information_with_ai(message, collected_info)
                collected_info.update(extracted_info)
                company = collected_info.get("company")
                
                if company:
                    # Move directly to asking if they need directions
                    print(f"--- [DELIVERY LOGIC] Company '{company}' identified, asking for location help ---")
                    response = templates['delivery_help'].replace("{company}", company) if response_language == 'hi' else f"I see you have a delivery from {company}. Do you need help getting here, or are you already here?"
                    return response, "asking_location_help", collected_info, action
                else:
                    # Ask for company first
                    response = "मैं आपकी डिलीवरी में मदद कर सकता हूँ। यह किस कंपनी से है?" if response_language == 'hi' else "I can help with your delivery. Which company is this from?"
                    return response, "asking_company_first", collected_info, action
            else:
                # Still not clear what they need, handle as unknown caller
                return self.handle_unknown_logic(message, "start", collected_info, caller_id, response_language)
        
        # Stage 2: After initial greeting, waiting for delivery mention
        if stage == "initial_greeting":
            if intent == "initial_delivery" or any(k in message.lower() for k in ["delivery", "parcel", "package"]):
                extracted_info = self.extract_information_with_ai(message, collected_info)
                collected_info.update(extracted_info)
                company = collected_info.get("company")
                
                if company:
                    response = templates['delivery_help'].replace("{company}", company) if response_language == 'hi' else f"I see you have a delivery from {company}. Do you need help getting here, or are you already here?"
                    return response, "asking_location_help", collected_info, action
                else:
                    response = "मैं आपकी डिलीवरी में मदद कर सकता हूँ। यह किस कंपनी से है?" if response_language == 'hi' else "I can help with your delivery. Which company is this from?"
                    return response, "asking_company_first", collected_info, action
            else:
                # Not a delivery call, handle as unknown caller
                return self.handle_unknown_logic(message, "start", collected_info, caller_id, response_language)
        
        # Stage 3: Asked for company name first
        if stage == "asking_company_first":
            extracted_info = self.extract_information_with_ai(message, collected_info)
            company = extracted_info.get("company") or message.strip().title()
            collected_info["company"] = company
            
            response = f"धन्यवाद! तो आपके पास {company} से डिलीवरी है। क्या आपको यहाँ आने में मदद चाहिए या आप पहले से यहाँ हैं?" if response_language == 'hi' else f"Thank you! So you have a delivery from {company}. Do you need help getting here, or are you already here?"
            return response, "asking_location_help", collected_info, action
        
        # Stage 4: Asking if they need location help
        if stage == "asking_location_help":
            print("--- [DELIVERY LOGIC] Processing location help response ---")
            
            # Check their response
            message_lower = message.lower().strip()
            
            # They need help with directions
            if any(phrase in message_lower for phrase in ["need help", "help", "directions", "how to get", "where is", "guide me", "lost", "मदद", "रास्ता", "कहाँ", "कैसे"]):
                response = "मैं आपकी यहाँ पहुँचने में मदद करूंगा। आपकी वर्तमान स्थिति या कोई पास का लैंडमार्क बताएं?" if response_language == 'hi' else "I'd be happy to help guide you here. What's your current location or a nearby landmark?"
                return response, "getting_current_location", collected_info, action
            
            # They're already here / at location
            elif any(phrase in message_lower for phrase in ["here", "arrived", "at the location", "reached", "outside", "at your place", "at the door", "यहाँ", "पहुँच", "आ गया", "आ चुका", "हूं", "हूँ"]):
                print("--- [DELIVERY LOGIC] Caller says they're here, checking for OTP need ---")
                return self.handle_arrival_and_otp_check(collected_info, response_language)
            
            # Ambiguous response, clarify
            else:
                response = "क्या आप यहाँ आने के लिए दिशा-निर्देश चाहते हैं या आप पहले से ही यहाँ पहुँच गए हैं?" if response_language == 'hi' else "Are you asking for directions to get here, or have you already arrived at the location?"
                return response, "asking_location_help", collected_info, action
        
        # Stage 5: Getting their current location for directions
        if stage == "getting_current_location":
            print("--- [DELIVERY LOGIC] Processing current location for directions ---")
            
            # Use delivery guidance service to find them and guide them
            guidance_result = self.delivery_guide.guide_delivery_person(
                landmark_description=message,
                max_radius_km=1.0  # Search within 1km of destination
            )
            
            if guidance_result['success']:
                landmark = guidance_result['landmark']
                route = guidance_result['route']
                directions = guidance_result['turn_by_turn_directions']
                
                # Save their location
                collected_info['current_location'] = {
                    'name': landmark['name'],
                    'address': landmark['address'],
                    'distance_km': landmark['distance_from_destination']
                }
                
                # Create comprehensive response
                response_parts = [
                    f"Perfect! I found you near {landmark['name']}.",
                    f"You're about {route['total_distance_km']}km away, roughly {route['estimated_time_minutes']} minutes walk.",
                    "Here are your directions:"
                ]
                
                # Add first 3 turn-by-turn directions
                for i, step in enumerate(directions[:3], 1):
                    response_parts.append(f"{i}. {step}")
                
                response_parts.append("Let me know when you arrive!")
                
                response_text = " ".join(response_parts)
                return response_text, "traveling_to_location", collected_info, action
            else:
                # Couldn't find the landmark
                error_message = guidance_result.get('error', 'Unknown error')
                suggestion = guidance_result.get('suggestion', 'Can you describe another nearby landmark?')
                
                response = f"I couldn't find '{message}' near the delivery address. {suggestion}"
                return response, "getting_current_location", collected_info, action
        
        # Stage 6: They're traveling, waiting for arrival
        if stage == "traveling_to_location":
            message_lower = message.lower().strip()
            
            # Check if they've arrived
            if any(phrase in message_lower for phrase in ["arrived", "here", "reached", "at the location", "outside", "at your place", "at the door"]):
                print("--- [DELIVERY LOGIC] Caller has arrived, checking for OTP ---")
                return self.handle_arrival_and_otp_check(collected_info)
            
            # They're asking for more help
            elif any(phrase in message_lower for phrase in ["lost", "can't find", "help", "confused", "where"]):
                return "What landmarks can you see around you? I can help guide you from there.", "getting_current_location", collected_info, action
            
            # General response while they're traveling
            else:
                return "Let me know when you reach the location!", "traveling_to_location", collected_info, action
        
        # Handle the rest of the existing delivery logic for OTP verification
        return self.handle_existing_delivery_logic(message, stage, collected_info, intent, action)
    
    def handle_arrival_and_otp_check(self, collected_info: Dict[str, Any], response_language: str = "en") -> Tuple[str, str, Dict[str, Any], Dict[str, Any]]:
        """Handle when delivery person arrives and check if they need OTP"""
        print("--- [DELIVERY LOGIC] Handling arrival and OTP check ---")
        templates = get_response_templates(response_language)
        
        company = collected_info.get("company")
        if not company:
            response = "बहुत अच्छा! आप यहाँ हैं। यह किस कंपनी की डिलीवरी है?" if response_language == 'hi' else "Great! You're here. Which company is this delivery from?"
            return response, "asking_company_for_otp", collected_info, {}
        
        # Create mock order for demo
        order_id = str(uuid.uuid4())
        self.order_wallet[order_id] = {
            "company": company,
            "status": "approved",  # Auto-approve for demo
            "otp": "123456"  # Mock OTP
        }
        collected_info['order_id'] = order_id
        
        # Directly ask if they need OTP rather than generic greeting
        if response_language == 'hi':
            response = f"बहुत अच्छा! आप {company} डिलीवरी के साथ यहाँ पहुँच गए हैं। क्या आपको OTP चाहिए?"
        else:
            response = f"Perfect! You've arrived with the {company} delivery. Do you need the OTP?"
        
        return response, "asking_if_otp_needed", collected_info, {}
    
    def handle_existing_delivery_logic(self, message: str, stage: str, collected_info: Dict[str, Any], intent: str, action: Dict[str, Any]) -> Tuple[str, str, Dict[str, Any], Dict[str, Any]]:
        """Handle the existing delivery logic for OTP verification (matches original.py)"""
        
        # Stage: Asking if they need OTP
        if stage == "asking_if_otp_needed":
            message_lower = message.lower().strip()
            
            # Enhanced detection for yes/affirmative responses including Hindi
            if any(phrase in message_lower for phrase in ["yes", "yeah", "yep", "need", "otp", "code", "चाहिए", "हाँ", "हां", "जी", "दे"]):
                # They need OTP - use SMS integration instead of mock OTP
                company = collected_info.get("company") or "delivery"
                
                # Return SMS integration format instead of direct OTP
                return "", "requesting_sms_otp", collected_info, {"type": "REQUEST_SMS_OTP", "company": company}
            
            elif any(phrase in message_lower for phrase in ["no", "nope", "don't need", "not needed", "नहीं", "ना"]):
                goodbye_msg = "ठीक है! आपका दिन शुभ हो और सुरक्षित डिलीवरी करें!" if collected_info.get("language") == "hi" else "Alright! Have a great day and safe delivery!"
                return goodbye_msg, "end_of_call", collected_info, action
            else:
                # Unclear response, ask again
                clarify_msg = "क्या आपको इस डिलीवरी के लिए OTP चाहिए? कृपया हाँ या ना कहें।" if collected_info.get("language") == "hi" else "Do you need me to provide the OTP for this delivery? Please say yes or no."
                return clarify_msg, "asking_if_otp_needed", collected_info, action
        
        # Stage: Asked for company name for OTP
        if stage == "asking_company_for_otp":
            extracted_info = self.extract_information_with_ai(message, collected_info)
            company = extracted_info.get("company") or message.strip().title()
            collected_info["company"] = company
            
            return self.handle_arrival_and_otp_check(collected_info)
        
        # Handle asking OTP company stage
        if stage == "asking_otp_company":
            extracted_info = self.extract_information_with_ai(message, collected_info)
            company = extracted_info.get("company") or message.strip().title()
            collected_info["company"] = company
            
            # Move directly to providing OTP
            return self.handle_direct_otp_request(message, "providing_otp", collected_info, collected_info.get("language", "en"))
        
        # Handle conversation ending
        if intent == "ending_conversation":
            return "You're welcome! Have a safe delivery!", "end_of_call", collected_info, action
        
        # Fallback
        return "I'm here to help with your delivery. What can I assist you with?", stage, collected_info, action
    
    def handle_direct_otp_request(self, message: str, stage: str, collected_info: Dict[str, Any], response_language: str = "en") -> Tuple[str, str, Dict[str, Any], Dict[str, Any]]:
        """Handle OTP requests directly without SMS integration - matches original.py flow"""
        templates = get_response_templates(response_language)
        action = {}
        
        print(f"🔐 [DIRECT OTP] Stage: {stage}, Message: '{message}'")
        
        # If no company specified yet, ask for it
        company = collected_info.get("company")
        if not company:
            # Try to extract company from current message
            extracted_info = self.extract_information_with_ai(message, collected_info)
            company = extracted_info.get("company")
            
            if company:
                collected_info.update(extracted_info)
                print(f"🔐 [DIRECT OTP] Company extracted: {company}")
            else:
                # Ask for company
                response_text = "आपको किस कंपनी का OTP चाहिए?" if response_language == 'hi' else "Which company is this OTP request for?"
                return response_text, "asking_otp_company", collected_info, action
        
        # We have company, provide OTP directly (mock for now)
        print(f"🔐 [DIRECT OTP] Providing OTP for company: {company}")
        
        # Create mock order if not exists
        order_id = collected_info.get("order_id")
        if not order_id:
            order_id = str(uuid.uuid4())
            self.order_wallet[order_id] = {
                "company": company,
                "status": "approved",
                "otp": "123456"  # Mock OTP
            }
            collected_info["order_id"] = order_id
        
        # Get OTP from service
        firebase_uid = collected_info.get('firebaseUid', 'demo-user')
        otp_result = self.otp_service.fetch_otp(firebase_uid, company, order_id)
        
        if otp_result["success"]:
            formatted_otp = format_otp_for_speech(otp_result["otp"])
            if response_language == 'hi':
                response_text = f"यहाँ आपका {company} का OTP है: {formatted_otp}"
            else:
                response_text = f"Here's your {company} OTP: {formatted_otp}"
            
            # Mark order as completed
            if order_id in self.order_wallet:
                self.order_wallet[order_id]["status"] = "completed"
            
            return response_text, "otp_provided", collected_info, action
        else:
            error_msg = "मुझे आपका OTP लाने में समस्या हो रही है। कृपया फिर से कोशिश करें।" if response_language == 'hi' else "I'm having trouble getting your OTP. Please try again."
            return error_msg, "otp_error", collected_info, action
    
    def handle_otp_request_logic(self, message: str, stage: str, collected_info: Dict[str, Any], response_language: str = "en", call_sid: str = None, conversation_history: list = None) -> Dict[str, Any]:
        """Handle OTP requests using the new requires_sms format"""
        intent = detect_user_intent(message)
        templates = get_response_templates(response_language)
        
        print(f"🔐 [OTP LOGIC] Stage: {stage}, Intent: {intent}")
        print(f"🔐 [OTP LOGIC] Collected info: {collected_info}")
        
        # Initialize conversation history if not provided
        if conversation_history is None:
            conversation_history = []
        
        # If user is asking for OTP, request SMS data from backend
        if intent == "requesting_otp" or stage == "providing_otp":
            company = collected_info.get('company')
            
            if not company:
                # Ask for company first
                response_text = "आपको किस कंपनी का OTP चाहिए?" if response_language == 'hi' else "Which company is this OTP request for?"
                
                return {
                    "response_text": response_text,
                    "requires_sms": False,
                    "call_sid": call_sid,
                    "conversation_stage": "asking_otp_company",
                    "intent": "clarify_company",
                    "updated_history": conversation_history + [
                        {"role": "user", "content": message},
                        {"role": "assistant", "content": response_text}
                    ],
                    "collected_info": collected_info
                }
            
            # We have company, request SMS data to find OTP
            if response_language == 'hi':
                waiting_message = f"मैं आपके हाल के संदेशों में {company} का OTP खोज रहा हूँ। कृपया एक क्षण प्रतीक्षा करें।"
            else:
                waiting_message = f"I'll check your recent messages for the {company} OTP. Please give me a moment."
            
            return {
                "response_text": waiting_message,
                "requires_sms": True,
                "call_sid": call_sid,
                "conversation_stage": "checking_sms", 
                "intent": "fetch_otp",
                "company_requested": company,
                "updated_history": conversation_history + [
                    {"role": "user", "content": message},
                    {"role": "assistant", "content": waiting_message}
                ],
                "collected_info": collected_info
            }
        
        # Handle other stages without SMS requirement
        return self._handle_non_sms_otp_logic(message, stage, collected_info, response_language, call_sid, conversation_history)
    
    def handle_sms_reprocessing(self, original_request: Dict[str, Any], sms_data: list, call_sid: str) -> Dict[str, Any]:
        """Process SMS data and provide final OTP response"""
        
        original_ai_response = original_request.get("original_ai_response", {})
        company = original_ai_response.get("company_requested", "delivery")
        conversation_history = original_request.get("original_ai_response", {}).get("updated_history", [])
        collected_info = original_request.get("collected_info", {})
        response_language = collected_info.get("language", "en")
        
        print(f"🔄 [SMS REPROCESS] Processing {len(sms_data)} SMS messages for {company}")
        
        # Parse SMS messages to find OTP
        from ..utils.sms_parser import SMSParser
        parser = SMSParser()
        
        # Convert SMS data to our format and parse
        processed_otps = []
        for sms in sms_data:
            message_text = sms.get("message", "")
            sender = sms.get("sender", "")
            
            # Parse the SMS content
            parsed_sms = parser.parse_sms(message_text, company)
            
            processed_otps.append({
                "otp": parsed_sms.otp,
                "sender": sender,
                "message": message_text,
                "company": parsed_sms.company or self._detect_company_from_sender(sender),
                "tracking_id": parsed_sms.tracking_id,
                "confidence": parsed_sms.confidence_score,
                "timestamp": sms.get("timestamp")
            })
        
        # Find best match for the requested company
        best_match = self._find_best_otp_match(processed_otps, company)
        
        if best_match and best_match.get("otp"):
            # Success - found OTP
            otp = best_match["otp"]
            formatted_otp = format_otp_for_speech(otp)
            sender = best_match.get("sender", "SMS")
            tracking_id = best_match.get("tracking_id")
            confidence = best_match.get("confidence", 0)
            
            # Build success response and end call
            if response_language == 'hi':
                if confidence >= 0.8:
                    response_text = f"मुझे आपका {company} OTP मिल गया! यह {formatted_otp} है। धन्यवाद और सुरक्षित डिलीवरी करें!"
                else:
                    response_text = f"मुझे {sender} से एक OTP मिला: {formatted_otp}। कृपया जाँच लें कि यह {company} का है। धन्यवाद!"
                
                if tracking_id:
                    response_text += f" ट्रैकिंग नंबर: {tracking_id}"
            else:
                if confidence >= 0.8:
                    response_text = f"I found your {company} OTP! It's {formatted_otp}. Thank you and have a safe delivery!"
                else:
                    response_text = f"I found an OTP from {sender}: {formatted_otp}. Please verify this is for {company}. Thank you!"
                
                if tracking_id:
                    response_text += f" Tracking ID: {tracking_id}"
            
            return {
                "response_text": response_text,
                "requires_sms": False,
                "conversation_stage": "call_ending",
                "intent": "provide_otp",
                "otp_found": otp,
                "company": company,
                "confidence": confidence,
                "end_call": True,
                "updated_history": conversation_history + [
                    {"role": "assistant", "content": response_text}
                ]
            }
        
        else:
            # No OTP found
            if len(sms_data) == 0:
                if response_language == 'hi':
                    response_text = "मुझे आपके हाल के संदेशों में कोई SMS नहीं मिला।"
                else:
                    response_text = "I don't see any recent SMS messages."
            else:
                if response_language == 'hi':
                    response_text = f"मैंने {len(sms_data)} संदेश देखे लेकिन {company} का कोई OTP नहीं मिला। क्या आप मैन्युअल रूप से OTP बता सकते हैं?"
                else:
                    response_text = f"I checked {len(sms_data)} messages but couldn't find a {company} OTP. Could you tell me the OTP manually?"
            
            return {
                "response_text": response_text,
                "requires_sms": False,
                "conversation_stage": "otp_not_found",
                "intent": "request_manual_otp",
                "messages_checked": len(sms_data),
                "updated_history": conversation_history + [
                    {"role": "assistant", "content": response_text}
                ]
            }
            
            if otp_result["success"]:
                otp = otp_result["otp"]
                formatted_otp = format_otp_for_speech(otp)
                sender = otp_result.get("sender", "SMS")
                confidence = otp_result.get("confidence", 0)
                total_checked = otp_result.get("total_checked", 0)
                tracking_id = otp_result.get("tracking_id")
                
                # Build intelligent response
                response_parts = []
                
                if response_language == 'hi':
                    if otp_result.get("fallback_used"):
                        response_parts.append(f"मुझे {company} का सटीक मैच नहीं मिला, लेकिन {sender} का OTP मिला: {formatted_otp}")
                    else:
                        response_parts.append(f"आपका {company} OTP मिल गया: {formatted_otp}")
                    
                    if tracking_id:
                        response_parts.append(f"ट्रैकिंग नंबर: {tracking_id}")
                    
                    if total_checked > 1:
                        response_parts.append(f"मैंने {total_checked} SMS देखे हैं।")
                        
                else:
                    if otp_result.get("fallback_used"):
                        response_parts.append(f"No exact {company} match, but found OTP from {sender}: {formatted_otp}")
                    else:
                        response_parts.append(f"Found your {company} OTP: {formatted_otp}")
                    
                    if tracking_id:
                        response_parts.append(f"Tracking: {tracking_id}")
                    
                    if total_checked > 1:
                        response_parts.append(f"Checked {total_checked} recent messages.")
                
                # Add confidence indicator for low confidence matches
                if confidence < 0.7:
                    if response_language == 'hi':
                        response_parts.append("कृपया जाँच लें कि यह सही OTP है।")
                    else:
                        response_parts.append("Please verify this is the correct OTP.")
                
                response_text = " ".join(response_parts)
                
                # Mark order as completed
                if order_id in self.order_wallet:
                    self.order_wallet[order_id]["status"] = "completed"
                
                print(f"✅ [BULK SMS] Successfully found OTP: {otp} (confidence: {confidence:.2f})")
                return response_text, "otp_provided", collected_info, action
                
            else:
                # No OTP found in bulk messages
                error_msg = otp_result.get("error", "Unknown error")
                total_checked = otp_result.get("total_checked", 0)
                
                if total_checked > 0:
                    if response_language == 'hi':
                        error_response = f"मैंने {total_checked} SMS देखे लेकिन {company} का OTP नहीं मिला। कृपया मैन्युअल रूप से बताएं।"
                    else:
                        error_response = f"I checked {total_checked} messages but couldn't find {company} OTP. Could you tell me the OTP manually?"
                    
                    print(f"❌ [BULK SMS] No OTP found for {company} in {total_checked} messages")
                    return error_response, "manual_otp_entry", collected_info, action
                else:
                    # No messages at all
                    if response_language == 'hi':
                        fallback_response = f"मुझे कोई SMS नहीं मिला: {error_msg}। कृपया OTP बताएं।"
                    else:
                        fallback_response = f"I couldn't find any messages: {error_msg}. Could you tell me the OTP?"
                    
                    print(f"❌ [BULK SMS] No messages found: {error_msg}")
                    return fallback_response, "manual_otp_entry", collected_info, action
        
        # Handle responses to our questions
        if stage == "asking_otp_company":
            extracted_info = self.extract_information_with_ai(message, collected_info)
            company = extracted_info.get("company") or message.strip().title()
            collected_info["company"] = company
            
            # Try again with the company info
            return self.handle_otp_request_logic("get otp", "providing_otp", collected_info, response_language)
        
        # Handle manual OTP entry when SMS parsing fails
        if stage == "manual_otp_entry":
            # Look for OTP pattern in user message
            import re
            otp_pattern = r'\b(\d{4,6})\b'
            otp_match = re.search(otp_pattern, message)
            
            if otp_match:
                otp = otp_match.group(1)
                formatted_otp = format_otp_for_speech(otp)
                company = collected_info.get('company', 'your order')
                
                if response_language == 'hi':
                    response = f"धन्यवाद! {company} के लिए आपका OTP {formatted_otp} है। क्या यह सही है?"
                else:
                    response = f"Thank you! Your OTP for {company} is {formatted_otp}. Is this correct?"
                
                collected_info['manual_otp'] = otp
                return response, "confirming_manual_otp", collected_info, {}
            else:
                if response_language == 'hi':
                    response = "मुझे OTP नंबर समझ नहीं आया। कृपया केवल 4 या 6 अंकों का OTP बताएं।"
                else:
                    response = "I couldn't understand the OTP. Please tell me just the 4 or 6 digit numbers."
                return response, "manual_otp_entry", collected_info, {}
        
        # Confirm manually entered OTP
        if stage == "confirming_manual_otp":
            if any(word in message.lower() for word in ['yes', 'correct', 'right', 'हाँ', 'सही', 'ठीक']):
                otp = collected_info.get('manual_otp')
                company = collected_info.get('company', 'your order')
                
                if response_language == 'hi':
                    response = f"बहुत अच्छे! {company} का OTP {format_otp_for_speech(otp)} सुरक्षित है। कुछ और मदद चाहिए?"
                else:
                    response = f"Perfect! Your {company} OTP {format_otp_for_speech(otp)} is confirmed. Need any other help?"
                
                return response, "otp_provided", collected_info, {}
            else:
                if response_language == 'hi':
                    response = "कोई बात नहीं। कृपया सही OTP बताएं।"
                else:
                    response = "No problem. Please tell me the correct OTP."
                return response, "manual_otp_entry", collected_info, {}
        
        return "I can help you get an OTP. Which company is this for?", "asking_otp_company", collected_info, {}
    
    def _handle_non_sms_otp_logic(self, message: str, stage: str, collected_info: Dict[str, Any], response_language: str, call_sid: str, conversation_history: list) -> Dict[str, Any]:
        """Handle OTP logic that doesn't require SMS data"""
        
        # Handle responses to our questions  
        if stage == "asking_otp_company":
            # Extract company from user response
            from ..utils.text_processing import extract_company_from_text
            company = extract_company_from_text(message) or message.strip().title()
            collected_info["company"] = company
            
            # Now request SMS data with the company info
            if response_language == 'hi':
                waiting_message = f"धन्यवाद! अब मैं {company} का OTP खोज रहा हूँ।"
            else:
                waiting_message = f"Thank you! Now I'll look for the {company} OTP."
            
            return {
                "response_text": waiting_message,
                "requires_sms": True,
                "call_sid": call_sid,
                "conversation_stage": "checking_sms",
                "intent": "fetch_otp",
                "company_requested": company,
                "updated_history": conversation_history + [
                    {"role": "user", "content": message},
                    {"role": "assistant", "content": waiting_message}
                ],
                "collected_info": collected_info
            }
        
        # Default response
        response_text = "मैं आपकी OTP खोजने में मदद कर सकता हूँ। किस कंपनी का है?" if response_language == 'hi' else "I can help you find an OTP. Which company is it for?"
        
        return {
            "response_text": response_text,
            "requires_sms": False,
            "call_sid": call_sid,
            "conversation_stage": "asking_otp_company",
            "intent": "clarify_company",
            "updated_history": conversation_history + [
                {"role": "user", "content": message},
                {"role": "assistant", "content": response_text}
            ],
            "collected_info": collected_info
        }
    
    def _find_best_otp_match(self, processed_otps: list, company: str) -> dict:
        """Find the best matching OTP from processed SMS data"""
        if not processed_otps:
            return None
        
        company_lower = company.lower() if company else ""
        best_match = None
        best_score = 0
        
        for otp_data in processed_otps:
            if not otp_data.get("otp"):
                continue
                
            score = 0
            
            # Direct company match
            detected_company = otp_data.get("company", "").lower()
            if detected_company and company_lower in detected_company:
                score += 50
            elif company_lower in detected_company:
                score += 30
            
            # Sender match
            sender = otp_data.get("sender", "").lower()
            if company_lower in sender:
                score += 40
            
            # Message content match
            message = otp_data.get("message", "").lower()
            if company_lower in message:
                score += 20
            
            # Confidence score
            confidence = otp_data.get("confidence", 0)
            score += confidence * 10
            
            # Recency bonus (assuming first in list is most recent)
            if otp_data == processed_otps[0]:
                score += 5
            
            if score > best_score:
                best_match = otp_data
                best_score = score
        
        return best_match
    
    def _detect_company_from_sender(self, sender: str) -> str:
        """Detect company from SMS sender"""
        if not sender:
            return "unknown"
        
        sender_lower = sender.lower()
        
        # Common sender patterns
        company_mapping = {
            "zomato": ["zomato", "zmt", "zm-"],
            "swiggy": ["swiggy", "swg", "sg-"],
            "amazon": ["amazon", "amzn", "az-"],
            "flipkart": ["flipkart", "fkrt", "fk-"],
            "bigbasket": ["bigbasket", "bb-", "bigb"],
            "dunzo": ["dunzo", "dz-"],
        }
        
        for company, patterns in company_mapping.items():
            if any(pattern in sender_lower for pattern in patterns):
                return company
        
        return "unknown"
    
    def handle_unknown_logic(self, message: str, stage: str, collected_info: Dict[str, Any], caller_id=None, response_language: str = "en") -> Tuple[str, str, Dict[str, Any], Dict[str, Any]]:
        """Handle conversation flow for unknown callers (matches original.py)"""
        templates = get_response_templates(response_language)
        
        if any(k in message.lower() for k in ['urgent', 'asap', 'emergency', 'जरूरी', 'तुरंत']):
            name_to_use = collected_info.get("name", "एक अज्ञात कॉलर" if response_language == 'hi' else "An unknown caller")
            response_text = templates.get('urgent_matter', "यह जरूरी लग रहा है। मैं तुरंत मालिक को सूचित करूंगा।" if response_language == 'hi' else "Okay, I understand this is urgent. I am notifying Ruchit immediately.")
            
            # Send urgent notification
            urgent_message = f"Urgent call from {name_to_use}."
            self.notification_service.send_urgent_notification(urgent_message)
            
            action = {"type": "URGENT_NOTIFICATION", "message": urgent_message}
            return response_text, "end_of_call", collected_info, action

        intent = detect_user_intent(message)
        action = {}

        if stage == "start":
            return templates['collect_name'], "asking_name", collected_info, action

        if stage == "collecting_contact" and intent == "provide_self_number":
            collected_info['phone'] = caller_id or "Caller's Number"
            
            # Send notification to owner about the unknown caller
            self.notification_service.send_unknown_caller_notification(collected_info)
            
            return "Okay, noted. Ruchit will call you back on the number you are calling from. Thank you!", "end_of_call", collected_info, action

        extracted_info = self.extract_information_with_ai(message, collected_info)
        collected_info.update(extracted_info)

        if stage == "asking_name":
            if collected_info.get("name"):
                name = collected_info['name']
                return f"Hi {name}! And what is the reason for your call?", "asking_purpose", collected_info, action
            else:
                # Try one more time with current message before giving up
                if len(message.strip()) > 0:
                    # If the message looks like it could be a name (not too long, has letters)
                    potential_name = message.strip()
                    if (len(potential_name) <= 20 and 
                        any(c.isalpha() for c in potential_name) and
                        potential_name.lower() not in ['yes', 'no', 'hello', 'hi']):
                        # Accept it as a name
                        collected_info["name"] = potential_name.title()
                        return f"Hi {potential_name.title()}! And what is the reason for your call?", "asking_purpose", collected_info, action
                
                return "I'm sorry, I didn't catch your name. Could you please spell it out?", "asking_name", collected_info, action

        if stage == "asking_purpose":
            if not collected_info.get("purpose"):
                collected_info["purpose"] = message
            
            # Use AI to determine if we need follow-up questions and what to ask
            if not collected_info.get("followup_asked"):
                ai_followup = self._get_ai_followup_questions(message, collected_info)
                
                if ai_followup.get("needs_followup"):
                    collected_info["followup_asked"] = True
                    collected_info["ai_followup_plan"] = ai_followup
                    return ai_followup["first_question"], "asking_followup", collected_info, action
            
            # Continue with normal flow if no followup needed or already asked
            if not collected_info.get("phone"):
                return "Got it. What's the best number for Ruchit to call you back on?", "collecting_contact", collected_info, action
            else:
                phone_for_speech = format_number_for_speech(collected_info['phone'])
                
                # Send notification to owner
                self.notification_service.send_unknown_caller_notification(collected_info)
                
                return f"Perfect, I have your number as {phone_for_speech}. I'll make sure Ruchit gets all this information and calls you back. Have a great day!", "end_of_call", collected_info, action

        # New stage for handling follow-up questions
        if stage == "asking_followup":
            # Store the additional information
            if not collected_info.get("additional_details"):
                collected_info["additional_details"] = []
            collected_info["additional_details"].append(message)
            
            # Use AI to determine if we need a second question
            followup_plan = collected_info.get("ai_followup_plan", {})
            followup_count = len(collected_info.get("additional_details", []))
            
            if followup_count == 1 and followup_plan.get("second_question"):
                return followup_plan["second_question"], "asking_second_followup", collected_info, action
            else:
                # Move to collecting contact info
                if not collected_info.get("phone"):
                    return "Thank you for those details. What's the best number for Ruchit to call you back on?", "collecting_contact", collected_info, action
                else:
                    phone_for_speech = format_number_for_speech(collected_info['phone'])
                    
                    # Send notification to owner
                    self.notification_service.send_unknown_caller_notification(collected_info)
                    
                    return f"Perfect, I have your number as {phone_for_speech}. I'll make sure Ruchit gets all this information and calls you back. Have a great day!", "end_of_call", collected_info, action

        # Handle second follow-up question
        if stage == "asking_second_followup":
            if not collected_info.get("additional_details"):
                collected_info["additional_details"] = []
            collected_info["additional_details"].append(message)
            
            if not collected_info.get("phone"):
                return "Excellent, thank you for all that information. What's the best number for Ruchit to call you back on?", "collecting_contact", collected_info, action
            else:
                phone_for_speech = format_number_for_speech(collected_info['phone'])
                
                # Send notification to owner
                self.notification_service.send_unknown_caller_notification(collected_info)
                
                return f"Perfect, I have your number as {phone_for_speech}. I'll make sure Ruchit gets all this detailed information and calls you back soon. Have a great day!", "end_of_call", collected_info, action

        if stage == "collecting_contact":
            if collected_info.get("phone"):
                phone_for_speech = format_number_for_speech(collected_info['phone'])
                
                # Send notification to owner
                self.notification_service.send_unknown_caller_notification(collected_info)
                
                return f"Great, I have your number as {phone_for_speech}. I'll make sure Ruchit gets all this information and calls you back. Thank you for calling, and have a wonderful day!", "end_of_call", collected_info, action
            else:
                return "I didn't quite catch that. Could you please provide a callback number?", "collecting_contact", collected_info, action

        # Final fallback - send notification anyway if we have some info
        if collected_info.get("name") or collected_info.get("purpose"):
            self.notification_service.send_unknown_caller_notification(collected_info)

        return "Thank you for calling. I'll make sure Ruchit gets your message. Have a great day!", "end_of_call", collected_info, action
    
    def extract_information_with_ai(self, message: str, collected_info: Dict[str, Any]) -> Dict[str, Any]:
        """Extract information using AI service"""
        # Use the real OpenAI service's extraction method
        if hasattr(self.openai_service, 'extract_information_with_ai'):
            return self.openai_service.extract_information_with_ai(message, collected_info)
        
        # Fallback to simple extraction
        extracted = {}
        message_lower = message.lower()
        
        # Extract company names
        companies = ['amazon', 'flipkart', 'swiggy', 'zomato', 'dunzo', 'zepto', 'bluedart']
        for company in companies:
            if company in message_lower:
                extracted["company"] = company.title()
                break
        
        # Extract phone numbers
        from ..utils.text_processing import extract_phone_number
        phone = extract_phone_number(message)
        if phone:
            extracted["phone"] = phone
        
        return extracted
    
    def _get_ai_followup_questions(self, purpose_message: str, collected_info: Dict[str, Any]) -> Dict[str, Any]:
        """Use AI to determine if follow-up questions are needed and what to ask"""
        caller_name = collected_info.get("name", "the caller")
        
        # Use real OpenAI service if available
        if hasattr(self.openai_service, 'client') and self.openai_service.client:
            try:
                prompt = f"""
You are an AI assistant helping to screen calls for Ruchit Gupta. A caller named {caller_name} said their reason for calling is: "{purpose_message}"

Your job is to determine if this call requires follow-up questions to gather important information that would help Ruchit prioritize and prepare for the callback.

Analyze the purpose and respond with JSON in this format:
{{
    "needs_followup": true/false,
    "importance_level": "high/medium/low",
    "first_question": "What specific question should I ask first?",
    "second_question": "What should I ask as a follow-up?" or null,
    "reasoning": "Why these questions are important"
}}

Guidelines:
- Ask follow-up questions for: business opportunities, investments, partnerships, sponsorships, collaborations, job opportunities, media requests, or anything that seems professionally important
- DON'T ask follow-ups for: simple inquiries, personal calls, complaints, or basic questions
- Focus on questions that would help Ruchit understand the opportunity, urgency, scale, or timeline
- Keep questions natural and conversational
- Maximum 2 follow-up questions

Examples of good follow-up questions:
- For sponsorship: "What type of sponsorship opportunity is this?" then "What's the budget range or scale you're considering?"
- For business: "What kind of business opportunity are you proposing?" then "What timeline are you working with?"
- For investment: "What type of investment are you looking to discuss?" then "What stage is your company/project at?"
"""

                response = self.openai_service.client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=300
                )
                
                import json
                ai_response = json.loads(response.choices[0].message.content)
                return ai_response
                
            except Exception as e:
                print(f"⚠️ AI followup generation failed: {e}")
                # Fall back to rule-based system
        
        # Fallback rule-based system (existing logic)
        return self._get_rule_based_followup(purpose_message)
    
    def _get_rule_based_followup(self, purpose_message: str) -> Dict[str, Any]:
        """Fallback rule-based follow-up question generation"""
        purpose_lower = purpose_message.lower()
        
        # Determine if we need follow-up questions
        business_keywords = [
            'sponsorship', 'business', 'collaboration', 'partnership', 
            'investment', 'project', 'proposal', 'meeting', 'interview',
            'opportunity', 'deal', 'funding', 'venture', 'startup',
            'media', 'press', 'journalist', 'article', 'feature'
        ]
        
        needs_followup = any(keyword in purpose_lower for keyword in business_keywords)
        
        if not needs_followup:
            return {
                "needs_followup": False,
                "importance_level": "low",
                "reasoning": "Simple inquiry that doesn't require detailed follow-up"
            }
        
        # Generate specific questions based on keywords
        if 'sponsorship' in purpose_lower:
            return {
                "needs_followup": True,
                "importance_level": "high",
                "first_question": "I see you're interested in sponsorship. What type of sponsorship opportunity are you proposing?",
                "second_question": "And what's the scale or budget range you're considering?",
                "reasoning": "Sponsorship requires understanding of type and scale for proper evaluation"
            }
        elif any(word in purpose_lower for word in ['investment', 'funding', 'venture']):
            return {
                "needs_followup": True,
                "importance_level": "high",
                "first_question": "I understand this is about investment. What kind of investment opportunity are you proposing?",
                "second_question": "What stage is your company or project currently at?",
                "reasoning": "Investment opportunities need clarity on type and maturity stage"
            }
        elif any(word in purpose_lower for word in ['business', 'collaboration', 'partnership']):
            return {
                "needs_followup": True,
                "importance_level": "medium",
                "first_question": "That sounds interesting! Can you tell me more about the nature of this business opportunity?",
                "second_question": "What timeline are you looking at for this collaboration?",
                "reasoning": "Business opportunities need scope and timeline clarification"
            }
        elif any(word in purpose_lower for word in ['media', 'press', 'journalist', 'article']):
            return {
                "needs_followup": True,
                "importance_level": "medium",
                "first_question": "I see this is a media inquiry. What publication or outlet are you with?",
                "second_question": "What's the focus or angle of the story you're working on?",
                "reasoning": "Media requests need publication details and story context"
            }
        else:
            return {
                "needs_followup": True,
                "importance_level": "medium",
                "first_question": "That sounds important! Could you provide a bit more detail about what you'd like to discuss?",
                "second_question": "What would be the best time frame for Ruchit to get back to you on this?",
                "reasoning": "Professional inquiry needs more context and timing"
            }
    
    def generate_conversation_summary(self, conversation_history: list, collected_info: Dict[str, Any] = None) -> str:
        """Generate a conversation summary (mock implementation)"""
        if not conversation_history:
            return "No conversation to summarize"
        
        # Simple summary based on the conversation flow
        company = collected_info.get("company") if collected_info else None
        stage = collected_info.get("stage") if collected_info else None
        
        if company:
            return f"Delivery person from {company} called for assistance. Provided directions and OTP as needed. Call completed successfully."
        else:
            return f"Unknown caller contacted for assistance. Collected contact information and forwarded to Ruchit. Call completed successfully."