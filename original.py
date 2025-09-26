from openai import OpenAI
import os
import requests
from dotenv import load_dotenv
from flask import Flask, request, jsonify
import json
import re
from datetime import datetime
from functools import wraps
import time
from geopy.distance import geodesic

app = Flask(__name__)
load_dotenv()

BASE_URL = os.getenv("BASE_URL", "http://localhost:5000")

# --- CONFIGURATION ---
USER_LOCATION = {
    "lat": float(os.getenv("USER_LAT", 12.912445713301228)),
    "lng": float(os.getenv("USER_LNG", 77.6359444711491))
}
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
APP_SECRET_KEY = os.getenv("APP_SECRET_KEY")
NODEJS_BACKEND_URL = os.getenv("NODEJS_BACKEND_URL", "http://localhost:3000")
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY")
OWNER_PHONE_NUMBER = os.getenv("OWNER_PHONE_NUMBER")

print(f"✅ Loaded APP_SECRET_KEY: '{APP_SECRET_KEY}'")
print(f"✅ Node.js Backend URL: {NODEJS_BACKEND_URL}")
print(f"✅ Internal API Key configured: {'Yes' if INTERNAL_API_KEY else 'No'}")

# --- SECURE ORDER WALLET ---
# The key is a unique order_id. The value is a dictionary of order details.
ORDER_WALLET = {}

# --- OPENAI CLIENT ---
try:
    openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    print("✅ OpenAI Client initialized successfully.")
except Exception as e:
    print(f"❌ Error initializing OpenAI Client: {e}")
    openai_client = None
    exit(1)

# --- HELPER FUNCTIONS ---

def send_push_notification(phone_number: str, message: str, approval_token: str):
    """Send push notification to Android app via Node.js backend"""
    try:
        notification_endpoint = f"{NODEJS_BACKEND_URL}/api/send-notification"
        
        payload = {
            "user_phone": phone_number,
            "title": "Delivery Verification Required",
            "message": message,
            "type": "delivery_approval",
            "approval_token": approval_token,
            "action_required": True,
            "timestamp": int(time.time())
        }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {INTERNAL_API_KEY}",
            "User-Agent": "DeliveryBot/1.0"
        }
        
        print(f"📱 [NOTIFICATION] Sending to Node.js: {notification_endpoint}")
        print(f"📱 [NOTIFICATION] Payload: {payload}")
        
        response = requests.post(
            notification_endpoint, 
            json=payload, 
            headers=headers, 
            timeout=15
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ [NOTIFICATION] Push notification sent successfully: {result}")
            return True
        else:
            print(f"❌ [NOTIFICATION] Failed: {response.status_code} - {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print("❌ [NOTIFICATION] Timeout connecting to Node.js backend")
        return False
    except requests.exceptions.ConnectionError:
        print("❌ [NOTIFICATION] Cannot connect to Node.js backend")
        return False
    except Exception as e:
        print(f"❌ [NOTIFICATION] Unexpected error: {e}")
        return False

def fetch_otp_from_backend(firebase_uid: str, sender: str, order_id: str):
    """
    Fetch OTP from Node.js backend for delivery verification
    
    Args:
        firebase_uid: User's Firebase UID
        sender: Company/service name (e.g., "Amazon", "Flipkart")
        order_id: Delivery order ID
    
    Returns:
        dict: OTP response or error
    """
    try:
        otp_endpoint = f"{NODEJS_BACKEND_URL}/api/delivery/otp/{firebase_uid}"
        
        params = {
            "sender": sender,
            "orderId": order_id
        }
        
        headers = {
            "Authorization": f"Bearer {INTERNAL_API_KEY}",
            "User-Agent": "DeliveryBot/1.0"
        }
        
        print(f"📱 [OTP] Fetching from: {otp_endpoint}")
        print(f"📱 [OTP] Params: {params}")
        
        response = requests.get(
            otp_endpoint, 
            params=params,
            headers=headers, 
            timeout=10
        )
        
        if response.status_code == 200:
            otp_data = response.json()
            print(f"✅ [OTP] Retrieved successfully: {otp_data}")
            return {
                "success": True,
                "otp": otp_data.get("otp"),
                "message": otp_data.get("message", "OTP retrieved successfully")
            }
        elif response.status_code == 404:
            print(f"❌ [OTP] No OTP found for the given parameters")
            return {
                "success": False,
                "error": "No OTP found for this delivery"
            }
        else:
            print(f"❌ [OTP] Backend error: {response.status_code} - {response.text}")
            return {
                "success": False,
                "error": f"Backend error: {response.status_code}"
            }
            
    except requests.exceptions.Timeout:
        print("❌ [OTP] Timeout connecting to Node.js backend")
        return {
            "success": False,
            "error": "Request timeout"
        }
    except requests.exceptions.ConnectionError:
        print("❌ [OTP] Cannot connect to Node.js backend")
        return {
            "success": False,
            "error": "Backend connection failed"
        }
    except Exception as e:
        print(f"❌ [OTP] Unexpected error: {e}")
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}"
        }

def format_otp_for_speech(otp: str) -> str:
    """
    Format OTP for clear speech synthesis
    
    Args:
        otp: The OTP string (e.g., "123456")
    
    Returns:
        str: Formatted OTP for speech (e.g., "1 2 3 4 5 6")
    """
    if not otp:
        return ""
    
    # Remove any non-digit characters
    clean_otp = re.sub(r'\D', '', str(otp))
    
    # Add spaces between digits for clear pronunciation
    return " ".join(clean_otp)

def clean_location_text(raw_text: str) -> str:
    """Removes filler words from a spoken location for better geocoding."""
    cleaned = raw_text.lower()
    cleaned = re.sub(r"^(i(\s*am|'m)?\s*(here\s*)?(in|at|near)\s+)", "", cleaned)
    return cleaned.strip().title()

def format_phone_number(number_string: str):
    if not isinstance(number_string, str): return None
    digits = re.sub(r'\D', '', number_string)
    if len(digits) == 10: return f"+91{digits}"
    if len(digits) == 12 and digits.startswith('91'): return f"+{digits}"
    return digits if digits else None

def format_number_for_speech(number_string: str):
    if not number_string: return ""
    return " ".join([ch for ch in number_string if ch.isdigit()])

def detect_user_intent(message: str):
    """Enhanced intent detection with better OTP recognition"""
    message_lower = message.lower().strip()
    message_cleaned = re.sub(r'[.!?]', '', message_lower)
    
    # Enhanced OTP detection patterns
    otp_patterns = [
        'otp', 'one time password', 'code', 'verification code', 
        'pin', 'security code', 'auth code', 'login code',
        'give me the code', 'what is the code', 'tell me the otp',
        'need the otp', 'share the otp', 'provide otp'
    ]
    
    if any(pattern in message_lower for pattern in otp_patterns):
        return "requesting_otp"
    
    # Check for company + OTP context
    company_keywords = ['amazon', 'flipkart', 'myntra', 'zomato', 'swiggy', 'delivery','zepto','bluedart']
    if (any(company in message_lower for company in company_keywords) and 
        any(otp in message_lower for otp in ['code', 'otp', 'pin'])):
        return "requesting_otp"
    
    # Rest of existing intent detection logic
    if any(k in message_lower for k in ["road", "nagar", "colony", "market", "station", "gate", "circle", "apartment", "complex", "mall", "near", "opposite", "metro", "bus stop"]): 
        return "providing_location"
    if any(k in message_lower for k in ["delivery", "parcel", "package", "amazon", "flipkart","swiggy", "zomato","zepto"]): 
        return "initial_delivery"
    if any(k in message_lower for k in ["it's fine", "it's ok", 'ask him to call', 'just call me back']): 
        return "non_urgent_callback"
    if any(k in message_lower for k in ['same number', 'this number', "number i'm calling from"]): 
        return "provide_self_number"
    if any(k in message_lower for k in ['call back', 'callback', 'call me back']): 
        return "requesting_callback"
    if message_cleaned in ['yes', 'yeah', 'yep', 'ok', 'okay', 'sure', 'correct']: 
        return "general_yes"
    if message_cleaned in ['no', 'nope', 'not really']: 
        return "declining"
    if any(k in message_lower for k in ['thank', 'bye', 'thanks']): 
        return "ending_conversation"
    
    return "general"

def extract_information_with_openai(message, collected_info):
    """Enhanced information extraction with better prompting for delivery companies."""
    if not openai_client: 
        return {}
    
    print("--- [INFO EXTRACTION] Attempting to extract info ---")
    print(f"--- [INFO EXTRACTION] Message: '{message}' ---")
    
    try:
        system_prompt = """You are an expert information extraction assistant for phone calls. 

Extract these fields from the user's message:
- "name": Person's name (if mentioned)
- "purpose": Reason for calling (if mentioned) 
- "phone": Phone number (if mentioned)
- "company": Company name (especially for deliveries - Amazon, Flipkart, Swiggy, Zomato, etc.)

IMPORTANT RULES:
1. For delivery messages like "I have a delivery from Amazon", extract "company": "Amazon"
2. For "delivery" without company, don't extract company
3. Return ONLY a valid JSON object
4. If no information is found, return {}

Examples:
- "I have a delivery from Amazon" → {"company": "Amazon"}
- "delivery for you" → {}
- "This is John from Flipkart" → {"name": "John", "company": "Flipkart"}
"""
        
        user_prompt = f"Current information: {json.dumps(collected_info)}\nUser's message: \"{message}\""
        
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=150
        )
        
        extracted = json.loads(response.choices[0].message.content.strip())
        print(f"✅ [INFO EXTRACTION] Extracted: {extracted}")
        
        if extracted.get("phone"):
            formatted = format_phone_number(extracted["phone"])
            if formatted: 
                extracted["phone"] = formatted
            else: 
                del extracted["phone"]
        
        if extracted.get("company"):
            extracted["company"] = extracted["company"].strip().title()
            
        return extracted
        
    except Exception as e:
        print(f"❌ [INFO EXTRACTION ERROR] {e}")
        return {}

def handle_otp_request_logic(message: str, stage: str, collected_info: dict):
    """
    Handle OTP requests integrated with existing delivery logic
    
    Args:
        message: User's message
        stage: Current conversation stage
        collected_info: Information collected so far (including firebaseUid)
    
    Returns:
        tuple: (response_text, new_stage, updated_info, action)
    """
    intent = detect_user_intent(message)
    action = {}
    
    print(f"🔐 [OTP LOGIC] Stage: {stage}, Intent: {intent}")
    print(f"🔐 [OTP LOGIC] Collected info: {collected_info}")
    
    # If user is asking for OTP
    if intent == "requesting_otp" or stage == "providing_otp":
        firebase_uid = collected_info.get('firebaseUid')
        company = collected_info.get('company')
        order_id = collected_info.get('order_id')
        
        if not firebase_uid:
            return "I need to identify you first. Please hold while I get your information.", "need_firebase_uid", collected_info, action
        
        if not company:
            return "Which company is this OTP request for?", "asking_otp_company", collected_info, action
            
        if not order_id:
            # Try to find order_id from ORDER_WALLET based on company
            found_order = None
            for oid, order_data in ORDER_WALLET.items():
                if (order_data.get("company", "").lower() == company.lower() and 
                    order_data.get("status") == "approved"):
                    found_order = oid
                    break
            
            if found_order:
                collected_info['order_id'] = found_order
                order_id = found_order
            else:
                return f"I need the order ID for the {company} delivery. Can you provide it?", "asking_order_id", collected_info, action
        
        # Now we have all required info - fetch OTP
        otp_result = fetch_otp_from_backend(firebase_uid, company, order_id)
        
        if otp_result["success"]:
            formatted_otp = format_otp_for_speech(otp_result["otp"])
            response_text = f"Here's your OTP for {company}: {formatted_otp}"
            
            # Mark order as completed in local wallet
            if order_id in ORDER_WALLET:
                ORDER_WALLET[order_id]["status"] = "completed"
            
            return response_text, "otp_provided", collected_info, action
        else:
            error_msg = otp_result.get("error", "Unknown error")
            return f"Sorry, I couldn't retrieve the OTP. {error_msg}", "otp_error", collected_info, action
    
    # Handle responses to our questions
    if stage == "asking_otp_company":
        extracted_info = extract_information_with_openai(message, collected_info)
        company = extracted_info.get("company") or message.strip().title()
        collected_info["company"] = company
        
        # Try again with the company info
        return handle_otp_request_logic("get otp", "providing_otp", collected_info)
    
    if stage == "asking_order_id":
        # Extract order ID from message
        order_id = message.strip()
        collected_info["order_id"] = order_id
        
        # Try again with order ID
        return handle_otp_request_logic("get otp", "providing_otp", collected_info)
    
    return "I can help you get an OTP. Which company is this for?", "asking_otp_company", collected_info, action

# --- GOOGLE MAPS FUNCTIONS (OPTIMIZED) ---
def enhance_search_query_with_ai(query):
    """Use OpenAI to dynamically enhance search queries with context."""
    if not openai_client:
        return get_fallback_queries(query)
    
    try:
        system_prompt = """You are a search query enhancement expert. Analyze the user's location query and enhance it for better Google Maps search results.

RULES:
1. Recognize brands and expand them (e.g., "Popeyes" → "Popeyes Louisiana Kitchen")
2. Add relevant context (restaurant, hotel, mall, etc.)
3. Include location context "near me" or "Bengaluru" when appropriate
4. Generate 3-4 variations of the query
5. Return ONLY a JSON array of query strings

Examples:
- Input: "popeyes" → Output: ["popeyes louisiana kitchen near me", "popeyes chicken restaurant", "popeyes bengaluru"]
- Input: "hsr layout" → Output: ["hsr layout bengaluru", "hsr layout sector", "hsr layout near me"]
- Input: "metro station" → Output: ["metro station near me", "namma metro station", "bangalore metro station"]
"""

        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Enhance this location query: '{query}'"}
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=150
        )
        
        result = json.loads(response.choices[0].message.content.strip())
        enhanced_queries = result.get("queries", []) if isinstance(result, dict) else result
        
        if query not in enhanced_queries:
            enhanced_queries.append(query)
            
        return enhanced_queries[:4]
        
    except Exception as e:
        print(f"❌ AI query enhancement failed: {e}")
        return get_fallback_queries(query)

def get_fallback_queries(query):
    """Fallback queries if AI enhancement fails."""
    fallback_queries = [
        f"{query} near me",
        f"{query} Bengaluru",
        query,
        f"{query} restaurant" if len(query.split()) < 3 else query
    ]
    return list(dict.fromkeys(fallback_queries))[:4]

def geocode_with_google(address_text, max_distance_km=10):
    """Enhanced geocoding with AI-powered query optimization."""
    cleaned_text = clean_location_text(address_text)
    
    if not cleaned_text or not GOOGLE_MAPS_API_KEY:
        return None
    
    enhanced_queries = enhance_search_query_with_ai(cleaned_text)
    final_results = []
    user_loc = (USER_LOCATION['lat'], USER_LOCATION['lng'])
    
    print(f"🔍 AI-enhanced queries for '{cleaned_text}': {enhanced_queries}")
    
    for query in enhanced_queries:
        try:
            # Try Text Search first
            url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
            params = {
                "query": query,
                "key": GOOGLE_MAPS_API_KEY,
                "location": f"{USER_LOCATION['lat']},{USER_LOCATION['lng']}",
                "radius": max_distance_km * 1000
            }
            
            resp = requests.get(url, params=params, timeout=10).json()
            
            if resp.get("status") != "OK":
                continue
                
            for place in resp.get("results", [])[:5]:  # Limit to top 5 results
                loc = place.get("geometry", {}).get("location")
                if not loc:
                    continue
                
                coords = (loc["lat"], loc["lng"])
                distance = geodesic(coords, user_loc).km
                
                if distance <= max_distance_km:
                    result_data = {
                        "lat": loc["lat"],
                        "lng": loc["lng"],
                        "place_name": place.get("name", "Unknown Place"),
                        "address": place.get("formatted_address") or place.get("vicinity", ""),
                        "distance_from_user": round(distance, 2),
                        "types": place.get("types", []),
                        "query_used": query
                    }
                    
                    # Avoid duplicates
                    if not any(r['place_name'] == result_data['place_name'] for r in final_results):
                        final_results.append(result_data)
            
        except Exception as e:
            print(f"❌ Geocoding error for query '{query}': {e}")
            continue
    
    # Sort by distance
    final_results.sort(key=lambda x: x["distance_from_user"])
    
    print(f"✅ Found {len(final_results)} results for '{cleaned_text}'")
    return final_results if final_results else None

def get_directions_from_google(origin_coords):
    """Get driving directions from origin to user location."""
    if not GOOGLE_MAPS_API_KEY:
        return None
    
    try:
        origin = f"{origin_coords['lat']},{origin_coords['lng']}"
        destination = f"{USER_LOCATION['lat']},{USER_LOCATION['lng']}"
        
        url = "https://maps.googleapis.com/maps/api/directions/json"
        params = {
            "origin": origin,
            "destination": destination,
            "mode": "driving",
            "key": GOOGLE_MAPS_API_KEY
        }
        
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        
        if data.get("status") != "OK" or not data.get("routes"):
            return None
        
        # Extract simplified directions
        route = data["routes"][0]
        legs = route.get("legs", [])
        
        if not legs:
            return None
        
        steps = []
        for step in legs[0].get("steps", [])[:6]:  # First 6 steps
            instr = step.get("html_instructions", "")
            instr_clean = re.sub(r'<.*?>', ' ', instr).strip()
            steps.append(instr_clean)
        
        if steps:
            return ". Then, ".join(steps)
        
        # Fallback: provide straight-line direction
        return f"Head towards the destination from {origin_coords.get('place_name', 'your location')}"
        
    except Exception as e:
        print(f"❌ Google Directions error: {e}")
        return None

def get_estimated_arrival_time(origin_coords):
    """Get estimated travel time from origin to destination."""
    if not GOOGLE_MAPS_API_KEY:
        return None
    
    try:
        origin = f"{origin_coords['lat']},{origin_coords['lng']}"
        destination = f"{USER_LOCATION['lat']},{USER_LOCATION['lng']}"
        
        url = "https://maps.googleapis.com/maps/api/directions/json"
        params = {
            "origin": origin,
            "destination": destination,
            "mode": "driving",
            "key": GOOGLE_MAPS_API_KEY,
            "departure_time": "now"
        }
        
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        
        if data.get("status") == "OK" and data.get("routes"):
            leg = data["routes"][0]["legs"][0]
            duration = leg.get("duration", {}).get("text", "")
            if duration:
                return f"Estimated travel time: {duration}"
        
        return None
        
    except Exception as e:
        print(f"❌ Travel time estimation error: {e}")
        return None
    
# --- UNKNOWN CALLER LOGIC ---
def handle_unknown_logic(message: str, stage: str, collected_info: dict, caller_id=None):
    """Handle conversation flow for unknown callers"""
    if any(k in message.lower() for k in ['urgent', 'asap', 'emergency']):
        name_to_use = collected_info.get("name", "An unknown caller")
        response_text = "Okay, I understand this is urgent. I am notifying Ruchit immediately."
        action = {"type": "URGENT_NOTIFICATION", "message": f"Urgent call from {name_to_use}."}
        return response_text, "end_of_call", collected_info, action

    intent = detect_user_intent(message)
    action = {}

    if stage == "start":
        return "May I know who's calling?", "asking_name", collected_info, action

    if stage == "collecting_contact" and intent == "provide_self_number":
        collected_info['phone'] = "Caller's Number"
        return "Okay, noted. Ruchit will call you back on the number you are calling from. Thank you!", "end_of_call", collected_info, action

    extracted_info = extract_information_with_openai(message, collected_info)
    collected_info.update(extracted_info)

    if stage == "asking_name":
        if collected_info.get("name"):
            return f"Hi {collected_info['name']}! And what is the reason for your call?", "asking_purpose", collected_info, action
        else:
            return "I'm sorry, I didn't catch your name. Could you please spell it out?", "asking_name", collected_info, action

    if stage == "asking_purpose":
        if not collected_info.get("purpose"):
            collected_info["purpose"] = message
        if not collected_info.get("phone"):
            return "Got it. What's the best number for Ruchit to call you back on?", "collecting_contact", collected_info, action
        else:
            phone_for_speech = format_number_for_speech(collected_info['phone'])
            return f"Perfect, I have your number as {phone_for_speech}. I'll pass this all on to Ruchit. Thanks for calling!", "end_of_call", collected_info, action

    if stage == "collecting_contact":
        if collected_info.get("phone"):
            phone_for_speech = format_number_for_speech(collected_info['phone'])
            return f"Great, I have your number as {phone_for_speech}. I'll pass this all on to Ruchit. Thanks for calling!", "end_of_call", collected_info, action
        else:
            return "I didn't quite catch that. Could you please provide a callback number?", "collecting_contact", collected_info, action

    return "Thank you. I'll make sure Ruchit gets the message.", "end_of_call", collected_info, action

# --- ENHANCED DELIVERY LOGIC WITH OTP INTEGRATION ---
def handle_delivery_logic(message: str, stage: str, collected_info: dict, caller_id=None):
    """
    Enhanced delivery logic with proper conversational flow:
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
        return handle_otp_request_logic(message, stage, collected_info)
    
    # Check if we're in an OTP-specific flow
    if stage in ["asking_otp_company", "asking_order_id", "providing_otp", "otp_provided"]:
        return handle_otp_request_logic(message, stage, collected_info)
    
    # Stage 1: Initial greeting - "How may I assist?"
    if stage == "start":
        print("--- [DELIVERY LOGIC] Initial greeting stage ---")
        
        # Check if this is already a delivery message
        if intent == "initial_delivery" or any(k in message.lower() for k in ["delivery", "parcel", "package"]):
            # Extract company information
            extracted_info = extract_information_with_openai(message, collected_info)
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
            extracted_info = extract_information_with_openai(message, collected_info)
            collected_info.update(extracted_info)
            company = collected_info.get("company")
            
            if company:
                return f"I see you have a delivery from {company}. Do you need help getting here, or are you already here?", "asking_location_help", collected_info, action
            else:
                return "I can help with your delivery. Which company is this from?", "asking_company_first", collected_info, action
        else:
            # Not a delivery call, handle as unknown caller
            return handle_unknown_logic(message, "start", collected_info, caller_id)
    
    # Stage 3: Asked for company name first
    if stage == "asking_company_first":
        extracted_info = extract_information_with_openai(message, collected_info)
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
            return handle_arrival_and_otp_check(collected_info)
        
        # Ambiguous response, clarify
        else:
            return "Are you asking for directions to get here, or have you already arrived at the location?", "asking_location_help", collected_info, action
    
    # Stage 5: Getting their current location for directions
    if stage == "getting_current_location":
        print("--- [DELIVERY LOGIC] Processing current location for directions ---")
        
        # Try to geocode their location
        geocode_results = geocode_with_google(message)
        
        if geocode_results and len(geocode_results) > 0:
            best_result = geocode_results[0]
            collected_info['current_location'] = best_result
            
            # Get directions
            directions = get_directions_from_google(best_result)
            eta = get_estimated_arrival_time(best_result)
            
            if directions:
                response_parts = [
                    f"I found your location: {best_result['place_name']}.",
                    f"Here are the directions: {directions}"
                ]
                
                if eta:
                    response_parts.append(eta)
                
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
            return handle_arrival_and_otp_check(collected_info)
        
        # They're asking for more help
        elif any(phrase in message_lower for phrase in ["lost", "can't find", "help", "confused", "where"]):
            return "What landmarks can you see around you? I can help guide you from there.", "getting_current_location", collected_info, action
        
        # General response while they're traveling
        else:
            return "Let me know when you reach the location!", "traveling_to_location", collected_info, action
    
    # Handle the rest of the existing delivery logic for OTP verification
    return handle_existing_delivery_logic(message, stage, collected_info, intent, action)

def handle_arrival_and_otp_check(collected_info):
    """Handle when delivery person arrives and check if they need OTP"""
    print("--- [DELIVERY LOGIC] Handling arrival and OTP check ---")
    
    company = collected_info.get("company")
    if not company:
        return "Great! You're here. Which company is this delivery from?", "asking_company_for_otp", {}, {}
    
    # Check if we have a pending order for this company
    pending_order = None
    order_id = None
    
    for oid, order_data in ORDER_WALLET.items():
        if (order_data.get("company", "").lower() == company.lower() and 
            order_data.get("status") == "pending"):
            pending_order = order_data
            order_id = oid
            break
    
    if not pending_order:
        return f"Perfect! You're here with the {company} delivery. However, I don't have any pending orders from {company} right now. Please check with the sender.", "end_of_call", collected_info, {}
    
    # Store order ID
    collected_info['order_id'] = order_id
    
    # Ask if they need OTP
    return f"Excellent! You've reached the location with your {company} delivery. Do you need the OTP?", "asking_if_otp_needed", collected_info, {}

def rate_limit_otp(max_requests=5, window=300):  # 5 requests per 5 minutes
    """Rate limiting decorator for OTP endpoints"""
    request_log = {}
    
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            client_ip = request.remote_addr
            firebase_uid = request.get_json().get("firebaseUid", client_ip)
            
            current_time = datetime.now().timestamp()
            key = f"{firebase_uid}:{client_ip}"
            
            # Clean old entries
            request_log[key] = [
                req_time for req_time in request_log.get(key, []) 
                if current_time - req_time < window
            ]
            
            # Check rate limit
            if len(request_log.get(key, [])) >= max_requests:
                return jsonify({
                    "success": False,
                    "error": "Too many OTP requests. Please wait before trying again.",
                    "retry_after": window
                }), 429
            
            # Log this request
            request_log.setdefault(key, []).append(current_time)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def handle_existing_delivery_logic(message, stage, collected_info, intent, action):
    """Handle the existing delivery logic for OTP verification"""
    
    # Stage: Asking if they need OTP
    if stage == "asking_if_otp_needed":
        message_lower = message.lower().strip()
        
        if any(phrase in message_lower for phrase in ["yes", "yeah", "yep", "need", "otp", "code"]):
            # They need OTP, proceed with verification
            company = collected_info.get("company")
            order_id = collected_info.get("order_id")
            order = ORDER_WALLET.get(order_id) if order_id else None
            
            if order and order.get("tracking_id"):
                return f"I have the order ready. Do you have the tracking ID for the {company} delivery?", "checking_tracking_availability", collected_info, action
            else:
                # No tracking ID in order, send approval notification
                return send_approval_notification(order_id, company, collected_info)
        
        elif any(phrase in message_lower for phrase in ["no", "nope", "don't need", "not needed"]):
            return "Alright! Have a great day and safe delivery!", "end_of_call", collected_info, action
        else:
            return "Do you need me to provide the OTP for this delivery? Please say yes or no.", "asking_if_otp_needed", collected_info, action
    
    # Stage: Asked for company name for OTP
    if stage == "asking_company_for_otp":
        extracted_info = extract_information_with_openai(message, collected_info)
        company = extracted_info.get("company") or message.strip().title()
        collected_info["company"] = company
        
        return handle_arrival_and_otp_check(collected_info)
    
    # All the existing stages for OTP verification
    if stage == "checking_tracking_availability":
        if intent == "general_yes":
            return "Please provide the tracking ID for verification.", "awaiting_tracking_id", collected_info, action
        elif intent == "declining":
            order_id = collected_info.get('order_id')
            company = collected_info.get('company')
            return send_approval_notification(order_id, company, collected_info)
        else:
            return "Do you have the tracking ID? Please say yes or no.", "checking_tracking_availability", collected_info, action

    if stage == "awaiting_tracking_id":
        provided_tracking_id = message.replace(" ", "").upper()
        order_id = collected_info.get('order_id')
        order = ORDER_WALLET.get(order_id)

        if order and order.get("tracking_id") == provided_tracking_id:
            # Use backend OTP system
            firebase_uid = collected_info.get('firebaseUid')
            company = collected_info.get('company')
            
            if firebase_uid and company and order_id:
                otp_result = fetch_otp_from_backend(firebase_uid, company, order_id)
                
                if otp_result["success"]:
                    formatted_otp = format_otp_for_speech(otp_result["otp"])
                    response_text = f"Tracking ID verified. Here's your OTP: {formatted_otp}"
                    ORDER_WALLET[order_id]["status"] = "completed"
                    return response_text, "end_of_call", collected_info, action
                else:
                    return f"Tracking verified, but I couldn't retrieve the OTP. {otp_result.get('error', 'Please try again.')}", "end_of_call", collected_info, action
            else:
                action = {"type": "PROVIDE_OTP"} 
                return "Tracking ID verified. One moment.", "end_of_call", collected_info, action
        else:
            return "That tracking ID doesn't match. Please check and try again.", "awaiting_tracking_id", collected_info, action

    if stage == "awaiting_approval":
        order_id = collected_info.get('order_id')
        order = ORDER_WALLET.get(order_id)
        
        if order and order.get("status") == "approved":
            firebase_uid = collected_info.get('firebaseUid')
            company = collected_info.get('company')
            
            if firebase_uid and company and order_id:
                otp_result = fetch_otp_from_backend(firebase_uid, company, order_id)
                
                if otp_result["success"]:
                    formatted_otp = format_otp_for_speech(otp_result["otp"])
                    response_text = f"Delivery approved. Here's your OTP: {formatted_otp}"
                    ORDER_WALLET[order_id]["status"] = "completed"
                    return response_text, "end_of_call", collected_info, action
                else:
                    return f"Delivery approved, but I couldn't retrieve the OTP. {otp_result.get('error', 'Please try again.')}", "end_of_call", collected_info, action
            else:
                action = {"type": "PROVIDE_OTP"}
                return "Delivery approved. One moment, please.", "end_of_call", collected_info, action
                
        elif order and order.get("status") == "denied":
            ORDER_WALLET.pop(order_id, None)
            return "The delivery was denied. Please contact the sender.", "end_of_call", collected_info, action
        else:
            if order_id in ORDER_WALLET:
                ORDER_WALLET.pop(order_id, None)
            return "I'm still waiting for approval. Please call back in a moment.", "end_of_call", collected_info, action

    # Handle conversation ending
    if intent == "ending_conversation":
        return "You're welcome! Have a safe delivery!", "end_of_call", collected_info, action
            
    # Fallback

def send_approval_notification(order_id, company, collected_info):
    """Helper function to send approval notification and return response"""
    action = {}
    approval_token = str(uuid.uuid4())
    ORDER_WALLET[order_id]['approval_token'] = approval_token
    
    # Create fallback web link
    approval_link = f"{BASE_URL}/approve-order?token={approval_token}"
    
    if OWNER_PHONE_NUMBER and INTERNAL_API_KEY:
        # Send push notification to Android app
        notification_sent = send_push_notification(
            OWNER_PHONE_NUMBER, 
            f"Delivery from {company} at door. Click to approve or deny.",
            approval_token
        )
        
        if notification_sent:
            return f"I have an order from {company}. I've sent a notification for approval. Please wait a moment.", "awaiting_approval", collected_info, action
        else:
            print("❌ Push notification failed, falling back to web approval")
    
    # Fallback: print web link (for development) or return error
    print(f"🔗 [FALLBACK] Web approval link: {approval_link}")
    return "I need to get approval but the notification system isn't available. Please try again later.", "end_of_call", collected_info, action


def generate_conversation_summary(conversation_history, collected_info=None):
    """
    Generate a 50-70 word summary of the conversation between AI and caller
    
    Args:
        conversation_history: List of conversation messages with roles
        collected_info: Dict containing collected information about the call
    
    Returns:
        str: Summary of the conversation
    """
    if not openai_client or not conversation_history:
        return "No conversation to summarize"
    
    try:
        # Extract only the conversation parts
        conversation_text = ""
        for message in conversation_history:
            role = message.get("role", "")
            parts = message.get("parts", [])
            
            if role == "user":
                conversation_text += f"Caller: {' '.join(parts)}\n"
            elif role == "model":
                conversation_text += f"AI: {' '.join(parts)}\n"
        
        # Add context from collected info
        context_info = ""
        if collected_info:
            company = collected_info.get("company", "")
            stage = collected_info.get("stage", "")
            if company:
                context_info += f"Company: {company}. "
            if stage:
                context_info += f"Final stage: {stage}. "
        
        system_prompt = """You are an expert at summarizing phone conversations. Create a concise 50-70 word summary of this conversation between an AI assistant and a caller.

Focus on:
- Who called (delivery person, unknown caller, etc.)
- What they needed (directions, OTP, general inquiry)
- What assistance was provided
- How the call concluded

Keep it professional and factual. Don't include unnecessary details."""

        user_prompt = f"""Context: {context_info}

Conversation:
{conversation_text}

Please provide a 50-70 word summary of this conversation."""

        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,
            max_tokens=150
        )
        
        summary = response.choices[0].message.content.strip()
        
        # Ensure it's within word count
        words = summary.split()
        if len(words) > 70:
            summary = ' '.join(words[:70]) + "..."
        elif len(words) < 50:
            summary += f" Call completed successfully."
        
        return summary
        
    except Exception as e:
        print(f"❌ [SUMMARY ERROR] {e}")
        return "Unable to generate conversation summary"





# --- MAIN ROUTES ---

@app.route("/generate", methods=["POST"])
def generate():
    """
    Main endpoint that handles conversation flow
    """
    try:
        data = request.get_json(force=True)
        new_message = data.get("new_message", "").strip()
        caller_role = data.get("caller_role", "unknown")
        history = data.get("history", []) or []
        stage = data.get("conversation_stage", "start")
        
        collected_info = data.get("collected_info", {}) or {}
        firebase_uid = data.get("firebaseUid")
        
        if firebase_uid:
            collected_info['firebaseUid'] = firebase_uid
        
        if not new_message: 
            return jsonify({"error": "'new_message' is required"}), 400
        
        # Handle conversation logic
        if caller_role == "delivery": 
            response_text, new_stage, updated_info, action = handle_delivery_logic(
                new_message, stage, collected_info
            )
        else: 
            caller_id = data.get("caller_id")
            response_text, new_stage, updated_info, action = handle_unknown_logic(
                new_message, stage, collected_info, caller_id
            )
        
        intent = detect_user_intent(new_message)
        
        # Handle OTP action - fetch OTP immediately if needed
        if action.get("type") == "PROVIDE_OTP":
            intent = "provide_otp"
            
            # Try to get OTP details from updated_info
            firebase_uid = updated_info.get('firebaseUid')
            company = updated_info.get('company')
            order_id = updated_info.get('order_id')
            
            if all([firebase_uid, company, order_id]):
                otp_result = fetch_otp_from_backend(firebase_uid, company, order_id)
                
                if otp_result["success"]:
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
            conversation_summary = generate_conversation_summary(updated_history, updated_info)
        
        print(f"🎯 Role={caller_role} | Intent={intent} | Stage: {stage} -> {new_stage}")
        
        response_data = {
            "response_text": response_text, 
            "updated_history": updated_history, 
            "intent": intent, 
            "stage": new_stage, 
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
            "details": str(e) if app.debug else None
        }), 500
    
@app.route("/api/get-otp", methods=["POST"])
@rate_limit_otp(max_requests=3, window=300)  # Stricter rate limiting for direct OTP
def get_otp_direct():
    """
    Direct OTP endpoint - use as fallback or for external integrations
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
        order_data = ORDER_WALLET.get(order_id)
        if order_data and order_data.get("status") != "approved":
            return jsonify({
                "success": False,
                "error": f"Order status is {order_data.get('status', 'unknown')}. Only approved orders can get OTP.",
                "speech_text": "The delivery hasn't been approved yet. Please wait for approval."
            }), 403
        
        # Fetch OTP from Node.js backend
        otp_result = fetch_otp_from_backend(firebase_uid, company, order_id)
        
        if otp_result["success"]:
            formatted_otp = format_otp_for_speech(otp_result["otp"])
            
            # Mark order as completed in local wallet
            if order_id in ORDER_WALLET:
                ORDER_WALLET[order_id]["status"] = "completed"
            
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

@app.route("/api/check-otp-status", methods=["POST"])
def check_otp_status():
    """
    New endpoint to check if OTP can be provided for an order
    """
    try:
        data = request.get_json()
        
        firebase_uid = data.get("firebaseUid")
        company = data.get("company")
        order_id = data.get("orderId")
        
        if not all([firebase_uid, company]):
            return jsonify({
                "success": False,
                "error": "Missing firebaseUid or company"
            }), 400
        
        # Find matching order if order_id not provided
        if not order_id:
            for oid, order_data in ORDER_WALLET.items():
                if (order_data.get("company", "").lower() == company.lower() and 
                    order_data.get("status") in ["pending", "approved"]):
                    order_id = oid
                    break
        
        if not order_id:
            return jsonify({
                "success": False,
                "can_provide_otp": False,
                "reason": "no_matching_order",
                "message": f"No pending orders found for {company}"
            })
        
        order_data = ORDER_WALLET.get(order_id)
        if not order_data:
            return jsonify({
                "success": False,
                "can_provide_otp": False,
                "reason": "order_not_found",
                "message": "Order not found in system"
            })
        
        status = order_data.get("status")
        
        return jsonify({
            "success": True,
            "can_provide_otp": status == "approved",
            "order_id": order_id,
            "status": status,
            "company": order_data.get("company"),
            "needs_approval": status == "pending",
            "message": {
                "pending": "Order needs approval before OTP can be provided",
                "approved": "OTP can be provided",
                "completed": "Order already completed",
                "denied": "Order was denied"
            }.get(status, "Unknown order status")
        })
        
    except Exception as e:
        print(f"❌ [CHECK OTP STATUS ERROR] {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route("/api/conversation-summary", methods=["POST"])
def get_conversation_summary():
    """
    Endpoint to generate conversation summary
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
        
        summary = generate_conversation_summary(conversation_history, collected_info)
        
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

@app.route("/api/bulk-otp-check", methods=["POST"])
def bulk_otp_check():
    """
    Check OTP availability for multiple companies/orders at once
    """
    try:
        data = request.get_json()
        firebase_uid = data.get("firebaseUid")
        companies = data.get("companies", [])  # List of company names
        
        if not firebase_uid:
            return jsonify({"error": "firebaseUid required"}), 400
        
        if not companies:
            # Return all available orders for this user
            available_orders = []
            for order_id, order_data in ORDER_WALLET.items():
                if order_data.get("status") in ["pending", "approved"]:
                    available_orders.append({
                        "order_id": order_id,
                        "company": order_data.get("company"),
                        "status": order_data.get("status"),
                        "can_provide_otp": order_data.get("status") == "approved"
                    })
            
            return jsonify({
                "success": True,
                "available_orders": available_orders,
                "total_count": len(available_orders)
            })
        
        # Check specific companies
        results = []
        for company in companies:
            matching_orders = []
            for order_id, order_data in ORDER_WALLET.items():
                if (order_data.get("company", "").lower() == company.lower() and 
                    order_data.get("status") in ["pending", "approved"]):
                    matching_orders.append({
                        "order_id": order_id,
                        "status": order_data.get("status"),
                        "can_provide_otp": order_data.get("status") == "approved"
                    })
            
            results.append({
                "company": company,
                "orders": matching_orders,
                "has_orders": len(matching_orders) > 0
            })
        
        return jsonify({
            "success": True,
            "results": results
        })
        
    except Exception as e:
        print(f"❌ [BULK OTP CHECK ERROR] {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route("/api/test-otp-flow", methods=["POST"])
def test_otp_flow():
    """
    Test endpoint to simulate complete OTP flow
    """
    try:
        data = request.get_json()
        firebase_uid = data.get("firebaseUid", "test-user-123")
        company = data.get("company", "Amazon")
        
        # Create a test order
        order_id = str(uuid.uuid4())
        ORDER_WALLET[order_id] = {
            "company": company,
            "otp": "123456",  # Test OTP
            "status": "approved",  # Pre-approved for testing
            "tracking_id": "TEST123"
        }
        
        # Test the OTP fetch
        otp_result = fetch_otp_from_backend(firebase_uid, company, order_id)
        
        return jsonify({
            "success": True,
            "test_order_id": order_id,
            "otp_fetch_result": otp_result,
            "message": "Test OTP flow completed"
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route("/api/otp-analytics", methods=["GET"])
def otp_analytics():
    """
    Analytics endpoint for OTP usage
    """
    try:
        # Count orders by status
        status_counts = {}
        company_counts = {}
        
        for order_data in ORDER_WALLET.values():
            status = order_data.get("status", "unknown")
            company = order_data.get("company", "unknown")
            
            status_counts[status] = status_counts.get(status, 0) + 1
            company_counts[company] = company_counts.get(company, 0) + 1
        
        return jsonify({
            "total_orders": len(ORDER_WALLET),
            "status_breakdown": status_counts,
            "company_breakdown": company_counts,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500
    
@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "healthy", 
        "openai_client": openai_client is not None, 
        "google_maps_api": GOOGLE_MAPS_API_KEY is not None,
        "nodejs_backend_configured": NODEJS_BACKEND_URL is not None,
        "internal_api_configured": INTERNAL_API_KEY is not None
    })

@app.route("/test-maps", methods=["POST"])
def test_maps():
    """Test endpoint for Google Maps functionality"""
    data = request.get_json(force=True)
    test_type = data.get("test_type")
    address = data.get("address", "Koramangala")
    
    if test_type == "geocode":
        result = geocode_with_google(address)
        return jsonify({"geocode_result": result})
    
    elif test_type == "directions":
        results = geocode_with_google(address)
        if results:
            directions = get_directions_from_google(results[0])
            eta = get_estimated_arrival_time(results[0])
            return jsonify({
                "place": results[0]["place_name"],
                "directions": directions,
                "eta": eta
            })
        return jsonify({"error": "No results found"})
    
    return jsonify({"error": "Invalid test_type"}), 400

@app.route("/add-order", methods=["POST"])
def add_order():
    """Secure endpoint to add order details to the wallet."""
    data = request.get_json()
    print(f"--- [AUTH] Comparing received key with server key: '{APP_SECRET_KEY}' ---")
    if not data or data.get("secret_key") != APP_SECRET_KEY:
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

    ORDER_WALLET[order_id] = order_data
    print(f"✅ Order added [{order_id}] for {company}")
    return jsonify({"success": True, "order_id": order_id})

@app.route("/approve-order", methods=["GET", "POST"])
def approve_order():
    """Handle order approval from web link or Android app"""
    
    # Web link approval (GET)
    if request.method == "GET":
        token = request.args.get('token')
        if not token:
            return "<h1>Error: No approval token provided.</h1>", 400

        order_id_to_approve = None
        for order_id, order_data in ORDER_WALLET.items():
            if order_data.get("approval_token") == token:
                order_id_to_approve = order_id
                break

        if order_id_to_approve:
            ORDER_WALLET[order_id_to_approve]["status"] = "approved"
            ORDER_WALLET[order_id_to_approve].pop("approval_token", None)
            print(f"✅ Order [{order_id_to_approve}] approved via web link.")
            return "<h1>Delivery Approved!</h1><p>The OTP has been released to the delivery person.</p>", 200
        else:
            return "<h1>Invalid or Expired Link</h1>", 404
    
    # Android app approval (POST)
    elif request.method == "POST":
        data = request.get_json()
        
        if data.get("api_key") != INTERNAL_API_KEY:
            return jsonify({"error": "Unauthorized"}), 401
        
        token = data.get("approval_token")
        user_action = data.get("action")  # "approve" or "deny"
        
        if not token:
            return jsonify({"error": "Missing approval token"}), 400
        
        order_id_to_approve = None
        for order_id, order_data in ORDER_WALLET.items():
            if order_data.get("approval_token") == token:
                order_id_to_approve = order_id
                break
        
        if not order_id_to_approve:
            return jsonify({"error": "Invalid or expired token"}), 404
        
        if user_action == "approve":
            ORDER_WALLET[order_id_to_approve]["status"] = "approved"
            ORDER_WALLET[order_id_to_approve].pop("approval_token", None)
            print(f"✅ Order [{order_id_to_approve}] approved via Android app.")
            return jsonify({"success": True, "message": "Delivery approved"})
        
        elif user_action == "deny":
            ORDER_WALLET[order_id_to_approve]["status"] = "denied"
            ORDER_WALLET[order_id_to_approve].pop("approval_token", None)
            print(f"❌ Order [{order_id_to_approve}] denied via Android app.")
            return jsonify({"success": True, "message": "Delivery denied"})
        
        else:
            return jsonify({"error": "Invalid action. Use 'approve' or 'deny'"}), 400

@app.route("/list-orders", methods=["GET"])
def list_orders():
    """Debug endpoint to see current orders in wallet"""
    return jsonify({
        "orders": ORDER_WALLET,
        "count": len(ORDER_WALLET)
    })

@app.route("/clear-orders", methods=["POST"])
def clear_orders():
    """Debug endpoint to clear all orders"""
    data = request.get_json()
    if data and data.get("secret_key") == APP_SECRET_KEY:
        ORDER_WALLET.clear()
        print("🗑️ All orders cleared from wallet")
        return jsonify({"success": True, "message": "All orders cleared"})
    return jsonify({"error": "Unauthorized"}), 401

if __name__ == "__main__":
    print("🚀 Starting Flask API on :5001 ...")
    print(f"📍 User location: {USER_LOCATION}")
    print(f"🗝️ OpenAI API: {'✅' if openai_client else '❌'}")
    print(f"🗺️ Google Maps API: {'✅' if GOOGLE_MAPS_API_KEY else '❌'}")
    print(f"📱 Node.js Backend: {NODEJS_BACKEND_URL}")
    print(f"🔐 Notification System: {'✅' if INTERNAL_API_KEY and OWNER_PHONE_NUMBER else '❌'}")
    app.run(port=5001, debug=True)
  