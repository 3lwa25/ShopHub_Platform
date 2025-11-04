"""
Product Catalog Models for Shop Hub
"""
from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.accounts.models import SellerProfile


class Category(models.Model):
    """
    Hierarchical product categories.
    Supports parent-child relationships for nested categories.
    """
    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=255, unique=True, db_index=True)
    
    # Hierarchical structure
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        help_text=_('Parent category (if subcategory)')
    )
    
    # Category details
    description = models.TextField(blank=True)
    image = models.ImageField(
        upload_to='categories/%Y/%m/',
        blank=True,
        null=True,
        help_text=_('Category banner image')
    )
    
    # Display settings
    is_active = models.BooleanField(default=True, db_index=True)
    display_order = models.PositiveIntegerField(
        default=0,
        help_text=_('Display order (lower numbers first)')
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'categories'
        verbose_name = _('Category')
        verbose_name_plural = _('Categories')
        ordering = ['display_order', 'name']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['is_active']),
            models.Index(fields=['parent']),
        ]
    
    def __str__(self):
        return self.get_full_path()
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    
    def get_full_path(self):
        """Return full category path (e.g., 'Fashion > Men's Clothing')"""
        if self.parent:
            return f"{self.parent.get_full_path()} > {self.name}"
        return self.name
    
    def get_all_children(self):
        """Recursively get all child categories"""
        children = list(self.children.all())
        for child in list(children):
            children.extend(child.get_all_children())
        return children


class Product(models.Model):
    """
    Main product model with all product information.
    """
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('out_of_stock', 'Out of Stock'),
    ]
    
    # Seller relationship
    seller = models.ForeignKey(
        SellerProfile,
        on_delete=models.CASCADE,
        related_name='products',
        db_index=True
    )
    
    # Category relationships
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products',
        db_index=True
    )
    category_path = models.CharField(
        max_length=255,
        blank=True,
        help_text=_('Full category path (e.g., "Fashion > Men\'s Clothing")')
    )
    
    # Basic product info
    title = models.CharField(max_length=500, db_index=True)
    slug = models.SlugField(max_length=550, unique=True, db_index=True)
    sku = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text=_('Stock Keeping Unit')
    )
    description = models.TextField(help_text=_('Product description'))
    
    # Pricing
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
        help_text=_('Product price (EGP)')
    )
    compare_at_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0.01)],
        help_text=_('Original price for showing discounts')
    )
    currency = models.CharField(max_length=3, default='EGP')
    
    # Inventory
    stock = models.PositiveIntegerField(
        default=0,
        help_text=_('Available quantity')
    )
    low_stock_threshold = models.PositiveIntegerField(
        default=10,
        help_text=_('Alert when stock falls below this number')
    )
    
    # Product attributes (flexible JSON field for colors, sizes, materials, etc.)
    attributes = models.JSONField(
        default=dict,
        blank=True,
        help_text=_('Product attributes like colors, sizes, materials (JSON)')
    )
    
    # Product status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active',
        db_index=True
    )
    is_featured = models.BooleanField(
        default=False,
        db_index=True,
        help_text=_('Show on homepage/featured sections')
    )
    
    # Ratings and reviews
    rating = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0), MaxValueValidator(5)],
        help_text=_('Average rating (0-5)')
    )
    review_count = models.PositiveIntegerField(
        default=0,
        help_text=_('Total number of reviews')
    )
    
    # Virtual Try-On
    vto_enabled = models.BooleanField(
        default=False,
        db_index=True,
        help_text=_('Enable Virtual Try-On for this product')
    )
    
    # SEO
    meta_title = models.CharField(max_length=255, blank=True)
    meta_description = models.TextField(blank=True)
    meta_keywords = models.CharField(max_length=500, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'products'
        verbose_name = _('Product')
        verbose_name_plural = _('Products')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['seller', 'status']),
            models.Index(fields=['category', 'status']),
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['-rating', '-review_count']),
            models.Index(fields=['is_featured', 'status']),
            models.Index(fields=['vto_enabled']),
        ]
    
    def __str__(self):
        return f"{self.title} (SKU: {self.sku})"
    
    def save(self, *args, **kwargs):
        # Auto-generate slug from title
        if not self.slug:
            base_slug = slugify(self.title)
            slug = base_slug
            counter = 1
            while Product.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        
        # Set category path if category is set
        if self.category:
            self.category_path = self.category.get_full_path()
        
        # Auto-set status based on stock
        if self.stock == 0 and self.status == 'active':
            self.status = 'out_of_stock'
        
        super().save(*args, **kwargs)
    
    @property
    def is_on_sale(self):
        """Check if product has a discount"""
        return bool(self.compare_at_price and self.compare_at_price > self.price)
    
    @property
    def discount_percentage(self):
        """Calculate discount percentage"""
        if self.is_on_sale:
            return round(((self.compare_at_price - self.price) / self.compare_at_price) * 100)
        return 0
    
    @property
    def is_low_stock(self):
        """Check if stock is below threshold"""
        return self.stock <= self.low_stock_threshold
    
    @property
    def is_in_stock(self):
        """Check if product is in stock"""
        return self.stock > 0
    
    def update_rating(self):
        """
        Recalculate average rating from reviews.
        Called when a new review is added or updated.
        """
        from apps.reviews.models import Review
        reviews = self.reviews.all()
        
        if reviews.exists():
            total_rating = sum(review.rating for review in reviews)
            self.review_count = reviews.count()
            self.rating = round(total_rating / self.review_count, 2)
        else:
            self.rating = 0.00
            self.review_count = 0
        
        self.save(update_fields=['rating', 'review_count', 'updated_at'])
    
    def reduce_stock(self, quantity):
        """Reduce stock after order"""
        if self.stock >= quantity:
            self.stock -= quantity
            self.save(update_fields=['stock', 'updated_at'])
            return True
        return False
    
    def increase_stock(self, quantity):
        """Increase stock (e.g., order cancellation)"""
        self.stock += quantity
        self.save(update_fields=['stock', 'updated_at'])


class ProductVariant(models.Model):
    """
    Product variants for different sizes, colors, etc.
    """
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='variants',
        db_index=True
    )
    
    # Variant identifiers
    variant_sku = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text=_('Unique SKU for this variant')
    )
    
    # Variant attributes
    size = models.CharField(max_length=50, blank=True)
    color = models.CharField(max_length=50, blank=True)
    
    # Additional attributes (JSON for flexibility)
    attributes = models.JSONField(
        default=dict,
        blank=True,
        help_text=_('Additional variant attributes')
    )
    
    # Pricing (if different from base product)
    price_adjustment = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text=_('Price difference from base product (+ or -)')
    )
    
    # Inventory
    stock = models.PositiveIntegerField(default=0)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'product_variants'
        verbose_name = _('Product Variant')
        verbose_name_plural = _('Product Variants')
        ordering = ['size', 'color']
        unique_together = [['product', 'size', 'color']]
        indexes = [
            models.Index(fields=['product', 'stock']),
            models.Index(fields=['variant_sku']),
        ]
    
    def __str__(self):
        parts = [self.product.title]
        if self.size:
            parts.append(f"Size: {self.size}")
        if self.color:
            parts.append(f"Color: {self.color}")
        return " - ".join(parts)
    
    @property
    def final_price(self):
        """Calculate final price with adjustment"""
        return self.product.price + self.price_adjustment
    
    @property
    def is_in_stock(self):
        """Check if variant is in stock"""
        return self.stock > 0


class ProductImage(models.Model):
    """
    Multiple images for a product.
    """
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='images',
        db_index=True
    )
    
    # Image file
    image = models.ImageField(
        upload_to='products/%Y/%m/',
        help_text=_('Product image')
    )
    
    # Image metadata
    alt_text = models.CharField(
        max_length=255,
        blank=True,
        help_text=_('Alternative text for SEO and accessibility')
    )
    
    # Primary image flag
    is_primary = models.BooleanField(
        default=False,
        db_index=True,
        help_text=_('Main product image')
    )
    
    # Display order
    display_order = models.PositiveIntegerField(
        default=0,
        help_text=_('Display order (lower numbers first)')
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'product_images'
        verbose_name = _('Product Image')
        verbose_name_plural = _('Product Images')
        ordering = ['display_order', 'created_at']
        indexes = [
            models.Index(fields=['product', 'is_primary']),
            models.Index(fields=['product', 'display_order']),
        ]
    
    def __str__(self):
        return f"Image for {self.product.title} {'(Primary)' if self.is_primary else ''}"
    
    def save(self, *args, **kwargs):
        # Auto-set alt text from product title if not provided
        if not self.alt_text:
            self.alt_text = f"{self.product.title} - Product Image"
        
        # If this is set as primary, unset other primary images
        if self.is_primary:
            ProductImage.objects.filter(
                product=self.product,
                is_primary=True
            ).exclude(pk=self.pk).update(is_primary=False)
        
        super().save(*args, **kwargs)

