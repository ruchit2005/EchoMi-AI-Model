# Live Delivery Location Integration

## Overview
The AI service now receives **live delivery location coordinates** from the backend instead of using hardcoded values. This allows the system to provide accurate directions to delivery personnel based on the actual delivery destination.

## What Changed

### Before (Hardcoded)
```python
# Config had fixed coordinates
USER_LAT = 12.970827983276324
USER_LNG = 79.15943441076058

# Service always used these values
delivery_guide = DeliveryGuidanceService(config)
```

### After (Live Coordinates)
```python
# Backend sends live coordinates with each request
{
    "delivery_location": {
        "latitude": 28.6139,
        "longitude": 77.2090
    }
}

# Service uses live coordinates when available, falls back to config
delivery_guide.guide_delivery_person(
    landmark_description="near pharmacy",
    destination_coords=(28.6139, 77.2090)  # Live coordinates
)
```

## Backend Request Format

The backend now sends delivery location in every request:

```json
{
    "caller_role": "delivery",
    "new_message": "I have a delivery from Swiggy",
    "history": [],
    "conversation_stage": "start",
    "collected_info": {},
    "call_sid": "CA123456",
    "response_language": "en",
    "delivery_location": {           
        "latitude": 28.6139,
        "longitude": 77.2090
    },
    "language_hints": {}
}
```

## Implementation Details

### 1. Request Handler (`app/routes/conversation.py`)
```python
# Extract delivery location from request
delivery_location = data.get("delivery_location")
if delivery_location:
    collected_info['delivery_location'] = delivery_location
    print(f"📍 [LOCATION] Received live coordinates: {lat}, {lng}")
```

### 2. Conversation Handler (`app/services/conversation_handler.py`)
```python
def handle_delivery_logic(self, message, stage, collected_info, 
                         caller_id=None, response_language="en", 
                         delivery_location=None):
    # Store live coordinates
    if delivery_location:
        self.current_delivery_location = delivery_location
        lat = delivery_location.get('latitude')
        lng = delivery_location.get('longitude')
    
    # Pass to guidance service when needed
    destination_coords = None
    if self.current_delivery_location:
        destination_coords = (
            self.current_delivery_location['latitude'],
            self.current_delivery_location['longitude']
        )
    
    guidance_result = self.delivery_guide.guide_delivery_person(
        landmark_description=message,
        destination_coords=destination_coords
    )
```

### 3. Delivery Guidance Service (`app/services/delivery_guidance_service.py`)
```python
def guide_delivery_person(self, landmark_description, max_radius_km=2.0, 
                         destination_coords=None):
    # Use live coordinates if provided, otherwise fall back to config
    if destination_coords:
        dest_lat, dest_lng = destination_coords
        print(f"[GUIDE] Using LIVE destination: {dest_lat}, {dest_lng}")
    else:
        dest_lat, dest_lng = self.destination_lat, self.destination_lng
        print(f"[GUIDE] Using CONFIG destination: {dest_lat}, {dest_lng}")
    
    # Search for landmarks near destination
    landmarks = self._search_overpass(
        landmark_description, 
        max_radius_km, 
        dest_lat, 
        dest_lng
    )
```

All internal methods (`_search_overpass`, `_search_osm`, `_get_directions`, `_calc_distance`) now accept optional destination coordinates and fall back to config values if not provided.

## Benefits

### ✅ Dynamic Location Support
- Each call can have different delivery destinations
- No need to restart service when location changes
- Supports multiple users/locations simultaneously

### ✅ Accurate Directions
- Directions calculated from delivery person's location to actual destination
- Distance calculations use real coordinates
- POI search happens near the correct address

### ✅ Backward Compatible
- Still works if `delivery_location` is not provided
- Falls back to config values (`USER_LAT`, `USER_LNG`)
- No breaking changes to existing functionality

### ✅ Testing Friendly
- Can test different locations without changing code
- Easy to simulate various scenarios
- Config values still work for local testing

## Testing

### Test with Live Coordinates
```bash
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{
    "caller_role": "delivery",
    "new_message": "Hello, I have a delivery from Swiggy",
    "conversation_stage": "start",
    "delivery_location": {
      "latitude": 28.6139,
      "longitude": 77.2090
    },
    "response_language": "en"
  }'
```

### Test Without Coordinates (Fallback)
```bash
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{
    "caller_role": "delivery",
    "new_message": "I need directions",
    "conversation_stage": "getting_current_location"
  }'
```

## Logging

The system logs coordinate source for debugging:

```
📍 [LOCATION] Received live coordinates: 28.6139, 77.2090
[DELIVERY LOCATION] Using live coordinates: 28.6139, 77.2090
[DELIVERY GUIDE] Using LIVE destination: 28.6139, 77.2090
```

Or when falling back:
```
[DELIVERY GUIDE] Using CONFIG destination: 12.970827, 79.159434
```

## Future Enhancements

Potential improvements:
1. **Caching**: Cache locations per call_sid for consistency
2. **Validation**: Add coordinate validation (range checks, format validation)
3. **Geocoding**: Reverse geocode coordinates to show address in logs
4. **Multi-destination**: Support multiple delivery stops in one call
5. **Location History**: Track delivery person's movement during call

## Configuration

The config values remain as fallback:
```python
# .env or config
USER_LAT=12.970827983276324
USER_LNG=79.15943441076058
```

These are used when:
- Backend doesn't send `delivery_location`
- Testing locally without backend
- Backward compatibility with old API clients

## Summary

The integration is complete and working:
- ✅ Backend sends live coordinates
- ✅ AI service extracts and uses them
- ✅ Directions based on real destination
- ✅ Falls back to config gracefully
- ✅ Fully backward compatible

No action needed from backend - it's already sending the coordinates correctly!
