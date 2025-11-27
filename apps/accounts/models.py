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


class ShippingAddress(models.Model):
    """
    Saved shipping addresses for users.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='shipping_addresses',
        db_index=True
    )
    
    # Address fields
    full_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20)
    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, default='Egypt')
    postal_code = models.CharField(max_length=20, blank=True)
    
    # Address metadata
    is_default = models.BooleanField(default=False, help_text=_('Default shipping address'))
    label = models.CharField(max_length=50, blank=True, help_text=_('Address label, e.g., Home, Work'))
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'shipping_addresses'
        verbose_name = _('Shipping Address')
        verbose_name_plural = _('Shipping Addresses')
        ordering = ['-is_default', '-created_at']
        indexes = [
            models.Index(fields=['user', 'is_default']),
        ]
    
    def __str__(self):
        return f"{self.full_name} - {self.city}, {self.country}"
    
    def to_dict(self):
        """Convert to dictionary for use in checkout"""
        return {
            'full_name': self.full_name,
            'email': self.user.email,
            'phone': self.phone,
            'address_line1': self.address_line1,
            'address_line2': self.address_line2,
            'city': self.city,
            'state': self.state,
            'country': self.country,
            'postal_code': self.postal_code,
        }
    
    def save(self, *args, **kwargs):
        # If this is set as default, unset other defaults for this user
        if self.is_default:
            ShippingAddress.objects.filter(user=self.user, is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


class SellerProfile(models.Model):
    """
    Extended profile for sellers.
    One-to-one relationship with User where role='seller'.
    """
    # One-to-one relationship with User (primary key)
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='seller_profile',
        primary_key=True,
        db_index=True
    )
    
    # Business information
    business_name = models.CharField(
        max_length=255,
        help_text=_('Official business name')
    )
    business_registration_number = models.CharField(
        max_length=100,
        blank=True,
        help_text=_('Business registration/license number')
    )
    
    # Contact information
    business_email = models.EmailField(
        blank=True,
        help_text=_('Business email (can differ from user email)')
    )
    business_phone = PhoneNumberField(
        blank=True,
        null=True,
        help_text=_('Business phone number')
    )
    business_address = models.TextField(
        blank=True,
        help_text=_('Business physical address')
    )
    
    # Business status
    is_approved = models.BooleanField(
        default=False,
        db_index=True,
        help_text=_('Seller account approved by admin')
    )
    is_verified = models.BooleanField(
        default=False,
        help_text=_('Business verified (documents checked)')
    )
    approval_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_('Date when seller was approved')
    )
    
    # Business metrics
    total_sales = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text=_('Total sales amount (EGP)')
    )
    total_orders = models.PositiveIntegerField(
        default=0,
        help_text=_('Total number of orders')
    )
    rating = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0,
        help_text=_('Average seller rating')
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'seller_profiles'
        verbose_name = _('Seller Profile')
        verbose_name_plural = _('Seller Profiles')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['is_approved']),
            models.Index(fields=['business_name']),
        ]
    
    def __str__(self):
        return f"{self.business_name} ({self.user.email})"
