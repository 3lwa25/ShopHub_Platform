"""
Virtual Try-On Views
Handles VTO interface, sessions, and image processing
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.core.files.base import ContentFile
from django.utils import timezone
from django.conf import settings
import uuid
import json
import base64
from datetime import timedelta

from apps.products.models import Product
from apps.virtual_tryon.models import VTOAsset, TryonSession, TryonImage
from apps.virtual_tryon.gemini_service import analyze_image_for_vto, remove_background_with_gemini


def vto_home(request):
    """
    Virtual Try-On homepage
    Shows VTO-enabled products grouped by category
    """
    # Get VTO-enabled products with good images
    vto_products = Product.objects.filter(
        status='active',
        vto_enabled=True
    ).prefetch_related('images', 'category', 'vto_assets').select_related('category')
    
    # Group by asset type
    products_by_type = {
        'glasses': vto_products.filter(vto_assets__asset_type='glasses').distinct(),
        'hats': vto_products.filter(vto_assets__asset_type='hat').distinct(),
        'jewelry': vto_products.filter(vto_assets__asset_type='jewelry').distinct(),
        'masks': vto_products.filter(vto_assets__asset_type='mask').distinct(),
        'accessories': vto_products.filter(vto_assets__asset_type='accessory').distinct(),
    }
    
    context = {
        'products_by_type': products_by_type,
        'total_vto_products': vto_products.count(),
    }
    
    return render(request, 'virtual_tryon/vto_home.html', context)


def vto_tryon(request, product_id):
    """
    Virtual Try-On interface for a specific product
    """
    product = get_object_or_404(
        Product,
        id=product_id,
        status='active',
        vto_enabled=True
    )
    
    # Get VTO assets for this product
    vto_assets = product.vto_assets.filter(is_active=True)
    
    if not vto_assets.exists():
        return redirect('virtual_tryon:vto_home')
    
    # Get primary VTO asset
    vto_asset = vto_assets.first()
    
    # Ensure anchor_points is valid JSON
    if vto_asset and vto_asset.anchor_points:
        import json
        try:
            # Ensure it's valid JSON
            if isinstance(vto_asset.anchor_points, str):
                json.loads(vto_asset.anchor_points)
            else:
                json.dumps(vto_asset.anchor_points)
        except (json.JSONDecodeError, TypeError):
            # Reset to empty dict if invalid
            vto_asset.anchor_points = {}
    
    # Get or create session
    session = get_or_create_session(request)
    
    # ENHANCED: Ensure vto_asset has overlay_image before passing to template
    if vto_asset and not vto_asset.overlay_image:
        # If no overlay image, redirect to VTO home
        return redirect('virtual_tryon:vto_home')
    
    context = {
        'product': product,
        'vto_assets': vto_assets,
        'vto_asset': vto_asset,
        'session_id': str(session.session_id),
    }
    
    return render(request, 'virtual_tryon/vto_tryon.html', context)


@require_http_methods(["POST"])
def vto_upload_photo(request):
    """
    Handle photo upload for VTO
    Accepts either file upload or base64 data from webcam
    """
    try:
        session_id = request.POST.get('session_id')
        product_id = request.POST.get('product_id')
        
        if not session_id or not product_id:
            return JsonResponse({'error': 'Missing required parameters'}, status=400)
        
        # Get session and product
        session = get_object_or_404(TryonSession, session_id=session_id)
        product = get_object_or_404(Product, id=product_id, vto_enabled=True)
        
        # Handle file upload or base64 data
        if 'photo' in request.FILES:
            photo = request.FILES['photo']
            tryon_image = TryonImage.objects.create(
                session=session,
                product=product,
                user_photo=photo,
                status='pending',
            )
        elif 'photo_data' in request.POST:
            # Base64 from webcam
            photo_data = request.POST['photo_data']
            
            # Remove data:image/png;base64, prefix if present
            if 'base64,' in photo_data:
                photo_data = photo_data.split('base64,')[1]
            
            # Decode base64
            image_data = base64.b64decode(photo_data)
            
            # Create TryonImage
            tryon_image = TryonImage.objects.create(
                session=session,
                product=product,
                status='pending',
            )
            
            # Save image
            filename = f"vto_{uuid.uuid4().hex[:8]}.png"
            tryon_image.user_photo.save(filename, ContentFile(image_data))
        else:
            return JsonResponse({'error': 'No photo provided'}, status=400)
        
        return JsonResponse({
            'success': True,
            'tryon_id': tryon_image.id,
            'photo_url': tryon_image.user_photo.url,
            'message': 'Photo uploaded successfully',
        })
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(["POST"])
def vto_save_result(request):
    """
    Save VTO result image (from client-side canvas)
    """
    try:
        tryon_id = request.POST.get('tryon_id')
        result_data = request.POST.get('result_data')
        face_data = request.POST.get('face_data', '{}')
        
        if not tryon_id or not result_data:
            return JsonResponse({'error': 'Missing required parameters'}, status=400)
        
        # Get TryonImage
        tryon_image = get_object_or_404(TryonImage, id=tryon_id)
        
        # Decode base64 result
        if 'base64,' in result_data:
            result_data = result_data.split('base64,')[1]
        
        image_data = base64.b64decode(result_data)
        
        # Save result image
        filename = f"vto_result_{uuid.uuid4().hex[:8]}.png"
        tryon_image.result_image.save(filename, ContentFile(image_data))
        
        # Save face data
        tryon_image.face_data = json.loads(face_data)
        tryon_image.status = 'completed'
        tryon_image.save(update_fields=['face_data', 'status'])
        
        return JsonResponse({
            'success': True,
            'result_url': tryon_image.result_image.url,
            'message': 'Result saved successfully',
        })
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(["POST"])
def vto_delete_photo(request):
    """
    Delete user photo (privacy)
    """
    try:
        tryon_id = request.POST.get('tryon_id')
        
        if not tryon_id:
            return JsonResponse({'error': 'Missing tryon_id'}, status=400)
        
        tryon_image = get_object_or_404(TryonImage, id=tryon_id)
        
        # Check ownership (session match)
        session_id = request.POST.get('session_id')
        if str(tryon_image.session.session_id) != session_id:
            return JsonResponse({'error': 'Unauthorized'}, status=403)
        
        # Delete image files
        if tryon_image.user_photo:
            tryon_image.user_photo.delete()
        if tryon_image.result_image:
            tryon_image.result_image.delete()
        
        tryon_image.delete()
        
        return JsonResponse({
            'success': True,
            'message': 'Photo deleted successfully',
        })
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def vto_history(request):
    """
    Show user's VTO history
    """
    user_sessions = TryonSession.objects.filter(
        user=request.user
    ).prefetch_related('images__product').order_by('-created_at')[:20]
    
    context = {
        'sessions': user_sessions,
    }
    
    return render(request, 'virtual_tryon/vto_history.html', context)


def get_or_create_session(request):
    """
    Get or create VTO session for user/guest
    """
    # Try to get session from session storage
    session_id = request.session.get('vto_session_id')
    
    if session_id:
        try:
            session = TryonSession.objects.get(session_id=session_id)
            if session.is_active:
                return session
        except TryonSession.DoesNotExist:
            pass
    
    # Create new session
    session = TryonSession.objects.create(
        user=request.user if request.user.is_authenticated else None,
        metadata={
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            'ip_address': get_client_ip(request),
        }
    )
    
    # Store in Django session
    request.session['vto_session_id'] = str(session.session_id)
    
    return session


@require_http_methods(["POST"])
def vto_analyze_image(request):
    """
    Analyze uploaded image with Gemini AI for better VTO placement
    Enhanced error handling and response validation
    """
    try:
        if 'image' not in request.FILES:
            return JsonResponse({
                'success': False,
                'error': 'No image provided'
            }, status=400)
        
        image_file = request.FILES['image']
        product_type = request.POST.get('product_type', 'clothing')
        placement_mode = request.POST.get('placement_mode', 'auto')
        
        print(f"🔍 Gemini Analysis Request: product_type={product_type}, placement_mode={placement_mode}, image_size={image_file.size}")
        
        # Read image bytes
        image_bytes = image_file.read()
        
        if not image_bytes or len(image_bytes) == 0:
            return JsonResponse({
                'success': False,
                'error': 'Empty image file'
            }, status=400)
        
        print(f"✅ Image bytes read: {len(image_bytes)} bytes")
        
        # Analyze with Gemini
        try:
            analysis = analyze_image_for_vto(image_bytes, product_type, placement_mode)
            print(f"✅ Gemini analysis complete: {analysis}")
            
            # Validate analysis response
            if not analysis:
                raise ValueError("Empty analysis response from Gemini")
            
            # Ensure required fields exist
            if 'recommended_position' not in analysis:
                analysis['recommended_position'] = {'x': 0.5, 'y': 0.5}
            if 'recommended_size' not in analysis:
                analysis['recommended_size'] = 0.25
            if 'recommended_rotation' not in analysis:
                analysis['recommended_rotation'] = 0
            if 'confidence' not in analysis:
                analysis['confidence'] = 0.5
            
            return JsonResponse({
                'success': True,
                'analysis': analysis,
            })
            
        except Exception as gemini_error:
            print(f"⚠️ Gemini API error: {gemini_error}")
            import traceback
            print(traceback.format_exc())
            
            # Return fallback analysis
            fallback = _fallback_analysis_response(product_type, placement_mode)
            return JsonResponse({
                'success': False,
                'error': str(gemini_error),
                'analysis': fallback
            })
    
    except Exception as e:
        import traceback
        print(f"❌ VTO analyze error: {e}")
        print(traceback.format_exc())
        
        product_type = request.POST.get('product_type', 'clothing')
        placement_mode = request.POST.get('placement_mode', 'auto')
        
        return JsonResponse({
            'success': False,
            'error': str(e),
            'analysis': _fallback_analysis_response(product_type, placement_mode)
        }, status=500)


def _fallback_analysis_response(product_type, placement_mode):
    """Fallback analysis response"""
    if placement_mode == 'face' or 'clothing' in product_type.lower():
        return {
            'scene_type': 'clothing',
            'recommended_position': {'x': 0.5, 'y': 0.5},
            'recommended_size': 0.25,
            'recommended_rotation': 0,
            'confidence': 0.5,
        }
    elif placement_mode == 'room':
        return {
            'scene_type': 'room',
            'recommended_position': {'x': 0.5, 'y': 0.65},
            'recommended_size': 0.2,
            'recommended_rotation': 0,
            'confidence': 0.5,
        }
    else:
        return {
            'scene_type': 'generic',
            'recommended_position': {'x': 0.5, 'y': 0.5},
            'recommended_size': 0.25,
            'recommended_rotation': 0,
            'confidence': 0.3,
        }


@require_http_methods(["POST"])
@require_http_methods(["POST"])
def vto_remove_background(request):
    """
    Remove background from product image using Gemini API for best quality
    """
    try:
        if 'image' not in request.FILES:
            return JsonResponse({
                'success': False,
                'error': 'No image provided'
            }, status=400)
        
        image_file = request.FILES['image']
        product_type = request.POST.get('product_type', 'clothing')
        
        print(f"🎨 Background Removal Request: product_type={product_type}, image_size={image_file.size}")
        
        # Read image bytes
        image_bytes = image_file.read()
        
        if not image_bytes or len(image_bytes) == 0:
            return JsonResponse({
                'success': False,
                'error': 'Empty image file'
            }, status=400)
        
        # Remove background with Gemini
        try:
            result = remove_background_with_gemini(image_bytes, product_type)
            print(f"✅ Background removal complete")
            
            if result and 'image_data' in result:
                return JsonResponse({
                    'success': True,
                    'image_data': result['image_data'],
                    'format': result.get('format', 'png')
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': 'Failed to remove background'
                }, status=500)
                
        except Exception as bg_error:
            print(f"⚠️ Background removal error: {bg_error}")
            import traceback
            print(traceback.format_exc())
            return JsonResponse({
                'success': False,
                'error': str(bg_error)
            }, status=500)
    
    except Exception as e:
        import traceback
        print(f"❌ Background removal error: {e}")
        print(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


def get_client_ip(request):
    """Get client IP address"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

