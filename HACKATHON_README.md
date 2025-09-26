# EchoMi AI Model - Hackathon Setup

## Quick Start (Phase 1 - Basic Flask Foundation)

### 1. Install Core Dependencies
```bash
pip install flask flask-cors pydantic python-dotenv
```

### 2. Run the Application
```bash
python main.py
```

### 3. Test the Endpoints

**Health Check:**
```bash
curl http://localhost:5000/api/health
```

**Status Check:**
```bash  
curl http://localhost:5000/api/status
```

**Home Page:**
```bash
curl http://localhost:5000/
```

## 🧪 Testing Without Backend

The application runs in **MOCK_MODE** by default, which means:
- ✅ No external API calls required
- ✅ No backend services needed  
- ✅ Static responses for testing
- ✅ Perfect for hackathon development

## 📋 Implementation Phases

- [x] **Phase 1**: Basic Flask foundation with health checks
- [ ] **Phase 2**: Core data models (Pydantic schemas)
- [ ] **Phase 3**: Text processing utilities
- [ ] **Phase 4**: Mock services for testing
- [ ] **Phase 5**: Conversation API endpoints
- [ ] **Phase 6**: LangGraph conversation flow
- [ ] **Phase 7**: Testing and validation endpoints
- [ ] **Phase 8**: Real service integration (when ready)

## 🎯 Current Status: Phase 1 Complete

Your Flask foundation is ready! The app will start on port 5000 with mock mode enabled for testing without any external dependencies.

**Next Step**: Let me know when you're ready for Phase 2 (Core Data Models).