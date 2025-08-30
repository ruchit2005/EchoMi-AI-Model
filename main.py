from openai import OpenAI
import os
import requests
from dotenv import load_dotenv
from flask import Flask, request, jsonify
import json
import re
from geopy.distance import geodesic

app = Flask(__name__)
load_dotenv()

# --- CONFIGURATION ---
USER_LOCATION = {
    "lat": float(os.getenv("USER_LAT", 12.912445713301228)),
    "lng": float(os.getenv("USER_LNG", 77.6359444711491))
}
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

# --- OPENAI CLIENT ---
try:
    openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    print("✅ OpenAI Client initialized successfully.")
except Exception as e:
    print(f"❌ Error initializing OpenAI Client: {e}")
    openai_client = None
    exit(1)

# --- HELPER FUNCTIONS ---
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
            temperature=0.1,  # Lower temperature for more consistent extraction
            max_tokens=150
        )
        
        extracted = json.loads(response.choices[0].message.content.strip())
        print(f"✅ [INFO EXTRACTION] Extracted: {extracted}")
        
        # Clean up phone number if present
        if extracted.get("phone"):
            formatted = format_phone_number(extracted["phone"])
            if formatted: 
                extracted["phone"] = formatted
            else: 
                del extracted["phone"]
        
        # Clean up company name if present
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

# --- DELIVERY LOGIC (OPTIMIZED) ---
# --- DELIVERY LOGIC (MODIFIED TO BE MORE DECISIVE) ---
# --- DELIVERY LOGIC (WITH PROACTIVE COMPANY EXTRACTION) ---
# --- DELIVERY LOGIC (FINAL, MORE ROBUST VERSION) ---
# --- DELIVERY LOGIC (FINAL, WITH DEBUG LOGGING) ---
def handle_delivery_logic(message: str, stage: str, collected_info: dict):
    """Handles the delivery flow with robust logging to debug proactive extraction."""
    intent = detect_user_intent(message)
    action = {}
    print(f"\n--- [DELIVERY LOGIC] START ---")
    print(f"--- [DELIVERY LOGIC] Stage: {stage}, Intent: {intent} ---")
    print(f"--- [DELIVERY LOGIC] Current collected_info: {collected_info} ---")

    # Stage 1: Handle the very first turn of a delivery call
    if stage == "start" and intent == "initial_delivery":
        print("--- [DELIVERY LOGIC] In Stage 1: 'start' with initial_delivery intent ---")
        
        # Extract information from the message
        extracted_info = extract_information_with_openai(message, collected_info)
        print(f"--- [DELIVERY LOGIC] Raw extracted_info: {extracted_info} ---")
        
        # Update collected_info with extracted information
        collected_info.update(extracted_info)
        print(f"--- [DELIVERY LOGIC] Updated collected_info: {collected_info} ---")
        
        company = collected_info.get("company")
        print(f"--- [DELIVERY LOGIC] Final company value: '{company}' ---")

        if company:
            print(f"--- [DELIVERY LOGIC] Company found: '{company}'. Skipping company question. ---")
            response_text = f"Got it, a delivery from {company}. Do you need directions to reach here?"
            new_stage = "asked_for_directions"
            print(f"--- [DELIVERY LOGIC] Returning: '{response_text}' with stage '{new_stage}' ---")
            return response_text, new_stage, collected_info, action
        else:
            print("--- [DELIVERY LOGIC] No company found. Asking for company. ---")
            response_text = "Which company is the delivery from?"
            new_stage = "asked_for_company"
            return response_text, new_stage, collected_info, action

    # Stage 2: Handle the turn after we've asked for the company name
    if stage == "asked_for_company":
        print("--- [DELIVERY LOGIC] In Stage 2: 'asked_for_company' ---")
        extracted_info = extract_information_with_openai(message, collected_info)
        company = extracted_info.get("company")
        
        if not company:
            # If OpenAI didn't extract it, treat the whole message as company name
            company = message.replace('.', '').strip()

        collected_info["company"] = company.title()
        return f"Got it, a delivery from {collected_info['company']}. Do you need directions to reach here?", "asked_for_directions", collected_info, action

    # Stage 3: Directions need assessment
    if stage == "asked_for_directions":
        print("--- [DELIVERY LOGIC] In Stage 3: 'asked_for_directions' ---")
        if intent == "general_yes":
            return "Sure. Where are you coming from? Please tell me a landmark or your current area.", "asked_for_location", collected_info, action
        elif intent == "declining":
            return "No problem! Please leave the package with the security guard, Kumar, at the main gate. Thank you!", "end_of_call", collected_info, action
        else:
            return "Sorry, I didn't get that. Do you need directions? Please say yes or no.", "asked_for_directions", collected_info, action

    # Stage 4: Location processing
    if stage == "asked_for_location":
        print("--- [DELIVERY LOGIC] In Stage 4: 'asked_for_location' ---")
        caller_location_text = message.strip()
        geocoded_results = geocode_with_google(caller_location_text)

        if not geocoded_results:
            return f"I couldn't find '{caller_location_text}' nearby. Could you please name a specific landmark, main road, or area in Bengaluru?", "asked_for_location", collected_info, action

        location_choice = geocoded_results[0]
        directions = get_directions_from_google(location_choice)
        eta = get_estimated_arrival_time(location_choice)
        
        response_parts = [f"Okay, from {location_choice['place_name']}:"]
        if directions: response_parts.append(f"Directions: {directions}.")
        if eta: response_parts.append(eta)
        response_parts.append("Please leave the package with Kumar at the main gate. Thank you!")
        
        return " ".join(response_parts), "directions_provided", collected_info, action

    # Stage 5: Conversation ending
    if intent == "ending_conversation":
        print("--- [DELIVERY LOGIC] In Stage 5: 'ending_conversation' ---")
        return "You're welcome! Thanks for the delivery and drive safely!", "end_of_call", collected_info, action

    # Fallback for any unexpected messages
    print(f"--- [DELIVERY LOGIC] Fallback reached. Stage: {stage}, Intent: {intent} ---")
    return "Sorry, I didn't quite understand. Could you please repeat that?", stage, collected_info, action

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
        "google_maps_api": GOOGLE_MAPS_API_KEY is not None
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

if __name__ == "__main__":
    print("🚀 Starting Flask API on :5001 ...")
    print(f"📍 User location: {USER_LOCATION}")
    print(f"🗝️ OpenAI API: {'✅' if openai_client else '❌'}")
    print(f"🗺️ Google Maps API: {'✅' if GOOGLE_MAPS_API_KEY else '❌'}")
    app.run(port=5001, debug=True)