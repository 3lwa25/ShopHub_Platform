"""
Views for Wishlist
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_http_methods

from apps.products.models import Product
from apps.accounts.decorators import not_seller
from apps.cart.views import get_or_create_cart
from apps.cart.models import CartItem
from .models import Wishlist, WishlistItem
from .forms import WishlistItemForm


def get_or_create_wishlist(user):
    """Get or create wishlist for user"""
    wishlist, created = Wishlist.objects.get_or_create(user=user)
    return wishlist


@not_seller
@login_required
@require_POST
def add_to_wishlist_view(request, product_id):
    """Add product to wishlist (AJAX)"""
    product = get_object_or_404(Product, id=product_id, status='active')
    wishlist = get_or_create_wishlist(request.user)
    
    # Check if already in wishlist
    if wishlist.has_product(product):
        return JsonResponse({
            'success': False,
            'message': 'Product is already in your wishlist.',
            'in_wishlist': True
        })
    
    # Add to wishlist
    item = wishlist.add_product(product)
    
    return JsonResponse({
        'success': True,
        'message': f'{product.title} added to wishlist!',
        'in_wishlist': True,
        'wishlist_count': wishlist.item_count
    })


@not_seller
@login_required
@require_POST
def remove_from_wishlist_view(request, item_id):
    """Remove product from wishlist (AJAX)"""
    item = get_object_or_404(WishlistItem, id=item_id, wishlist__user=request.user)
    product_title = item.product.title
    item.delete()
    
    wishlist = get_or_create_wishlist(request.user)
    
    return JsonResponse({
        'success': True,
        'message': f'{product_title} removed from wishlist.',
        'in_wishlist': False,
        'wishlist_count': wishlist.item_count
    })


@not_seller
@login_required
@require_POST
def toggle_wishlist_view(request, product_id):
    """Toggle product in wishlist (AJAX)"""
    product = get_object_or_404(Product, id=product_id, status='active')
    wishlist = get_or_create_wishlist(request.user)
    
    if wishlist.has_product(product):
        # Remove from wishlist
        wishlist.remove_product(product)
        return JsonResponse({
            'success': True,
            'message': f'{product.title} removed from wishlist.',
            'in_wishlist': False,
            'wishlist_count': wishlist.item_count
        })
    else:
        # Add to wishlist
        wishlist.add_product(product)
        return JsonResponse({
            'success': True,
            'message': f'{product.title} added to wishlist!',
            'in_wishlist': True,
            'wishlist_count': wishlist.item_count
        })


@not_seller
@login_required
def wishlist_view(request):
    """Display user's wishlist"""
    wishlist = get_or_create_wishlist(request.user)
    items = wishlist.items.select_related('product', 'product__seller').prefetch_related('product__images').all()
    
    # Filtering
    view_type = request.GET.get('view', 'grid')
    sort_by = request.GET.get('sort', 'recent')
    
    if sort_by == 'price_low':
        items = items.order_by('product__price', '-added_at')
    elif sort_by == 'price_high':
        items = items.order_by('-product__price', '-added_at')
    elif sort_by == 'name':
        items = items.order_by('product__title', '-added_at')
    elif sort_by == 'priority':
        items = items.order_by('-priority', '-added_at')
    else:  # recent (default)
        items = items.order_by('-added_at')
    
    # Filter by stock status
    stock_filter = request.GET.get('stock')
    if stock_filter == 'in_stock':
        items = items.filter(product__stock__gt=0)
    elif stock_filter == 'out_of_stock':
        items = items.filter(product__stock=0)
    
    context = {
        'wishlist': wishlist,
        'items': items,
        'view_type': view_type,
        'sort_by': sort_by,
        'stock_filter': stock_filter,
        'share_url': request.build_absolute_uri(),
    }
    return render(request, 'wishlist/wishlist.html', context)


@not_seller
@login_required
@require_POST
def move_to_cart_view(request, item_id):
    """Move wishlist item to cart"""
    item = get_object_or_404(WishlistItem, id=item_id, wishlist__user=request.user)
    product = item.product
    wishlist = item.wishlist
    
    # Check stock
    if not product.is_in_stock:
        return JsonResponse({
            'success': False,
            'message': f'{product.title} is currently out of stock.'
        })
    
    cart = get_or_create_cart(request)
    if not cart:
        return JsonResponse({
            'success': False,
            'message': 'Unable to access your cart. Please try again.'
        }, status=400)
    
    # Check if item already exists in cart
    existing_cart_item = CartItem.objects.filter(cart=cart, product=product).first()
    
    if existing_cart_item:
        # Item already in cart - don't add again, just inform user
        return JsonResponse({
            'success': False,
            'message': f'{product.title} is already in your cart. Please update quantity from cart page.'
        })
    
    # Add item to cart with quantity 1
    max_quantity = min(product.stock, 1)  # Add only 1 item
    CartItem.objects.create(
        cart=cart,
        product=product,
        quantity=1
    )
    
    # Remove from wishlist
    item.delete()
    
    return JsonResponse({
        'success': True,
        'message': f'{product.title} moved to cart!',
        'cart_count': cart.total_items,
        'wishlist_count': wishlist.item_count,
    })


@not_seller
@login_required
def edit_wishlist_item_view(request, item_id):
    """Edit wishlist item notes and priority"""
    item = get_object_or_404(WishlistItem, id=item_id, wishlist__user=request.user)
    
    if request.method == 'POST':
        form = WishlistItemForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            messages.success(request, 'Wishlist item updated.')
            return redirect('wishlist:wishlist')
    else:
        form = WishlistItemForm(instance=item)
    
    context = {
        'form': form,
        'item': item,
        'product': item.product,
    }
    return render(request, 'wishlist/edit_item.html', context)


@not_seller
@login_required
@require_POST
def clear_wishlist_view(request):
    """Clear entire wishlist"""
    wishlist = get_or_create_wishlist(request.user)
    count = wishlist.items.count()
    wishlist.items.all().delete()
    
    messages.success(request, f'Removed {count} item(s) from your wishlist.')
    return redirect('wishlist:wishlist')


@login_required
def check_wishlist_status(request, product_id):
    """Check if product is in user's wishlist (AJAX)"""
    if request.user.is_seller:
        return JsonResponse({'in_wishlist': False})
    
    product = get_object_or_404(Product, id=product_id)
    wishlist = get_or_create_wishlist(request.user)
    
    return JsonResponse({
        'in_wishlist': wishlist.has_product(product),
        'wishlist_count': wishlist.item_count
    })

