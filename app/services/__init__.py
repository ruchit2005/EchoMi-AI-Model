"""Service imports and initialization"""

from ..config.config import Config

# Import real services
from .real_openai_service import RealOpenAIService
from .mapbox_service import MapboxService
from .real_otp_service import RealOTPService
from .sms_service import SMSService
from .notification_service import NotificationService

# Initialize services - always use real services
openai_service = RealOpenAIService(Config)
maps_service = MapboxService(Config)
otp_service = RealOTPService(Config)
sms_service = SMSService(Config)
notification_service = NotificationService(Config)

__all__ = [
    'openai_service',
    'maps_service', 
    'otp_service',
    'sms_service',
    'notification_service'
]
