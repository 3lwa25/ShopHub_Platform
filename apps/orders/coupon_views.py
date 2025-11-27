"""
Coupon Views
"""
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import models
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST, require_http_methods
from django.utils import timezone

from apps.accounts.decorators import buyer_required, not_seller
from apps.cart.models import Cart
from apps.orders.coupon_forms import CouponApplyForm
from apps.orders.coupon_models import Coupon, CouponUsage
from apps.orders.utils import get_cart_for_request


@not_seller
@login_required
@require_POST
def validate_coupon_view(request):
    """AJAX endpoint to validate coupon code"""
    code = request.POST.get('coupon_code', '').strip().upper()
    
    if not code:
        return JsonResponse({
            'valid': False,
            'message': 'Please enter a coupon code.'
        })
    
    try:
        coupon = Coupon.objects.get(code__iexact=code, is_active=True)
    except Coupon.DoesNotExist:
        return JsonResponse({
            'valid': False,
            'message': 'Invalid coupon code.'
        })
    
    # Get cart for validation
    cart = get_cart_for_request(request)
    cart_items = cart.items.all() if cart else []
    
    # Validate coupon
    is_valid, error_msg = coupon.is_valid(user=request.user)
    
    if not is_valid:
        return JsonResponse({
            'valid': False,
            'message': error_msg
        })
    
    # Check if can apply to cart
    if not coupon.can_apply_to_cart(cart_items):
        return JsonResponse({
            'valid': False,
            'message': 'This coupon cannot be applied to items in your cart.'
        })
    
    # Calculate cart total
    cart_total = sum(item.subtotal for item in cart_items) if cart_items else Decimal('0.00')
    
    # Check minimum order value
    if cart_total < coupon.min_order_value:
        return JsonResponse({
            'valid': False,
            'message': f'Minimum order value of EGP {coupon.min_order_value} required for this coupon.'
        })
    
    # Calculate discount
    discount_amount = coupon.calculate_discount(cart_total, cart_items)
    final_total = max(Decimal('0.00'), cart_total - discount_amount)
    
    return JsonResponse({
        'valid': True,
        'message': f'Coupon "{coupon.code}" applied successfully!',
        'coupon': {
            'code': coupon.code,
            'discount_type': coupon.discount_type,
            'discount_display': coupon.get_discount_display(),
        },
        'discount_amount': str(discount_amount),
        'cart_total': str(cart_total),
        'final_total': str(final_total),
    })


@not_seller
@login_required
@require_http_methods(["GET", "POST"])
def apply_coupon_view(request):
    """Apply coupon to cart"""
    cart = get_cart_for_request(request)
    if not cart or cart.items.count() == 0:
        messages.error(request, 'Your cart is empty.')
        return redirect('cart:cart_view')
    
    if request.method == 'POST':
        form = CouponApplyForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data['coupon_code']
            try:
                coupon = Coupon.objects.get(code__iexact=code, is_active=True)
            except Coupon.DoesNotExist:
                messages.error(request, 'Invalid coupon code.')
                return redirect('cart:cart_view')
            
            # Validate coupon
            is_valid, error_msg = coupon.is_valid(user=request.user)
            if not is_valid:
                messages.error(request, error_msg)
                return redirect('cart:cart_view')
            
            # Check cart items
            cart_items = cart.items.all()
            if not coupon.can_apply_to_cart(cart_items):
                messages.error(request, 'This coupon cannot be applied to items in your cart.')
                return redirect('cart:cart_view')
            
            # Check minimum order value
            cart_total = sum(item.subtotal for item in cart_items)
            if cart_total < coupon.min_order_value:
                messages.error(request, f'Minimum order value of EGP {coupon.min_order_value} required.')
                return redirect('cart:cart_view')
            
            # Store coupon in session
            request.session['applied_coupon_code'] = coupon.code
            messages.success(request, f'Coupon "{coupon.code}" applied successfully!')
        else:
            messages.error(request, 'Please enter a valid coupon code.')
    
    return redirect('cart:cart_view')


@not_seller
@login_required
@require_POST
def remove_coupon_view(request):
    """Remove applied coupon"""
    if 'applied_coupon_code' in request.session:
        del request.session['applied_coupon_code']
        messages.info(request, 'Coupon removed.')
    return redirect('cart:cart_view')


@buyer_required
@login_required
def available_coupons_view(request):
    """Display available coupons for the user"""
    from django.db.models import Q
    
    now = timezone.now()
    coupons = Coupon.objects.filter(
        is_active=True,
        valid_from__lte=now,
        valid_to__gte=now
    ).exclude(
        Q(max_uses__isnull=False) & Q(current_uses__gte=models.F('max_uses'))
    )
    
    # Filter by user eligibility
    available_coupons = []
    for coupon in coupons:
        is_valid, _ = coupon.is_valid(user=request.user)
        if is_valid:
            available_coupons.append(coupon)
    
    context = {
        'coupons': available_coupons,
    }
    return render(request, 'orders/coupons/available_coupons.html', context)

