"""Service factory for switching between mock and real services"""

from app.config.config import Config

class ServiceFactory:
    """Factory class to provide appropriate services based on configuration"""
    
    def __init__(self, config: Config):
        self.config = config
        self._openai_service = None
        self._maps_service = None
        self._otp_service = None
    
    @property
    def openai_service(self):
        """Get OpenAI service (real or mock based on configuration)"""
        if self._openai_service is None:
            if self.config.MOCK_MODE:
                from app.services.mock_openai_service import MockOpenAIService
                self._openai_service = MockOpenAIService(self.config)
            else:
                from app.services.real_openai_service import RealOpenAIService
                self._openai_service = RealOpenAIService(self.config)
        
        return self._openai_service
    
    @property
    def maps_service(self):
        """Get Maps service (real or mock based on configuration)"""
        if self._maps_service is None:
            if self.config.MOCK_MODE:
                from app.services.mock_maps_service import MockMapsService
                self._maps_service = MockMapsService(self.config)
            else:
                from app.services.real_maps_service import RealMapsService
                self._maps_service = RealMapsService(self.config)
        
        return self._maps_service
    
    @property
    def otp_service(self):
        """Get OTP service (real or mock based on configuration)"""
        if self._otp_service is None:
            if self.config.MOCK_MODE:
                from app.services.mock_otp_service import MockOTPService
                self._otp_service = MockOTPService(self.config)
            else:
                from app.services.real_otp_service import RealOTPService
                self._otp_service = RealOTPService(self.config)
        
        return self._otp_service
    
    def reset_services(self):
        """Reset all services (useful for configuration changes)"""
        self._openai_service = None
        self._maps_service = None
        self._otp_service = None
    
    def get_service_status(self):
        """Get status of all services for debugging"""
        return {
            'mode': 'REAL' if not self.config.MOCK_MODE else 'MOCK',
            'openai_service': type(self.openai_service).__name__,
            'maps_service': type(self.maps_service).__name__,
            'otp_service': type(self.otp_service).__name__,
            'config': {
                'mock_mode': self.config.MOCK_MODE,
                'has_openai_key': bool(getattr(self.config, 'OPENAI_API_KEY', None)),
                'has_maps_key': bool(getattr(self.config, 'GOOGLE_MAPS_API_KEY', None)),
                'debug': self.config.DEBUG
            }
        }