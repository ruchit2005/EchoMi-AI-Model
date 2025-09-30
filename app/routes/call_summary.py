"""Call Summary API routes for generating call summaries from transcripts"""

from flask import Blueprint, request, jsonify
from ..models.schemas import CallSummaryRequest, CallSummaryResponse
from ..services.call_summary_service import CallSummaryService
from ..config.config import Config
import logging
from pydantic import ValidationError

call_summary_bp = Blueprint('call_summary', __name__)

# Initialize services
config = Config()
call_summary_service = CallSummaryService(config)

logger = logging.getLogger(__name__)

@call_summary_bp.route('/generate-summary', methods=['POST'])
def generate_call_summary():
    """
    Generate a summary of a phone call from the transcript
    
    Expected request format:
    {
        "callSid": "CA4353c2f8024d9e686149aa564b4d4eef",
        "callerNumber": "+918777508827",
        "userName": "Ruchit Gupta",
        "duration": 120,
        "transcript": "[10:30:00] Caller: Hello, I need help...",
        "startTime": "2025-09-27T10:30:00Z",
        "requestType": "call_summary"
    }
    """
    try:
        # Validate request data
        data = request.get_json(force=True)
        if not data:
            return jsonify({
                "response_text": "No data provided",
                "status": "error"
            }), 400
            
        # Validate using Pydantic model
        try:
            call_request = CallSummaryRequest(**data)
        except ValidationError as ve:
            logger.error(f"Validation error: {ve}")
            return jsonify({
                "response_text": f"Invalid request data: {str(ve)}",
                "status": "error"
            }), 400
        
        logger.info(f"📞 [CALL SUMMARY] Processing call {call_request.callSid} from {call_request.callerNumber}")
        
        # Generate summary using the service
        summary_result = call_summary_service.generate_summary(
            call_sid=call_request.callSid,
            caller_number=call_request.callerNumber,
            user_name=call_request.userName,
            duration=call_request.duration,
            transcript=call_request.transcript,
            start_time=call_request.startTime
        )
        
        if summary_result["success"]:
            response = CallSummaryResponse(
                response_text=summary_result["summary"],
                status="success",
                call_duration=summary_result.get("formatted_duration"),
                key_points=summary_result.get("key_points", []),
                call_type=summary_result.get("call_type")
            )
            
            logger.info(f"✅ [CALL SUMMARY] Generated for call {call_request.callSid}")
            return jsonify(response.model_dump()), 200
            
        else:
            logger.error(f"❌ [CALL SUMMARY] Failed for call {call_request.callSid}: {summary_result.get('error')}")
            return jsonify({
                "response_text": f"Failed to generate summary: {summary_result.get('error', 'Unknown error')}",
                "status": "error"
            }), 500
            
    except Exception as e:
        logger.error(f"❌ [CALL SUMMARY] Unexpected error: {str(e)}")
        return jsonify({
            "response_text": "Internal server error while generating call summary",
            "status": "error"
        }), 500

@call_summary_bp.route('/summary-health', methods=['GET'])
def summary_health_check():
    """Health check for call summary service"""
    try:
        health_status = call_summary_service.get_health_status()
        return jsonify({
            "service": "call_summary",
            "status": "healthy" if health_status["openai_available"] else "degraded",
            "openai_configured": health_status["openai_available"],
            "timestamp": health_status["timestamp"]
        }), 200
    except Exception as e:
        return jsonify({
            "service": "call_summary",
            "status": "unhealthy",
            "error": str(e)
        }), 500