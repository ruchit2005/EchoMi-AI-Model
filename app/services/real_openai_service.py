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
        """AI-powered extraction with intelligent company name correction for misheard audio"""
        if not self.client:
            # Fallback to simple extraction if no API key
            return self._fallback_extraction(message, collected_info)
        
        print("--- [INFO EXTRACTION] Attempting to extract info ---")
        print(f"--- [INFO EXTRACTION] Message: '{message}' ---")
        
        try:
            system_prompt = """You are an expert at understanding phone conversations with delivery personnel, even when audio transcription is imperfect.

CONTEXT: Audio transcription systems often mishear company names. Your job is to intelligently identify and CORRECT these errors.

Common mishearings you should recognize and fix:
- "speaky", "sweegy", "sweeji" → Swiggy
- "zoomato", "zometto" → Zomato  
- "amazen", "amazone", "amzon" → Amazon
- "flipcart", "flipcard" → Flipkart
- "stick see", "dtic" → DTDC
- "uber eat" → Uber Eats
- And ANY OTHER similar phonetic errors for delivery/courier companies

Extract these fields:
- "name": ONLY the person's actual name (extract from "My name is X", "I am X", "This is X")
- "purpose": Reason for calling (if mentioned)
- "phone": Phone number (if mentioned)  
- "company": The CORRECTED company name (use your intelligence to fix mishearings)

CRITICAL RULES:
1. For names: Extract ONLY the actual name, NOT the phrase "my name is" or "I am"
2. Use your knowledge of common Indian/global delivery companies to correct misspellings
3. Return ONLY valid JSON

Examples:
- "My name is Ruchit" → {"name": "Ruchit"}
- "I am John calling" → {"name": "John"}
- "This is Priya" → {"name": "Priya"}
- "I have delivery from speaky" → {"company": "Swiggy"}
- "delivery from amazen" → {"company": "Amazon"}
- "My name is राज from zoomato" → {"name": "राज", "company": "Zomato"}
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
            
            # Clean and format extracted name (in case AI didn't follow instructions perfectly)
            if extracted.get("name"):
                import re
                name = extracted["name"]
                # Remove common prefixes if they somehow got included
                name = re.sub(r'^(my name is|i am|this is|i\'m)\s+', '', name, flags=re.IGNORECASE).strip()
                # Capitalize properly
                extracted["name"] = name.title()
            
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
        """Simple fallback extraction when OpenAI is not available - now with fuzzy matching"""
        extracted = {}
        message_lower = message.lower()
        
        # Extract company names with fuzzy matching for misheard words
        from ..utils.text_processing import extract_company_with_fuzzy_matching
        company = extract_company_with_fuzzy_matching(message)
        if company:
            extracted["company"] = company
        
        # Extract names (improved pattern matching)
        import re
        
        # Pattern 1: "My name is X" or "my name is X"
        name_patterns = [
            r'my name is\s+([a-zA-Z\u0900-\u097F]+)',  # Includes Hindi characters
            r'i am\s+([a-zA-Z\u0900-\u097F]+)',
            r'this is\s+([a-zA-Z\u0900-\u097F]+)',
            r'i\'m\s+([a-zA-Z\u0900-\u097F]+)',
        ]
        
        for pattern in name_patterns:
            match = re.search(pattern, message_lower, re.IGNORECASE)
            if match:
                potential_name = match.group(1).strip()
                # Capitalize properly (handles both English and Hindi)
                if potential_name.isalpha() and len(potential_name) > 1:
                    extracted["name"] = potential_name.title()
                    print(f"✅ [FALLBACK] Extracted name: {extracted['name']}")
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