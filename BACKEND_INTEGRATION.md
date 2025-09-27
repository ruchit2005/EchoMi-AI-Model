# Backend Integration Guide

## 🔗 Connecting Your Backend to EchoMi AI Model

This guide explains how to configure your Node.js backend to work with the EchoMi AI Model for OTP management with MongoDB integration.

## 📋 Backend Requirements

Your Node.js backend should implement these endpoints:

### 1. Health Check Endpoint
```http
GET /api/health
Authorization: Bearer {INTERNAL_API_KEY}
```

**Response:**
```json
{
  "status": "ok",
  "database": "connected",
  "timestamp": "2024-09-26T10:30:00Z"
}
```

### 2. OTP Endpoint (Main Integration Point)
```http
GET /api/delivery/otp/{firebase_uid}?sender={company}&orderId={order_id}
Authorization: Bearer {INTERNAL_API_KEY}
User-Agent: DeliveryBot/1.0
```

**Parameters:**
- `firebase_uid` (path): User's Firebase UID
- `sender` (query): Delivery company name (e.g., "Amazon", "Flipkart")
- `orderId` (query): Order identifier

**Expected Response:**
```json
{
  "success": true,
  "otp": "1234",
  "message": "OTP retrieved successfully"
}
```

**Error Response:**
```json
{
  "success": false,
  "error": "No OTP found for this delivery"
}
```

### 3. MongoDB Test Endpoint
```http
POST /api/test/mongodb
Authorization: Bearer {INTERNAL_API_KEY}
Content-Type: application/json

{
  "firebase_uid": "test-user",
  "test_query": true
}
```

**Response:**
```json
{
  "success": true,
  "mongodb_status": "connected",
  "test_results": {
    "query_time": "45ms",
    "collections_accessible": true
  }
}
```

## 🚀 AI Model Configuration Endpoints

### 1. Configure Backend Connection
Your backend can register itself with the AI model:

```http
POST http://localhost:5000/api/admin/configure-backend
Content-Type: application/json

{
  "backend_url": "http://localhost:3000",
  "api_key": "your-internal-api-key",
  "admin_secret": "hackathon-admin-2024"
}
```

### 2. Test Backend Connectivity
```http
POST http://localhost:5000/api/admin/test-backend
Content-Type: application/json

{
  "firebase_uid": "test-user-123"
}
```

### 3. Check Backend Status
```http
GET http://localhost:5000/api/admin/backend-status
```

## 🔧 Environment Variables

Set these in your AI model's `.env` file:

```env
# Backend Configuration
NODEJS_BACKEND_URL=http://localhost:3000
INTERNAL_API_KEY=your-secure-api-key
ADMIN_SECRET=hackathon-admin-2024

# MongoDB Connection (handled by your backend)
# Your backend should have these:
# MONGODB_URI=mongodb://localhost:27017/echomi
# MONGODB_DATABASE=echomi
```

## 📊 MongoDB Schema (Suggested)

Your MongoDB collection should store OTPs like this:

```javascript
// Collection: otps
{
  "_id": ObjectId("..."),
  "firebase_uid": "user123",
  "company": "Amazon", 
  "order_id": "AMZ123456",
  "otp": "1234",
  "created_at": ISODate("2024-09-26T10:30:00Z"),
  "expires_at": ISODate("2024-09-26T10:35:00Z"),
  "status": "active", // active, used, expired
  "phone_number": "+1234567890",
  "delivery_address": "123 Main St..."
}
```

## 🔄 Integration Flow

1. **AI Model requests OTP:**
   ```
   AI Model → GET /api/delivery/otp/{firebase_uid} → Your Backend
   ```

2. **Your Backend queries MongoDB:**
   ```javascript
   const otp = await db.collection('otps')
     .findOne({
       firebase_uid: firebase_uid,
       company: company,
       order_id: order_id,
       status: 'active'
     }, { sort: { created_at: -1 } });
   ```

3. **Backend returns single OTP:**
   ```json
   {
     "success": true,
     "otp": "1234",
     "message": "OTP retrieved successfully"
   }
   ```

4. **AI Model uses the OTP for conversation**

## 🧪 Testing the Integration

1. **Start your AI model:**
   ```bash
   cd D:\EchoMi-AI-Model
   python main.py
   ```

2. **Configure backend connection:**
   ```bash
   curl -X POST http://localhost:5000/api/admin/configure-backend \
     -H "Content-Type: application/json" \
     -d '{
       "backend_url": "http://localhost:3000",
       "api_key": "your-api-key",
       "admin_secret": "hackathon-admin-2024"
     }'
   ```

3. **Test the connection:**
   ```bash
   curl -X POST http://localhost:5000/api/admin/test-backend \
     -H "Content-Type: application/json" \
     -d '{"firebase_uid": "test-user"}'
   ```

4. **Test OTP retrieval:**
   ```bash
   curl -X POST http://localhost:5000/api/get-otp \
     -H "Content-Type: application/json" \
     -d '{
       "firebaseUid": "user123",
       "company": "Amazon",
       "orderId": "AMZ123"
     }'
   ```

## 📞 Voice Call Integration

When your Twilio backend detects language and calls the AI model:

```javascript
// In your Twilio webhook
const response = await axios.post('http://localhost:5000/generate', {
  new_message: transcribed_text,
  caller_role: detected_role,
  conversation_stage: current_stage,
  response_language: detected_language, // 'hi' or 'en'
  firebaseUid: user_firebase_id,
  caller_id: caller_phone_number,
  history: conversation_history
});

// The AI model will automatically fetch OTPs from your MongoDB
// via your backend when needed
```

## ⚡ Quick Start Script

Here's a Node.js example for your backend:

```javascript
// Example backend endpoint  
app.get('/api/delivery/otp/:firebase_uid', async (req, res) => {
  try {
    const { firebase_uid } = req.params;
    const { sender, orderId } = req.query;
    
    // Query MongoDB for single latest OTP
    const otp = await db.collection('otps')
      .findOne({
        firebase_uid,
        company: { $regex: new RegExp(sender, 'i') },
        order_id: orderId,
        status: 'active'
      }, { sort: { created_at: -1 } });
    
    if (otp) {
      res.json({
        success: true,
        otp: otp.otp,
        message: "OTP retrieved successfully"
      });
    } else {
      res.status(404).json({
        success: false,
        error: "No OTP found for this delivery"
      });
    }
    
  } catch (error) {
    res.status(500).json({
      success: false,
      error: error.message
    });
  }
});
```

## 🎯 Summary

Your backend integration is now ready! The AI model will:

1. ✅ Connect to your Node.js backend
2. ✅ Fetch the last 10 OTPs from MongoDB  
3. ✅ Use the latest OTP in conversations
4. ✅ Support multi-lingual responses (Hindi/English)
5. ✅ Handle fallback when backend is unavailable

The AI model endpoint is: `http://localhost:5000/generate` with language support!