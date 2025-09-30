"""Call Summary Service for generating intelligent summaries from call transcripts"""

import time
import re
from datetime import datetime
from typing import Dict, List, Any, Optional
from ..config.config import Config

# Try to import OpenAI, handle gracefully if not available
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    OpenAI = None

class CallSummaryService:
    """Service for generating AI-powered call summaries"""
    
    def __init__(self, config: Config):
        self.config = config
        self.client = None
        
        if OPENAI_AVAILABLE and config.OPENAI_API_KEY:
            try:
                self.client = OpenAI(api_key=config.OPENAI_API_KEY)
            except Exception as e:
                print(f"⚠️ OpenAI client initialization failed for call summary: {e}")
                self.client = None
        elif not OPENAI_AVAILABLE:
            print("⚠️ OpenAI package not available for call summary")
        else:
            print("⚠️ OpenAI API key not configured for call summary")
    
    def generate_summary(
        self,
        call_sid: str,
        caller_number: str, 
        user_name: str,
        duration: int,
        transcript: str,
        start_time: str
    ) -> Dict[str, Any]:
        """
        Generate an intelligent summary of a phone call
        
        Args:
            call_sid: Unique call identifier
            caller_number: Phone number of caller
            user_name: Name of the user
            duration: Call duration in seconds
            transcript: Full conversation transcript
            start_time: Call start time
            
        Returns:
            Dictionary with summary and metadata
        """
        try:
            # Format duration
            formatted_duration = self._format_duration(duration)
            
            # Extract key information
            call_type = self._identify_call_type(transcript)
            
            if self.client:
                # Use OpenAI for intelligent summary
                summary = self._generate_ai_summary(transcript, call_type, duration)
                key_points = self._extract_key_points(transcript)
            else:
                # Fallback to rule-based summary
                summary = self._generate_fallback_summary(transcript, call_type, caller_number, user_name, duration)
                key_points = self._extract_basic_key_points(transcript)
            
            return {
                "success": True,
                "summary": summary,
                "formatted_duration": formatted_duration,
                "key_points": key_points,
                "call_type": call_type,
                "caller_number": caller_number,
                "user_name": user_name
            }
            
        except Exception as e:
            print(f"❌ [CALL SUMMARY] Error generating summary: {e}")
            return {
                "success": False,
                "error": str(e),
                "summary": "Failed to generate call summary due to an error."
            }
    
    def _generate_ai_summary(self, transcript: str, call_type: str, duration: int) -> str:
        """Generate summary using OpenAI"""
        system_prompt = f"""You are an expert call summarizer for a delivery assistance AI system. 
        
Analyze the following phone call transcript and generate a concise, professional summary.
        
Call Type: {call_type}
Duration: {self._format_duration(duration)}
        
Focus on:
- Main purpose of the call
- Key actions taken by the AI assistant
- Outcome/resolution status
- Any important details (delivery company, OTP provided, directions given, etc.)

Keep the summary under 150 words and write in a professional, clear style."""
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Transcript:\n{transcript}"}
                ],
                max_tokens=200,
                temperature=0.3
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            print(f"❌ AI summary generation failed: {e}")
            return self._generate_fallback_summary(transcript, call_type, "", "", 0)
    
    def _generate_fallback_summary(self, transcript: str, call_type: str, caller_number: str, user_name: str, duration: int) -> str:
        """Generate basic summary without AI"""
        # Clean transcript for analysis
        clean_transcript = re.sub(r'\[\d+:\d+:\d+\]', '', transcript).strip()
        
        # Basic summary template
        summary_parts = []
        
        if call_type == "delivery":
            summary_parts.append("Delivery person called for assistance.")
            
            # Check for company mentions
            companies = ["Amazon", "Flipkart", "Swiggy", "Zomato", "Uber", "delivery"]
            mentioned_company = None
            for company in companies:
                if company.lower() in clean_transcript.lower():
                    mentioned_company = company
                    break
            
            if mentioned_company:
                summary_parts.append(f"Delivery from {mentioned_company}.")
            
            # Check for OTP requests
            if "otp" in clean_transcript.lower() or "code" in clean_transcript.lower():
                summary_parts.append("OTP assistance provided.")
            
            # Check for directions
            if any(word in clean_transcript.lower() for word in ["direction", "location", "help getting", "where"]):
                summary_parts.append("Location assistance provided.")
                
        elif call_type == "inquiry":
            summary_parts.append("Customer inquiry call.")
        else:
            summary_parts.append("General assistance call.")
        
        summary_parts.append(f"Call duration: {self._format_duration(duration)}.")
        summary_parts.append("Call handled by AI assistant.")
        
        return " ".join(summary_parts)
    
    def _extract_key_points(self, transcript: str) -> List[str]:
        """Extract key points using AI"""
        if not self.client:
            return self._extract_basic_key_points(transcript)
            
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system", 
                        "content": "Extract 3-5 key points from this call transcript. Return as a simple list, one point per line, no formatting."
                    },
                    {"role": "user", "content": transcript}
                ],
                max_tokens=150,
                temperature=0.2
            )
            
            key_points = response.choices[0].message.content.strip().split('\n')
            return [point.strip().lstrip('- ').lstrip('• ') for point in key_points if point.strip()]
            
        except Exception:
            return self._extract_basic_key_points(transcript)
    
    def _extract_basic_key_points(self, transcript: str) -> List[str]:
        """Extract basic key points without AI"""
        points = []
        clean_transcript = transcript.lower()
        
        if "delivery" in clean_transcript:
            points.append("Delivery assistance request")
        if "otp" in clean_transcript or "code" in clean_transcript:
            points.append("OTP/verification code provided")
        if any(word in clean_transcript for word in ["direction", "location", "help getting"]):
            points.append("Location/direction assistance")
        if any(company in clean_transcript for company in ["amazon", "swiggy", "zomato", "flipkart"]):
            points.append("Company-specific delivery support")
        if "arrived" in clean_transcript or "here" in clean_transcript:
            points.append("Delivery person arrival confirmation")
            
        return points[:5]  # Limit to 5 points
    
    def _identify_call_type(self, transcript: str) -> str:
        """Identify the type of call from transcript"""
        clean_transcript = transcript.lower()
        
        # Delivery-related keywords
        delivery_keywords = ["delivery", "deliver", "parcel", "package", "otp", "code", "amazon", "swiggy", "zomato", "flipkart"]
        if any(keyword in clean_transcript for keyword in delivery_keywords):
            return "delivery"
        
        # Inquiry keywords
        inquiry_keywords = ["inquiry", "question", "help", "support", "information"]
        if any(keyword in clean_transcript for keyword in inquiry_keywords):
            return "inquiry"
        
        return "general"
    
    def _format_duration(self, duration_seconds: int) -> str:
        """Format duration in human-readable format"""
        if duration_seconds < 60:
            return f"{duration_seconds} seconds"
        elif duration_seconds < 3600:
            minutes = duration_seconds // 60
            seconds = duration_seconds % 60
            return f"{minutes}m {seconds}s"
        else:
            hours = duration_seconds // 3600
            minutes = (duration_seconds % 3600) // 60
            return f"{hours}h {minutes}m"
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get health status of the call summary service"""
        return {
            "openai_available": self.client is not None,
            "openai_configured": bool(self.config.OPENAI_API_KEY) if hasattr(self.config, 'OPENAI_API_KEY') else False,
            "timestamp": time.time()
        }