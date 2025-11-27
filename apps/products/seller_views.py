"""
Seller Product Management Views
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils.text import slugify
from apps.accounts.decorators import approved_seller_required
from .models import Product, ProductImage, ProductVariant, Category
from .forms import ProductForm, ProductImageFormSet, ProductVariantFormSet


@approved_seller_required
def seller_product_list(request):
    """
    List all products for the seller
    """
    seller_profile = request.user.seller_profile
    
    # Get products
    products = Product.objects.filter(seller=seller_profile).select_related(
        'category'
    ).prefetch_related('images').order_by('-created_at')
    
    # Search
    search_query = request.GET.get('search', '')
    if search_query:
        products = products.filter(
            Q(title__icontains=search_query) |
            Q(sku__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    
    # Filter by status
    status = request.GET.get('status', '')
    if status:
        products = products.filter(status=status)
    
    # Filter by category
    category_id = request.GET.get('category', '')
    if category_id:
        products = products.filter(category_id=category_id)
    
    # Pagination
    paginator = Paginator(products, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get categories for filter
    categories = Category.objects.filter(is_active=True).order_by('name')
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'status': status,
        'categories': categories,
        'selected_category': category_id,
    }
    
    return render(request, 'seller/products/product_list.html', context)


@approved_seller_required
def seller_product_add(request):
    """
    Add a new product
    """
    seller_profile = request.user.seller_profile
    
    product_instance = Product(seller=seller_profile)

    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product_instance)
        image_formset = ProductImageFormSet(request.POST, request.FILES, instance=product_instance, prefix='images')
        variant_formset = ProductVariantFormSet(request.POST, request.FILES, instance=product_instance, prefix='variants')
        
        if form.is_valid() and image_formset.is_valid() and variant_formset.is_valid():
            # Save product
            product = form.save(commit=False)
            product.seller = seller_profile
            if not product.slug:
                product.slug = slugify(product.title)
            product.save()
            
            image_formset.instance = product
            image_formset.save()

            variant_formset.instance = product
            variant_formset.save()
            
            messages.success(request, f'Product \"{product.title}\" added successfully!')
            return redirect('products:seller_products')
    else:
        form = ProductForm(instance=product_instance)
        image_formset = ProductImageFormSet(instance=product_instance, prefix='images')
        variant_formset = ProductVariantFormSet(instance=product_instance, prefix='variants')
    
    context = {
        'form': form,
        'image_formset': image_formset,
        'variant_formset': variant_formset,
        'action': 'Add',
    }
    
    return render(request, 'seller/products/product_form.html', context)


@approved_seller_required
def seller_product_edit(request, pk):
    """
    Edit an existing product
    """
    seller_profile = request.user.seller_profile
    product = get_object_or_404(Product, pk=pk, seller=seller_profile)
    
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        image_formset = ProductImageFormSet(request.POST, request.FILES, instance=product, prefix='images')
        variant_formset = ProductVariantFormSet(request.POST, instance=product, prefix='variants')
        
        if form.is_valid() and image_formset.is_valid() and variant_formset.is_valid():
            product = form.save()
            image_formset.save()
            variant_formset.save()
            
            messages.success(request, f'Product \"{product.title}\" updated successfully!')
            return redirect('products:seller_products')
    else:
        form = ProductForm(instance=product)
        image_formset = ProductImageFormSet(instance=product, prefix='images')
        variant_formset = ProductVariantFormSet(instance=product, prefix='variants')
    
    context = {
        'form': form,
        'image_formset': image_formset,
        'variant_formset': variant_formset,
        'product': product,
        'action': 'Edit',
    }
    
    return render(request, 'seller/products/product_form.html', context)


@approved_seller_required
def seller_product_delete(request, pk):
    """
    Delete a product
    """
    seller_profile = request.user.seller_profile
    product = get_object_or_404(Product, pk=pk, seller=seller_profile)
    
    if request.method == 'POST':
        product_title = product.title
        product.delete()
        messages.success(request, f'Product \"{product_title}\" deleted successfully!')
        return redirect('products:seller_products')
    
    context = {
        'product': product,
    }
    
    return render(request, 'seller/products/product_delete_confirm.html', context)


@approved_seller_required
def seller_product_bulk_update(request):
    """
    Bulk update product status
    """
    if request.method == 'POST':
        product_ids = request.POST.getlist('product_ids')
        action = request.POST.get('action')
        
        if not product_ids:
            messages.warning(request, 'No products selected.')
            return redirect('products:seller_products')
        
        seller_profile = request.user.seller_profile
        products = Product.objects.filter(id__in=product_ids, seller=seller_profile)
        
        if action == 'activate':
            count = products.update(status='active')
            messages.success(request, f'{count} product(s) activated.')
        elif action == 'deactivate':
            count = products.update(status='inactive')
            messages.success(request, f'{count} product(s) deactivated.')
        elif action == 'delete':
            count = products.count()
            products.delete()
            messages.success(request, f'{count} product(s) deleted.')
        else:
            messages.error(request, 'Invalid action.')
    
    return redirect('products:seller_products')

