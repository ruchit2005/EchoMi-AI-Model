# SMS-Based Backend Integration

## Overview
The EchoMi AI Model now works with SMS messages instead of direct OTP retrieval. The backend sends SMS messages to users, and the AI agent extracts OTP codes and tracking information from the SMS content.

## Backend Integration Format

### 1. SMS Message Retrieval

**HTTP Method:** `GET`

**Endpoint:** `/api/sms/messages/{firebase_uid}`

**URL Structure:**
```
GET http://your-backend.com/api/sms/messages/user123?company=Zomato&phone_number=9876543210
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
    "company": "Zomato",           // Optional: Filter by delivery company
    "phone_number": "9876543210"   // Optional: Filter by phone number
}
```

### 2. SMS Response Format

**Success Response (200):**
```json
{
    "messages": [
        {
            "message": "Your Zomato order OTP is 1234. Order ID: ZMT123456789. Delivery by Raj.",
            "sender": "ZOMATO",
            "timestamp": "2025-09-26T14:30:00Z",
            "phone_number": "9876543210"
        },
        {
            "message": "Amazon delivery code 5678 for order AMZN987654321. Track at amazon.in",
            "sender": "AMAZON",
            "timestamp": "2025-09-26T15:45:00Z", 
            "phone_number": "9876543210"
        }
    ],
    "total_count": 2
}
```

**Not Found Response (404):**
```json
{
    "error": "No SMS messages found",
    "messages": []
}
```

## SMS Parsing Capabilities

The AI agent automatically extracts:

### OTP Codes
- 4-digit codes: `1234`
- 6-digit codes: `123456`
- Pattern-based extraction from text like "OTP is 1234"

### Tracking Information
- Order IDs: `ZMT123456789`, `AMZN987654321`
- Tracking numbers: `1234567890123`
- Delivery person names: `Raj`, `Priya`

### Company Detection
Supports automatic detection of:
- **Zomato**: `zomato`, `zmt`
- **Swiggy**: `swiggy`, `swg`
- **Amazon**: `amazon`, `amzn`
- **Flipkart**: `flipkart`, `fkrt`
- **BigBasket**: `bigbasket`, `bb`
- **Dunzo**: `dunzo`

## Node.js Backend Implementation

### Route Example
```javascript
// Route: GET /api/sms/messages/:firebase_uid
app.get('/api/sms/messages/:firebase_uid', async (req, res) => {
    try {
        const { firebase_uid } = req.params;
        const { company, phone_number } = req.query;
        
        // Verify authorization
        const authHeader = req.headers.authorization;
        if (!authHeader?.startsWith('Bearer ')) {
            return res.status(401).json({ error: 'Unauthorized' });
        }
        
        const apiKey = authHeader.split(' ')[1];
        if (apiKey !== process.env.INTERNAL_API_KEY) {
            return res.status(401).json({ error: 'Invalid API key' });
        }
        
        // Build query for SMS messages
        const query = { firebase_uid };
        if (company) query.company_detected = new RegExp(company, 'i');
        if (phone_number) query.phone_number = phone_number;
        
        // Fetch recent SMS messages (last 24 hours)
        const messages = await SMS.find(query)
            .sort({ timestamp: -1 })
            .limit(20)
            .select('message sender timestamp phone_number');
        
        if (messages.length === 0) {
            return res.status(404).json({ 
                error: "No SMS messages found",
                messages: []
            });
        }
        
        // Return SMS messages for AI parsing
        res.status(200).json({
            messages: messages.map(msg => ({
                message: msg.message,
                sender: msg.sender,
                timestamp: msg.timestamp,
                phone_number: msg.phone_number
            })),
            total_count: messages.length
        });
        
    } catch (error) {
        console.error('SMS fetch error:', error);
        res.status(500).json({ 
            error: "Database error" 
        });
    }
});
```

### MongoDB Schema
```javascript
const smsSchema = new mongoose.Schema({
    firebase_uid: { type: String, required: true, index: true },
    phone_number: { type: String, required: true },
    message: { type: String, required: true },
    sender: { type: String, required: true },
    timestamp: { type: Date, default: Date.now, index: true },
    company_detected: { type: String }, // Auto-detected from message content
    otp_extracted: { type: String },    // AI can populate this after parsing
    tracking_id: { type: String },      // AI can populate this after parsing
    processed: { type: Boolean, default: false }
});

// Compound index for efficient queries
smsSchema.index({ firebase_uid: 1, timestamp: -1 });
smsSchema.index({ firebase_uid: 1, company_detected: 1 });
```

## AI Model Response Processing

After parsing SMS messages, the AI provides intelligent responses:

### English Response Example
```
"I found your Zomato delivery OTP: 1234. Your order ZMT123456789 is being delivered by Raj. Would you like me to help with anything else?"
```

### Hindi Response Example  
```
"आपका Zomato डिलीवरी OTP मिल गया: 1234। आपका ऑर्डर ZMT123456789 राज द्वारा डिलीवर किया जा रहा है। क्या आपको कोई और मदद चाहिए?"
```

## Configuration

### Environment Variables
```env
# Backend Configuration
NODEJS_BACKEND_URL=http://your-backend.com
INTERNAL_API_KEY=your-secret-internal-key

# MongoDB (in your backend)
MONGODB_URI=your-mongodb-connection-string
```

### Admin Endpoints
The AI model provides admin endpoints for testing:

**POST** `/api/admin/configure-backend`
```json
{
    "backend_url": "http://your-backend.com",
    "internal_api_key": "your-secret-key"
}
```

**POST** `/api/admin/test-backend`
```json
{
    "firebase_uid": "test-user-123"
}
```

## Benefits of SMS-Based Approach

1. **Realistic Integration**: Works with actual SMS delivery system
2. **Intelligent Parsing**: AI extracts relevant information automatically
3. **Multi-Company Support**: Handles different delivery companies
4. **Flexible Matching**: Pattern-based extraction works with various formats
5. **Multi-lingual**: Supports Hindi and English responses
6. **Backward Compatible**: Maintains existing API structure

This approach allows your backend to simply forward SMS messages to the AI, which then intelligently extracts and responds with the relevant delivery information.