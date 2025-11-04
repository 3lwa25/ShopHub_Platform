"""
User and Seller Profile Models for Shop Hub
"""
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _
from phonenumber_field.modelfields import PhoneNumberField


class User(AbstractUser):
    """
    Custom User model with role-based authentication.
    Supports buyer, seller, and admin roles.
    """
    ROLE_CHOICES = [
        ('buyer', 'Buyer'),
        ('seller', 'Seller'),
        ('admin', 'Admin'),
    ]
    
    # Core fields (username, email, password inherited from AbstractUser)
    email = models.EmailField(_('email address'), unique=True)
    role = models.CharField(
        max_length=10,
        choices=ROLE_CHOICES,
        default='buyer',
        db_index=True
    )
    
    # Additional profile fields
    full_name = models.CharField(max_length=255, blank=True)
    phone = PhoneNumberField(blank=True, null=True, help_text=_('Contact phone number'))
    avatar = models.ImageField(
        upload_to='avatars/%Y/%m/',
        blank=True,
        null=True,
        help_text=_('Profile picture')
    )
    
    # Email verification
    verified = models.BooleanField(
        default=False,
        help_text=_('Email verified status')
    )
    
    # Account status
    is_active = models.BooleanField(default=True)
    last_login = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Make email the primary login field
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']
    
    class Meta:
        db_table = 'users'
        verbose_name = _('User')
        verbose_name_plural = _('Users')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['role']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.email} ({self.get_role_display()})"
    
    @property
    def is_buyer(self):
        """Check if user is a buyer"""
        return self.role == 'buyer'
    
    @property
    def is_seller(self):
        """Check if user is a seller"""
        return self.role == 'seller'
    
    @property
    def is_admin_user(self):
        """Check if user is an admin"""
        return self.role == 'admin' or self.is_superuser
    
    def save(self, *args, **kwargs):
        # Ensure full_name is set if not provided
        if not self.full_name:
            self.full_name = f"{self.first_name} {self.last_name}".strip() or self.username
        super().save(*args, **kwargs)


class SellerProfile(models.Model):
    """
    Extended profile for sellers.
    One-to-one relationship with User where role='seller'.
    """
    # One-to-one relationship with User
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='seller_profile',
        primary_key=True
    )
    
    # Business information
    business_name = models.CharField(
        max_length=255,
        help_text=_('Shop/Business name')
    )
    business_description = models.TextField(
        blank=True,
        help_text=_('Describe your business')
    )
    logo = models.ImageField(
        upload_to='seller_logos/%Y/%m/',
        blank=True,
        null=True,
        help_text=_('Business logo')
    )
    
    # Business address
    address = models.TextField(blank=True, help_text=_('Business address'))
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, default='Egypt')
    postal_code = models.CharField(max_length=20, blank=True)
    
    # Verification and status
    verified_seller = models.BooleanField(
        default=False,
        help_text=_('Admin-verified seller badge')
    )
    
    # Performance metrics
    total_sales = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00,
        help_text=_('Total sales amount (EGP)')
    )
    total_orders = models.PositiveIntegerField(
        default=0,
        help_text=_('Total completed orders')
    )
    rating = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0.00,
        help_text=_('Average seller rating (0-5)')
    )
    rating_count = models.PositiveIntegerField(
        default=0,
        help_text=_('Number of ratings received')
    )
    
    # Social media links
    website = models.URLField(blank=True, max_length=500)
    facebook = models.URLField(blank=True, max_length=500)
    instagram = models.URLField(blank=True, max_length=500)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'seller_profiles'
        verbose_name = _('Seller Profile')
        verbose_name_plural = _('Seller Profiles')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.business_name} (Seller: {self.user.email})"
    
    def update_rating(self):
        """
        Recalculate average rating from product reviews.
        Called when a new review is added.
        """
        from apps.products.models import Product
        from apps.reviews.models import Review
        
        # Get all products by this seller
        seller_products = Product.objects.filter(seller=self)
        
        # Get all reviews for these products
        reviews = Review.objects.filter(product__in=seller_products)
        
        if reviews.exists():
            total_rating = sum(review.rating for review in reviews)
            self.rating_count = reviews.count()
            self.rating = round(total_rating / self.rating_count, 2)
            self.save(update_fields=['rating', 'rating_count', 'updated_at'])
    
    def update_sales(self, amount):
        """
        Update total sales when an order is completed.
        
        Args:
            amount (Decimal): Order amount to add to total sales
        """
        self.total_sales += amount
        self.total_orders += 1
        self.save(update_fields=['total_sales', 'total_orders', 'updated_at'])

