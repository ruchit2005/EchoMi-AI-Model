"""Conversation handler matching original.py flow exactly"""

import uuid
from typing import Dict, Any, Tuple, Optional
from ..utils.text_processing import detect_user_intent, format_otp_for_speech, format_number_for_speech
from .service_factory import ServiceFactory

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
    
    def handle_delivery_logic(self, message: str, stage: str, collected_info: Dict[str, Any], caller_id=None) -> Tuple[str, str, Dict[str, Any], Dict[str, Any]]:
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
        
        print(f"\n--- [DELIVERY LOGIC] START ---")
        print(f"--- [DELIVERY LOGIC] Stage: {stage}, Intent: {intent} ---")
        print(f"--- [DELIVERY LOGIC] Message: '{message}' ---")
        print(f"--- [DELIVERY LOGIC] Current collected_info: {collected_info} ---")
        
        # Handle OTP requests at any stage
        if intent == "requesting_otp":
            return self.handle_otp_request_logic(message, stage, collected_info)
        
        # Check if we're in an OTP-specific flow
        if stage in ["asking_otp_company", "asking_order_id", "providing_otp", "otp_provided"]:
            return self.handle_otp_request_logic(message, stage, collected_info)
        
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
                    return f"Hi! I see you have a delivery from {company}. Do you need help getting here, or are you already here?", "asking_location_help", collected_info, action
                else:
                    # Ask for company first
                    return "Hi! I can help with your delivery. Which company is this delivery from?", "asking_company_first", collected_info, action
            else:
                # Generic greeting
                return "Hi! How may I assist you today?", "initial_greeting", collected_info, action
        
        # Stage 2: After initial greeting, waiting for delivery mention
        if stage == "initial_greeting":
            if intent == "initial_delivery" or any(k in message.lower() for k in ["delivery", "parcel", "package"]):
                extracted_info = self.extract_information_with_ai(message, collected_info)
                collected_info.update(extracted_info)
                company = collected_info.get("company")
                
                if company:
                    return f"I see you have a delivery from {company}. Do you need help getting here, or are you already here?", "asking_location_help", collected_info, action
                else:
                    return "I can help with your delivery. Which company is this from?", "asking_company_first", collected_info, action
            else:
                # Not a delivery call, handle as unknown caller
                return self.handle_unknown_logic(message, "start", collected_info, caller_id)
        
        # Stage 3: Asked for company name first
        if stage == "asking_company_first":
            extracted_info = self.extract_information_with_ai(message, collected_info)
            company = extracted_info.get("company") or message.strip().title()
            collected_info["company"] = company
            
            return f"Thank you! So you have a delivery from {company}. Do you need help getting here, or are you already here?", "asking_location_help", collected_info, action
        
        # Stage 4: Asking if they need location help
        if stage == "asking_location_help":
            print("--- [DELIVERY LOGIC] Processing location help response ---")
            
            # Check their response
            message_lower = message.lower().strip()
            
            # They need help with directions
            if any(phrase in message_lower for phrase in ["need help", "help", "directions", "how to get", "where is", "guide me", "lost"]):
                return "I'd be happy to help guide you here. What's your current location or a nearby landmark?", "getting_current_location", collected_info, action
            
            # They're already here / at location
            elif any(phrase in message_lower for phrase in ["here", "arrived", "at the location", "reached", "outside", "at your place", "at the door"]):
                print("--- [DELIVERY LOGIC] Caller says they're here, checking for OTP need ---")
                return self.handle_arrival_and_otp_check(collected_info)
            
            # Ambiguous response, clarify
            else:
                return "Are you asking for directions to get here, or have you already arrived at the location?", "asking_location_help", collected_info, action
        
        # Stage 5: Getting their current location for directions
        if stage == "getting_current_location":
            print("--- [DELIVERY LOGIC] Processing current location for directions ---")
            
            # Try to geocode their location
            geocode_results = self.maps_service.geocode_location(message)
            
            if geocode_results and len(geocode_results) > 0:
                best_result = geocode_results[0]
                collected_info['current_location'] = best_result
                
                # Get directions and ETA
                directions_result = self.maps_service.get_directions_to_customer(
                    current_location=best_result,
                    customer_address="123 Main St, Bangalore"  # Mock customer address
                )
                
                if directions_result.get("directions"):
                    response_parts = [
                        f"I found your location: {best_result['place_name']}.",
                        f"Here are the directions: {directions_result['directions']}"
                    ]
                    
                    if directions_result.get("eta"):
                        response_parts.append(directions_result["eta"])
                    
                    response_parts.append("Let me know when you arrive!")
                    
                    response_text = " ".join(response_parts)
                    return response_text, "traveling_to_location", collected_info, action
                else:
                    return f"I found your location: {best_result['place_name']}, but I couldn't get detailed directions. Please use your GPS to navigate to the delivery address. Let me know when you arrive!", "traveling_to_location", collected_info, action
            else:
                return "I couldn't find that location. Could you try a more specific address or nearby landmark?", "getting_current_location", collected_info, action
        
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
    
    def handle_arrival_and_otp_check(self, collected_info: Dict[str, Any]) -> Tuple[str, str, Dict[str, Any], Dict[str, Any]]:
        """Handle when delivery person arrives and check if they need OTP"""
        print("--- [DELIVERY LOGIC] Handling arrival and OTP check ---")
        
        company = collected_info.get("company")
        if not company:
            return "Great! You're here. Which company is this delivery from?", "asking_company_for_otp", {}, {}
        
        # Check if we have a pending order for this company
        pending_order = None
        order_id = None
        
        for oid, order_data in self.order_wallet.items():
            if (order_data.get("company", "").lower() == company.lower() and 
                order_data.get("status") == "pending"):
                pending_order = order_data
                order_id = oid
                break
        
        if not pending_order:
            # Create a mock order for testing
            order_id = str(uuid.uuid4())
            self.order_wallet[order_id] = {
                "company": company,
                "status": "approved",  # Auto-approve for demo
                "otp": "123456"  # Mock OTP
            }
        
        # Store order ID
        collected_info['order_id'] = order_id
        
        # Ask if they need OTP
        return f"Excellent! You've reached the location with your {company} delivery. Do you need the OTP?", "asking_if_otp_needed", collected_info, {}
    
    def handle_existing_delivery_logic(self, message: str, stage: str, collected_info: Dict[str, Any], intent: str, action: Dict[str, Any]) -> Tuple[str, str, Dict[str, Any], Dict[str, Any]]:
        """Handle the existing delivery logic for OTP verification (matches original.py)"""
        
        # Stage: Asking if they need OTP
        if stage == "asking_if_otp_needed":
            message_lower = message.lower().strip()
            
            if any(phrase in message_lower for phrase in ["yes", "yeah", "yep", "need", "otp", "code"]):
                # They need OTP, proceed with verification
                company = collected_info.get("company")
                order_id = collected_info.get("order_id")
                order = self.order_wallet.get(order_id) if order_id else None
                
                if order and order.get("tracking_id"):
                    return f"I have the order ready. Do you have the tracking ID for the {company} delivery?", "checking_tracking_availability", collected_info, action
                else:
                    # For demo, directly provide OTP
                    firebase_uid = collected_info.get('firebaseUid', 'demo-user')
                    otp_result = self.otp_service.fetch_otp(firebase_uid, company, order_id)
                    
                    if otp_result["success"]:
                        formatted_otp = format_otp_for_speech(otp_result["otp"])
                        response_text = f"Here's your OTP for {company}: {formatted_otp}"
                        
                        # Mark order as completed
                        if order_id in self.order_wallet:
                            self.order_wallet[order_id]["status"] = "completed"
                        
                        return response_text, "end_of_call", collected_info, action
                    else:
                        return f"Sorry, I couldn't retrieve the OTP. {otp_result.get('error', 'Please try again.')}", "otp_error", collected_info, action
            
            elif any(phrase in message_lower for phrase in ["no", "nope", "don't need", "not needed"]):
                return "Alright! Have a great day and safe delivery!", "end_of_call", collected_info, action
            else:
                return "Do you need me to provide the OTP for this delivery? Please say yes or no.", "asking_if_otp_needed", collected_info, action
        
        # Stage: Asked for company name for OTP
        if stage == "asking_company_for_otp":
            extracted_info = self.extract_information_with_ai(message, collected_info)
            company = extracted_info.get("company") or message.strip().title()
            collected_info["company"] = company
            
            return self.handle_arrival_and_otp_check(collected_info)
        
        # Handle conversation ending
        if intent == "ending_conversation":
            return "You're welcome! Have a safe delivery!", "end_of_call", collected_info, action
        
        # Fallback
        return "I'm here to help with your delivery. What can I assist you with?", stage, collected_info, action
    
    def handle_otp_request_logic(self, message: str, stage: str, collected_info: Dict[str, Any]) -> Tuple[str, str, Dict[str, Any], Dict[str, Any]]:
        """Handle OTP requests integrated with existing delivery logic (matches original.py)"""
        intent = detect_user_intent(message)
        action = {}
        
        print(f"🔐 [OTP LOGIC] Stage: {stage}, Intent: {intent}")
        print(f"🔐 [OTP LOGIC] Collected info: {collected_info}")
        
        # If user is asking for OTP
        if intent == "requesting_otp" or stage == "providing_otp":
            firebase_uid = collected_info.get('firebaseUid', 'demo-user')
            company = collected_info.get('company')
            order_id = collected_info.get('order_id')
            
            if not company:
                return "Which company is this OTP request for?", "asking_otp_company", collected_info, action
                
            if not order_id:
                # Create a demo order
                order_id = str(uuid.uuid4())
                self.order_wallet[order_id] = {
                    "company": company,
                    "status": "approved",
                    "otp": "123456"
                }
                collected_info['order_id'] = order_id
            
            # Fetch OTP
            otp_result = self.otp_service.fetch_otp(firebase_uid, company, order_id)
            
            if otp_result["success"]:
                formatted_otp = format_otp_for_speech(otp_result["otp"])
                response_text = f"Here's your OTP for {company}: {formatted_otp}"
                
                # Mark order as completed
                if order_id in self.order_wallet:
                    self.order_wallet[order_id]["status"] = "completed"
                
                return response_text, "otp_provided", collected_info, action
            else:
                error_msg = otp_result.get("error", "Unknown error")
                return f"Sorry, I couldn't retrieve the OTP. {error_msg}", "otp_error", collected_info, action
        
        # Handle responses to our questions
        if stage == "asking_otp_company":
            extracted_info = self.extract_information_with_ai(message, collected_info)
            company = extracted_info.get("company") or message.strip().title()
            collected_info["company"] = company
            
            # Try again with the company info
            return self.handle_otp_request_logic("get otp", "providing_otp", collected_info)
        
        return "I can help you get an OTP. Which company is this for?", "asking_otp_company", collected_info, action
    
    def handle_unknown_logic(self, message: str, stage: str, collected_info: Dict[str, Any], caller_id=None) -> Tuple[str, str, Dict[str, Any], Dict[str, Any]]:
        """Handle conversation flow for unknown callers (matches original.py)"""
        if any(k in message.lower() for k in ['urgent', 'asap', 'emergency']):
            name_to_use = collected_info.get("name", "An unknown caller")
            response_text = "Okay, I understand this is urgent. I am notifying Ruchit immediately."
            
            # Send urgent notification
            urgent_message = f"Urgent call from {name_to_use}."
            self.notification_service.send_urgent_notification(urgent_message)
            
            action = {"type": "URGENT_NOTIFICATION", "message": urgent_message}
            return response_text, "end_of_call", collected_info, action

        intent = detect_user_intent(message)
        action = {}

        if stage == "start":
            return "May I know who's calling?", "asking_name", collected_info, action

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
        """Extract information using AI (enhanced implementation to handle mixed languages)"""
        extracted = {}
        
        message_lower = message.lower()
        
        # Extract company names
        companies = ['amazon', 'flipkart', 'swiggy', 'zomato', 'dunzo', 'zepto', 'bluedart']
        for company in companies:
            if company in message_lower:
                extracted["company"] = company.title()
                break
        
        # Enhanced name extraction with better patterns
        name_patterns = [
            # Direct patterns
            r"my name is\s+([a-zA-Z\s]+)",
            r"i am\s+([a-zA-Z\s]+)", 
            r"this is\s+([a-zA-Z\s]+)",
            r"i'm\s+([a-zA-Z\s]+)",
            # Spelled out patterns
            r"([a-z]\s+[a-z]\s+[a-z]\s+[a-z]\s+[a-z])",  # r u d r a
            r"([a-z]\s+[a-z]\s+[a-z]\s+[a-z])",  # r u d r  
            r"([a-z]\s+[a-z]\s+[a-z])",  # a b c
            # Mixed language patterns
            r"name is\s+([^\s,]+)",  # Captures non-English names
            r"is\s+([^\s,\.]+)",  # Generic capture after "is"
        ]
        
        import re
        for pattern in name_patterns:
            match = re.search(pattern, message_lower)
            if match:
                potential_name = match.group(1).strip()
                
                # Clean up spelled out names (r u d r a -> rudra)
                if ' ' in potential_name and len(potential_name.split()) > 2:
                    # Check if it's spelled out (single letters with spaces)
                    parts = potential_name.split()
                    if all(len(part) == 1 and part.isalpha() for part in parts):
                        potential_name = ''.join(parts)
                
                # Filter out common words and very short/long names
                if (potential_name and 
                    len(potential_name) > 1 and 
                    len(potential_name) < 20 and
                    potential_name not in ['calling', 'talking', 'speaking', 'here', 'you', 'me']):
                    extracted["name"] = potential_name.title()
                    break
        
        # If still no name found, try to extract from non-English text
        if not extracted.get("name"):
            # Look for patterns like "रूद्रा" or similar
            words = message.split()
            for word in words:
                # Skip common English words
                if (word not in ['my', 'name', 'is', 'this', 'i', 'am', 'the', 'a', 'an'] and
                    len(word) > 1 and len(word) < 15):
                    # Could be a name in another language
                    extracted["name"] = word.strip('.,!?').title()
                    break
        
        # Extract phone numbers using the improved utility function
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