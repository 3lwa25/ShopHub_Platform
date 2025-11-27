"""
Advanced Search and Recommendation Views
"""
from decimal import Decimal
from datetime import timedelta

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count, Avg
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.products.models import Product, Category
from apps.products.search_models import SearchQuery, BrowsingHistory, ProductComparison
from apps.products.forms import ProductSearchForm


@require_http_methods(["GET"])
def advanced_search_view(request):
    """Advanced product search with filters"""
    query = request.GET.get('q', '').strip()
    form = ProductSearchForm(request.GET or None)
    
    # Start with all active products
    products = Product.objects.filter(status='active').select_related('seller', 'category').prefetch_related('images')
    
    # Text search
    if query:
        products = products.filter(
            Q(title__icontains=query) |
            Q(description__icontains=query) |
            Q(sku__icontains=query) |
            Q(category__name__icontains=query)
        )
    
    # Filters
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    if min_price:
        try:
            products = products.filter(price__gte=float(min_price))
        except ValueError:
            pass
    if max_price:
        try:
            products = products.filter(price__lte=float(max_price))
        except ValueError:
            pass
    
    # Category filter
    category_slug = request.GET.get('category')
    if category_slug:
        try:
            category = Category.objects.get(slug=category_slug, is_active=True)
            all_categories = [category] + category.get_all_children()
            products = products.filter(category__in=all_categories)
        except Category.DoesNotExist:
            pass
    
    # Rating filter
    min_rating = request.GET.get('min_rating')
    if min_rating:
        try:
            products = products.filter(rating__gte=float(min_rating))
        except ValueError:
            pass
    
    # In stock filter
    in_stock_only = request.GET.get('in_stock')
    if in_stock_only:
        products = products.filter(stock__gt=0)
    
    # Sorting
    sort_by = request.GET.get('sort_by', '-created_at')
    valid_sorts = {
        'newest': '-created_at',
        'price_low': 'price',
        'price_high': '-price',
        'rating': '-rating',
        'popular': '-review_count',
        'relevance': '-created_at',  # Default for search
    }
    if sort_by in valid_sorts:
        products = products.order_by(valid_sorts[sort_by])
    else:
        products = products.order_by('-created_at')
    
    # Log search query
    if query:
        session_key = request.session.session_key
        if not session_key:
            request.session.create()
            session_key = request.session.session_key
        
        SearchQuery.objects.create(
            user=request.user if request.user.is_authenticated else None,
            session_key=session_key if not request.user.is_authenticated else '',
            query=query,
            results_count=products.count(),
            filters_applied={
                'min_price': min_price,
                'max_price': max_price,
                'category': category_slug,
                'min_rating': min_rating,
                'in_stock': in_stock_only,
            }
        )
    
    # Pagination
    paginator = Paginator(products, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Get popular searches
    popular_searches = SearchQuery.popular_searches(days=7, limit=10)
    
    context = {
        'query': query,
        'form': form,
        'products': page_obj,
        'page_obj': page_obj,
        'total_count': paginator.count,
        'popular_searches': popular_searches,
    }
    return render(request, 'products/search.html', context)


@require_http_methods(["GET"])
def search_suggestions_api(request):
    """AJAX endpoint for search autocomplete"""
    query = request.GET.get('q', '').strip()
    
    if len(query) < 2:
        return JsonResponse({'suggestions': []})
    
    # Search products
    products = Product.objects.filter(
        status='active',
        title__icontains=query
    )[:5]
    
    # Search categories
    categories = Category.objects.filter(
        is_active=True,
        name__icontains=query
    )[:3]
    
    suggestions = []
    
    # Add product suggestions
    for product in products:
        suggestions.append({
            'type': 'product',
            'title': product.title,
            'url': f'/products/{product.slug}/',
            'image': product.images.first().image.url if product.images.exists() else None,
            'price': str(product.price),
        })
    
    # Add category suggestions
    for category in categories:
        suggestions.append({
            'type': 'category',
            'title': category.name,
            'url': f'/products/category/{category.slug}/',
        })
    
    return JsonResponse({'suggestions': suggestions})


@require_http_methods(["GET"])
def search_history_view(request):
    """Display user search history"""
    if not request.user.is_authenticated:
        messages.info(request, 'Please log in to view your search history.')
        return redirect('accounts:login')
    
    searches = SearchQuery.objects.filter(user=request.user).order_by('-created_at')[:20]
    
    context = {
        'searches': searches,
    }
    return render(request, 'products/search_history.html', context)


def track_product_view(request, product_id):
    """Track product view for recommendations"""
    product = get_object_or_404(Product, id=product_id, status='active')
    
    # Get session key
    session_key = request.session.session_key
    if not session_key:
        request.session.create()
        session_key = request.session.session_key
    
    # Track view
    BrowsingHistory.objects.create(
        user=request.user if request.user.is_authenticated else None,
        session_key=session_key if not request.user.is_authenticated else '',
        product=product,
        referrer=request.META.get('HTTP_REFERER', ''),
    )
    
    return JsonResponse({'success': True})


@require_http_methods(["GET"])
def recommendations_for_user(request):
    """Get personalized product recommendations"""
    if not request.user.is_authenticated:
        # For anonymous users, show trending products
        return trending_products_view(request)
    
    # Get recently viewed products
    try:
        recent_views = BrowsingHistory.recent_views(user=request.user, limit=10)
        viewed_product_ids = [view.product.id for view in recent_views if view.product]
    except:
        viewed_product_ids = []
    
    if not viewed_product_ids:
        # No browsing history, show trending products
        return trending_products_view(request)
    
    # Get products from same categories
    viewed_products = Product.objects.filter(id__in=viewed_product_ids, status='active')
    categories = viewed_products.values_list('category', flat=True).distinct()
    
    if not categories:
        # No valid categories, show trending
        return trending_products_view(request)
    
    # Recommend products from same categories
    recommendations = list(Product.objects.filter(
        category__in=categories,
        status='active'
    ).exclude(
        id__in=viewed_product_ids
    ).annotate(
        avg_rating=Avg('reviews__rating')
    ).order_by('-avg_rating', '-review_count', '-created_at')[:12])
    
    # If not enough recommendations, add popular products
    if len(recommendations) < 12:
        existing_ids = [p.id for p in recommendations] + viewed_product_ids
        additional = Product.objects.filter(
            status='active'
        ).exclude(
            id__in=existing_ids
        ).annotate(
            avg_rating=Avg('reviews__rating')
        ).order_by('-avg_rating', '-review_count', '-created_at')[:12 - len(recommendations)]
        recommendations.extend(additional)
    
    context = {
        'products': recommendations,
        'title': 'Recommended for You',
    }
    return render(request, 'products/recommendations.html', context)


@require_http_methods(["GET"])
def similar_products_api(request, product_id):
    """AJAX endpoint for similar products"""
    product = get_object_or_404(Product, id=product_id, status='active')
    
    # Find similar products (same category, similar price range)
    price_range = product.price * Decimal('0.2')  # 20% price range
    
    import random
    similar = list(Product.objects.filter(
        category=product.category,
        status='active',
        price__gte=product.price - price_range,
        price__lte=product.price + price_range,
    ).exclude(id=product.id))
    
    # Shuffle for variety - different recommendations each time
    random.shuffle(similar)
    similar = similar[:4]
    
    products_data = []
    for p in similar:
        products_data.append({
            'id': p.id,
            'title': p.title,
            'price': str(p.price),
            'image': p.images.first().image.url if p.images.exists() else None,
            'url': f'/products/{p.slug}/',
        })
    
    return JsonResponse({'products': products_data})


@require_http_methods(["GET"])
def trending_products_view(request):
    """Display trending products"""
    try:
        # Get most viewed products in last 7 days
        trending = BrowsingHistory.trending_products(days=7, limit=12)
        product_ids = [item['product'] for item in trending if 'product' in item]
        
        if product_ids:
            products = Product.objects.filter(id__in=product_ids, status='active')
            # Order by view count
            product_dict = {p.id: p for p in products}
            ordered_products = [product_dict[pid] for pid in product_ids if pid in product_dict]
        else:
            # No trending data, show popular products by reviews
            ordered_products = Product.objects.filter(
                status='active'
            ).annotate(
                avg_rating=Avg('reviews__rating')
            ).order_by('-avg_rating', '-review_count', '-created_at')[:12]
    except:
        # Fallback to popular products
        ordered_products = Product.objects.filter(
            status='active'
        ).annotate(
            avg_rating=Avg('reviews__rating')
        ).order_by('-avg_rating', '-review_count', '-created_at')[:12]
    
    context = {
        'products': ordered_products,
        'title': 'Trending Products',
    }
    return render(request, 'products/recommendations.html', context)


@require_http_methods(["GET"])
def recently_viewed_view(request):
    """Display recently viewed products"""
    try:
        if request.user.is_authenticated:
            recent_views = BrowsingHistory.recent_views(user=request.user, limit=12)
        else:
            session_key = request.session.session_key
            if session_key:
                recent_views = BrowsingHistory.recent_views(session_key=session_key, limit=12)
            else:
                recent_views = []
        
        products = [view.product for view in recent_views if hasattr(view, 'product') and view.product.status == 'active']
    except:
        products = []
    
    context = {
        'products': products,
        'title': 'Recently Viewed',
    }
    return render(request, 'products/recommendations.html', context)

