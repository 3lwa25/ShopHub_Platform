"""
Views for Product Catalog
"""
from decimal import Decimal

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q
from django.http import JsonResponse
from .models import Product, Category, ProductImage, ProductVariant
from .forms import ProductSearchForm, ProductForm, ProductImageForm, ProductVariantForm


def product_list_view(request):
    """Display all products with filtering and search"""
    products = Product.objects.filter(status='active').select_related('seller', 'category').prefetch_related('images')
    
    # Get filter form
    form = ProductSearchForm(request.GET or None)
    
    # Search query with relevance prioritization
    search_query = request.GET.get('q', '').strip()
    if search_query:
        from django.db.models import Case, When, Value, IntegerField
        
        products = products.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(category__name__icontains=search_query) |
            Q(sku__icontains=search_query) |
            Q(seller__user__full_name__icontains=search_query)
        ).annotate(
            # Prioritize matches: title > category > description
            relevance=Case(
                When(title__icontains=search_query, then=Value(1)),
                When(category__name__icontains=search_query, then=Value(2)),
                When(description__icontains=search_query, then=Value(3)),
                default=Value(4),
                output_field=IntegerField()
            )
        )
    
    # Category filter
    category_slug = request.GET.get('category')
    if category_slug:
        try:
            category = Category.objects.get(slug=category_slug, is_active=True)
            # Include products from subcategories
            all_categories = [category] + category.get_all_children()
            products = products.filter(category__in=all_categories)
        except Category.DoesNotExist:
            pass
    
    # Price range filter
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
    
    # Rating filter
    min_rating = request.GET.get('min_rating')
    if min_rating:
        try:
            products = products.filter(rating__gte=float(min_rating))
        except ValueError:
            pass
    
    # In stock filter
    if request.GET.get('in_stock'):
        products = products.filter(stock__gt=0)
    
    # Sorting
    import random
    sort_by = request.GET.get('sort_by', 'shuffle')  # Default to shuffle
    valid_sorts = ['-created_at', 'price', '-price', '-rating', '-review_count', 'shuffle', 'most_recent']
    if sort_by in valid_sorts:
        if sort_by == 'shuffle':
            # Shuffle products randomly
            products_list = list(products)
            random.shuffle(products_list)
            paginator = Paginator(products_list, 24)
            page_number = request.GET.get('page', 1)
            try:
                page_obj = paginator.get_page(page_number)
            except (EmptyPage, PageNotAnInteger):
                page_obj = paginator.get_page(1)
        elif sort_by == 'most_recent':
            # Most recent (newest first)
            products = products.order_by('-created_at')
            paginator = Paginator(products, 24)
            page_number = request.GET.get('page', 1)
            page_obj = paginator.get_page(page_number)
        else:
            products = products.order_by(sort_by)
            paginator = Paginator(products, 24)
            page_number = request.GET.get('page', 1)
            page_obj = paginator.get_page(page_number)
    else:
        # Default shuffle if invalid sort
        products_list = list(products)
        random.shuffle(products_list)
        paginator = Paginator(products_list, 20)
        page_number = request.GET.get('page', 1)
        try:
            page_obj = paginator.get_page(page_number)
        except (EmptyPage, PageNotAnInteger):
            page_obj = paginator.get_page(1)
    
    # Get all categories for filter sidebar
    categories = Category.objects.filter(parent=None, is_active=True).prefetch_related('children')
    
    context = {
        'page_obj': page_obj,
        'products': page_obj,
        'form': form,
        'categories': categories,
        'search_query': search_query,
        'total_count': paginator.count,
        'view_type': request.GET.get('view', 'grid'),  # grid or list
    }
    
    return render(request, 'products/products.html', context)


def product_detail_view(request, slug):
    """Display product detail page"""
    product = get_object_or_404(
        Product.objects.select_related('seller', 'category').prefetch_related('images', 'variants', 'vto_assets'),
        slug=slug
    )
    
    # Get primary image or first image
    primary_image = product.images.filter(is_primary=True).first() or product.images.first()
    all_images = product.images.all()
    
    # Get related products (same category, similar price range) - shuffled
    import random
    related_products = list(Product.objects.filter(
        category=product.category,
        status='active'
    ).exclude(id=product.id).select_related('category').prefetch_related('images'))
    
    # Shuffle related products for variety
    random.shuffle(related_products)
    related_products = related_products[:6]
    
    # Get frequently bought together products
    # Find products that were purchased in the same orders
    from apps.orders.models import OrderItem
    from django.db.models import Count
    
    # Get orders containing this product
    order_ids = OrderItem.objects.filter(product=product).values_list('order_id', flat=True)
    
    # Find other products in those orders
    frequently_bought_together = []
    if order_ids:
        frequently_bought_together = Product.objects.filter(
            orderitem__order_id__in=order_ids,
            status='active'
        ).exclude(
            id=product.id
        ).annotate(
            purchase_count=Count('orderitem')
        ).order_by('-purchase_count').select_related('category').prefetch_related('images')[:4]
    
    # If no frequently bought together, show similar products
    if not frequently_bought_together:
        price_range = product.price * Decimal('0.3')  # 30% price range
        frequently_bought_together = Product.objects.filter(
            category=product.category,
            status='active',
            price__gte=product.price - price_range,
            price__lte=product.price + price_range,
        ).exclude(id=product.id).select_related('category').prefetch_related('images')[:4]
    
    # Get VTO info if enabled
    vto_asset = None
    if product.vto_enabled:
        vto_asset = product.vto_assets.filter(is_active=True).first()
    
    context = {
        'product': product,
        'primary_image': primary_image,
        'all_images': all_images,
        'related_products': related_products,
        'frequently_bought_together': frequently_bought_together,
        'variants': product.variants.all(),
        'vto_asset': vto_asset,
    }
    
    return render(request, 'products/product_detail.html', context)


def category_products_view(request, slug):
    """Display products in a specific category"""
    category = get_object_or_404(Category, slug=slug, is_active=True)
    
    # Get all products in this category and subcategories
    all_categories = [category] + category.get_all_children()
    products = Product.objects.filter(
        category__in=all_categories,
        status='active'
    ).select_related('seller', 'category').prefetch_related('images')
    
    # Apply filters
    form = ProductSearchForm(request.GET or None)
    
    # Price filter
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
    
    # Rating filter
    min_rating = request.GET.get('min_rating')
    if min_rating:
        try:
            products = products.filter(rating__gte=float(min_rating))
        except ValueError:
            pass
    
    # Sorting
    import random
    sort_by = request.GET.get('sort_by', 'shuffle')  # Default to shuffle
    valid_sorts = ['-created_at', 'price', '-price', '-rating', '-review_count', 'shuffle', 'most_recent']
    if sort_by in valid_sorts:
        if sort_by == 'shuffle':
            # Shuffle products randomly
            products_list = list(products)
            random.shuffle(products_list)
            paginator = Paginator(products_list, 24)
            page_number = request.GET.get('page', 1)
            try:
                page_obj = paginator.get_page(page_number)
            except (EmptyPage, PageNotAnInteger):
                page_obj = paginator.get_page(1)
        elif sort_by == 'most_recent':
            # Most recent (newest first)
            products = products.order_by('-created_at')
            paginator = Paginator(products, 24)
            page_number = request.GET.get('page', 1)
            page_obj = paginator.get_page(page_number)
        else:
            products = products.order_by(sort_by)
            paginator = Paginator(products, 24)
            page_number = request.GET.get('page', 1)
            page_obj = paginator.get_page(page_number)
    else:
        # Default shuffle
        products_list = list(products)
        random.shuffle(products_list)
        paginator = Paginator(products_list, 20)
        page_number = request.GET.get('page', 1)
        try:
            page_obj = paginator.get_page(page_number)
        except (EmptyPage, PageNotAnInteger):
            page_obj = paginator.get_page(1)
    
    # Get subcategories
    subcategories = category.children.filter(is_active=True)
    
    # Get best sellers for this category (featured products)
    best_sellers = Product.objects.filter(
        category__in=all_categories,
        status='active',
        is_featured=True
    ).prefetch_related('images')[:10]
    
    # Get most recent products (newest additions)
    most_recent = Product.objects.filter(
        category__in=all_categories,
        status='active'
    ).prefetch_related('images').order_by('-created_at')[:10]
    
    context = {
        'category': category,
        'page_obj': page_obj,
        'products': page_obj,
        'subcategories': subcategories,
        'form': form,
        'total_count': paginator.count,
        'view_type': request.GET.get('view', 'grid'),
        'best_sellers': best_sellers,
        'most_recent': most_recent,
    }
    
    return render(request, 'products/category.html', context)


def search_products_view(request):
    """Search products with query"""
    query = request.GET.get('q', '').strip()
    products = Product.objects.filter(status='active')
    
    if query:
        products = products.filter(
            Q(title__icontains=query) |
            Q(description__icontains=query) |
            Q(sku__icontains=query) |
            Q(category_path__icontains=query)
        ).select_related('seller', 'category').prefetch_related('images')
    else:
        products = products.none()
    
    # Pagination
    paginator = Paginator(products, 24)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'query': query,
        'page_obj': page_obj,
        'products': page_obj,
        'total_count': paginator.count,
    }
    
    return render(request, 'products/search_results.html', context)


def product_autocomplete_view(request):
    """AJAX autocomplete for product search"""
    query = request.GET.get('q', '').strip()
    
    if len(query) < 2:
        return JsonResponse({'results': []})
    
    products = Product.objects.filter(
        Q(title__icontains=query) | Q(sku__icontains=query),
        status='active'
    ).select_related('category')[:10]
    
    results = []
    for product in products:
        # Get primary image
        primary_image = product.images.filter(is_primary=True).first()
        image_url = primary_image.image.url if primary_image else None
        
        results.append({
            'id': product.id,
            'title': product.title,
            'slug': product.slug,
            'price': str(product.price),
            'image': image_url,
            'category': product.category.name if product.category else 'Uncategorized',
        })
    
    return JsonResponse({'results': results})


def quick_view_ajax(request, slug):
    """AJAX view for quick product preview"""
    product = get_object_or_404(
        Product.objects.select_related('seller', 'category').prefetch_related('images'),
        slug=slug,
        status='active'
    )
    
    # Get primary image
    primary_image = product.images.filter(is_primary=True).first() or product.images.first()
    
    data = {
        'id': product.id,
        'title': product.title,
        'slug': product.slug,
        'price': str(product.price),
        'compare_at_price': str(product.compare_at_price) if product.compare_at_price else None,
        'discount_percentage': product.discount_percentage,
        'description': product.description[:200] + '...' if len(product.description) > 200 else product.description,
        'rating': str(product.rating),
        'review_count': product.review_count,
        'stock': product.stock,
        'is_in_stock': product.is_in_stock,
        'image': primary_image.image.url if primary_image else None,
        'category': product.category.name if product.category else 'Uncategorized',
        'seller': product.seller.user.full_name if product.seller else 'Unknown',
    }
    
    return JsonResponse(data)

