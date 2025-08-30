from openai import OpenAI
import os
import requests
from dotenv import load_dotenv
from flask import Flask, request, jsonify
import json
import re

app = Flask(__name__)
load_dotenv()

# --- CONFIGURATION ---
USER_LOCATION = {
    "lat": float(os.getenv("USER_LAT", 12.912445713301228)),
    "lng": float(os.getenv("USER_LNG", 77.6359444711491))
}
MAPBOX_TOKEN = os.getenv("MAPBOX_API_KEY")

# --- OPENAI CLIENT ---
try:
    openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    print("✅ OpenAI Client initialized successfully.")
except Exception as e:
    print(f"❌ Error initializing OpenAI Client: {e}")
    openai_client = None
    exit(1)

# --- HELPER FUNCTIONS ---
def format_phone_number(number_string: str):
    """Format phone number to Indian standard with +91 prefix"""
    if not isinstance(number_string, str):
        return None
    digits = re.sub(r'\D', '', number_string)
    if len(digits) == 10:
        return f"+91{digits}"
    if len(digits) == 12 and digits.startswith('91'):
        return f"+{digits}"
    return digits if digits else None

def format_number_for_speech(number_string: str):
    """Convert phone number to speech-friendly format with spaces"""
    if not number_string:
        return ""
    return " ".join([ch for ch in number_string if ch.isdigit()])

def detect_user_intent(message: str):
    """Detect user intent from their message"""
    message_lower = message.lower().strip()
    message_cleaned = re.sub(r'[.!?]', '', message_lower)

    # Location keywords
    if any(k in message_lower for k in [
        "road", "nagar", "colony", "market", "station", "gate", "circle", 
        "apartment", "complex", "mall", "near", "opposite", "metro", "bus stop"
    ]):
        return "providing_location"
        
    # Delivery keywords
    if any(k in message_lower for k in ["delivery", "parcel", "package", "amazon", "flipkart"]):
        return "initial_delivery"
    
    # Callback related
    if any(k in message_lower for k in ["it's fine", "it's ok", 'ask him to call', 'just call me back']):
        return "non_urgent_callback"
    if any(k in message_lower for k in ['same number', 'this number', "number i'm calling from"]):
        return "provide_self_number"
    if any(k in message_lower for k in ['call back', 'callback', 'call me back']):
        return "requesting_callback"
    
    # Simple yes/no responses
    if message_cleaned in ['yes', 'yeah', 'yep', 'ok', 'okay', 'sure', 'correct']:
        return "general_yes"
    if message_cleaned in ['no', 'nope', 'not really']:
        return "declining"
    
    # Ending conversation
    if any(k in message_lower for k in ['thank', 'bye', 'thanks']):
        return "ending_conversation"
    
    return "general"

def extract_information_with_openai(message, collected_info):
    """Extract structured information using OpenAI"""
    if not openai_client:
        return {}
    
    try:
        system_prompt = """
        You are an expert information extraction assistant.
        Extract any of the following fields from the user's message: 'name', 'purpose', 'phone', 'company'.
        You MUST return ONLY a valid JSON object.
        If no new information is found, return {}.
        """
        user_prompt = f"""
        Current information already collected: {json.dumps(collected_info)}
        User's latest message: "{message}"
        """

        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=200
        )

        extracted_text = response.choices[0].message.content.strip()
        extracted = json.loads(extracted_text)

        # Format phone number if extracted
        if extracted.get("phone"):
            formatted_number = format_phone_number(extracted["phone"])
            if formatted_number:
                extracted["phone"] = formatted_number
            else:
                del extracted["phone"]

        print(f"✅ [INFO EXTRACTION] Extracted: {extracted}")
        return extracted
    except Exception as e:
        print(f"❌ [INFO EXTRACTION ERROR] {e}")
        return {}

# --- MAPBOX FUNCTIONS ---
def geocode_with_proximity(address_text):
    """
    Geocode an address string near the user's location using Mapbox.
    Returns dict with lat, lng, place_name or None if not found.
    """
    if not MAPBOX_TOKEN:
        print("❌ MAPBOX_TOKEN not configured")
        return None

    try:
        url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{address_text}.json"
        params = {
            "access_token": MAPBOX_TOKEN,
            "proximity": f"{USER_LOCATION['lng']},{USER_LOCATION['lat']}",
            "limit": 1
        }
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if not data.get("features"):
            return None

        feature = data["features"][0]
        coords = feature.get("geometry", {}).get("coordinates")
        place_name = feature.get("place_name", address_text)

        if coords and len(coords) == 2:
            return {
                "lng": coords[0],
                "lat": coords[1],
                "place_name": place_name
            }
        return None

    except Exception as e:
        print(f"❌ Geocoding error: {e}")
        return None

def get_directions_from_caller(caller_address):
    """
    Get driving directions from caller's location to user's location.
    Returns: (coordinates_dict, place_name, directions_text)
    """
    caller_result = geocode_with_proximity(caller_address)
    if not caller_result:
        return None, None, None

    try:
        url = (
            f"https://api.mapbox.com/directions/v5/mapbox/driving/"
            f"{caller_result['lng']},{caller_result['lat']};"
            f"{USER_LOCATION['lng']},{USER_LOCATION['lat']}"
        )
        params = {
            "steps": "true",
            "overview": "full",
            "access_token": MAPBOX_TOKEN
        }

        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if not data.get("routes"):
            return caller_result, caller_result["place_name"], None

        # Extract turn-by-turn directions
        legs = data["routes"][0].get("legs", [])
        if not legs or not legs[0].get("steps"):
            return caller_result, caller_result["place_name"], None

        steps = legs[0]["steps"]
        directions_list = []
        
        for step in steps[:4]:  # Limit to first 4 steps for brevity
            instruction = step.get("maneuver", {}).get("instruction")
            if instruction:
                directions_list.append(instruction)

        if directions_list:
            directions = ". Then, ".join(directions_list)
            return caller_result, caller_result["place_name"], directions
        else:
            return caller_result, caller_result["place_name"], None

    except Exception as e:
        print(f"❌ Directions error: {e}")
        return caller_result, caller_result["place_name"], None

# --- UNKNOWN CALLER LOGIC ---
def handle_unknown_logic(message: str, stage: str, collected_info: dict, caller_id=None):
    """Handle conversation flow for unknown callers"""
    
    # Check for urgent calls first
    if any(k in message.lower() for k in ['urgent', 'asap', 'emergency']):
        name_to_use = collected_info.get("name", "An unknown caller")
        response_text = "Okay, I understand this is urgent. I am notifying Ruchit immediately."
        action = {"type": "URGENT_NOTIFICATION", "message": f"Urgent call from {name_to_use}."}
        return response_text, "end_of_call", collected_info, action

    intent = detect_user_intent(message)
    action = {}

    if stage == "start":
        return "May I know who's calling?", "asking_name", collected_info, action

    # Handle self-number provision
    if stage == "collecting_contact" and intent == "provide_self_number":
        collected_info['phone'] = "Caller's Number"
        return "Okay, noted. Ruchit will call you back on the number you are calling from. Thank you!", "end_of_call", collected_info, action

    # Extract information using OpenAI
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

# --- DELIVERY CALLER LOGIC ---
def handle_delivery_logic(message: str, stage: str, collected_info: dict):
    """Handle conversation flow for delivery persons"""
    intent = detect_user_intent(message)
    action = {}

    # Stage 1: Initial delivery mention
    if stage == "start" and intent == "initial_delivery":
        return "Which company is the delivery from?", "asked_for_company", collected_info, action

    # Stage 2: Getting company name
    if stage == "asked_for_company":
        collected_info["company"] = message.replace('.', '').strip().title()
        return f"Got it, a delivery from {collected_info['company']}. Do you need directions to reach here?", "asked_for_directions", collected_info, action

    # Stage 3: Asking about directions
    if stage == "asked_for_directions":
        if intent == "general_yes":
            return "Sure. Where are you coming from? Please tell me a landmark or your area.", "asked_for_location", collected_info, action
        elif intent == "declining":
            return "No problem! Please leave the package with the security guard, Kumar, at the main gate.", "end_of_call", collected_info, action
        else:
            # Handle unclear responses
            return "Sorry, I didn't get that. Do you need directions? Please say yes or no.", "asked_for_directions", collected_info, action

    # Stage 4: Getting location and providing directions
    if stage == "asked_for_location":
        # Accept any response as a location attempt (more robust than intent checking)
        caller_location_text = message.strip()
        
        start_coords, start_place_name, directions = get_directions_from_caller(caller_location_text)
        
        if not start_coords:
            return f"I couldn't find a location for '{caller_location_text}'. Could you please name a more specific landmark or area?", "asked_for_location", collected_info, action

        response_end = "Please leave the package with Kumar at the main gate."
        
        if directions:
            return f"From {start_place_name}: {directions}. {response_end}", "directions_provided", collected_info, action
        else:
            # Fallback if directions fail but geocoding works
            return f"From {start_place_name}, please head towards the destination address. {response_end}", "directions_provided", collected_info, action

    # Handle conversation ending
    if intent == "ending_conversation":
        return "You're welcome! Thanks for the delivery and drive safely!", "end_of_call", collected_info, action

    # Fallback for unexpected states
    return "Sorry, I didn't quite understand. Could you please repeat that?", stage, collected_info, action

# --- MAIN ROUTES ---
@app.route("/generate", methods=["POST"])
def generate():
    """Main endpoint for processing conversation turns"""
    try:
        data = request.get_json(force=True)
        new_message = data.get("new_message", "").strip()
        caller_role = data.get("caller_role", "unknown")
        history = data.get("history", []) or []
        stage = data.get("conversation_stage", "start")
        collected_info = data.get("collected_info", {}) or {}
        caller_id = data.get("caller_id")

        if not new_message:
            return jsonify({"error": "'new_message' is required"}), 400

        # Initialize default values
        response_text, new_stage, updated_info, action = "", stage, collected_info, {}

        # Route to appropriate handler
        if caller_role == "delivery":
            response_text, new_stage, updated_info, action = handle_delivery_logic(new_message, stage, collected_info)
        else:
            # Default to unknown caller logic
            response_text, new_stage, updated_info, action = handle_unknown_logic(new_message, stage, collected_info, caller_id)

        # Detect intent for metadata
        intent = detect_user_intent(new_message)
        
        # Update conversation history
        updated_history = history + [
            {"role": "user", "parts": [new_message]},
            {"role": "model", "parts": [response_text]}
        ]

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
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "openai_client": openai_client is not None,
        "mapbox_token": MAPBOX_TOKEN is not None
    })

@app.route("/test", methods=["POST"])
def test_endpoints():
    """Test endpoint for debugging"""
    data = request.get_json(force=True)
    test_type = data.get("test_type")
    
    if test_type == "geocode":
        address = data.get("address", "MG Road Bangalore")
        result = geocode_with_proximity(address)
        return jsonify({"geocode_result": result})
    
    elif test_type == "directions":
        address = data.get("address", "MG Road Bangalore")
        coords, place_name, directions = get_directions_from_caller(address)
        return jsonify({
            "coordinates": coords,
            "place_name": place_name,
            "directions": directions
        })
    
    elif test_type == "intent":
        message = data.get("message", "I have a delivery")
        intent = detect_user_intent(message)
        return jsonify({"intent": intent})
    
    return jsonify({"error": "Invalid test_type"}), 400

if __name__ == "__main__":
    print("🚀 Starting Flask API on :5001 ...")
    print(f"📍 User location: {USER_LOCATION}")
    print(f"🗝️ OpenAI API: {'✅' if openai_client else '❌'}")
    print(f"🗺️ Mapbox API: {'✅' if MAPBOX_TOKEN else '❌'}")
    app.run(port=5001, debug=True)