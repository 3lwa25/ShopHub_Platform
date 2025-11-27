"""
Views for Product Reviews
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.db.models import Q, Count, Avg
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import timedelta

from apps.products.models import Product
from apps.orders.models import OrderItem
from apps.accounts.decorators import buyer_required, approved_seller_required
from .models import Review, ReviewHelpful, ReviewImage
from .forms import ReviewForm, ReviewImageForm, SellerResponseForm
from apps.notifications.models import Notification


@buyer_required
@login_required
def write_review_view(request, order_item_id):
    """Allow buyers to write a review for a product they purchased"""
    order_item = get_object_or_404(OrderItem, id=order_item_id, order__buyer=request.user)
    product = order_item.product
    
    # Check if review already exists
    existing_review = Review.objects.filter(buyer=request.user, product=product).first()
    if existing_review:
        messages.info(request, 'You have already reviewed this product. You can edit your review below.')
        return redirect('reviews:edit_review', review_id=existing_review.id)
    
    # Check if order is delivered
    if order_item.order.status != 'DELIVERED':
        messages.warning(request, 'You can only review products from delivered orders.')
        return redirect('orders:buyer_order_detail', order_number=order_item.order.order_number)
    
    if request.method == 'POST':
        form = ReviewForm(request.POST, user=request.user, product=product)
        if form.is_valid():
            review = form.save(commit=False)
            review.buyer = request.user
            review.product = product
            review.order_item = order_item
            review.order = order_item.order
            review.status = 'pending'  # Requires admin approval
            review.save()
            
            Notification.create_notification(
                user=request.user,
                notification_type='system',
                title='Review Submitted',
                message=f'Your review for "{product.title}" has been submitted and is pending approval.',
                link=f'/products/{product.slug}/#reviews',
            )
            
            # Handle image uploads
            images = request.FILES.getlist('images')
            for image in images[:5]:  # Limit to 5 images
                ReviewImage.objects.create(review=review, image=image)
            
            messages.success(request, 'Your review has been submitted and is pending approval.')
            return redirect('reviews:product_reviews', product_id=product.id)
    else:
        form = ReviewForm(user=request.user, product=product, initial={'order_item': order_item})
    
    context = {
        'form': form,
        'product': product,
        'order_item': order_item,
    }
    return render(request, 'reviews/write_review.html', context)


@buyer_required
@login_required
def edit_review_view(request, review_id):
    """Allow buyers to edit their existing review"""
    review = get_object_or_404(Review, id=review_id, buyer=request.user)
    
    # Check if review can be edited (within 30 days)
    days_since_creation = (timezone.now() - review.created_at).days
    if days_since_creation > 30:
        messages.warning(request, 'You can only edit reviews within 30 days of posting.')
        return redirect('reviews:product_reviews', product_id=review.product.id)
    
    if request.method == 'POST':
        form = ReviewForm(request.POST, instance=review, user=request.user, product=review.product)
        if form.is_valid():
            review = form.save()
            review.status = 'pending'  # Re-approve after edit
            
            # Handle new image uploads
            images = request.FILES.getlist('images')
            for image in images[:5]:
                ReviewImage.objects.create(review=review, image=image)
            
            messages.success(request, 'Your review has been updated and is pending approval.')
            return redirect('reviews:product_reviews', product_id=review.product.id)
    else:
        form = ReviewForm(instance=review, user=request.user, product=review.product)
    
    context = {
        'form': form,
        'review': review,
        'product': review.product,
        'existing_images': review.images.all(),
    }
    return render(request, 'reviews/edit_review.html', context)


def product_reviews_view(request, product_id):
    """Display all reviews for a product"""
    product = get_object_or_404(Product, id=product_id)
    
    # Get approved reviews
    reviews = Review.objects.filter(product=product, status='approved').select_related('buyer').prefetch_related('images', 'helpful_votes')
    
    # Filtering
    rating_filter = request.GET.get('rating')
    if rating_filter:
        try:
            rating = int(rating_filter)
            if 1 <= rating <= 5:
                reviews = reviews.filter(rating=rating)
        except ValueError:
            pass
    
    # Sorting
    sort_by = request.GET.get('sort', 'recent')
    if sort_by == 'helpful':
        reviews = reviews.order_by('-helpful_count', '-created_at')
    elif sort_by == 'highest':
        reviews = reviews.order_by('-rating', '-created_at')
    elif sort_by == 'lowest':
        reviews = reviews.order_by('rating', '-created_at')
    else:  # recent (default)
        reviews = reviews.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(reviews, 10)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Statistics
    total_reviews = reviews.count()
    avg_rating = reviews.aggregate(avg=Avg('rating'))['avg'] or 0
    rating_distribution = reviews.values('rating').annotate(count=Count('id')).order_by('-rating')
    
    # Check if user can review
    can_review = False
    if request.user.is_authenticated and not request.user.is_seller:
        # Check if user has purchased and delivered this product
        has_purchased = OrderItem.objects.filter(
            order__buyer=request.user,
            product=product,
            order__status='DELIVERED'
        ).exists()
        has_reviewed = Review.objects.filter(buyer=request.user, product=product).exists()
        can_review = has_purchased and not has_reviewed
    
    context = {
        'product': product,
        'reviews': page_obj,
        'total_reviews': total_reviews,
        'avg_rating': round(avg_rating, 1) if avg_rating else 0,
        'rating_distribution': rating_distribution,
        'can_review': can_review,
        'sort_by': sort_by,
        'rating_filter': rating_filter,
    }
    return render(request, 'reviews/product_reviews.html', context)


@login_required
@require_POST
def mark_helpful_view(request, review_id):
    """Mark a review as helpful (AJAX)"""
    review = get_object_or_404(Review, id=review_id, status='approved')
    
    # Check if user already voted
    helpful_vote, created = ReviewHelpful.objects.get_or_create(
        review=review,
        user=request.user
    )
    
    if created:
        review.helpful_count += 1
        review.save(update_fields=['helpful_count'])
        return JsonResponse({
            'success': True,
            'message': 'Thank you for your feedback!',
            'helpful_count': review.helpful_count
        })
    else:
        return JsonResponse({
            'success': False,
            'message': 'You have already marked this review as helpful.'
        })


@approved_seller_required
@login_required
def seller_respond_view(request, review_id):
    """Allow sellers to respond to reviews of their products"""
    review = get_object_or_404(Review, id=review_id, status='approved')
    
    # Check if seller owns this product
    if review.product.seller.user != request.user:
        messages.error(request, 'You can only respond to reviews of your own products.')
        return redirect('reviews:product_reviews', product_id=review.product.id)
    
    # Check if already responded
    if review.seller_response:
        messages.info(request, 'You have already responded to this review.')
        return redirect('reviews:product_reviews', product_id=review.product.id)
    
    if request.method == 'POST':
        form = SellerResponseForm(request.POST)
        if form.is_valid():
            review.seller_response = form.cleaned_data['response']
            review.seller_responded_at = timezone.now()
            review.save(update_fields=['seller_response', 'seller_responded_at'])
            messages.success(request, 'Your response has been posted.')
            return redirect('reviews:product_reviews', product_id=review.product.id)
    else:
        form = SellerResponseForm()
    
    context = {
        'form': form,
        'review': review,
        'product': review.product,
    }
    return render(request, 'reviews/seller_respond.html', context)


@buyer_required
@login_required
def delete_review_view(request, review_id):
    """Allow buyers to delete their own review"""
    review = get_object_or_404(Review, id=review_id, buyer=request.user)
    product_id = review.product.id
    
    if request.method == 'POST':
        review.delete()
        messages.success(request, 'Your review has been deleted.')
        return redirect('reviews:product_reviews', product_id=product_id)
    
    context = {
        'review': review,
        'product': review.product,
    }
    return render(request, 'reviews/delete_review_confirm.html', context)

