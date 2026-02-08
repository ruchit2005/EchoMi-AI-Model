"""Service factory for managing real services"""

from app.config.config import Config

class ServiceFactory:
    """Factory class to provide services"""
    
    def __init__(self, config: Config):
        self.config = config
        self._openai_service = None
        self._maps_service = None
        self._otp_service = None
        self._notification_service = None
    
    @property
    def openai_service(self):
        """Get OpenAI service"""
        if self._openai_service is None:
            from app.services.real_openai_service import RealOpenAIService
            self._openai_service = RealOpenAIService(self.config)
        return self._openai_service
    
    @property
    def maps_service(self):
        """Get Maps service"""
        if self._maps_service is None:
            # Use Mapbox service for production
            from app.services.mapbox_service import MapboxService
            self._maps_service = MapboxService(self.config)
        return self._maps_service
    
    @property
    def notification_service(self):
        """Get Notification service"""
        if self._notification_service is None:
            from app.services.notification_service import NotificationService
            self._notification_service = NotificationService(self.config)
        return self._notification_service
    
    @property
    def otp_service(self):
        """Get SMS/OTP service"""
        if self._otp_service is None:
            from app.services.sms_service import SMSService
            self._otp_service = SMSService(self.config)
        return self._otp_service
    
    @property
    def sms_service(self):
        """Get SMS service - alias for otp_service"""
        return self.otp_service