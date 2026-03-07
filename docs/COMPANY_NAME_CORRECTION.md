# Company Name Correction for Misheard Audio Transcription

## Problem
When delivery personnel call and mention company names like "Swiggy" or "Zomato", audio transcription AI sometimes mishears them as:
- "speaky" instead of "Swiggy"
- "zoomato" instead of "Zomato"
- "amazen" instead of "Amazon"
- etc.

## Solution: Two-Tier Intelligent Correction

### 1. Primary: AI-Powered Correction (Recommended)
When OpenAI API is available, the system uses GPT-4o-mini to **intelligently understand and correct** misheard company names.

**How it works:**
- The AI is prompted with examples of common mishearings
- Uses natural language understanding and context
- Can recognize NEW variations without hardcoding
- More flexible and maintainable

**Example prompt excerpt:**
```
Common mishearings you should recognize and fix:
- "speaky", "sweegy", "sweeji" → Swiggy
- "zoomato", "zometto" → Zomato  
- "amazen", "amazone" → Amazon
...and ANY OTHER similar phonetic errors
```

**Benefits:**
- ✅ Understands context: "delivery from speaky" → company is "Swiggy"
- ✅ No hardcoded list needed for every variation
- ✅ Can handle unknown variations intelligently
- ✅ Learns from examples in the system prompt
- ✅ More maintainable - just update the prompt

### 2. Fallback: Fuzzy Matching
When OpenAI API is **not available**, the system falls back to algorithmic fuzzy matching.

**How it works:**
- Character-level similarity (Levenshtein distance)
- Phonetic matching (consonant patterns)
- Hardcoded list of delivery companies with common variations

**Benefits:**
- ✅ Works offline (no API required)
- ✅ Deterministic and fast
- ✅ No API costs
- ✅ Reliable for known variations

**Drawback:**
- ⚠️ Requires maintaining hardcoded lists
- ⚠️ Cannot handle completely new variations

## Implementation

### Files Modified:

1. **`app/services/real_openai_service.py`**
   - Enhanced `extract_information_with_ai()` with intelligent correction prompt
   - AI learns to recognize and fix mishearings contextually

2. **`app/utils/text_processing.py`**
   - Added `fuzzy_match_company_name()` as fallback
   - Added `extract_company_with_fuzzy_matching()` wrapper
   - Includes 20+ delivery companies with variations

3. **`app/services/conversation_handler.py`**
   - Uses AI extraction as primary method
   - Falls back to fuzzy matching when AI unavailable

## Usage

The correction happens automatically in:
- Initial caller identification
- Company name extraction from messages
- OTP request handling
- Intent detection

## Testing

```bash
# Test fuzzy matching fallback
python test_fuzzy_matching.py

# Test AI-powered correction (requires OpenAI API key)
python test_ai_company_correction.py
```

## Supported Companies

The system recognizes (and corrects mishearings for):
- Food Delivery: Swiggy, Zomato, Uber Eats, Dunzo
- E-commerce: Amazon, Flipkart, Myntra, BigBasket, Blinkit
- Courier: BlueDart, DTDC, FedEx, DHL, Delhivery
- And more...

## Configuration

To enable AI-powered correction, set your OpenAI API key:
```bash
# .env file
OPENAI_API_KEY=sk-your-api-key-here
```

Without the API key, the system automatically uses fuzzy matching fallback.

## Why This Approach?

1. **Best of Both Worlds**: AI intelligence when available, reliable fallback when not
2. **Cost Effective**: Only uses API for extraction (cheap operation)
3. **Maintainable**: Update prompt examples instead of hardcoded lists
4. **Flexible**: AI can handle new variations without code changes
5. **Reliable**: Works even without internet/API access

## Example Corrections

| Audio Input → | AI Detects | Fallback Detects | Confidence |
|--------------|------------|------------------|------------|
| "speaky" | Swiggy | Swiggy | 100% |
| "zoomato" | Zomato | Zomato | 100% |
| "amazen" | Amazon | Amazon | 100% |
| "stick see" | DTDC | DTDC | 84% |
| "new-variation" | (learns) | Not detected | - |

**Key advantage**: AI can recognize completely new variations that weren't hardcoded!
