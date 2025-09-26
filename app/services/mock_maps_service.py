"""Mock Google Maps service for testing without API key"""

import time
import random
from typing import List, Optional, Dict, Any
from ..models import LocationData
from ..utils import clean_text_input

class MockMapsService:
    """Mock Google Maps service for testing delivery location queries"""
    
    def __init__(self, config=None):
        self.config = config
        self.mock_locations = self._initialize_mock_locations()
        self.call_count = 0
    
    def _initialize_mock_locations(self) -> Dict[str, LocationData]:
        """Initialize mock location database"""
        return {
            'pizza hut': LocationData(
                name="Pizza Hut - Koramangala",
                address="123 100 Feet Road, Koramangala, Bangalore 560034",
                latitude=12.9352,
                longitude=77.6245,
                place_id="ChIJ123_mock_pizza_hut",
                distance_from_user=2.5
            ),
            'mcdonald': LocationData(
                name="McDonald's - Brigade Road",
                address="45 Brigade Road, Ashok Nagar, Bangalore 560001",
                latitude=12.9716,
                longitude=77.5946,
                place_id="ChIJ456_mock_mcdonalds",
                distance_from_user=3.2
            ),
            'kfc': LocationData(
                name="KFC - MG Road",
                address="78 MG Road, Bangalore 560001",
                latitude=12.9758,
                longitude=77.6063,
                place_id="ChIJ789_mock_kfc",
                distance_from_user=3.8
            ),
            'starbucks': LocationData(
                name="Starbucks Coffee - UB City Mall",
                address="UB City Mall, Vittal Mallya Road, Bangalore 560001",
                latitude=12.9719,
                longitude=77.5937,
                place_id="ChIJ012_mock_starbucks",
                distance_from_user=4.1
            ),
            'dominos': LocationData(
                name="Domino's Pizza - Indiranagar",
                address="234 100 Feet Road, Indiranagar, Bangalore 560038",
                latitude=12.9784,
                longitude=77.6408,
                place_id="ChIJ345_mock_dominos",
                distance_from_user=5.2
            ),
            'restaurant': LocationData(
                name="The Restaurant - HSR Layout",
                address="567 27th Main Road, HSR Layout, Bangalore 560102",
                latitude=12.9081,
                longitude=77.6476,
                place_id="ChIJ678_mock_restaurant",
                distance_from_user=6.8
            )
        }
    
    def geocode_location(self, address_text: str, max_distance_km: int = 10) -> Optional[List[LocationData]]:
        """
        Mock geocoding - finds locations matching the address text
        
        Args:
            address_text: Location text to search for
            max_distance_km: Maximum distance filter
            
        Returns:
            List of LocationData objects or None
        """
        self.call_count += 1
        
        # Simulate API delay
        time.sleep(0.1)
        
        # Clean the input
        clean_query = clean_text_input(address_text.lower())
        
        if not clean_query:
            return None
        
        # Find matching locations
        matches = []
        for key, location in self.mock_locations.items():
            if (key in clean_query or 
                clean_query in location.name.lower() or 
                clean_query in location.address.lower()):
                
                # Filter by distance
                if location.distance_from_user <= max_distance_km:
                    matches.append(location)
        
        # If no direct matches, return some nearby restaurants
        if not matches and any(word in clean_query for word in ['food', 'restaurant', 'delivery', 'order']):
            matches = [self.mock_locations['pizza hut'], self.mock_locations['mcdonald']]
        
        # Sort by distance
        matches.sort(key=lambda x: x.distance_from_user)
        
        return matches if matches else None
    
    def get_navigation_directions(
        self, 
        current_location: str, 
        destination_address: str,
        include_detailed_steps: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Get detailed navigation from current location to delivery address
        
        Args:
            current_location: Delivery person's current location (can be vague)
            destination_address: Customer's delivery address
            include_detailed_steps: Include turn-by-turn directions
            
        Returns:
            Detailed navigation information
        """
        self.call_count += 1
        
        # Simulate API delay
        time.sleep(0.3)
        
        # Try to geocode both locations
        current_coords = self._get_location_coordinates(current_location)
        destination_coords = self._get_location_coordinates(destination_address)
        
        if not destination_coords:
            return None
        
        # Calculate mock distance and duration
        base_distance = random.uniform(2.0, 12.0)
        travel_time = max(5, int(base_distance * 3 + random.randint(-5, 10)))
        
        # Generate detailed navigation steps
        steps = self._generate_navigation_steps(
            current_location, 
            destination_address, 
            base_distance
        )
        
        # Generate voice-friendly directions
        voice_directions = self._generate_voice_directions(
            current_location,
            destination_address,
            steps
        )
        
        navigation_data = {
            'status': 'OK',
            'origin': {
                'address': current_location,
                'coordinates': current_coords
            },
            'destination': {
                'address': destination_address,
                'coordinates': destination_coords
            },
            'distance': f"{base_distance:.1f} km",
            'duration': f"{travel_time} mins",
            'traffic_condition': random.choice(['light', 'moderate', 'heavy']),
            'steps': steps if include_detailed_steps else [],
            'voice_directions': voice_directions,
            'summary': f"Navigate {base_distance:.1f} km from {current_location} to {destination_address}. Estimated time: {travel_time} minutes."
        }
        
        return navigation_data
    
    def _get_location_coordinates(self, location: str) -> Optional[Dict[str, float]]:
        """Get coordinates for a location (mock implementation)"""
        
        # Check if it matches any known location
        location_lower = location.lower()
        for key, loc_data in self.mock_locations.items():
            if (key in location_lower or 
                location_lower in loc_data.name.lower() or
                location_lower in loc_data.address.lower()):
                return {
                    'lat': loc_data.latitude,
                    'lng': loc_data.longitude
                }
        
        # Generate mock coordinates for unknown locations
        # Bangalore area coordinates (rough bounds)
        base_lat = 12.9716  # Bangalore center
        base_lng = 77.5946
        
        return {
            'lat': base_lat + random.uniform(-0.1, 0.1),
            'lng': base_lng + random.uniform(-0.1, 0.1)
        }
    
    def _generate_navigation_steps(
        self, 
        origin: str, 
        destination: str, 
        distance: float
    ) -> List[Dict[str, Any]]:
        """Generate turn-by-turn navigation steps"""
        
        steps = []
        
        # Step 1: Head out from current location
        steps.append({
            'step_number': 1,
            'instruction': f"Head towards the main road from {origin}",
            'distance': f"{distance * 0.1:.1f} km",
            'duration': "2-3 mins",
            'maneuver': "start"
        })
        
        # Step 2-4: Middle navigation steps
        road_types = ['main road', 'highway', 'inner road', 'service road']
        directions = ['left', 'right', 'straight']
        landmarks = ['traffic signal', 'metro station', 'mall', 'hospital', 'school', 'temple']
        
        num_middle_steps = random.randint(2, 4)
        for i in range(num_middle_steps):
            step_num = i + 2
            road = random.choice(road_types)
            direction = random.choice(directions)
            landmark = random.choice(landmarks)
            
            steps.append({
                'step_number': step_num,
                'instruction': f"Turn {direction} at the {landmark} and continue on {road}",
                'distance': f"{distance * 0.3:.1f} km",
                'duration': f"{random.randint(3, 8)} mins",
                'maneuver': direction
            })
        
        # Final step: Arrive at destination
        steps.append({
            'step_number': len(steps) + 1,
            'instruction': f"Your destination {destination} will be on your left/right",
            'distance': f"{distance * 0.1:.1f} km",
            'duration': "1-2 mins",
            'maneuver': "arrive"
        })
        
        return steps
    
    def _generate_voice_directions(
        self, 
        origin: str, 
        destination: str, 
        steps: List[Dict[str, Any]]
    ) -> str:
        """Generate voice-friendly directions for delivery person"""
        
        voice_parts = []
        
        voice_parts.append(f"Starting navigation from {origin} to {destination}.")
        
        # Add key steps in simple language
        if len(steps) > 2:
            voice_parts.append("Here are your main directions:")
            voice_parts.append(f"First, {steps[0]['instruction'].lower()}.")
            
            if len(steps) > 3:
                middle_step = steps[len(steps)//2]
                voice_parts.append(f"Then, {middle_step['instruction'].lower()}.")
            
            final_step = steps[-1]
            voice_parts.append(f"Finally, {final_step['instruction'].lower()}.")
        
        voice_parts.append(f"Total distance is approximately {steps[0].get('distance', 'unknown')}.")
        voice_parts.append("Drive safely and call if you need more help!")
        
        return " ".join(voice_parts)

    def get_directions(self, origin: str, destination: str) -> Optional[Dict[str, Any]]:
        """
        Mock directions API
        
        Args:
            origin: Starting location
            destination: Destination location
            
        Returns:
            Mock directions data
        """
        self.call_count += 1
        
        # Simulate API delay
        time.sleep(0.2)
        
        # Generate mock directions
        mock_directions = {
            'status': 'OK',
            'distance': f"{random.uniform(1.0, 8.0):.1f} km",
            'duration': f"{random.randint(5, 25)} mins",
            'steps': [
                f"Head towards {destination} from {origin}",
                "Take the main road",
                "Turn right at the traffic signal", 
                f"You will find {destination} on your left"
            ],
            'directions_text': f"To reach {destination} from {origin}: Head towards the main road, take a right at the signal, and look for the destination on your left. Approximately {random.randint(5, 25)} minutes away."
        }
        
        return mock_directions
    
    def search_nearby_places(self, location: str, place_type: str = "restaurant") -> List[LocationData]:
        """
        Mock nearby places search
        
        Args:
            location: Center location for search
            place_type: Type of places to search for
            
        Returns:
            List of nearby places
        """
        self.call_count += 1
        
        # Simulate API delay
        time.sleep(0.1)
        
        # Return random subset of mock locations
        all_locations = list(self.mock_locations.values())
        random.shuffle(all_locations)
        
        return all_locations[:3]  # Return top 3 results
    
    def get_place_details(self, place_id: str) -> Optional[Dict[str, Any]]:
        """
        Mock place details API
        
        Args:
            place_id: Google Places ID
            
        Returns:
            Mock place details
        """
        self.call_count += 1
        
        # Find location by place_id
        for location in self.mock_locations.values():
            if location.place_id == place_id:
                return {
                    'name': location.name,
                    'address': location.address,
                    'phone': '+91 80 1234 5678',
                    'rating': round(random.uniform(3.5, 4.8), 1),
                    'opening_hours': 'Open 24 hours' if 'McDonald' in location.name else '10:00 AM - 11:00 PM',
                    'place_id': location.place_id
                }
        
        return None
    
    def is_configured(self) -> bool:
        """Check if service is configured (always true for mock)"""
        return True
    
    def get_service_stats(self) -> Dict[str, Any]:
        """Get mock service statistics"""
        return {
            'service_name': 'MockMapsService',
            'total_calls': self.call_count,
            'locations_in_database': len(self.mock_locations),
            'status': 'active',
            'mock_mode': True
        }