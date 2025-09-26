# EchoMi AI Delivery Assistant - Testing Guide

## 🧪 Complete Testing Without Backend Dependencies

Your application is now ready for testing the complete delivery person flow!

## 🚀 Quick Start

1. **Install dependencies:**
```bash
pip install flask flask-cors pydantic python-dotenv
```

2. **Start the application:**
```bash
python main.py
```

3. **Application will start at:** `http://localhost:5000`

## 📞 Testing the Enhanced Delivery Person Flow

### Scenario 1: Delivery Person Requests OTP + Gets Customer Address

**Request:**
```bash
curl -X POST http://localhost:5000/api/conversation/process \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Hi, I am here for Swiggy delivery. Can I get the OTP?",
    "caller_type": "delivery_person",
    "firebase_uid": "test_user_123",
    "caller_id": "+91 98765 43210"
  }'
```

**Expected Response:**
- AI detects: Delivery person requesting OTP
- System finds Swiggy order in mock database
- Returns OTP (1234) formatted for speech: "1 2 3 4"
- **NEW:** Provides customer's delivery address
- **NEW:** Suggests navigation help if current location is provided

### Scenario 2: Complete Navigation Flow (Current Location → Customer Address)

**Request:**
```bash
curl -X POST http://localhost:5000/api/conversation/process \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I am currently at Cubbon Park. Need directions to apartment 3B, Brigade Towers, Brigade Road",
    "caller_type": "delivery_person",
    "session_id": "nav_session_001"
  }'
```

**Expected Response:**
- AI detects: Navigation request with current location
- Extracts current location: "Cubbon Park"
- Extracts destination: "apartment 3B, Brigade Towers, Brigade Road"
- **NEW:** Provides turn-by-turn directions
- **NEW:** Gives distance, time estimate, and voice-friendly instructions
- **NEW:** Includes traffic conditions and detailed steps

### Scenario 3: Progressive Conversation (OTP → Navigation)

**Step 1 - Get OTP and Address:**
```bash
curl -X POST http://localhost:5000/api/conversation/process \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Need OTP for Zomato order",
    "session_id": "delivery_session_002",
    "firebase_uid": "test_user_456"
  }'
```

**Step 2 - Request Navigation from Current Location:**
```bash
curl -X POST http://localhost:5000/api/conversation/process \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I am at MG Road metro station. How do I get to the customer address?",
    "session_id": "delivery_session_002"
  }'
```

**Expected Flow:**
- Step 1: Returns Zomato OTP (5678) + customer address in Whitefield
- Step 2: Uses session context to provide navigation from MG Road to Whitefield
- **NEW:** Provides detailed route with landmarks and estimated time

### Scenario 3: Complete Conversation Flow

**Step 1 - Greeting:**
```bash
curl -X POST http://localhost:5000/api/conversation/process \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Hello",
    "session_id": "delivery_session_001"
  }'
```

**Step 2 - OTP Request:**
```bash
curl -X POST http://localhost:5000/api/conversation/process \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I need OTP for Zomato order",
    "session_id": "delivery_session_001",
    "firebase_uid": "test_user_456"
  }'
```

**Step 3 - Location Help:**
```bash
curl -X POST http://localhost:5000/api/conversation/process \
  -H "Content-Type: application/json" \
  -d '{
    "message": "How do I get to McDonald Brigade Road?",
    "session_id": "delivery_session_001"
  }'
```

## 🗺️ Enhanced Navigation Testing

### Test Current Location Extraction

**Various ways to express current location:**
```bash
# Test 1: "I am at" format
curl -X POST http://localhost:5000/api/conversation/process \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I am at Bangalore Railway Station, how to reach the delivery address?",
    "caller_type": "delivery_person"
  }'

# Test 2: "Currently at" format  
curl -X POST http://localhost:5000/api/conversation/process \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Currently at Forum Mall, need directions to customer",
    "caller_type": "delivery_person"
  }'

# Test 3: "Near" format
curl -X POST http://localhost:5000/api/conversation/process \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I am near Indiranagar metro, where is the delivery address?",
    "caller_type": "delivery_person"  
  }'
```

### Test Navigation Features

The enhanced navigation system provides:

1. **Turn-by-turn Directions**: Step-by-step instructions
2. **Voice-friendly Instructions**: Clear, conversational directions  
3. **Distance & Time Estimates**: Realistic travel calculations
4. **Landmark-based Navigation**: Uses recognizable landmarks
5. **Traffic Conditions**: Mock traffic status (light/moderate/heavy)

**Sample Navigation Response:**
```
Perfect! I'll guide you from Cubbon Park to apartment 3B, Brigade Towers, Brigade Road.
Distance: 3.2 km, Time: 12 mins.

Starting navigation from Cubbon Park to apartment 3B, Brigade Towers, Brigade Road.
Here are your main directions:
First, head towards the main road from Cubbon Park.
Then, turn right at the traffic signal and continue on main road.  
Finally, your destination apartment 3B, Brigade Towers, Brigade Road will be on your left/right.
Total distance is approximately 0.3 km.
Drive safely and call if you need more help!
```

## 🔐 Enhanced Mock OTP Service

Updated with realistic customer addresses:

1. **SWGY123456789** (Swiggy) - OTP: 1234
   - Address: "apartment 3B, Brigade Towers, 135 Brigade Road, Bangalore 560001"

2. **ZOM987654321** (Zomato) - OTP: 5678  
   - Address: "Flat 204, Prestige Shantiniketan, Whitefield Main Road, Bangalore 560066"

3. **UBR555444333** (Uber Eats) - OTP: 9012
   - Address: "House 15, 2nd Cross, Koramangala 5th Block, Bangalore 560034"

4. **DMZ777888999** (Dunzo) - OTP: 3456
   - Address: "Villa 23, Embassy Golf Links, Off Intermediate Ring Road, Bangalore 560071"

**Test OTP Retrieval:**
```bash
curl -X POST http://localhost:5000/api/conversation/process \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Need OTP for Uber Eats delivery",
    "firebase_uid": "test_user_789"
  }'
```

## 🔍 Session Management Testing

**Check conversation status:**
```bash
curl http://localhost:5000/api/conversation/status/delivery_session_001
```

**View active sessions:**
```bash
curl http://localhost:5000/api/conversation/active-sessions
```

**Reset a session:**
```bash
curl -X POST http://localhost:5000/api/conversation/reset/delivery_session_001
```

## 🧠 AI Response Testing

The mock OpenAI service provides contextual responses:

- **Greetings:** Welcomes delivery person and asks how to help
- **OTP Requests:** Asks for company name, then provides OTP with order ID
- **Location Queries:** Provides address, distance, and directions
- **Unclear Messages:** Asks for clarification with helpful options

## 📊 Service Testing Endpoints

**Health Check:**
```bash
curl http://localhost:5000/api/health
```

**Test All Models:**
```bash
curl http://localhost:5000/api/models/test
```

**Application Status:**
```bash
curl http://localhost:5000/api/status
```

## 🎯 Expected Results Summary

### ✅ What Works Now:

1. **Complete Delivery Flow:** Person calls → gets OTP + customer address → requests navigation → gets turn-by-turn directions
2. **Smart Intent Detection:** Automatically detects OTP requests, location queries, and navigation requests
3. **Enhanced Navigation:** Extracts current location and provides detailed directions to customer address
4. **Mock Google Maps:** Returns realistic navigation with turn-by-turn directions
5. **Mock OTP System:** Provides delivery OTPs + customer addresses for major companies
6. **Conversation Memory:** Maintains context for progressive conversations (OTP → Navigation)
7. **Speech-Friendly Formatting:** OTPs and directions formatted for voice clarity
8. **Current Location Detection:** Recognizes various ways delivery persons express their location
9. **Voice-Friendly Directions:** Conversational navigation instructions with landmarks

### 🔧 No External Dependencies Needed:

- ✅ No OpenAI API key required
- ✅ No Google Maps API key required  
- ✅ No backend services needed
- ✅ No database setup required
- ✅ Perfect for hackathon development!

## 🚀 Next Steps

When you're ready to integrate real services:

1. **Add OpenAI API key** to environment variables
2. **Add Google Maps API key** for real geocoding
3. **Connect to backend** for actual OTP retrieval
4. **Add Redis** for production session storage

The mock services can be easily replaced with real implementations without changing the API interface!

---

**🎉 Your delivery assistant is ready for hackathon demo!** All endpoints work independently without external dependencies.