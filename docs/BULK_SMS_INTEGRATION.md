# Bulk SMS-Based Backend Integration

## Overview
The EchoMi AI Model now fetches the **latest 10 OTP messages** from your backend when requested. Your Android app uploads SMS messages to the backend, and the AI intelligently finds the best matching OTP for the requested delivery company.

## ⚙️ High-Level Flow

1. **Android App → Backend**: Uploads SMS messages periodically via `/api/sms/upload`
2. **AI Model → Backend**: Requests latest 10 OTPs via `/api/sms/latest`  
3. **AI Model Processing**: Intelligently selects best OTP match for the company
4. **AI Response**: Provides OTP with confidence level and additional details

## Backend Integration Format

### 1. SMS Upload Endpoint (Android App)

**HTTP Method:** `POST`

**Endpoint:** `/api/sms/upload`

**Request Body:**
```json
{
    "userId": "USER_MONGODB_OBJECTID",
    "messages": [
        {
            "sender": "AX-ZOMATO",
            "message": "Your Zomato order OTP is 1234. Order ID: ZMT123456789",
            "otp": "1234",
            "receivedAt": "2025-09-26T14:30:00Z"
        }
    ]
}
```

**Headers:**
```json
{
    "Authorization": "Bearer user-auth-token",
    "Content-Type": "application/json"
}
```

### 2. Bulk OTP Retrieval (AI Model)

**HTTP Method:** `GET`

**Endpoint:** `/api/sms/latest`

**URL Structure:**
```
GET http://your-backend.com/api/sms/latest?userId=USER_OBJECTID&limit=10
```

**Headers:**
```json
{
    "Authorization": "Bearer your-internal-api-key",
    "User-Agent": "DeliveryBot/1.0",
    "Content-Type": "application/json"
}
```

**Query Parameters:**
```json
{
    "userId": "USER_MONGODB_OBJECTID",
    "limit": 10
}
```

### 3. Backend Response Format

**Success Response (200):**
```json
[
    {
        "sender": "AX-ZOMATO",
        "message": "Your Zomato order OTP is 1234. Order ID: ZMT123456789",
        "otp": "1234",
        "receivedAt": "2025-09-26T14:30:00Z"
    },
    {
        "sender": "SG-SWIGGY", 
        "message": "Swiggy delivery OTP: 5678. Track: SWG987654321",
        "otp": "5678",
        "receivedAt": "2025-09-26T15:45:00Z"
    }
]
```

## AI Processing Intelligence

The AI processes all 10 messages and:

### 1. Company Matching
- **Direct Match**: Sender contains company name (`AX-ZOMATO` → Zomato)
- **Message Content**: Company mentioned in message text
- **Smart Detection**: Recognizes common sender patterns

### 2. Confidence Scoring
- **High (0.8-1.0)**: Exact company match + recent + valid OTP
- **Medium (0.6-0.8)**: Partial match or older message
- **Low (0.4-0.6)**: Generic OTP with weak indicators

### 3. Intelligent Selection
```javascript
// AI selection logic
1. Find exact company matches → Score: +50
2. Check sender patterns → Score: +40  
3. Analyze message content → Score: +20
4. Apply confidence multiplier → Score: +10
5. Recent message bonus → Score: +5
```

## Node.js Backend Implementation

### MongoDB Schema
```javascript
const smsSchema = new mongoose.Schema({
    userId: { 
        type: mongoose.Schema.Types.ObjectId, 
        ref: 'User', 
        required: true,
        index: true 
    },
    sender: { type: String, required: true },
    message: { type: String, required: true },
    otp: { type: String }, // Pre-extracted by Android app
    receivedAt: { type: Date, default: Date.now, index: true },
    processed: { type: Boolean, default: false }
});

// Compound indexes for performance
smsSchema.index({ userId: 1, receivedAt: -1 });
smsSchema.index({ userId: 1, sender: 1 });
```

### Upload Controller
```javascript
const uploadSms = async (req, res) => {
    try {
        const { userId, messages } = req.body;
        
        if (!userId || !messages) {
            return res.status(400).json({ 
                error: 'userId and messages are required' 
            });
        }

        // Save messages with user association
        const saved = await SmsLog.insertMany(
            messages.map(msg => ({
                ...msg,
                userId: new mongoose.Types.ObjectId(userId)
            }))
        );

        res.json({ 
            success: true, 
            savedCount: saved.length 
        });
        
    } catch (err) {
        console.error('❌ SMS upload failed:', err);
        res.status(500).json({ error: 'Failed to upload SMS' });
    }
};
```

### Latest OTPs Controller
```javascript
const getLatestSms = async (req, res) => {
    try {
        const { userId } = req.query;
        const limit = parseInt(req.query.limit) || 10;

        if (!userId) {
            return res.status(400).json({ error: 'userId is required' });
        }

        // Fetch latest OTP messages
        const sms = await SmsLog.find({ 
            userId: new mongoose.Types.ObjectId(userId)
        })
        .sort({ receivedAt: -1 })
        .limit(limit)
        .select('sender message otp receivedAt');

        if (sms.length === 0) {
            return res.status(404).json({ 
                error: "No OTP messages found" 
            });
        }

        res.json(sms);
        
    } catch (err) {
        console.error('❌ Failed to fetch SMS:', err);
        res.status(500).json({ error: 'Failed to fetch SMS' });
    }
};
```

## AI Response Examples

### Successful Match
```
English: "Found your Zomato OTP: 1-2-3-4. Tracking: ZMT123456789. Checked 10 recent messages."

Hindi: "आपका Zomato OTP मिल गया: १-२-३-४। ट्रैकिंग नंबर: ZMT123456789। मैंने 10 SMS देखे हैं।"
```

### Fallback Match  
```
English: "No exact Zomato match, but found OTP from AX-DELIVERY: 5-6-7-8. Please verify this is correct."

Hindi: "Zomato का सटीक मैच नहीं मिला, लेकिन AX-DELIVERY का OTP मिला: ५-६-७-८। कृपया जाँच लें।"
```

### No Match
```
English: "I checked 10 messages but couldn't find Zomato OTP. Could you tell me the OTP manually?"

Hindi: "मैंने 10 SMS देखे लेकिन Zomato का OTP नहीं मिला। कृपया मैन्युअल रूप से बताएं।"
```

## Configuration

### Environment Variables
```env
# Backend Configuration  
NODEJS_BACKEND_URL=http://your-backend.com
INTERNAL_API_KEY=your-secret-internal-key

# MongoDB
MONGODB_URI=your-mongodb-connection-string
```

### Admin Testing Endpoints

**POST** `/api/admin/test-bulk-sms`
```json
{
    "userId": "USER_OBJECTID",
    "count": 10
}
```

**POST** `/api/admin/test-sms-parsing`
```json
{
    "messages": [
        "Your Zomato order OTP is 1234. Order ID: ZMT123456789",
        "Swiggy delivery OTP: 5678. Track: SWG987654321"
    ]
}
```

## Benefits of Bulk SMS Approach

1. **🎯 Intelligent Selection**: AI picks best OTP from 10 options
2. **📱 Real SMS Integration**: Works with actual phone SMS data
3. **🚀 High Success Rate**: Multiple options increase match probability  
4. **🔍 Context Aware**: Considers sender, content, and timing
5. **🌐 Multi-lingual**: Hindi/English responses maintained
6. **⚡ Fast Processing**: Bulk fetch reduces API calls
7. **🔄 Backward Compatible**: Existing code continues to work

This approach ensures maximum OTP retrieval success while maintaining intelligent company matching!