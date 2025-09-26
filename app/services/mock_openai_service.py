"""Mock OpenAI service for testing conversations (simplified)"""

import time
import random
import json
from typing import Dict, Any, List, Optional

class MockOpenAIService:
    """Mock OpenAI service for generating conversation responses"""
    
    def __init__(self, config=None):
        self.config = config
        self.call_count = 0
    
    def extract_information_with_ai(self, message: str, collected_info: Dict[str, Any]) -> Dict[str, Any]:
        """Mock information extraction (matches original.py logic)"""
        extracted = {}
        message_lower = message.lower()
        
        # Extract company names
        companies = ['amazon', 'flipkart', 'swiggy', 'zomato', 'dunzo', 'zepto', 'bluedart', 'myntra']
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
        
        # Extract phone numbers (basic pattern)
        import re
        phone_pattern = r'(\+91[-\s]?)?[6-9]\d{9}'
        phone_match = re.search(phone_pattern, message)
        if phone_match:
            extracted["phone"] = phone_match.group(0)
        
        return extracted
    
    def enhance_search_query_with_ai(self, query: str) -> List[str]:
        """Mock query enhancement for location search"""
        enhanced_queries = []
        
        # Add "near me" variant
        enhanced_queries.append(f"{query} near me")
        
        # Add "Bengaluru" variant
        enhanced_queries.append(f"{query} Bengaluru")
        
        # Add original query
        enhanced_queries.append(query)
        
        # Add restaurant variant for short queries
        if len(query.split()) < 3:
            enhanced_queries.append(f"{query} restaurant")
        
        return enhanced_queries[:4]
    
    def generate_conversation_summary(self, conversation_history: List[Dict[str, Any]], collected_info: Dict[str, Any] = None) -> str:
        """Generate a simple conversation summary"""
        if not conversation_history:
            return "No conversation to summarize"
        
        # Simple summary based on collected info
        company = collected_info.get("company") if collected_info else None
        
        if company:
            return f"Delivery person from {company} called for assistance. Provided directions and OTP support. Call completed successfully."
        else:
            return "Customer called for assistance. Collected contact information. Call completed successfully."