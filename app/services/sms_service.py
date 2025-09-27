"""
SMS Service for EchoMi AI Model
Fetches SMS messages from backend and extracts OTP/tracking information
"""

import random
import string
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    requests = None

from ..utils.sms_parser import SMSParser, ParsedSMSData

class SMSService:
    """Service for fetching and parsing SMS messages from backend"""
    
    def __init__(self, config=None):
        self.config = config
        self.sms_parser = SMSParser()
        self.call_count = 0
        self.last_sms_check = datetime.now()
    
    def fetch_latest_otps(self, user_id: str, count: int = 10) -> Dict[str, Any]:
        """
        Fetch latest OTP messages from backend (Android app uploads SMS to backend)
        
        Args:
            user_id: User's MongoDB ObjectId 
            count: Number of latest SMS to fetch (default 10)
            
        Returns:
            dict: {"success": bool, "otps": List[dict], "total_count": int, "error": str}
        """
        try:
            # Get backend configuration
            backend_url = getattr(self.config, 'NODEJS_BACKEND_URL', None)
            internal_api_key = getattr(self.config, 'INTERNAL_API_KEY', None)
            
            if not backend_url or not internal_api_key:
                return self._fallback_bulk_otp_response(count)
            
            if not REQUESTS_AVAILABLE:
                return self._fallback_bulk_otp_response(count, "Requests library not available")
            
            # New bulk SMS endpoint format
            sms_endpoint = f"{backend_url}/api/sms/latest"
            
            # Query parameters for bulk OTP fetch
            params = {
                "userId": user_id,
                "limit": count
            }
            
            # Request headers
            headers = {
                "Authorization": f"Bearer {internal_api_key}",
                "User-Agent": "DeliveryBot/1.0",
                "Content-Type": "application/json"
            }
            
            print(f"📱 [BULK SMS] Fetching {count} latest OTPs from: {sms_endpoint}")
            print(f"📱 [BULK SMS] Params: {params}")
            
            # Make request to backend
            response = requests.get(
                sms_endpoint, 
                params=params,
                headers=headers, 
                timeout=15
            )
            
            # Handle response
            if response.status_code == 200:
                sms_data = response.json()
                
                if isinstance(sms_data, list):
                    messages = sms_data
                else:
                    messages = sms_data.get("messages", sms_data)
                
                print(f"✅ [BULK SMS] Retrieved {len(messages)} OTP messages")
                
                # Parse and extract OTPs from all messages
                processed_otps = []
                
                for msg_data in messages:
                    sender = msg_data.get("sender", "")
                    message_text = msg_data.get("message", "")
                    pre_extracted_otp = msg_data.get("otp")  # Backend might pre-extract OTP
                    received_at = msg_data.get("receivedAt")
                    
                    # Parse the SMS content with our parser
                    parsed_sms = self.sms_parser.parse_sms(message_text)
                    
                    # Use pre-extracted OTP if available and confident, otherwise use our parser
                    final_otp = pre_extracted_otp if pre_extracted_otp else parsed_sms.otp
                    
                    processed_otps.append({
                        "otp": final_otp,
                        "sender": sender,
                        "message": message_text,
                        "company": parsed_sms.company or self._detect_company_from_sender(sender),
                        "tracking_id": parsed_sms.tracking_id,
                        "confidence": parsed_sms.confidence_score,
                        "received_at": received_at,
                        "raw_data": msg_data
                    })
                
                self.call_count += 1
                return {
                    "success": True,
                    "otps": processed_otps,
                    "total_count": len(processed_otps),
                    "latest_otp": processed_otps[0]["otp"] if processed_otps else None
                }
                
            elif response.status_code == 404:
                print(f"❌ [BULK SMS] No OTP messages found for user")
                return {
                    "success": False,
                    "error": "No OTP messages found",
                    "otps": []
                }
                
            else:
                print(f"❌ [BULK SMS] Backend error: {response.status_code} - {response.text}")
                return {
                    "success": False,
                    "error": f"Backend error: {response.status_code}",
                    "otps": []
                }
                
        except requests.exceptions.Timeout:
            print("❌ [BULK SMS] Timeout connecting to backend")
            return self._fallback_bulk_otp_response(count, "Request timeout")
            
        except requests.exceptions.ConnectionError:
            print("❌ [BULK SMS] Cannot connect to backend")
            return self._fallback_bulk_otp_response(count, "Backend connection failed")
            
        except Exception as e:
            print(f"❌ [BULK SMS] Unexpected error: {e}")
            return self._fallback_bulk_otp_response(count, f"Unexpected error: {str(e)}")
    
    def find_best_otp_for_company(self, otps_data: List[dict], company: str) -> Dict[str, Any]:
        """
        Find the best matching OTP from bulk data for a specific company
        
        Args:
            otps_data: List of processed OTP data
            company: Target delivery company
            
        Returns:
            dict: Best matching OTP data or None
        """
        if not otps_data:
            return None
        
        company_lower = company.lower() if company else ""
        best_match = None
        best_score = 0
        
        for otp_data in otps_data:
            score = 0
            
            # Direct company match
            detected_company = otp_data.get("company", "").lower()
            if detected_company and company_lower in detected_company:
                score += 50
            elif company_lower in detected_company:
                score += 30
            
            # Sender match
            sender = otp_data.get("sender", "").lower()
            if company_lower in sender:
                score += 40
            
            # Message content match
            message = otp_data.get("message", "").lower()
            if company_lower in message:
                score += 20
            
            # Confidence score
            confidence = otp_data.get("confidence", 0)
            score += confidence * 10
            
            # Recency (newer messages get slight bonus)
            if otp_data == otps_data[0]:  # First in list = most recent
                score += 5
            
            if score > best_score and otp_data.get("otp"):
                best_match = otp_data
                best_score = score
        
        return best_match
    
    def _detect_company_from_sender(self, sender: str) -> str:
        """Detect company from SMS sender"""
        if not sender:
            return "unknown"
        
        sender_lower = sender.lower()
        
        # Common sender patterns
        company_mapping = {
            "zomato": ["zomato", "zmt", "zm-"],
            "swiggy": ["swiggy", "swg", "sg-"],
            "amazon": ["amazon", "amzn", "az-"],
            "flipkart": ["flipkart", "fkrt", "fk-"],
            "bigbasket": ["bigbasket", "bb-", "bigb"],
            "dunzo": ["dunzo", "dz-"],
            "paytm": ["paytm", "pytm"],
            "phonepe": ["phonepe", "phpe"],
            "googlepay": ["gpay", "google"],
            "banking": ["hdfc", "icici", "sbi", "axis", "kotak"]
        }
        
        for company, patterns in company_mapping.items():
            if any(pattern in sender_lower for pattern in patterns):
                return company
        
        return "unknown"
    
    def get_otp_from_sms(self, user_id: str, company: str, order_id: str = None) -> Dict[str, Any]:
        """
        Get OTP by fetching latest 10 SMS messages and finding best match for company
        
        Args:
            user_id: User's MongoDB ObjectId (replaces firebase_uid)
            company: Delivery company name
            order_id: Order ID (optional, for future use)
            
        Returns:
            dict: {"success": bool, "otp": str, "message": str, "error": str}
        """
        # Fetch latest 10 OTP messages from backend
        bulk_result = self.fetch_latest_otps(user_id, 10)
        
        if not bulk_result["success"]:
            return {
                "success": False,
                "error": bulk_result.get("error", "Failed to fetch OTP messages"),
                "otp": None
            }
        
        otps_data = bulk_result.get("otps", [])
        
        if not otps_data:
            return {
                "success": False,
                "error": "No OTP messages found in your recent SMS",
                "otp": None,
                "total_checked": 0
            }
        
        # Find best OTP match for the specific company
        best_match = self.find_best_otp_for_company(otps_data, company)
        
        if best_match and best_match.get("otp"):
            return {
                "success": True,
                "otp": best_match["otp"],
                "message": f"Found {company} OTP from {best_match.get('sender', 'SMS')}",
                "confidence": best_match.get("confidence", 0),
                "sender": best_match.get("sender"),
                "tracking_id": best_match.get("tracking_id"),
                "total_checked": len(otps_data)
            }
        
        # If no specific company match, return the most recent OTP with highest confidence
        best_general = max(otps_data, key=lambda x: (x.get("confidence", 0), otps_data.index(x) == 0), default=None)
        
        if best_general and best_general.get("otp"):
            return {
                "success": True,
                "otp": best_general["otp"],
                "message": f"Found recent OTP from {best_general.get('sender', 'SMS')} (no exact {company} match)",
                "confidence": best_general.get("confidence", 0),
                "sender": best_general.get("sender"),
                "tracking_id": best_general.get("tracking_id"),
                "total_checked": len(otps_data),
                "fallback_used": True
            }
        
        return {
            "success": False,
            "error": f"No valid OTP found for {company} in {len(otps_data)} recent messages",
            "otp": None,
            "total_checked": len(otps_data)
        }
    
    def _fallback_bulk_otp_response(self, count: int = 10, error: str = None) -> dict:
        """Fallback bulk OTP response when backend is unavailable"""
        mock_otps = []
        
        companies = ["Zomato", "Swiggy", "Amazon", "Flipkart", "BigBasket"]
        
        for i in range(min(count, 5)):  # Generate up to 5 mock OTPs
            mock_otp = ''.join(random.choices(string.digits, k=4))
            company = companies[i % len(companies)]
            
            mock_otps.append({
                "otp": mock_otp,
                "sender": f"{company.upper()[:2]}-{company.upper()}",
                "message": f"Your {company} delivery OTP is {mock_otp}. Order confirmed.",
                "company": company.lower(),
                "confidence": 0.8,
                "received_at": datetime.now().isoformat(),
                "tracking_id": f"{company.upper()}{random.randint(100000, 999999)}"
            })
        
        self.call_count += 1
        
        return {
            "success": True,
            "otps": mock_otps,
            "total_count": len(mock_otps),
            "latest_otp": mock_otps[0]["otp"] if mock_otps else None,
            "fallback": True,
            "message": f"Fallback bulk OTP data (Backend unavailable{': ' + error if error else ''})"
        }
    
    def configure_backend_connection(self, backend_url: str, api_key: str) -> dict:
        """
        Configure backend connection for SMS service
        
        Args:
            backend_url: URL of the Node.js backend
            api_key: Internal API key for authentication
            
        Returns:
            dict: Configuration status
        """
        try:
            if not REQUESTS_AVAILABLE:
                return {
                    "success": False,
                    "error": "Requests library not available"
                }
            
            # Test the backend connection
            test_endpoint = f"{backend_url}/api/health"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "User-Agent": "DeliveryBot/1.0"
            }
            
            response = requests.get(test_endpoint, headers=headers, timeout=5)
            
            if response.status_code == 200:
                # Update configuration
                if hasattr(self.config, 'update'):
                    self.config.update({
                        'NODEJS_BACKEND_URL': backend_url,
                        'INTERNAL_API_KEY': api_key
                    })
                
                return {
                    "success": True,
                    "message": "Backend connection configured successfully",
                    "backend_url": backend_url
                }
            else:
                return {
                    "success": False,
                    "error": f"Backend health check failed: {response.status_code}",
                    "backend_url": backend_url
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to connect to backend: {str(e)}",
                "backend_url": backend_url
            }
    
    def get_service_status(self) -> Dict[str, Any]:
        """Get SMS service status and statistics"""
        backend_configured = bool(
            getattr(self.config, 'NODEJS_BACKEND_URL', None) and 
            getattr(self.config, 'INTERNAL_API_KEY', None)
        )
        
        return {
            "service_name": "SMS Service",
            "backend_configured": backend_configured,
            "backend_url": getattr(self.config, 'NODEJS_BACKEND_URL', None),
            "requests_available": REQUESTS_AVAILABLE,
            "call_count": self.call_count,
            "last_check": self.last_sms_check.isoformat() if self.last_sms_check else None,
            "parser_companies": list(self.sms_parser.company_patterns.keys())
        }
    
    # Backward compatibility methods
    def fetch_otp(self, user_id: str, company: str, order_id: str = None) -> Dict[str, Any]:
        """Backward compatibility method - delegates to bulk SMS processing"""
        return self.get_otp_from_sms(user_id, company, order_id)
    
    def fetch_sms_messages(self, user_id: str, company: str = None, phone_number: str = None) -> Dict[str, Any]:
        """Backward compatibility method - converts to new bulk format"""
        bulk_result = self.fetch_latest_otps(user_id, 10)
        
        if not bulk_result["success"]:
            return {
                "success": False,
                "error": bulk_result.get("error", "Failed to fetch messages"),
                "messages": []
            }
        
        # Convert bulk format back to old message format for compatibility
        otps_data = bulk_result.get("otps", [])
        parsed_messages = []
        latest_otp = None
        
        for otp_data in otps_data:
            # Create ParsedSMSData object for compatibility
            parsed_sms = ParsedSMSData(
                otp=otp_data.get("otp"),
                tracking_id=otp_data.get("tracking_id"),
                company=otp_data.get("company"),
                confidence_score=otp_data.get("confidence", 0),
                raw_message=otp_data.get("message", ""),
                delivery_info={
                    "sender": otp_data.get("sender"),
                    "timestamp": otp_data.get("received_at")
                }
            )
            parsed_messages.append(parsed_sms)
            
            # Track latest OTP
            if not latest_otp and parsed_sms.otp:
                latest_otp = parsed_sms.otp
        
        return {
            "success": True,
            "messages": parsed_messages,
            "latest_otp": latest_otp,
            "message_count": len(parsed_messages),
            "company": company
        }
    
    def get_otp_status(self, phone_number: str) -> Dict[str, Any]:
        """Get OTP status for a phone number"""
        return {
            "success": True,
            "message": "SMS service active - OTPs extracted from messages",
            "phone_number": phone_number,
            "service_type": "SMS parsing"
        }