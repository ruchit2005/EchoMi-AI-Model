from openai import OpenAI
import os
from dotenv import load_dotenv
from flask import Flask, request, jsonify
import json
import time
import requests
import re

app = Flask(__name__)


load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)

# ======================================================================


try:
    openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    print("✅ OpenAI Client initialized successfully.")

except Exception as e:
    print(f"❌ Error initializing OpenAI Client: {e}")
    openai_client = None
    exit(1)


## Mapbox
MAPBOX_ACCESS_TOKEN=os.getenv("MAPBOX_API_KEY")


# ======================================================================
# HELPER FUNCTIONS
# ======================================================================


def format_phone_number(number_string: str):
    """
    Clean and standardize phone numbers (focus: India).
    """
    if not isinstance(number_string, str):
        return None
    digits = re.sub(r'\D', '', number_string)
    if len(digits) == 10:
        return f"+91{digits}"
    if len(digits) == 12 and digits.startswith('91'):
        return f"+{digits}"
    return digits if digits else None

def format_number_for_speech(number_string: str):
    """
    Makes a phone number easier to read out (e.g., +919876543210 -> "nine eight seven six five four three two one zero").
    """
    if not number_string:
        return ""
    return " ".join(number_string)

def detect_user_intent(message: str):
    """
    Classify the user's intent based on simple keyword rules.
    """
    message_lower = message.lower().strip()
    message_cleaned = re.sub(r'[.!?]', '', message_lower)

    if any(k in message_lower for k in ["it's fine", "it's ok", 'ask him to call', 'just call me back']):
        return "non_urgent_callback"
    if any(k in message_lower for k in ['same number', 'this number', "number i'm calling from"]):
        return "provide_self_number"
    if any(k in message_lower for k in ['call back', 'callback', 'call me back']):
        return "requesting_callback"
    if message_cleaned in ['yes', 'yeah', 'yep', 'ok', 'okay', 'sure']:
        return "general_yes"
    if message_cleaned in ['no', 'nope', 'not really']:
        return "declining"
    if any(k in message_lower for k in ['thank', 'bye', 'thanks']):
        return "ending_conversation"
    return "general"


def extract_information_with_openai(message, collected_info):
    if not openai_client: return {}
    try:
        # The system prompt instructs the model to behave in a specific way
        system_prompt = """
        You are an expert information extraction assistant. 
        Extract any of the following fields from the user's message: 'name', 'purpose', 'phone', 'company'.
        You MUST return ONLY a valid JSON object. 
        If no new information is found, return an empty JSON object {}.
        """
        
        # The user prompt contains the context and the new message
        user_prompt = f"""
        Current information already collected: {json.dumps(collected_info)}
        User's latest message: "{message}"
        """

        # Make the API call to OpenAI
        response = openai_client.chat.completions.create(
            model="gpt-4o",  # Or "gpt-3.5-turbo"
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"}, # Ensures the output is valid JSON
            temperature=0.2, # Lower temperature for more predictable output
            request_timeout=10
        )
        
        # Extract the JSON string from the response
        extracted_text = response.choices[0].message.content
        extracted = json.loads(extracted_text)
        
        # Format the phone number if it exists
        if extracted.get("phone"):
            formatted_number = format_phone_number(extracted["phone"])
            if formatted_number:
                extracted["phone"] = formatted_number
            else:
                del extracted["phone"] # Remove invalid phone number
                
        print(f"✅ [INFO EXTRACTION] Extracted: {extracted}")
        return extracted
        
    except Exception as e:
        print(f"❌ [INFO EXTRACTION ERROR] {e}")
        return {}
    
    # ======================================================================
# UNKNOWN CALLER LOGIC
# ======================================================================

def handle_unknown_logic(message: str, stage: str, collected_info: dict, caller_id=None):
    """
    Handles calls from unknown people (not family, not delivery).
    """
    # Urgent check always first
    if any(k in message.lower() for k in ['urgent', 'asap', 'emergency']):
        name_to_use = collected_info.get("name", "An unknown caller")
        response_text = "Okay, I understand this is urgent. I am notifying Ruchit immediately."
        action = {"type": "URGENT_NOTIFICATION", "message": f"Urgent call from {name_to_use}."}
        return response_text, "end_of_call", collected_info, action

    intent = detect_user_intent(message)
    action = {}

    if stage == "start":
        return "Hello, you've reached Ruchit's AI assistant. May I know who's calling?", "asking_name", collected_info, action

    if stage == "collecting_contact" and intent == "provide_self_number":
        collected_info['phone'] = "Caller's Number"
        return "Okay, noted. Ruchit will call you back on the number you are calling from. Thank you!", "end_of_call", collected_info, action

    # Try extracting info
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


@app.route("/generate", methods=["POST"])
def generate():
    data = request.get_json(force=True)

    # Extract input fields
    user_msg = data.get("new_message", "")
    stage = data.get("conversation_stage", "start")
    collected_info = data.get("collected_info", {})
    caller_id = data.get("caller_id", None)

    # Run your logic
    response, stage, collected_info, action = handle_unknown_logic(
        message=user_msg,
        stage=stage,
        collected_info=collected_info,
        caller_id=caller_id
    )

    # Send back response as JSON
    return jsonify({
        "response_text": response,
        "stage": stage,
        "collected_info": collected_info,
        "action": action
    })




if __name__ == "__main__":
    print("🚀 Starting Flask API with OpenAI...")
    app.run(port=5001, debug=True)

    collected_info = {}
    stage = "start"

    while True:
        user_msg = input("Caller: ")
        if user_msg.lower() in ["exit", "quit"]:
            break

        response, stage, collected_info, action = handle_unknown_logic(
            message=user_msg,
            stage=stage,
            collected_info=collected_info
        )

        print(f"Assistant: {response}")
        print(f"👉 Stage: {stage} | Info: {collected_info} | Action: {action}")
