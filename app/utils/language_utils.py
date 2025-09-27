"""
Language detection utilities for multi-lingual support
"""

import re
from typing import Dict, Any

def detect_language(text: str) -> str:
    """
    Detect language from text - supports Hindi and English
    Returns 'hi' for Hindi, 'en' for English
    """
    if not text or not text.strip():
        return 'en'  # Default to English
    
    text = text.strip()
    
    # Check for Devanagari script (Hindi)
    devanagari_pattern = r'[\u0900-\u097F]'
    if re.search(devanagari_pattern, text):
        return 'hi'
    
    # Check for common Hindi words in Romanized form
    hindi_keywords = [
        'hai', 'hain', 'aur', 'kya', 'kaise', 'kahan', 'kab', 'kaun',
        'mere', 'mera', 'aapka', 'aap', 'hum', 'main', 'ye', 'vo',
        'delivery', 'parcel', 'package', 'amazon', 'flipkart',
        'namaste', 'dhanyawad', 'kripaya', 'madat', 'chahiye'
    ]
    
    text_lower = text.lower()
    hindi_word_count = sum(1 for word in hindi_keywords if word in text_lower)
    
    # If we find multiple Hindi words, consider it Hindi
    if hindi_word_count >= 2:
        return 'hi'
    
    # Check for mixed usage - if there are some Hindi indicators but also English
    if hindi_word_count >= 1 and any(word in text_lower for word in ['delivery', 'amazon', 'flipkart']):
        return 'hi'  # Treat as Hindi context
    
    # Default to English
    return 'en'

def get_language_config(language: str) -> Dict[str, Any]:
    """
    Get configuration for specific language
    """
    configs = {
        'hi': {
            'name': 'Hindi',
            'code': 'hi',
            'greeting': 'नमस्ते',
            'thank_you': 'धन्यवाद',
            'welcome': 'आपका स्वागत है',
            'help': 'मदद',
            'delivery': 'डिलीवरी',
            'otp': 'ओटीपी'
        },
        'en': {
            'name': 'English',
            'code': 'en',
            'greeting': 'Hello',
            'thank_you': 'Thank you',
            'welcome': 'Welcome',
            'help': 'help',
            'delivery': 'delivery',
            'otp': 'OTP'
        }
    }
    
    return configs.get(language, configs['en'])

def format_mixed_text(text: str, target_language: str) -> str:
    """
    Format text for better pronunciation in target language
    """
    if target_language == 'hi':
        # Keep numbers and company names in English for better TTS
        text = re.sub(r'\b(amazon|flipkart|swiggy|zomato|zepto|myntra|bluedart)\b', 
                     lambda m: m.group(0).title(), text, flags=re.IGNORECASE)
    
    return text

def get_response_templates(language: str) -> Dict[str, str]:
    """
    Get response templates for specific language
    """
    templates = {
        'en': {
            'greeting': "Hello! How may I assist you today?",
            'delivery_help': "Thank you! I can help with your delivery. Are you here or do you need directions?",
            'need_directions': "I'll help you get here. Let me get the directions for you.",
            'arrived': "Great! You've arrived. Do you need the OTP for delivery?",
            'otp_provide': "Here's your OTP for {company}: {otp}",
            'unknown_caller': "Hello! I'm an AI assistant. May I know who's calling and how I can help you?",
            'collect_name': "May I know who's calling?",
            'collect_purpose': "Thanks {name}. What's the purpose of your call today?",
            'urgent_matter': "This seems urgent. I'll notify the owner immediately.",
            'callback_info': "I'll let them know you called. Is {phone} the best number to reach you?"
        },
        'hi': {
            'greeting': "नमस्ते! मैं आपकी कैसे मदद कर सकता हूँ?",
            'delivery_help': "धन्यवाद! आपकी डिलीवरी के लिए मैं आपकी मदद कर सकता हूँ। क्या आप यहाँ हैं या आपको रास्ता चाहिए?",
            'need_directions': "मैं आपको यहाँ पहुँचने में मदद करूंगा। मैं आपके लिए रास्ता निकालता हूँ।",
            'arrived': "बहुत अच्छा! आप पहुँच गए हैं। क्या आपको डिलीवरी के लिए OTP चाहिए?",
            'otp_provide': "यहाँ {company} के लिए आपका OTP है: {otp}",
            'unknown_caller': "नमस्ते! मैं एक AI असिस्टेंट हूँ। कृपया बताएं आप कौन हैं और मैं आपकी कैसे मदद कर सकता हूँ?",
            'collect_name': "कृपया बताएं आप कौन हैं?",
            'collect_purpose': "धन्यवाद {name}। आज आपके कॉल का क्या उद्देश्य है?",
            'urgent_matter': "यह जरूरी लग रहा है। मैं तुरंत मालिक को सूचित करूंगा।",
            'callback_info': "मैं उन्हें बताऊंगा कि आपने कॉल किया था। क्या {phone} आपसे संपर्क करने के लिए सबसे अच्छा नंबर है?"
        }
    }
    
    return templates.get(language, templates['en'])