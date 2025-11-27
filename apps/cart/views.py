"""
Views for Shopping Cart
Handles cart operations: view, add, update, remove, clear
"""
from decimal import Decimal

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.contrib.auth.decorators import login_required
from apps.products.models import Product
from apps.accounts.decorators import not_seller
from .models import Cart, CartItem
from .forms import AddToCartForm, UpdateQuantityForm


def get_or_create_cart(request):
    """
    Get or create cart for user or session
    Sellers cannot have carts - they don't shop
    """
    # Sellers shouldn't reach here due to @not_seller decorator, but double-check
    if request.user.is_authenticated and request.user.is_seller:
        return None
    
    if request.user.is_authenticated:
        cart, created = Cart.objects.get_or_create(user=request.user)
    else:
        # For anonymous users, use session
        if not request.session.session_key:
            request.session.create()
        session_key = request.session.session_key
        cart, created = Cart.objects.get_or_create(session_key=session_key)
    return cart


@not_seller
def cart_view(request):
    """Display the shopping cart"""
    cart = get_or_create_cart(request)
    cart_items = cart.items.select_related('product').prefetch_related('product__images')
    
    # Check stock availability for all items
    out_of_stock_items = []
    for item in cart_items:
        if not item.is_in_stock:
            out_of_stock_items.append(item)
    
    # Calculate coupon discount if applied
    applied_coupon = None
    discount_amount = Decimal('0.00')
    cart_total = cart.total_price
    
    # Check if reward points are being used
    reward_points_used = bool(request.session.get('rewards_redemption', {}).get('points', 0))
    
    if request.user.is_authenticated and not request.user.is_seller:
        applied_coupon_code = request.session.get('applied_coupon_code', '').strip()
        if applied_coupon_code:
            try:
                from apps.orders.coupon_models import Coupon
                applied_coupon = Coupon.objects.get(code__iexact=applied_coupon_code, is_active=True)
                
                # Validate coupon
                is_valid, _ = applied_coupon.is_valid(user=request.user)
                if is_valid and applied_coupon.can_apply_to_cart(cart_items):
                    if cart_total >= applied_coupon.min_order_value:
                        discount_amount = applied_coupon.calculate_discount(cart_total, cart_items)
                    else:
                        # Coupon doesn't meet minimum, remove it
                        del request.session['applied_coupon_code']
                        applied_coupon = None
                else:
                    # Invalid coupon, remove it
                    del request.session['applied_coupon_code']
                    applied_coupon = None
            except:
                # Coupon not found, remove from session
                if 'applied_coupon_code' in request.session:
                    del request.session['applied_coupon_code']
                applied_coupon = None
    
    # Calculate shipping and tax
    from apps.orders.shipping_utils import calculate_shipping_fee, calculate_order_totals
    
    shipping_fee = calculate_shipping_fee(cart_items, applied_coupon, reward_points_used)
    totals = calculate_order_totals(cart_total, shipping_fee, discount_amount)
    
    context = {
        'cart': cart,
        'cart_items': cart_items,
        'out_of_stock_items': out_of_stock_items,
        'applied_coupon': applied_coupon,
        'discount_amount': totals['discount'],
        'shipping_fee': totals['shipping'],
        'tax_amount': totals['tax'],
        'cart_total': cart_total,
        'final_total': totals['total'],
    }
    return render(request, 'cart/cart.html', context)


@not_seller
@require_POST
def add_to_cart(request):
    """Add a product to the cart (with AJAX support)"""
    product_id = request.POST.get('product_id')
    quantity = int(request.POST.get('quantity', 1))
    
    if not product_id:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': 'Product ID is required'}, status=400)
        messages.error(request, 'Product ID is required.')
        return redirect('products:product_list')
    
    # Get product
    try:
        product = Product.objects.get(id=product_id, status='active')
    except Product.DoesNotExist:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': 'Product not found'}, status=404)
        messages.error(request, 'Product not found.')
        return redirect('products:product_list')
    
    # Check stock
    if product.stock < quantity:
        message = f'Only {product.stock} items available in stock.'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': message}, status=400)
        messages.error(request, message)
        return redirect('products:product_detail', slug=product.slug)
    
    # Get or create cart
    cart = get_or_create_cart(request)
    
    # Add or update cart item
    cart_item, created = CartItem.objects.get_or_create(
        cart=cart,
        product=product,
        defaults={'quantity': quantity, 'price_at_addition': product.price}
    )
    
    if not created:
        # Update quantity
        new_quantity = cart_item.quantity + quantity
        if new_quantity > product.stock:
            message = f'Cannot add more. Only {product.stock} items available.'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': message}, status=400)
            messages.error(request, message)
            return redirect('products:product_detail', slug=product.slug)
        
        cart_item.quantity = new_quantity
        cart_item.save()
        message = f'Updated {product.title} quantity to {cart_item.quantity}.'
    else:
        message = f'Added {product.title} to your cart.'
    
    # AJAX response
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'message': message,
            'cart_count': cart.total_items,
            'cart_total': float(cart.total_price),
            'item_quantity': cart_item.quantity
        })
    
    # Regular response
    messages.success(request, message)
    return redirect('cart:cart_view')


@not_seller
@require_POST
def update_cart_item(request, item_id):
    """Update cart item quantity (with AJAX support)"""
    try:
        cart = get_or_create_cart(request)
        cart_item = get_object_or_404(CartItem, id=item_id, cart=cart)
    except CartItem.DoesNotExist:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': 'Cart item not found'}, status=404)
        messages.error(request, 'Cart item not found.')
        return redirect('cart:cart_view')
    
    quantity = int(request.POST.get('quantity', 1))
    
    # Validate quantity
    if quantity < 1:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': 'Quantity must be at least 1'}, status=400)
        messages.error(request, 'Quantity must be at least 1.')
        return redirect('cart:cart_view')
    
    if quantity > cart_item.product.stock:
        message = f'Only {cart_item.product.stock} items available.'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': message}, status=400)
        messages.error(request, message)
        return redirect('cart:cart_view')
    
    # Update quantity
    cart_item.quantity = quantity
    cart_item.save()
    
    message = 'Cart updated successfully.'
    
    # AJAX response
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'message': message,
            'cart_count': cart.total_items,
            'cart_total': float(cart.total_price),
            'item_subtotal': float(cart_item.subtotal),
            'item_quantity': cart_item.quantity
        })
    
    # Regular response
    messages.success(request, message)
    return redirect('cart:cart_view')


@not_seller
@require_POST
def remove_from_cart(request, item_id):
    """Remove an item from the cart (with AJAX support)"""
    try:
        cart = get_or_create_cart(request)
        cart_item = get_object_or_404(CartItem, id=item_id, cart=cart)
    except CartItem.DoesNotExist:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': 'Cart item not found'}, status=404)
        messages.error(request, 'Cart item not found.')
        return redirect('cart:cart_view')
    
    product_title = cart_item.product.title
    cart_item.delete()
    
    message = f'Removed {product_title} from your cart.'
    
    # AJAX response
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'message': message,
            'cart_count': cart.total_items,
            'cart_total': float(cart.total_price)
        })
    
    # Regular response
    messages.success(request, message)
    return redirect('cart:cart_view')


@not_seller
@require_POST
def clear_cart(request):
    """Clear all items from the cart"""
    cart = get_or_create_cart(request)
    cart.clear()
    
    message = 'Your cart has been cleared.'
    
    # AJAX response
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'message': message,
            'cart_count': 0,
            'cart_total': 0.0
        })
    
    # Regular response
    messages.success(request, message)
    return redirect('cart:cart_view')


@not_seller
def cart_count(request):
    """Get cart item count (AJAX endpoint)"""
    cart = get_or_create_cart(request)
    return JsonResponse({
        'count': cart.total_items,
        'total': float(cart.total_price)
    })
