from openai import OpenAI
import os
from dotenv import load_dotenv
from flask import Flask, request, jsonify
import json
import re

app = Flask(__name__)
load_dotenv()

# ======================================================================
# OpenAI Client
# ======================================================================

try:
    openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    print("✅ OpenAI Client initialized successfully.")
except Exception as e:
    print(f"❌ Error initializing OpenAI Client: {e}")
    openai_client = None
    exit(1)

# ======================================================================
# HELPER FUNCTIONS
# ======================================================================

def format_phone_number(number_string: str):
    if not isinstance(number_string, str):
        return None
    digits = re.sub(r'\D', '', number_string)
    if len(digits) == 10:
        return f"+91{digits}"
    if len(digits) == 12 and digits.startswith('91'):
        return f"+{digits}"
    return digits if digits else None

def format_number_for_speech(number_string: str):
    if not number_string:
        return ""
    return " ".join([ch for ch in number_string if ch.isdigit()])

def detect_user_intent(message: str):
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
            temperature=0.2,
            max_tokens=200
        )

        extracted_text = response.choices[0].message.content.strip()
        extracted = json.loads(extracted_text)

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

# ======================================================================
# UNKNOWN CALLER LOGIC
# ======================================================================

def handle_unknown_logic(message: str, stage: str, collected_info: dict, caller_id=None):
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

# ======================================================================
# ROUTES
# ======================================================================

@app.route("/generate", methods=["POST"])
def generate():
    data = request.get_json(force=True)
    new_message = data.get("new_message","").strip()
    caller_role = data.get("caller_role","unknown")
    history = data.get("history", []) or []
    stage = data.get("conversation_stage","start")
    collected_info = data.get("collected_info", {}) or {}

    if not new_message:
        return jsonify({"error":"'new_message' is required"}), 400

    if caller_role != "unknown":
        caller_role = "unknown"

    intent = detect_user_intent(new_message)

    response_text, new_stage, updated_info, action = handle_unknown_logic(
        new_message, stage, collected_info
    )

    updated_history = history + [
        {"role":"user","parts":[new_message]},
        {"role":"model","parts":[response_text]}
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

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status":"healthy"})

if __name__ == "__main__":
    print("🚀 Starting Flask API on :5001 ...")
    app.run(port=5001, debug=True)
