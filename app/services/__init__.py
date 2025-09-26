"""Service imports and initialization"""

from ..config.config import Config

# Import mock services for testing
from .mock_openai_service import MockOpenAIService
from .mock_maps_service import MockMapsService
from .mock_otp_service import MockOTPService

# Initialize services based on configuration
if Config.MOCK_MODE:
    # Use mock services for testing
    openai_service = MockOpenAIService()
    maps_service = MockMapsService()
    otp_service = MockOTPService()
else:
    # Real services will be implemented later
    # from .real_openai_service import RealOpenAIService
    # from .real_maps_service import RealMapsService
    # from .real_otp_service import RealOTPService
    
    # For now, fall back to mock services
    openai_service = MockOpenAIService()
    maps_service = MockMapsService()
    otp_service = MockOTPService()

__all__ = [
    'openai_service',
    'maps_service', 
    'otp_service'
]
