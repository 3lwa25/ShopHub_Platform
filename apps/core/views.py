"""
Core views for Shop Hub
Handles homepage and main navigation
"""
from django.shortcuts import render
from django.db.models import Count, Avg, Q, F
from django.utils import timezone
from datetime import timedelta

from apps.products.models import Product, Category
from apps.reviews.models import Review


def home_view(request):
    """
    Enhanced homepage with featured products, categories, and trending items
    """
    # Get featured products (high-rated, active, with images)
    featured_products = Product.objects.filter(
        status='active',
        rating__gte=4.0
    ).select_related('seller', 'category').prefetch_related('images').order_by('-rating', '-review_count')[:8]
    
    # Get new arrivals (products added in last 7 days)
    seven_days_ago = timezone.now() - timedelta(days=7)
    new_arrivals = Product.objects.filter(
        status='active',
        created_at__gte=seven_days_ago  # Only products from last 7 days
    ).select_related('seller', 'category').prefetch_related('images').order_by('-created_at')[:8]
    
    # If less than 8 new products, fill with recent ones
    if new_arrivals.count() < 8:
        new_arrivals = Product.objects.filter(
            status='active'
        ).select_related('seller', 'category').prefetch_related('images').order_by('-created_at')[:8]
    
    # Get trending products (most reviewed/rated, excluding new arrivals)
    new_arrival_ids = [p.id for p in new_arrivals]
    trending_products = Product.objects.filter(
        status='active',
        review_count__gte=1  # Must have at least 1 review to be trending
    ).exclude(
        id__in=new_arrival_ids  # Exclude new arrivals to make them distinct
    ).select_related('seller', 'category').prefetch_related('images').order_by('-review_count', '-rating')[:8]
    
    # Get main categories for showcase (parent categories only)
    main_categories = Category.objects.filter(
        parent__isnull=True,
        is_active=True
    ).annotate(
        product_count=Count('products', filter=Q(products__status='active'))
    ).order_by('display_order')[:8]
    
    # Get products on sale (compare_at_price higher than price)
    sale_products = Product.objects.filter(
        status='active',
        compare_at_price__isnull=False,
        compare_at_price__gt=F('price')
    ).annotate(
        discount_percent=((F('compare_at_price') - F('price')) / F('compare_at_price')) * 100
    ).select_related('seller', 'category').prefetch_related('images').order_by('-discount_percent')[:8]
    
    # Get VTO-enabled products
    vto_products = Product.objects.filter(
        status='active',
        vto_enabled=True
    ).select_related('seller', 'category').prefetch_related('images')[:4]
    
    # Get total statistics
    stats = {
        'total_products': Product.objects.filter(status='active').count(),
        'total_categories': Category.objects.filter(is_active=True).count(),
        'total_reviews': Review.objects.count(),
    }
    
    context = {
        'featured_products': featured_products,
        'new_arrivals': new_arrivals,
        'trending_products': trending_products,
        'main_categories': main_categories,
        'sale_products': sale_products,
        'vto_products': vto_products,
        'stats': stats,
    }
    
    return render(request, 'home.html', context)


def search_autocomplete(request):
    """
    AJAX autocomplete for navbar search
    """
    from django.http import JsonResponse
    
    query = request.GET.get('q', '').strip()
    
    if len(query) < 2:
        return JsonResponse({'results': []})
    
    # Search products and categories
    products = Product.objects.filter(
        status='active',
        title__icontains=query
    ).select_related('category').values('id', 'title', 'slug', 'price', 'category__name')[:5]
    
    categories = Category.objects.filter(
        is_active=True,
        name__icontains=query
    ).values('id', 'name', 'slug')[:3]
    
    results = {
        'products': list(products),
        'categories': list(categories),
    }
    
    return JsonResponse(results)

