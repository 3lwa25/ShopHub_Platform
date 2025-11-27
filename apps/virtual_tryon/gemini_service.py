"""
Gemini API Service for Virtual Try-On
Provides intelligent image analysis for better product placement
"""
import json
import base64
import io
from django.conf import settings

try:
    from PIL import Image, ImageFilter, ImageEnhance
    PIL_AVAILABLE = True
    ImageFilter = ImageFilter
    ImageEnhance = ImageEnhance
except ImportError:
    PIL_AVAILABLE = False
    Image = None
    ImageFilter = None
    ImageEnhance = None

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    np = None

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    genai = None


def analyze_image_for_vto(image_bytes, product_type, placement_mode='auto'):
    """
    Analyze image using Gemini API for intelligent VTO placement
    
    Args:
        image_bytes: Image file bytes
        product_type: Type of product (clothing, accessory, room object, etc.)
        placement_mode: 'face', 'room', or 'auto'
    
    Returns:
        dict with analysis results:
        {
            'scene_type': 'clothing' | 'room' | 'generic',
            'body_landmarks': {...} or None,
            'room_surfaces': [...] or None,
            'recommended_position': {'x': 0.5, 'y': 0.6},  # as percentages
            'recommended_size': 0.25,  # as percentage of image width
            'recommended_rotation': 0,
            'confidence': 0.0-1.0
        }
    """
    if not GEMINI_AVAILABLE or not hasattr(settings, 'GEMINI_API_KEY'):
        return _fallback_analysis(image_bytes, product_type, placement_mode)
    
    try:
        # Configure Gemini
        api_key = getattr(settings, 'GEMINI_API_KEY', None)
        if not api_key or api_key == '' or api_key == 'AIzaSyC7vffx7nSy6vxjcbKpowQRae2OzONpWvs':
            print("⚠️ Gemini API key not configured or using default, using fallback")
            return _fallback_analysis(image_bytes, product_type, placement_mode)
        
        print(f"🔑 Using Gemini API key: {api_key[:10]}...")
        genai.configure(api_key=api_key)
        
        # Use Gemini 2.0 Flash for vision
        model_name = getattr(settings, 'GEMINI_MODEL_NAME', 'gemini-2.0-flash-exp')
        print(f"🤖 Attempting to use model: {model_name}")
        
        try:
            model = genai.GenerativeModel(model_name)
            print(f"✅ Model {model_name} loaded successfully")
        except Exception as model_error:
            print(f"⚠️ Model {model_name} failed, trying gemini-1.5-flash: {model_error}")
            # Fallback to gemini-1.5-flash if 2.0 not available
            try:
                model = genai.GenerativeModel('gemini-1.5-flash')
                print("✅ Fallback model gemini-1.5-flash loaded")
            except Exception as fallback_error:
                print(f"❌ Fallback model also failed: {fallback_error}")
                raise
        
        # Prepare image
        try:
            if not PIL_AVAILABLE:
                raise ImportError("PIL not available")
            image = Image.open(io.BytesIO(image_bytes))
            print(f"✅ Image loaded: {image.size[0]}x{image.size[1]}")
        except Exception as img_error:
            print(f"❌ Failed to open image: {img_error}")
            raise
        
        # Build prompt based on product type and placement mode
        prompt = _build_analysis_prompt(product_type, placement_mode)
        print(f"📝 Prompt built for {product_type} in {placement_mode} mode")
        
        # Call Gemini
        
        try:
            response = model.generate_content(
                [prompt, image],
                generation_config={
                    'temperature': 0.1,
                    'max_output_tokens': 1000,
                }
            )
            
            # ENHANCED: Check for finish_reason and handle blocked/safety issues
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'finish_reason'):
                    finish_reason = candidate.finish_reason
                    # finish_reason 2 = SAFETY (content blocked)
                    # finish_reason 3 = RECITATION (potential copyright)
                    # finish_reason 4 = OTHER
                    if finish_reason in [2, 3, 4]:
                        print(f"⚠️ Gemini blocked response (finish_reason: {finish_reason}), using fallback")
                        return _fallback_analysis(image_bytes, product_type, placement_mode)
            
            # ENHANCED: Safely access response.text with error handling
            try:
                response_text = response.text if hasattr(response, 'text') and response.text else None
                if not response_text:
                    print("⚠️ Empty response from Gemini")
                    return _fallback_analysis(image_bytes, product_type, placement_mode)
                
                print(f"📥 Gemini response received: {len(response_text)} chars")
                print(f"Response preview: {response_text[:200]}...")
                
                # Parse response
                result = _parse_gemini_response(response_text, product_type, placement_mode)
                print(f"✅ Parsed result: {result}")
                return result
                
            except Exception as text_error:
                print(f"⚠️ Error accessing response.text: {text_error}")
                if 'finish_reason' in str(text_error) or 'Part' in str(text_error):
                    print("⚠️ Gemini response blocked or invalid, using fallback")
                return _fallback_analysis(image_bytes, product_type, placement_mode)
            
        except Exception as api_error:
            print(f"❌ Gemini API call failed: {api_error}")
            print(f"Error type: {type(api_error).__name__}")
            # Check if it's the specific finish_reason error
            if 'finish_reason' in str(api_error) or 'Part' in str(api_error):
                print("⚠️ Gemini response blocked or invalid, using fallback analysis")
                return _fallback_analysis(image_bytes, product_type, placement_mode)
            import traceback
            print(traceback.format_exc())
            raise
        
    except Exception as e:
        print(f"❌ Gemini API error: {type(e).__name__}: {e}")
        import traceback
        print(traceback.format_exc())
        return _fallback_analysis(image_bytes, product_type, placement_mode)


def _build_analysis_prompt(product_type, placement_mode):
    """Build analysis prompt for Gemini"""
    
    if placement_mode == 'face' or 'clothing' in product_type.lower() or 'wear' in product_type.lower():
        # Clothing analysis
        prompt = f"""Analyze this image for virtual try-on of a {product_type}.

Focus on detecting:
1. Is there a person in the image? (yes/no)
2. If yes, provide body landmarks as percentages of image dimensions:
   - Face center: {{x, y}}
   - Shoulder width: width in pixels
   - Shoulder position: {{x, y}}
   - Torso center: {{x, y}}
   - Torso width: width in pixels
   - Torso height: height in pixels
3. Recommended clothing placement:
   - Position (x, y as percentages 0-1)
   - Size (width as percentage of image width)
   - Rotation angle in degrees
4. Scene type: 'clothing' or 'generic'

Return ONLY valid JSON in this exact format:
{{
  "scene_type": "clothing",
  "has_person": true,
  "body_landmarks": {{
    "face": {{"x": 0.5, "y": 0.3, "width": 0.15, "height": 0.2}},
    "shoulders": {{"x": 0.5, "y": 0.45, "width": 0.3}},
    "torso": {{"x": 0.5, "y": 0.6, "width": 0.28, "height": 0.4}}
  }},
  "recommended_position": {{"x": 0.5, "y": 0.5}},
  "recommended_size": 0.25,
  "recommended_rotation": 0,
  "confidence": 0.9
}}"""
    
    elif placement_mode == 'room' or 'room' in product_type.lower() or 'decor' in product_type.lower():
        # Room object analysis
        prompt = f"""Analyze this image for placing a {product_type} in the room.

Focus on detecting:
1. Room type and surfaces:
   - Floor surfaces (tables, counters, shelves)
   - Wall surfaces
   - Best placement areas
2. Recommended placement:
   - Position (x, y as percentages 0-1)
   - Size (width as percentage of image width)
   - Rotation angle for perspective
3. Scene type: 'room' or 'generic'

Return ONLY valid JSON in this exact format:
{{
  "scene_type": "room",
  "room_surfaces": [
    {{"type": "table", "x": 0.5, "y": 0.7, "width": 0.4, "height": 0.1}}
  ],
  "recommended_position": {{"x": 0.5, "y": 0.65}},
  "recommended_size": 0.2,
  "recommended_rotation": 0,
  "confidence": 0.85
}}"""
    
    else:
        # Auto-detect
        prompt = f"""Analyze this image for virtual try-on of a {product_type}.

Determine:
1. Scene type: 'clothing' (has person), 'room' (interior space), or 'generic'
2. If clothing: detect body landmarks
3. If room: detect surfaces
4. Recommended placement position, size, and rotation

Return ONLY valid JSON with scene_type, body_landmarks or room_surfaces, recommended_position, recommended_size, recommended_rotation, confidence."""
    
    return prompt


def _parse_gemini_response(response_text, product_type, placement_mode):
    """Parse Gemini response and extract structured data"""
    
    if not response_text:
        print("⚠️ Empty response text from Gemini")
        return _fallback_analysis(None, product_type, placement_mode)
    
    print(f"🔍 Parsing Gemini response: {len(response_text)} chars")
    
    try:
        # Try to extract JSON from response
        # Gemini sometimes wraps JSON in markdown or adds text
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1
        
        if json_start >= 0 and json_end > json_start:
            json_str = response_text[json_start:json_end]
            print(f"📋 Extracted JSON: {json_str[:200]}...")
            
            data = json.loads(json_str)
            print(f"✅ JSON parsed successfully")
            
            # Validate and normalize
            result = {
                'scene_type': data.get('scene_type', 'generic'),
                'body_landmarks': data.get('body_landmarks'),
                'room_surfaces': data.get('room_surfaces'),
                'recommended_position': data.get('recommended_position', {'x': 0.5, 'y': 0.5}),
                'recommended_size': float(data.get('recommended_size', 0.25)),
                'recommended_rotation': float(data.get('recommended_rotation', 0)),
                'confidence': float(data.get('confidence', 0.7)),
            }
            
            # Convert percentages to absolute if needed
            if 'has_person' in data and data.get('has_person'):
                result['has_person'] = True
            
            print(f"✅ Parsed result: scene_type={result['scene_type']}, confidence={result['confidence']}")
            return result
        else:
            print(f"⚠️ No JSON found in response")
            print(f"Full response: {response_text}")
            
    except json.JSONDecodeError as e:
        print(f"❌ JSON decode error: {e}")
        print(f"Response: {response_text[:500]}")
    except (KeyError, ValueError) as e:
        print(f"❌ Error parsing response: {e}")
        print(f"Response: {response_text[:200]}")
    except Exception as e:
        print(f"❌ Unexpected error parsing response: {type(e).__name__}: {e}")
        import traceback
        print(traceback.format_exc())
    
    # Fallback
    print("⚠️ Using fallback analysis")
    return _fallback_analysis(None, product_type, placement_mode)


def remove_background_with_gemini(image_bytes, product_type='clothing'):
    """
    Remove background from product image using Gemini API for best quality
    Uses Gemini's vision capabilities to identify and remove background
    
    Returns:
        dict with 'image_data' (base64) and 'format' (png)
    """
    if not GEMINI_AVAILABLE or not hasattr(settings, 'GEMINI_API_KEY'):
        return _fallback_background_removal(image_bytes)
    
    try:
        api_key = getattr(settings, 'GEMINI_API_KEY', None)
        if not api_key or api_key == '':
            return _fallback_background_removal(image_bytes)
        
        genai.configure(api_key=api_key)
        
        # Use Gemini 2.0 Flash for vision
        model_name = getattr(settings, 'GEMINI_MODEL_NAME', 'gemini-2.0-flash-exp')
        try:
            model = genai.GenerativeModel(model_name)
        except Exception:
            model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Prepare image
        if not PIL_AVAILABLE:
            return _fallback_background_removal(image_bytes)
        image = Image.open(io.BytesIO(image_bytes))
        print(f"🎨 Processing image for background removal: {image.size[0]}x{image.size[1]}")
        
        # Build prompt for background removal
        prompt = f"""Remove the background from this {product_type} product image. 
        
Return ONLY a JSON object with:
1. A detailed description of the product object/clothing
2. The exact boundaries of the product
3. Recommended background removal method

Format:
{{
  "product_description": "detailed description",
  "boundaries": "description of edges",
  "removal_method": "chroma|edge|segmentation"
}}"""
        
        # Call Gemini with proper error handling for finish_reason
        try:
            response = model.generate_content(
                [prompt, image],
                generation_config={
                    'temperature': 0.1,
                    'max_output_tokens': 500,
                }
            )
            
            # ENHANCED: Check for finish_reason and handle blocked/safety issues
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'finish_reason'):
                    finish_reason = candidate.finish_reason
                    # finish_reason 2 = SAFETY (content blocked)
                    # finish_reason 3 = RECITATION (potential copyright)
                    # finish_reason 4 = OTHER
                    if finish_reason in [2, 3, 4]:
                        print(f"⚠️ Gemini blocked response (finish_reason: {finish_reason}), using fallback")
                        return _fallback_background_removal(image_bytes)
            
            # ENHANCED: Safely access response.text with error handling
            try:
                response_text = response.text if hasattr(response, 'text') and response.text else None
                if response_text:
                    print(f"📥 Gemini background analysis: {response_text[:200]}")
                else:
                    print("⚠️ No text in Gemini response, using fallback")
                    return _fallback_background_removal(image_bytes)
            except Exception as text_error:
                print(f"⚠️ Error accessing response.text: {text_error}, using fallback")
                return _fallback_background_removal(image_bytes)
            
            # Use Gemini's analysis to guide removal
            # For now, use advanced edge detection and chroma key
            return _advanced_background_removal(image_bytes, product_type)
            
        except Exception as api_error:
            print(f"⚠️ Gemini API call error: {api_error}")
            # Check if it's the specific finish_reason error
            if 'finish_reason' in str(api_error) or 'Part' in str(api_error):
                print("⚠️ Gemini response blocked or invalid, using fallback background removal")
            return _fallback_background_removal(image_bytes)
        
    except Exception as e:
        print(f"Gemini background removal error: {e}")
        return _fallback_background_removal(image_bytes)


def _advanced_background_removal(image_bytes, product_type):
    """Advanced background removal using multiple techniques"""
    if not PIL_AVAILABLE or not NUMPY_AVAILABLE:
        return _fallback_background_removal(image_bytes)
    
    try:
        image = Image.open(io.BytesIO(image_bytes)).convert('RGBA')
        width, height = image.size
        
        # Convert to numpy for processing
        img_array = np.array(image)
        data = img_array.copy()
        
        # Method 1: Edge detection for object boundaries
        gray = image.convert('L')
        if ImageFilter:
            edges = gray.filter(ImageFilter.FIND_EDGES)
            edge_array = np.array(edges)
        else:
            # Fallback: create empty edge array
            edge_array = np.zeros((height, width), dtype=np.uint8)
        
        # Method 2: Sample background from corners and edges
        corner_samples = []
        edge_margin = min(width, height) // 20
        
        # Sample corners
        for x in [0, width-1]:
            for y in [0, height-1]:
                if x < edge_margin or x > width - edge_margin or y < edge_margin or y > height - edge_margin:
                    corner_samples.append(img_array[y, x, :3])
        
        # Sample edges
        for i in range(0, width, width//20):
            corner_samples.append(img_array[0, i, :3])  # Top
            corner_samples.append(img_array[height-1, i, :3])  # Bottom
        for i in range(0, height, height//20):
            corner_samples.append(img_array[i, 0, :3])  # Left
            corner_samples.append(img_array[i, width-1, :3])  # Right
        
        # Calculate dominant background color
        corner_samples = np.array(corner_samples)
        bg_color = np.median(corner_samples, axis=0).astype(int)
        
        print(f"🎨 Detected background: RGB({bg_color[0]}, {bg_color[1]}, {bg_color[2]})")
        
        # Method 3: Adaptive threshold based on edge detection and color
        threshold = 50
        feather_distance = 3
        
        for y in range(height):
            for x in range(width):
                pixel = img_array[y, x]
                r, g, b, a = pixel
                
                # Calculate color difference
                color_diff = np.abs(pixel[:3] - bg_color).sum()
                
                # Check edge strength
                edge_strength = edge_array[y, x]
                
                # Adaptive removal
                if color_diff < threshold and edge_strength < 50:
                    # Definitely background
                    data[y, x, 3] = 0
                elif color_diff < threshold * 1.5:
                    # Probably background, feather edge
                    feather_factor = (color_diff / (threshold * 1.5))
                    data[y, x, 3] = int(data[y, x, 3] * feather_factor)
                elif edge_strength > 100:
                    # Strong edge, keep fully opaque
                    data[y, x, 3] = 255
                # else keep original alpha
        
        # Convert back to PIL Image
        result_image = Image.fromarray(data, 'RGBA')
        
        # Convert to base64
        output = io.BytesIO()
        result_image.save(output, format='PNG')
        output.seek(0)
        image_data = base64.b64encode(output.read()).decode('utf-8')
        
        return {
            'image_data': image_data,
            'format': 'png'
        }
        
    except Exception as e:
        print(f"Advanced background removal error: {e}")
        return _fallback_background_removal(image_bytes)


def _fallback_background_removal(image_bytes):
    """Fallback background removal using simple chroma key"""
    if not PIL_AVAILABLE or not NUMPY_AVAILABLE:
        return None
    
    try:
        image = Image.open(io.BytesIO(image_bytes)).convert('RGBA')
        width, height = image.size
        img_array = np.array(image)
        data = img_array.copy()
        
        # Simple corner-based removal
        corner_samples = [
            img_array[0, 0, :3],
            img_array[0, width-1, :3],
            img_array[height-1, 0, :3],
            img_array[height-1, width-1, :3]
        ]
        bg_color = np.median(corner_samples, axis=0).astype(int)
        
        threshold = 40
        for y in range(height):
            for x in range(width):
                pixel = img_array[y, x, :3]
                diff = np.abs(pixel - bg_color).sum()
                if diff < threshold:
                    data[y, x, 3] = 0
                else:
                    feather = min(diff / threshold, 1.0)
                    data[y, x, 3] = int(data[y, x, 3] * feather)
        
        result_image = Image.fromarray(data, 'RGBA')
        output = io.BytesIO()
        result_image.save(output, format='PNG')
        output.seek(0)
        image_data = base64.b64encode(output.read()).decode('utf-8')
        
        return {
            'image_data': image_data,
            'format': 'png'
        }
    except Exception as e:
        print(f"Fallback background removal error: {e}")
        return None


def _fallback_analysis(image_bytes, product_type, placement_mode):
    """Fallback analysis when Gemini is not available"""
    
    if placement_mode == 'face' or 'clothing' in product_type.lower():
        return {
            'scene_type': 'clothing',
            'body_landmarks': None,
            'room_surfaces': None,
            'recommended_position': {'x': 0.5, 'y': 0.5},
            'recommended_size': 0.25,
            'recommended_rotation': 0,
            'confidence': 0.5,
        }
    elif placement_mode == 'room':
        return {
            'scene_type': 'room',
            'body_landmarks': None,
            'room_surfaces': None,
            'recommended_position': {'x': 0.5, 'y': 0.65},
            'recommended_size': 0.2,
            'recommended_rotation': 0,
            'confidence': 0.5,
        }
    else:
        return {
            'scene_type': 'generic',
            'body_landmarks': None,
            'room_surfaces': None,
            'recommended_position': {'x': 0.5, 'y': 0.5},
            'recommended_size': 0.25,
            'recommended_rotation': 0,
            'confidence': 0.3,
        }

