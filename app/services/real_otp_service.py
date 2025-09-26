"""Real OTP service implementation"""

import random
import string
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    requests = None

class RealOTPService:
    """Real OTP service for production SMS and call functionality"""
    
    def __init__(self, config):
        self.config = config
        self.sms_api_key = getattr(config, 'SMS_API_KEY', None)
        self.call_api_key = getattr(config, 'CALL_API_KEY', None)
        self.otp_store = {}  # In production, use Redis or database
        self.call_count = 0
    
    def generate_otp(self) -> str:
        """Generate a 6-digit OTP"""
        return ''.join(random.choices(string.digits, k=6))
    
    def send_otp_via_sms(self, phone_number: str, customer_name: str = None) -> Dict[str, Any]:
        """Send OTP via SMS using real SMS service (matches original.py)"""
        try:
            otp = self.generate_otp()
            
            # Store OTP with expiration (5 minutes)
            self.otp_store[phone_number] = {
                'otp': otp,
                'expires_at': datetime.now() + timedelta(minutes=5),
                'attempts': 0
            }
            
            if self.sms_api_key and self.config.ENABLE_REAL_SMS and REQUESTS_AVAILABLE:
                # Use real SMS service (example with Twilio or MSG91)
                result = self._send_real_sms(phone_number, otp, customer_name)
                if result['success']:
                    self.call_count += 1
                    return {
                        'success': True,
                        'message': f'OTP sent via SMS to {phone_number}',
                        'otp': otp if self.config.DEBUG else None,  # Only in debug mode
                        'method': 'SMS'
                    }
            
            # Fallback to mock/debug mode
            self.call_count += 1
            return {
                'success': True,
                'message': f'OTP sent via SMS to {phone_number} (Debug mode)',
                'otp': otp,  # Always show in fallback mode
                'method': 'SMS_DEBUG'
            }
            
        except Exception as e:
            print(f"❌ SMS OTP error: {e}")
            return {
                'success': False,
                'message': f'Failed to send OTP via SMS: {str(e)}',
                'method': 'SMS'
            }
    
    def send_otp_via_call(self, phone_number: str, customer_name: str = None) -> Dict[str, Any]:
        """Send OTP via voice call using real call service (matches original.py)"""
        try:
            otp = self.generate_otp()
            
            # Store OTP with expiration (5 minutes)
            self.otp_store[phone_number] = {
                'otp': otp,
                'expires_at': datetime.now() + timedelta(minutes=5),
                'attempts': 0
            }
            
            if self.call_api_key and self.config.ENABLE_REAL_CALLS and REQUESTS_AVAILABLE:
                # Use real voice call service
                result = self._make_real_call(phone_number, otp, customer_name)
                if result['success']:
                    self.call_count += 1
                    return {
                        'success': True,
                        'message': f'OTP sent via voice call to {phone_number}',
                        'otp': otp if self.config.DEBUG else None,  # Only in debug mode
                        'method': 'CALL'
                    }
            
            # Fallback to mock/debug mode
            self.call_count += 1
            return {
                'success': True,
                'message': f'OTP sent via voice call to {phone_number} (Debug mode)',
                'otp': otp,  # Always show in fallback mode
                'method': 'CALL_DEBUG'
            }
            
        except Exception as e:
            print(f"❌ Voice call OTP error: {e}")
            return {
                'success': False,
                'message': f'Failed to send OTP via voice call: {str(e)}',
                'method': 'CALL'
            }
    
    def verify_otp(self, phone_number: str, provided_otp: str) -> Dict[str, Any]:
        """Verify the OTP provided by the customer"""
        if phone_number not in self.otp_store:
            return {
                'valid': False,
                'message': 'No OTP found for this number. Please request a new OTP.'
            }
        
        otp_data = self.otp_store[phone_number]
        
        # Check if OTP has expired
        if datetime.now() > otp_data['expires_at']:
            del self.otp_store[phone_number]
            return {
                'valid': False,
                'message': 'OTP has expired. Please request a new OTP.'
            }
        
        # Check attempts limit
        if otp_data['attempts'] >= 3:
            del self.otp_store[phone_number]
            return {
                'valid': False,
                'message': 'Too many attempts. Please request a new OTP.'
            }
        
        # Verify OTP
        if provided_otp == otp_data['otp']:
            del self.otp_store[phone_number]
            return {
                'valid': True,
                'message': 'OTP verified successfully!'
            }
        else:
            otp_data['attempts'] += 1
            return {
                'valid': False,
                'message': f'Invalid OTP. {3 - otp_data["attempts"]} attempts remaining.'
            }
    
    def _send_real_sms(self, phone_number: str, otp: str, customer_name: str = None) -> Dict[str, Any]:
        """Send SMS using real SMS service (Twilio/MSG91/etc.)"""
        try:
            # Example with MSG91 API (adjust based on your SMS provider)
            name_part = f"Hi {customer_name}, " if customer_name else ""
            message = f"{name_part}Your delivery verification OTP is: {otp}. Valid for 5 minutes. - EchoMi"
            
            # MSG91 example (replace with your SMS provider)
            url = "https://api.msg91.com/api/v5/otp"
            headers = {
                "authkey": self.sms_api_key,
                "Content-Type": "application/json"
            }
            payload = {
                "template_id": "YOUR_TEMPLATE_ID",  # Replace with your template ID
                "mobile": phone_number,
                "message": message
            }
            
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            
            if response.status_code == 200:
                return {'success': True, 'response': response.json()}
            else:
                return {'success': False, 'error': f"SMS API error: {response.status_code}"}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _make_real_call(self, phone_number: str, otp: str, customer_name: str = None) -> Dict[str, Any]:
        """Make voice call using real call service (Twilio/etc.)"""
        try:
            # Example with Twilio Voice API (adjust based on your call provider)
            name_part = f"Hi {customer_name}, " if customer_name else ""
            message = f"{name_part}Your delivery verification O T P is: {' '.join(otp)}. I repeat, your O T P is: {' '.join(otp)}. Valid for 5 minutes."
            
            # Twilio example (replace with your call provider)
            url = f"https://api.twilio.com/2010-04-01/Accounts/{self.config.TWILIO_ACCOUNT_SID}/Calls.json"
            
            payload = {
                "From": self.config.TWILIO_PHONE_NUMBER,
                "To": phone_number,
                "Twiml": f"<Response><Say voice='alice'>{message}</Say></Response>"
            }
            
            response = requests.post(
                url, 
                data=payload, 
                auth=(self.config.TWILIO_ACCOUNT_SID, self.call_api_key),
                timeout=10
            )
            
            if response.status_code == 201:
                return {'success': True, 'response': response.json()}
            else:
                return {'success': False, 'error': f"Call API error: {response.status_code}"}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def get_otp_status(self, phone_number: str) -> Dict[str, Any]:
        """Get OTP status for a phone number"""
        if phone_number not in self.otp_store:
            return {
                'exists': False,
                'message': 'No active OTP for this number'
            }
        
        otp_data = self.otp_store[phone_number]
        time_remaining = (otp_data['expires_at'] - datetime.now()).total_seconds()
        
        if time_remaining <= 0:
            del self.otp_store[phone_number]
            return {
                'exists': False,
                'message': 'OTP has expired'
            }
        
        return {
            'exists': True,
            'time_remaining': int(time_remaining),
            'attempts_used': otp_data['attempts'],
            'attempts_remaining': 3 - otp_data['attempts']
        }