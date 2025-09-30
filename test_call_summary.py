#!/usr/bin/env python3
"""
Test Call Summary Feature
Quick test to verify the call summary generation works correctly
"""

import requests
import json
from datetime import datetime

def test_call_summary_local():
    """Test the call summary endpoint locally"""
    
    print("🧪 Testing Call Summary Feature...")
    
    # Sample call data matching your backend's format
    test_call_data = {
        "callSid": "CA4353c2f8024d9e686149aa564b4d4eef",
        "callerNumber": "+918777508827",
        "userName": "Ruchit Gupta",
        "duration": 120,
        "transcript": "[10:30:00] Caller: Hello, I have a delivery from Amazon\n[10:30:05] AI Assistant: Hi! I see you have a delivery from Amazon. Do you need help getting here, or are you already here?\n[10:30:10] Caller: I'm already here\n[10:30:15] AI Assistant: Perfect! You've arrived with the Amazon delivery. Do you need the OTP?\n[10:30:20] Caller: Yes, I do need the OTP\n[10:30:25] AI Assistant: Here's your Amazon OTP: 1 2 3 4. Thank you and have a safe delivery!",
        "startTime": "2025-09-27T10:30:00Z",
        "requestType": "call_summary"
    }
    
    # Test URL (adjust if your Flask app runs on different port)
    url = "http://localhost:5000/generate-summary"
    
    try:
        print(f"📡 Making request to: {url}")
        print(f"📋 Request data: {json.dumps(test_call_data, indent=2)}")
        
        response = requests.post(url, json=test_call_data, timeout=30)
        
        print(f"📊 Response Status: {response.status_code}")
        print(f"📄 Response Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Call Summary Generated Successfully!")
            print(f"📝 Summary: {result.get('response_text', 'No summary')}")
            print(f"⏱️ Duration: {result.get('call_duration', 'Unknown')}")
            print(f"📋 Key Points: {result.get('key_points', [])}")
            print(f"📞 Call Type: {result.get('call_type', 'Unknown')}")
            
        else:
            print(f"❌ Request failed with status {response.status_code}")
            print(f"Error: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to Flask app. Make sure it's running on http://localhost:5000")
        print("💡 Run: python main.py")
    except Exception as e:
        print(f"❌ Error: {e}")

def test_health_endpoint():
    """Test the health endpoint for call summary"""
    url = "http://localhost:5000/summary-health"
    
    try:
        print(f"🏥 Testing health endpoint: {url}")
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Health Check Passed!")
            print(f"📊 Status: {result.get('status', 'Unknown')}")
            print(f"🤖 OpenAI Configured: {result.get('openai_configured', False)}")
        else:
            print(f"❌ Health check failed: {response.status_code}")
            print(response.text)
            
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to health endpoint")
    except Exception as e:
        print(f"❌ Health check error: {e}")

if __name__ == "__main__":
    print("🚀 Call Summary Feature Test")
    print("=" * 50)
    
    # Test health first
    test_health_endpoint()
    print()
    
    # Test main functionality
    test_call_summary_local()
    
    print("\n✨ Test completed!")