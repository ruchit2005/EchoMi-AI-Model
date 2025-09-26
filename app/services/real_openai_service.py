"""Real OpenAI service implementation"""

import json
from typing import Dict, Any, Optional

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    OpenAI = None

class RealOpenAIService:
    """Real OpenAI service for production use"""
    
    def __init__(self, config):
        self.config = config
        self.api_key = config.OPENAI_API_KEY
        self.client = None
        self.call_count = 0
        
        if OPENAI_AVAILABLE and self.api_key:
            try:
                self.client = OpenAI(api_key=self.api_key)
            except Exception as e:
                print(f"⚠️ OpenAI client initialization failed: {e}")
                self.client = None
        elif not OPENAI_AVAILABLE:
            print("⚠️ OpenAI package not installed. Using fallback mode.")
        else:
            print("⚠️ OpenAI API key not configured. Using fallback mode.")
    
    def extract_information_with_ai(self, message: str, collected_info: Dict[str, Any]) -> Dict[str, Any]:
        """Enhanced information extraction with better prompting for delivery companies (matches original.py)"""
        if not self.client:
            # Fallback to simple extraction if no API key
            return self._fallback_extraction(message, collected_info)
        
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
            
            response = self.client.chat.completions.create(
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
            
            # Format phone number if found
            if extracted.get("phone"):
                from ..utils.text_processing import format_phone_number
                formatted = format_phone_number(extracted["phone"])
                if formatted: 
                    extracted["phone"] = formatted
                else: 
                    del extracted["phone"]
            
            # Format company name
            if extracted.get("company"):
                extracted["company"] = extracted["company"].strip().title()
                
            self.call_count += 1
            return extracted
            
        except Exception as e:
            print(f"❌ [INFO EXTRACTION ERROR] {e}")
            return self._fallback_extraction(message, collected_info)
    
    def _fallback_extraction(self, message: str, collected_info: Dict[str, Any]) -> Dict[str, Any]:
        """Simple fallback extraction when OpenAI is not available"""
        extracted = {}
        message_lower = message.lower()
        
        # Extract company names
        companies = ['amazon', 'flipkart', 'swiggy', 'zomato', 'dunzo', 'zepto', 'bluedart']
        for company in companies:
            if company in message_lower:
                extracted["company"] = company.title()
                break
        
        # Extract names (simple pattern matching)
        if any(phrase in message_lower for phrase in ["my name is", "i am", "this is"]):
            words = message.split()
            for i, word in enumerate(words):
                if word.lower() in ["is", "am"] and i + 1 < len(words):
                    potential_name = words[i + 1].strip()
                    if potential_name.isalpha() and len(potential_name) > 1:
                        extracted["name"] = potential_name.title()
                        break
        
        return extracted
    
    def generate_conversation_summary(self, conversation_history: list, collected_info: Dict[str, Any] = None) -> str:
        """Generate a 50-70 word summary of the conversation (matches original.py)"""
        if not self.client or not conversation_history:
            return self._fallback_summary(collected_info)
        
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

            response = self.client.chat.completions.create(
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
            
            self.call_count += 1
            return summary
            
        except Exception as e:
            print(f"❌ [SUMMARY ERROR] {e}")
            return self._fallback_summary(collected_info)
    
    def _fallback_summary(self, collected_info: Dict[str, Any] = None) -> str:
        """Simple fallback summary when OpenAI is not available"""
        if not collected_info:
            return "Phone conversation completed successfully."
        
        company = collected_info.get("company")
        if company:
            return f"Delivery person from {company} called for assistance. Provided directions and OTP as needed. Call completed successfully."
        else:
            return f"Unknown caller contacted for assistance. Collected contact information and forwarded to Ruchit. Call completed successfully."