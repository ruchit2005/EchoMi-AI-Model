"""Mock OTP service for testing delivery workflows"""

import time
import random
import string
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from ..models import OTPRequest, OTPResponse, OrderData, OrderStatus
from ..utils import format_otp_for_speech

class MockOTPService:
    """Mock OTP service for testing delivery OTP workflows"""
    
    def __init__(self, config=None):
        self.config = config
        self.call_count = 0
        self.mock_orders = self._initialize_mock_orders()
    
    def _initialize_mock_orders(self) -> Dict[str, OrderData]:
        """Initialize mock order database with realistic delivery addresses"""
        return {
            'SWGY123456789': OrderData(
                order_id='SWGY123456789',
                company='Swiggy',
                tracking_id='TRACK001',
                customer_phone='+91 98765 43210',
                delivery_address='apartment 3B, Brigade Towers, 135 Brigade Road, Bangalore 560001',
                otp='1234',
                status=OrderStatus.APPROVED,
                created_at=datetime.now() - timedelta(minutes=30)
            ),
            'ZOM987654321': OrderData(
                order_id='ZOM987654321',
                company='Zomato',
                tracking_id='TRACK002', 
                customer_phone='+91 87654 32109',
                delivery_address='Flat 204, Prestige Shantiniketan, Whitefield Main Road, Bangalore 560066',
                otp='5678',
                status=OrderStatus.PENDING,
                created_at=datetime.now() - timedelta(minutes=15)
            ),
            'UBR555444333': OrderData(
                order_id='UBR555444333',
                company='Uber Eats',
                tracking_id='TRACK003',
                customer_phone='+91 76543 21098',
                delivery_address='House 15, 2nd Cross, Koramangala 5th Block, Bangalore 560034',
                otp='9012',
                status=OrderStatus.APPROVED,
                created_at=datetime.now() - timedelta(minutes=45)
            ),
            'DMZ777888999': OrderData(
                order_id='DMZ777888999',
                company='Dunzo',
                tracking_id='TRACK004',
                customer_phone='+91 65432 10987',
                delivery_address='Villa 23, Embassy Golf Links, Off Intermediate Ring Road, Bangalore 560071',
                otp='3456',
                status=OrderStatus.APPROVED,
                created_at=datetime.now() - timedelta(minutes=20)
            )
        }
    
    def fetch_otp(self, request: OTPRequest) -> OTPResponse:
        """
        Mock OTP fetching for delivery orders
        
        Args:
            request: OTP request with order details
            
        Returns:
            OTP response with order information
        """
        self.call_count += 1
        
        # Simulate API delay
        time.sleep(0.3)
        
        # Try to find order by company and firebase_uid combination
        company_lower = request.company.lower()
        
        # Find matching orders by company
        matching_orders = []
        for order_id, order in self.mock_orders.items():
            if order.company.lower() in company_lower or company_lower in order.company.lower():
                matching_orders.append(order)
        
        if matching_orders:
            # Return the first matching order
            order = matching_orders[0]
            
            # Generate formatted OTP for speech
            formatted_otp = format_otp_for_speech(order.otp)
            
            return OTPResponse(
                success=True,
                otp=order.otp,
                order_id=order.order_id,
                formatted_otp=formatted_otp,
                message=f"OTP retrieved successfully for {order.company} order {order.order_id}",
                error=None
            )
        else:
            # Generate a random OTP for unknown orders (mock scenario)
            mock_otp = ''.join(random.choices(string.digits, k=4))
            formatted_otp = format_otp_for_speech(mock_otp)
            
            return OTPResponse(
                success=True,
                otp=mock_otp,
                order_id=f"{request.company.upper()}{random.randint(100000, 999999)}",
                formatted_otp=formatted_otp,
                message=f"Mock OTP generated for {request.company} delivery",
                error=None
            )
    
    def add_order(
        self,
        order_id: str,
        company: str,
        customer_phone: Optional[str] = None,
        delivery_address: Optional[str] = None,
        tracking_id: Optional[str] = None
    ) -> bool:
        """
        Add a new order to the mock database
        
        Args:
            order_id: Unique order identifier
            company: Delivery company name
            customer_phone: Customer phone number
            delivery_address: Delivery address
            tracking_id: Tracking ID
            
        Returns:
            Success status
        """
        # Generate random OTP
        otp = ''.join(random.choices(string.digits, k=4))
        
        order = OrderData(
            order_id=order_id,
            company=company,
            customer_phone=customer_phone,
            delivery_address=delivery_address,
            tracking_id=tracking_id or f"TRACK{random.randint(100, 999)}",
            otp=otp,
            status=OrderStatus.PENDING
        )
        
        self.mock_orders[order_id] = order
        return True
    
    def get_order(self, order_id: str) -> Optional[OrderData]:
        """
        Get order details by order ID
        
        Args:
            order_id: Order identifier
            
        Returns:
            Order data or None if not found
        """
        return self.mock_orders.get(order_id)
    
    def find_order_by_company(self, company: str, phone: Optional[str] = None) -> Optional[OrderData]:
        """
        Find order by company and optionally by phone
        
        Args:
            company: Delivery company name
            phone: Optional customer phone number
            
        Returns:
            Order data or None if not found
        """
        company_lower = company.lower()
        
        for order in self.mock_orders.values():
            if (order.company.lower() in company_lower or 
                company_lower in order.company.lower()):
                
                # If phone provided, match it too
                if phone and order.customer_phone:
                    # Simple phone matching (remove spaces and special chars)
                    clean_phone = ''.join(filter(str.isdigit, phone))[-10:]
                    clean_order_phone = ''.join(filter(str.isdigit, order.customer_phone))[-10:]
                    
                    if clean_phone == clean_order_phone:
                        return order
                elif not phone:
                    return order
        
        return None
    
    def update_order_status(self, order_id: str, status: OrderStatus) -> bool:
        """
        Update order status
        
        Args:
            order_id: Order identifier
            status: New status
            
        Returns:
            Success status
        """
        if order_id in self.mock_orders:
            self.mock_orders[order_id].status = status
            self.mock_orders[order_id].updated_at = datetime.now()
            return True
        return False
    
    def get_orders_by_status(self, status: OrderStatus) -> list[OrderData]:
        """
        Get all orders with specific status
        
        Args:
            status: Order status to filter by
            
        Returns:
            List of orders with the status
        """
        return [order for order in self.mock_orders.values() if order.status == status]
    
    def get_order_stats(self) -> Dict[str, Any]:
        """Get order statistics"""
        total_orders = len(self.mock_orders)
        status_counts = {}
        
        for status in OrderStatus:
            count = len([o for o in self.mock_orders.values() if o.status == status])
            status_counts[status.value] = count
        
        return {
            'total_orders': total_orders,
            'status_breakdown': status_counts,
            'recent_orders': len([o for o in self.mock_orders.values() 
                                if o.created_at > datetime.now() - timedelta(hours=1)])
        }
    
    def is_configured(self) -> bool:
        """Check if service is configured (always true for mock)"""
        return True
    
    def get_service_stats(self) -> Dict[str, Any]:
        """Get mock service statistics"""
        return {
            'service_name': 'MockOTPService',
            'total_calls': self.call_count,
            'orders_in_database': len(self.mock_orders),
            'status': 'active',
            'mock_mode': True
        }