"""Text processing utilities for conversation handling (matches original.py flow)"""

import re
import string
from typing import List, Optional, Dict, Any

def clean_location_text(raw_text: str) -> str:
    """Removes filler words from a spoken location for better geocoding (matches original)"""
    cleaned = raw_text.lower()
    cleaned = re.sub(r"^(i(\s*am|'m)?\s*(here\s*)?(in|at|near)\s+)", "", cleaned)
    return cleaned.strip().title()

def extract_phone_number(message: str) -> Optional[str]:
    """Extract phone number from various spoken formats"""
    if not message:
        return None
    
    # Remove common words and clean the message
    cleaned = re.sub(r'\b(call|me|on|at|number|is|my)\b', ' ', message.lower())
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    # Patterns to match different phone number formats
    patterns = [
        # US/International format: (965) 060-6105
        r'\(?(\d{3})\)?[-.\s]*(\d{3})[-.\s]*(\d{4})',
        # Indian format: +91 9876543210
        r'\+?91[-.\s]*(\d{10})',
        # 10 digit: 9876543210
        r'(\d{10})',
        # Spoken format: nine six five zero six zero six one zero five
        r'(\d{3}[-.\s]*\d{3}[-.\s]*\d{4})',
        # Various other formats
        r'(\d{4}[-.\s]*\d{3}[-.\s]*\d{3})',
        r'(\d{2}[-.\s]*\d{4}[-.\s]*\d{4})',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, message)
        if match:
            if len(match.groups()) == 3:  # Three-part number like (965) 060-6105
                phone = match.group(1) + match.group(2) + match.group(3)
            else:
                phone = match.group(1)
            
            # Clean up the phone number - remove all non-digits except +
            phone = re.sub(r'[^\d+]', '', phone)
            
            # Validate length
            if len(phone) >= 10:
                return phone
    
    return None

def format_phone_number(number_string: str):
    """Format phone number for Indian numbers (matches original logic)"""
    if not isinstance(number_string, str): 
        return None
    
    digits = re.sub(r'\D', '', number_string)
    
    if len(digits) == 10: 
        return f"+91{digits}"
    if len(digits) == 12 and digits.startswith('91'): 
        return f"+{digits}"
    
    return digits if digits else None

def format_number_for_speech(number_string: str):
    """Format number for speech (matches original)"""
    if not number_string: 
        return ""
    return " ".join([ch for ch in number_string if ch.isdigit()])

def format_otp_for_speech(otp: str) -> str:
    """Format OTP for clear speech synthesis (matches original)"""
    if not otp:
        return ""
    
    # Remove any non-digit characters
    clean_otp = re.sub(r'\D', '', str(otp))
    
    # Add spaces between digits for clear pronunciation
    return " ".join(clean_otp)

def detect_user_intent(message: str) -> str:
    """Enhanced intent detection with better OTP recognition (matches original.py exactly)"""
    message_lower = message.lower().strip()
    message_cleaned = re.sub(r'[.!?]', '', message_lower)
    
    # Enhanced OTP detection patterns (matching original + Hindi support)
    otp_patterns = [
        'otp', 'one time password', 'code', 'verification code', 
        'pin', 'security code', 'auth code', 'login code',
        'give me the code', 'what is the code', 'tell me the otp',
        'need the otp', 'share the otp', 'provide otp',
        'otp चाहिए', 'ओटीपी चाहिए', 'कोड चाहिए', 'चाहिए otp'
    ]
    
    if any(pattern in message_lower for pattern in otp_patterns):
        return "requesting_otp"
    
    # Check for company + OTP context (enhanced with Hindi support)
    company_keywords = ['amazon', 'flipkart', 'myntra', 'zomato', 'swiggy', 'delivery','zepto','bluedart', 'का', 'से']
    if (any(company in message_lower for company in company_keywords) and 
        any(otp in message_lower for otp in ['code', 'otp', 'pin', 'चाहिए', 'कोड'])):
        return "requesting_otp"
    
    # Rest of existing intent detection logic (matching original exactly)
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

def extract_current_location(message: str) -> Optional[str]:
    """Extract current location from user message"""
    message_lower = message.lower().strip()
    
    # Remove common phrases
    location_patterns = [
        r"i am at (.+)",
        r"currently at (.+)",
        r"from (.+)",
        r"near (.+)",
        r"at (.+)",
        r"my location is (.+)"
    ]
    
    for pattern in location_patterns:
        match = re.search(pattern, message_lower)
        if match:
            location = match.group(1).strip()
            # Clean up common endings
            location = re.sub(r'\s+(now|currently|right now)$', '', location)
            return clean_location_text(location)
    
    # If no pattern matches, try to extract potential location words
    location_words = []
    words = message_lower.split()
    
    for i, word in enumerate(words):
        if word in ["at", "near", "from", "in"]:
            # Take the next few words as potential location
            location_words.extend(words[i+1:i+4])
            break
    
    if location_words:
        location = " ".join(location_words)
        return clean_location_text(location)
    
    return None

def is_navigation_request(message: str) -> bool:
    """Check if message is requesting navigation help"""
    navigation_keywords = [
        "directions", "how to get", "where", "navigate", "guide me",
        "lost", "can't find", "help me reach", "way to", "route"
    ]
    
    message_lower = message.lower()
    return any(keyword in message_lower for keyword in navigation_keywords)

def extract_delivery_destination(message: str) -> Optional[str]:
    """Extract delivery destination from message"""
    # Look for delivery address patterns
    destination_patterns = [
        r"deliver to (.+)",
        r"delivery at (.+)",
        r"going to (.+)",
        r"destination is (.+)",
        r"address is (.+)"
    ]
    
    message_lower = message.lower()
    for pattern in destination_patterns:
        match = re.search(pattern, message_lower)
        if match:
            return clean_location_text(match.group(1))
    
    return None

def extract_company_names(text: str) -> List[str]:
    """Extract delivery company names from text"""
    companies = [
        'swiggy', 'zomato', 'uber eats', 'ubereats', 'dunzo', 'amazon',
        'flipkart', 'myntra', 'big basket', 'bigbasket', 'grofers',
        'blinkit', 'zepto', 'instamart', 'bb daily', 'bluedart'
    ]
    
    found_companies = []
    text_lower = text.lower()
    
    for company in companies:
        if company in text_lower:
            # Normalize company name
            if company == 'uber eats' or company == 'ubereats':
                found_companies.append('Uber Eats')
            elif company == 'big basket' or company == 'bigbasket':
                found_companies.append('BigBasket')
            elif company == 'bluedart':
                found_companies.append('BlueDart')
            else:
                found_companies.append(company.title())
    
    return list(set(found_companies))  # Remove duplicates

# Legacy functions for compatibility
def clean_text_input(text: str) -> str:
    """Clean and normalize user input text"""
    if not text:
        return ""
    
    # Basic cleaning
    text = text.strip()
    text = re.sub(r'\s+', ' ', text)  # Multiple spaces to single space
    text = re.sub(r'[^\w\s\-\.\,\!\?]', '', text)  # Keep basic punctuation
    
    return text

def extract_phone_numbers(text: str) -> List[str]:
    """Extract phone numbers from text"""
    # Indian phone number patterns
    patterns = [
        r'\+91[-\s]?[6-9]\d{9}',  # +91 format
        r'[6-9]\d{9}',            # 10 digit format
        r'0[1-9]\d{8,9}'          # STD format
    ]
    
    phone_numbers = []
    for pattern in patterns:
        matches = re.findall(pattern, text.replace(' ', '').replace('-', ''))
        phone_numbers.extend(matches)
    
    return list(set(phone_numbers))  # Remove duplicates

def extract_order_ids(text: str) -> List[str]:
    """Extract potential order IDs from text"""
    # Common order ID patterns
    patterns = [
        r'[A-Z]{2,4}\d{6,12}',     # SWGY123456789, ZOM123456
        r'\d{10,15}',              # Pure numeric IDs
        r'[A-Z]+\d+[A-Z]*\d*'     # Mixed alphanumeric
    ]
    
    order_ids = []
    for pattern in patterns:
        matches = re.findall(pattern, text.upper())
        order_ids.extend(matches)
    
    return list(set(order_ids))

def extract_addresses(text: str) -> List[str]:
    """Extract potential addresses from text"""
    # Address keywords
    address_keywords = [
        'street', 'road', 'avenue', 'lane', 'block', 'sector', 
        'apartment', 'flat', 'building', 'house', 'floor',
        'near', 'opposite', 'behind', 'front'
    ]
    
    # Look for text containing address keywords
    sentences = re.split(r'[.!?]', text)
    addresses = []
    
    for sentence in sentences:
        sentence = sentence.strip().lower()
        if any(keyword in sentence for keyword in address_keywords):
            addresses.append(sentence.title())
    
    return addresses

def format_location_for_speech(location: str) -> str:
    """Format location information for clear speech"""
    if not location:
        return ""
    
    # Replace common abbreviations
    abbreviations = {
        'st': 'street',
        'rd': 'road',
        'ave': 'avenue',
        'blvd': 'boulevard',
        'apt': 'apartment',
        'bldg': 'building',
        'flr': 'floor'
    }
    
    words = location.lower().split()
    formatted_words = []
    
    for word in words:
        # Remove punctuation for checking
        clean_word = word.strip(string.punctuation)
        if clean_word in abbreviations:
            formatted_words.append(abbreviations[clean_word])
        else:
            formatted_words.append(word)
    
    return ' '.join(formatted_words)

def detect_caller_type(text: str) -> str:
    """Detect caller type from message content (for compatibility)"""
    text_lower = text.lower()
    
    delivery_keywords = [
        'delivery', 'deliver', 'order', 'food', 'pickup', 'collect',
        'swiggy', 'zomato', 'uber eats', 'dunzo', 'amazon',
        'outside', 'gate', 'building', 'apartment', 'otp'
    ]
    
    customer_keywords = [
        'ordered', 'waiting', 'where is my', 'tracking', 'cancel',
        'complaint', 'refund', 'wrong order'
    ]
    
    # Count keyword matches
    delivery_score = sum(1 for keyword in delivery_keywords if keyword in text_lower)
    customer_score = sum(1 for keyword in customer_keywords if keyword in text_lower)
    
    if delivery_score > customer_score:
        return "delivery_person"
    elif customer_score > 0:
        return "customer"
    else:
        return "unknown"

def is_address_query(text: str) -> bool:
    """Check if the message is asking for address/location help"""
    address_indicators = [
        'where', 'address', 'location', 'directions', 'way to reach',
        'how to get', 'find', 'navigate', 'route', 'path'
    ]
    
    text_lower = text.lower()
    return any(indicator in text_lower for indicator in address_indicators)

def is_otp_request(text: str) -> bool:
    """Check if the message is requesting OTP"""
    otp_indicators = [
        'otp', 'code', 'verification', 'pin', 'password',
        'delivery code', 'order code', 'confirm'
    ]
    
    text_lower = text.lower()
    return any(indicator in text_lower for indicator in otp_indicators)

def calculate_confidence_score(text: str, intent: str, caller_type: str) -> float:
    """Calculate confidence score for intent detection"""
    base_confidence = 0.5
    
    # Boost confidence based on keyword matches
    text_lower = text.lower()
    
    if intent == "requesting_otp" and any(word in text_lower for word in ['otp', 'code', 'verification']):
        base_confidence += 0.3
    
    if intent == "providing_location" and any(word in text_lower for word in ['where', 'address', 'location']):
        base_confidence += 0.3
    
    if caller_type == "delivery_person" and intent in ["requesting_otp", "providing_location"]:
        base_confidence += 0.2
    
    return min(base_confidence, 0.95)  # Cap at 95%

def extract_company_from_text(text: str) -> Optional[str]:
    """Extract company name from user text"""
    if not text:
        return None
    
    text_lower = text.lower().strip()
    
    # Common delivery companies and their variations
    company_patterns = {
        "zomato": ["zomato", "zmt"],
        "swiggy": ["swiggy", "swg"],
        "amazon": ["amazon", "amzn", "amz"],
        "flipkart": ["flipkart", "fkrt", "fk"],
        "bigbasket": ["bigbasket", "big basket", "bb"],
        "dunzo": ["dunzo"],
        "myntra": ["myntra"],
        "bluedart": ["bluedart", "blue dart"],
        "delhivery": ["delhivery"],
        "fedex": ["fedex"],
        "paytm": ["paytm"],
        "phonepe": ["phonepe", "phone pe"],
        "gpay": ["gpay", "google pay"],
    }
    
    # Look for exact matches first
    for company, patterns in company_patterns.items():
        for pattern in patterns:
            if pattern in text_lower:
                return company.title()
    
    # If no match found, return the text as-is (cleaned up)
    # Remove common words
    cleaned_text = re.sub(r'\b(from|for|of|the|a|an)\b', '', text_lower).strip()
    if cleaned_text and len(cleaned_text) > 2:
        return cleaned_text.title()
    
    return None