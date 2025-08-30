from openai import OpenAI
import os
import requests
from dotenv import load_dotenv
from flask import Flask, request, jsonify
import json
import re
import uuid
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
    message_lower = message.lower().strip()
    message_cleaned = re.sub(r'[.!?]', '', message_lower)
    if any(k in message_lower for k in ["road", "nagar", "colony", "market", "station", "gate", "circle", "apartment", "complex", "mall", "near", "opposite", "metro", "bus stop"]): return "providing_location"
    if any(k in message_lower for k in ['otp', 'one time password', 'code']): return "requesting_otp"
    if any(k in message_lower for k in ["delivery", "parcel", "package", "amazon", "flipkart"]): return "initial_delivery"
    if any(k in message_lower for k in ["it's fine", "it's ok", 'ask him to call', 'just call me back']): return "non_urgent_callback"
    if any(k in message_lower for k in ['same number', 'this number', "number i'm calling from"]): return "provide_self_number"
    if any(k in message_lower for k in ['call back', 'callback', 'call me back']): return "requesting_callback"
    if message_cleaned in ['yes', 'yeah', 'yep', 'ok', 'okay', 'sure', 'correct']: return "general_yes"
    if message_cleaned in ['no', 'nope', 'not really']: return "declining"
    if any(k in message_lower for k in ['thank', 'bye', 'thanks']): return "ending_conversation"
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

# --- DELIVERY LOGIC ---
def handle_delivery_logic(message: str, stage: str, collected_info: dict, caller_id=None):
    """
    Handles delivery verification with two notification scenarios:
    Case 1: Delivery person doesn't have tracking ID
    Case 2: OTP message from company doesn't contain tracking ID
    """
    intent = detect_user_intent(message)
    action = {}
    print(f"\n--- [DELIVERY LOGIC] START ---")
    print(f"--- [DELIVERY LOGIC] Stage: {stage}, Intent: {intent} ---")
    print(f"--- [DELIVERY LOGIC] Message: '{message}' ---")
    print(f"--- [DELIVERY LOGIC] Current collected_info: {collected_info} ---")

    # Handle OTP requests at any stage
    if intent == "requesting_otp":
        company = collected_info.get("company")
        if not company:
            return "To get an OTP, please first tell me which company you are from.", "asked_for_company", collected_info, action

        # Find the order for the company
        order_id, order_data = None, None
        for id, data in ORDER_WALLET.items():
            if data.get("company") == company and data.get("status") == "pending":
                order_id, order_data = id, data
                break
        
        if not order_data:
            return f"I don't have a pending order from {company} that needs an OTP.", "end_of_call", collected_info, action

        collected_info['order_id'] = order_id
        
        # Branch to the correct verification method
        if order_data.get("tracking_id"):
            return f"Okay, to get the OTP for {company}, please provide the tracking ID.", "awaiting_tracking_id", collected_info, action
        else:
            # Push notification for approval
            approval_token = str(uuid.uuid4())
            ORDER_WALLET[order_id]['approval_token'] = approval_token
            
            if OWNER_PHONE_NUMBER and INTERNAL_API_KEY:
                notification_sent = send_push_notification(
                    OWNER_PHONE_NUMBER, 
                    f"Delivery from {company} requesting OTP. Click to approve or deny.",
                    approval_token
                )
                if notification_sent:
                    return "I've sent a notification to the owner for approval. Please hold.", "awaiting_approval", collected_info, action
            
            # Fallback
            approval_link = f"{BASE_URL}/approve-order?token={approval_token}"
            print(f"🔗 [FALLBACK] Web approval link: {approval_link}")
            return "I need owner approval, but the notification system isn't available.", "end_of_call", collected_info, action

    # Stage 1: Initial delivery call
    if stage == "start":
        print("--- [DELIVERY LOGIC] Processing initial delivery message ---")
        extracted_info = extract_information_with_openai(message, collected_info)
        print(f"--- [DELIVERY LOGIC] Extracted info: {extracted_info} ---")
        
        collected_info.update(extracted_info)
        company = collected_info.get("company")
        print(f"--- [DELIVERY LOGIC] Company: '{company}' ---")
        
        if not company:
            print("--- [DELIVERY LOGIC] No company found, asking for company ---")
            return "Hi, which company is this delivery from?", "asked_for_company", collected_info, action

        # Find pending order for this company
        pending_order = next((data for id, data in ORDER_WALLET.items() 
                            if data.get("company", "").lower() == company.lower() and data.get("status") == "pending"), None)

        if not pending_order:
            print(f"--- [DELIVERY LOGIC] No pending orders for '{company}' ---")
            return f"I don't have any pending orders from {company} right now. Please check with the sender.", "end_of_call", collected_info, action

        # Store order ID
        order_id = next(id for id, data in ORDER_WALLET.items() if data is pending_order)
        collected_info['order_id'] = order_id
        print(f"--- [DELIVERY LOGIC] Found pending order: {order_id} ---")

        # Check if OTP message has tracking ID (Case 2)
        if not pending_order.get("tracking_id"):
            print("--- [DELIVERY LOGIC] CASE 2: OTP message has no tracking ID - sending notification ---")
            return send_approval_notification(order_id, company, collected_info)
        else:
            print("--- [DELIVERY LOGIC] OTP message has tracking ID - asking delivery person ---")
            return f"I have an order from {company}. Do you have the tracking ID?", "checking_tracking_availability", collected_info, action

    # Stage 2: Handle company name collection
    if stage == "asked_for_company":
        print("--- [DELIVERY LOGIC] Processing company name response ---")
        extracted_info = extract_information_with_openai(message, collected_info)
        company = extracted_info.get("company")
        
        if not company:
            company = message.replace('.', '').strip().title()
        
        collected_info["company"] = company
        
        # Find pending order
        pending_order = next((data for id, data in ORDER_WALLET.items() 
                            if data.get("company", "").lower() == company.lower() and data.get("status") == "pending"), None)

        if not pending_order:
            return f"I don't have any pending orders from {company} right now.", "end_of_call", collected_info, action

        order_id = next(id for id, data in ORDER_WALLET.items() if data is pending_order)
        collected_info['order_id'] = order_id

        # Check tracking ID availability
        if not pending_order.get("tracking_id"):
            print("--- [DELIVERY LOGIC] CASE 2: OTP message has no tracking ID - sending notification ---")
            return send_approval_notification(order_id, company, collected_info)
        else:
            return f"I have an order from {company}. Do you have the tracking ID?", "checking_tracking_availability", collected_info, action

    # Stage 3: Check if delivery person has tracking ID
    if stage == "checking_tracking_availability":
        print("--- [DELIVERY LOGIC] Delivery person response about having tracking ID ---")
        if intent == "general_yes":
            print("--- [DELIVERY LOGIC] Delivery person has tracking ID - requesting it ---")
            return "Please provide the tracking ID for verification.", "awaiting_tracking_id", collected_info, action
        elif intent == "declining":
            print("--- [DELIVERY LOGIC] CASE 1: Delivery person doesn't have tracking ID - sending notification ---")
            order_id = collected_info.get('order_id')
            company = collected_info.get('company')
            return send_approval_notification(order_id, company, collected_info)
        else:
            return "Do you have the tracking ID? Please say yes or no.", "checking_tracking_availability", collected_info, action

    # Stage 4: Verify tracking ID
    if stage == "awaiting_tracking_id":
        print("--- [DELIVERY LOGIC] Verifying provided tracking ID ---")
        provided_tracking_id = message.replace(" ", "").upper()
        order_id = collected_info.get('order_id')
        order = ORDER_WALLET.get(order_id)

        if order and order.get("tracking_id") == provided_tracking_id:
            otp = order.get("otp")
            company = order.get("company")
            ORDER_WALLET.pop(order_id, None)
            print(f"--- [DELIVERY LOGIC] Tracking verified, releasing OTP: {otp} ---")
            return f"Tracking ID verified. Your OTP is: {otp}. Thank you!", "end_of_call", collected_info, action
        else:
            print("--- [DELIVERY LOGIC] Tracking verification failed ---")
            return "That tracking ID doesn't match. Please check and try again.", "awaiting_tracking_id", collected_info, action

    # Stage 5: Waiting for push notification approval
    if stage == "awaiting_approval":
        print("--- [DELIVERY LOGIC] Checking if notification was approved ---")
        order_id = collected_info.get('order_id')
        order = ORDER_WALLET.get(order_id)
        
        if order and order.get("status") == "approved":
            otp = order.get("otp")
            company = order.get("company")
            ORDER_WALLET.pop(order_id, None)
            print(f"--- [DELIVERY LOGIC] Notification approved, releasing OTP: {otp} ---")
            return f"Delivery approved! Your OTP is: {otp}. Thank you!", "end_of_call", collected_info, action
        elif order and order.get("status") == "denied":
            ORDER_WALLET.pop(order_id, None)
            return "The delivery was denied. Please contact the sender.", "end_of_call", collected_info, action
        else:
            return "Still waiting for approval. Please hold on.", "awaiting_approval", collected_info, action

    # Handle conversation ending
    if intent == "ending_conversation":
        return "You're welcome! Have a safe delivery!", "end_of_call", collected_info, action
            
    # Fallback
    return "Which company is this delivery from?", "asked_for_company", collected_info, action

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

# --- MAIN ROUTES ---
@app.route("/generate", methods=["POST"])
def generate():
    try:
        data = request.get_json(force=True)
        new_message, caller_role = data.get("new_message", "").strip(), data.get("caller_role", "unknown")
        history, stage = data.get("history", []) or [], data.get("conversation_stage", "start")
        collected_info, caller_id = data.get("collected_info", {}) or {}, data.get("caller_id")
        
        if not new_message: 
            return jsonify({"error": "'new_message' is required"}), 400
        
        if caller_role == "delivery": 
            response_text, new_stage, updated_info, action = handle_delivery_logic(new_message, stage, collected_info)
        else: 
            response_text, new_stage, updated_info, action = handle_unknown_logic(new_message, stage, collected_info, caller_id)
        
        intent = detect_user_intent(new_message)
        updated_history = history + [{"role": "user", "parts": [new_message]}, {"role": "model", "parts": [response_text]}]
        
        print(f"🎯 Role={caller_role} | Intent={intent} | Stage: {stage} -> {new_stage}")
        
        return jsonify({
            "response_text": response_text, 
            "updated_history": updated_history, 
            "intent": intent, 
            "stage": new_stage, 
            "collected_info": updated_info, 
            "action": action
        })
        
    except Exception as e:
        print(f"❌ [GENERATE ERROR] {e}")
        return jsonify({"error": "Internal server error"}), 500

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