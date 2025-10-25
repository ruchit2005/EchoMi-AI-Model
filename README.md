# 🎙️ EchoMi AI Model

**Intelligent Voice-Activated Delivery Assistant with SMS-Based OTP Integration**

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![Flask](https://img.shields.io/badge/Flask-3.0.0-green.svg)
![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o--mini-orange.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

## 🚀 Overview

EchoMi AI Model is a sophisticated Flask-based AI assistant designed to handle delivery conversations, OTP management, and customer interactions through voice interfaces. It integrates with Node.js backends for SMS processing and provides intelligent conversation flow management with multi-language support.

## ✨ Key Features

### 🎯 **Core Capabilities**
- **Voice-Activated Conversations**: Natural language processing for delivery scenarios
- **Smart OTP Management**: SMS-based OTP retrieval and delivery
- **Multi-Language Support**: English and Hindi conversation flows
- **Role Identification**: Automatic detection of delivery personnel vs. unknown callers
- **Call Summarization**: AI-powered conversation summaries and insights

### 🔗 **Integrations**
- **OpenAI GPT-4o-mini**: Advanced natural language understanding
- **Node.js Backend**: SMS message processing and storage
- **MongoDB Integration**: Data persistence through backend API
- **Google Maps API**: Location services (configurable)
- **Notification System**: Real-time alerts for unknown callers

### 🛡️ **Security & Reliability**
- **Bearer Token Authentication**: Secure API communication
- **Environment-based Configuration**: Secure credential management
- **Fallback Systems**: Graceful degradation when services are unavailable
- **Error Handling**: Comprehensive logging and error recovery

## 📋 Prerequisites

- **Python 3.11+**
- **Node.js Backend** (for SMS integration)
- **OpenAI API Key**
- **Google Maps API Key** (optional)
- **ngrok** (for local development with webhooks)

## 🔧 Installation

### 1. Clone the Repository
```bash
git clone https://github.com/ruchit2005/EchoMi-AI-Model.git
cd EchoMi-AI-Model
```

### 2. Set Up Python Virtual Environment
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/macOS
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Create a `.env` file in the root directory:

```env
# Required API Keys
OPENAI_API_KEY=sk-proj-your-openai-api-key-here
GOOGLE_MAPS_API_KEY=your-google-maps-api-key-here

# Backend Integration
NODEJS_BACKEND_URL=https://echomibackend-production.up.railway.app
INTERNAL_API_KEY=your-secure-internal-api-key
OWNER_PHONE_NUMBER=+1234567890

# Application Configuration
BASE_URL=https://your-flask-app.ngrok-free.app
APP_SECRET_KEY=your-flask-secret-key
USER_LAT=12.970827983276324
USER_LNG=79.15943441076058
```

### 5. Start the Application
```bash
python main.py
```

The API will be available at `http://localhost:5000`

## 🌐 API Endpoints

### 🎯 **Core Conversation**
```http
POST /generate
Content-Type: application/json

{
  "new_message": "Hello, I have a delivery from Amazon",
  "caller_role": "delivery",
  "conversation_stage": "start",
  "response_language": "en",
  "call_sid": "unique-call-identifier",
  "firebaseUid": "user-firebase-uid"
}
```

### 🔐 **Direct OTP Retrieval**
```http
POST /api/get-otp
Content-Type: application/json

{
  "company": "Amazon",
  "order_id": "AMZ123456789",
  "firebaseUid": "user-firebase-uid"
}
```

### 📊 **Call Summary Generation**
```http
POST /generate-summary
Content-Type: application/json

{
  "callSid": "CA4353c2f8024d9e686149aa564b4d4eef",
  "callerNumber": "+918777508827",
  "userName": "John Doe",
  "duration": 120,
  "transcript": "[10:30:00] Caller: Hello...",
  "startTime": "2025-09-27T10:30:00Z"
}
```

### 🏥 **Health & Status**
```http
GET /health
GET /summary-health
GET /api/status
```

### ⚙️ **Admin & Configuration**
```http
POST /api/admin/configure-backend
POST /api/admin/test-backend
GET /api/admin/backend-status
```

## 🔄 Conversation Flow

### 📦 **Delivery Personnel Interaction**
1. **Role Identification**: "Hello, I have a delivery"
2. **Company Detection**: Extracts company name (Amazon, Flipkart, etc.)
3. **OTP Request**: "Do you need the OTP?"
4. **SMS Integration**: Fetches OTP from backend SMS data
5. **OTP Delivery**: Provides formatted OTP with confirmation

### 👤 **Unknown Caller Handling**
1. **Greeting**: Polite introduction and assistance offer
2. **Information Collection**: Name, purpose, contact details
3. **Notification**: Sends approval request to owner
4. **Follow-up**: Additional details if needed

### 🌍 **Multi-Language Support**
- **English**: Default conversation language
- **Hindi**: Full conversation flow in Hindi
- **Auto-Detection**: Language identification from user input

## 🔗 Backend Integration

### Required Node.js Endpoints

Your Node.js backend must implement these endpoints:

#### **SMS Integration**
```javascript
GET /api/sms/latest?userId={firebase_uid}&count=10
POST /api/send-notification
```

#### **OTP Management**
```javascript
GET /api/delivery/otp/{firebase_uid}?sender={company}&orderId={order_id}
```

#### **Health Check**
```javascript
GET /api/health
```

See `BACKEND_INTEGRATION.md` and `NOTIFICATION_ENDPOINT_GUIDE.md` for detailed implementation guides.

## 📁 Project Structure

```
EchoMi-AI-Model/
├── app/
│   ├── config/
│   │   ├── config.py              # Application configuration
│   │   └── __init__.py
│   ├── graphs/
│   │   ├── conversation_manager.py # Conversation state management
│   │   └── nodes.py               # LangGraph nodes (future)
│   ├── models/
│   │   └── schemas.py             # Pydantic data models
│   ├── routes/
│   │   ├── conversation.py        # Main conversation endpoints
│   │   ├── call_summary.py        # Call summarization API
│   │   ├── admin.py               # Admin & configuration
│   │   └── health.py              # Health check endpoints
│   ├── services/
│   │   ├── conversation_handler.py # Core conversation logic
│   │   ├── openai_service.py      # OpenAI API integration
│   │   ├── sms_service.py         # SMS processing service
│   │   ├── real_otp_service.py    # OTP management service
│   │   ├── notification_service.py # Push notification service
│   │   └── service_factory.py     # Service factory pattern
│   └── utils/
│       ├── language_utils.py      # Multi-language utilities
│       ├── sms_parser.py          # SMS parsing and OTP extraction
│       └── text_processing.py     # Text processing utilities
├── docs/
│   ├── BACKEND_INTEGRATION.md     # Backend setup guide
│   ├── BULK_SMS_INTEGRATION.md    # SMS integration details
│   └── SMS_BACKEND_INTEGRATION.md # Detailed SMS setup
├── requirements.txt               # Python dependencies
├── main.py                       # Flask application entry point
├── .env                          # Environment configuration
└── README.md                     # This file
```

## 🧪 Testing

### Run the Test Suite
```bash
# Test call summary feature
python test_call_summary.py

# Test SMS integration
python test_sms_integration.py
```

### Manual Testing Examples

#### **Delivery Conversation**
```bash
curl -X POST http://localhost:5000/generate \
  -H "Content-Type: application/json" \
  -d '{
    "new_message": "Hello, I have a delivery from Amazon",
    "caller_role": "delivery",
    "conversation_stage": "start",
    "response_language": "en"
  }'
```

#### **OTP Request**
```bash
curl -X POST http://localhost:5000/api/get-otp \
  -H "Content-Type: application/json" \
  -d '{
    "company": "Amazon",
    "order_id": "AMZ123456789",
    "firebaseUid": "demo-user"
  }'
```

## 🐛 Troubleshooting

### Common Issues

#### **404 Error on Notifications**
- **Problem**: `Cannot POST /api/send-notification`
- **Solution**: Implement the notification endpoint in your Node.js backend
- **Guide**: See `NOTIFICATION_ENDPOINT_GUIDE.md`

#### **OpenAI API Errors**
- **Problem**: Invalid API key or quota exceeded
- **Solution**: Check your OpenAI API key and billing status
- **Config**: Update `OPENAI_API_KEY` in `.env`

#### **SMS Integration Not Working**
- **Problem**: Backend SMS endpoints not responding
- **Solution**: Verify Node.js backend is running and endpoints are implemented
- **Debug**: Check `/api/admin/backend-status` for connectivity

#### **Environment Variables Not Loading**
- **Problem**: Missing or incorrect environment variables
- **Solution**: Ensure `.env` file is in root directory and properly formatted
- **Check**: Use `/health` endpoint to verify configuration

### Debug Mode
Enable detailed logging by setting:
```env
FLASK_DEBUG=True
```

## 🚀 Deployment

### Local Development with ngrok
```bash
# Start Flask app
python main.py

# In another terminal, expose with ngrok
ngrok http 5000

# Update .env with ngrok URL
BASE_URL=https://your-random-url.ngrok-free.app
```

### Production Deployment
1. **Choose a Platform**: Heroku, Google Cloud, AWS, etc.
2. **Set Environment Variables**: Configure all required API keys
3. **Update Backend URLs**: Point to production backend
4. **Enable HTTPS**: Ensure secure communication
5. **Monitor Logs**: Set up logging and monitoring

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **OpenAI** for providing the GPT-4o-mini API
- **Flask** community for the excellent web framework
- **Twilio** for SMS and voice services inspiration
- **LangChain** for future graph-based conversation management

## 📞 Support

For support and questions:
- **Issues**: [GitHub Issues](https://github.com/ruchit2005/EchoMi-AI-Model/issues)
- **Email**: ruchit2005@example.com
- **Documentation**: Check the `docs/` folder for detailed guides

---

<div align="center">

**Made with ❤️ for seamless delivery experiences**

[🌟 Star this repo](https://github.com/ruchit2005/EchoMi-AI-Model) if you find it helpful!

</div>