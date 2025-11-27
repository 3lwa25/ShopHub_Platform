"""
Views for User Authentication and Profile Management
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.urls import reverse_lazy
from django.db import transaction
from django.utils import timezone
from .models import User, SellerProfile
from .forms import UserRegistrationForm, UserLoginForm, UserProfileForm, SellerProfileForm


def register_view(request):
    """
    User registration view with role selection.
    """
    if request.user.is_authenticated:
        return redirect('accounts:profile')
    
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            
            # Create seller profile if role is seller
            if user.role == 'seller':
                seller_profile = SellerProfile.objects.create(
                    user=user,
                    business_name=f"{user.full_name}'s Shop",
                    country='Egypt'
                )
                messages.success(
                    request,
                    f'Account created successfully! Please complete your seller profile.'
                )
                return redirect('accounts:seller_profile_create')
            else:
                messages.success(
                    request,
                    f'Account created successfully! Welcome to Shop Hub, {user.full_name}!'
                )
                login(request, user)
                return redirect('accounts:profile')
    else:
        form = UserRegistrationForm()
    
    return render(request, 'accounts/register.html', {'form': form})


def login_view(request):
    """
    User login view.
    """
    if request.user.is_authenticated:
        return redirect('accounts:profile')
    
    if request.method == 'POST':
        form = UserLoginForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            remember_me = form.cleaned_data.get('remember_me', False)
            
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                
                # Update last_login
                user.last_login = timezone.now()
                user.save(update_fields=['last_login'])
                
                # Set session expiry
                if not remember_me:
                    request.session.set_expiry(0)  # Session expires on browser close
                else:
                    request.session.set_expiry(86400 * 30)  # 30 days
                
                messages.success(request, f'Welcome back, {user.full_name}!')
                
                # Redirect based on role
                next_url = request.GET.get('next')
                
                if user.is_admin_user:
                    # Admin users go to admin dashboard
                    return redirect('accounts:admin_dashboard')
                elif user.is_seller:
                    # Sellers go to seller dashboard
                    return redirect('accounts:seller_dashboard')
                elif user.is_buyer:
                    # Buyers go to home page
                    return redirect(next_url if next_url else 'core:home')
                else:
                    return redirect('core:home')
            else:
                messages.error(request, 'Invalid email/username or password.')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = UserLoginForm()
    
    return render(request, 'accounts/login.html', {'form': form})


@login_required
def logout_view(request):
    """
    User logout view.
    """
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('accounts:login')


@login_required
def profile_view(request):
    """
    User profile view and edit.
    """
    user = request.user
    
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('accounts:profile')
    else:
        form = UserProfileForm(instance=user)
    
    context = {
        'user': user,
        'form': form,
        'seller_profile': getattr(user, 'seller_profile', None),
    }
    
    return render(request, 'accounts/profile.html', context)


@login_required
def seller_profile_create_view(request):
    """
    Create seller profile for new sellers.
    """
    if not request.user.is_seller:
        messages.error(request, 'Only sellers can access this page.')
        return redirect('accounts:profile')
    
    if hasattr(request.user, 'seller_profile'):
        messages.info(request, 'Seller profile already exists.')
        return redirect('accounts:seller_profile_edit')
    
    if request.method == 'POST':
        form = SellerProfileForm(request.POST, request.FILES)
        if form.is_valid():
            seller_profile = form.save(commit=False)
            seller_profile.user = request.user
            seller_profile.save()
            messages.success(request, 'Seller profile created successfully!')
            return redirect('accounts:seller_dashboard')
    else:
        form = SellerProfileForm()
    
    return render(request, 'accounts/seller_profile_create.html', {'form': form})


@login_required
def seller_profile_edit_view(request):
    """
    Edit seller profile.
    """
    if not request.user.is_seller:
        messages.error(request, 'Only sellers can access this page.')
        return redirect('accounts:profile')
    
    seller_profile = get_object_or_404(SellerProfile, user=request.user)
    
    if request.method == 'POST':
        form = SellerProfileForm(request.POST, request.FILES, instance=seller_profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Seller profile updated successfully!')
            return redirect('accounts:seller_dashboard')
    else:
        form = SellerProfileForm(instance=seller_profile)
    
    return render(request, 'accounts/seller_profile_edit.html', {'form': form, 'seller_profile': seller_profile})


