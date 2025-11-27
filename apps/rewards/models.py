"""
Rewards System Models for Shop Hub
"""
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.utils import timezone
from apps.orders.models import Order
from apps.products.models import Product


class RewardAccount(models.Model):
    """
    Reward points account for buyers.
    Tracks points balance and lifetime statistics.
    """
    # One-to-one relationship with User (buyer only)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reward_account',
        primary_key=True
    )
    
    # Current points balance
    points_balance = models.IntegerField(
        default=0,
        help_text=_('Current available points')
    )
    
    # Lifetime statistics
    total_earned = models.IntegerField(
        default=0,
        help_text=_('Total points earned (lifetime)')
    )
    total_spent = models.IntegerField(
        default=0,
        help_text=_('Total points redeemed (lifetime)')
    )
    
    # Tier/Level (optional for gamification)
    tier = models.CharField(
        max_length=20,
        default='bronze',
        choices=[
            ('bronze', 'Bronze'),
            ('silver', 'Silver'),
            ('gold', 'Gold'),
            ('platinum', 'Platinum'),
        ],
        help_text=_('Reward tier based on activity')
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'reward_accounts'
        verbose_name = _('Reward Account')
        verbose_name_plural = _('Reward Accounts')
    
    def __str__(self):
        return f"{self.user.email} - {self.points_balance} points"
    
    def add_points(self, amount, transaction_type, order=None, description=''):
        """
        Add points to account and create transaction record.
        
        Args:
            amount (int): Points to add
            transaction_type (str): Type of transaction
            order (Order): Related order if applicable
            description (str): Transaction description
        """
        self.points_balance += amount
        self.total_earned += amount
        self.save(update_fields=['points_balance', 'total_earned', 'updated_at'])
        
        # Create transaction record
        PointsTransaction.objects.create(
            user=self.user,
            order=order,
            transaction_type=transaction_type,
            amount=amount,
            balance_after=self.points_balance,
            description=description
        )
        
        # Update tier based on total earned
        self.update_tier()
    
    def redeem_points(self, amount, order=None, description=''):
        """
        Redeem points from account.
        
        Args:
            amount (int): Points to redeem
            order (Order): Related order if applicable
            description (str): Transaction description
        
        Returns:
            bool: True if successful, False if insufficient balance
        """
        if self.points_balance < amount:
            return False
        
        self.points_balance -= amount
        self.total_spent += amount
        self.save(update_fields=['points_balance', 'total_spent', 'updated_at'])
        
        # Create transaction record
        PointsTransaction.objects.create(
            user=self.user,
            order=order,
            transaction_type='redeemed',
            amount=-amount,  # Negative for redemption
            balance_after=self.points_balance,
            description=description
        )
        
        return True
    
    def update_tier(self):
        """Update user tier based on total earned points"""
        old_tier = self.tier
        
        if self.total_earned >= 10000:
            new_tier = 'platinum'
        elif self.total_earned >= 5000:
            new_tier = 'gold'
        elif self.total_earned >= 2000:
            new_tier = 'silver'
        else:
            new_tier = 'bronze'
        
        if self.tier != new_tier:
            self.tier = new_tier
            self.save(update_fields=['tier', 'updated_at'])
            
            # Send tier upgrade notification
            try:
                from apps.rewards.views import send_tier_upgrade_email
                send_tier_upgrade_email(self.user, old_tier, new_tier)
            except Exception as e:
                print(f"Error sending tier upgrade notification: {e}")
    
    @property
    def points_value_egp(self):
        """
        Calculate monetary value of current points balance in EGP.
        Based on settings.POINTS_TO_DOLLAR_RATIO
        """
        from django.conf import settings
        ratio = getattr(settings, 'POINTS_TO_DOLLAR_RATIO', 0.01)
        # Convert to EGP (assuming 1 USD = 30 EGP)
        return round(self.points_balance * ratio * 30, 2)


class PointsTransaction(models.Model):
    """
    Transaction history for reward points.
    Tracks all points earned, redeemed, and adjustments.
    """
    TRANSACTION_TYPES = [
        ('earned', 'Points Earned'),
        ('redeemed', 'Points Redeemed'),
        ('bonus', 'Bonus Points'),
        ('referral', 'Referral Bonus'),
        ('expired', 'Points Expired'),
        ('adjustment', 'Manual Adjustment'),
    ]
    
    # User
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='points_transactions',
        db_index=True
    )
    
    # Related order (if applicable)
    order = models.ForeignKey(
        Order,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='points_transactions'
    )
    
    # Transaction details
    transaction_type = models.CharField(
        max_length=20,
        choices=TRANSACTION_TYPES,
        db_index=True
    )
    
    # Amount (positive for earning, negative for redemption)
    amount = models.IntegerField(
        help_text=_('Points amount (+ for earned, - for redeemed)')
    )
    
    # Balance after this transaction
    balance_after = models.IntegerField(
        help_text=_('Points balance after this transaction')
    )
    
    # Description
    description = models.CharField(
        max_length=500,
        blank=True,
        help_text=_('Transaction description')
    )
    
    # Expiration (optional)
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_('When these points expire (if applicable)')
    )
    
    # Timestamp
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        db_table = 'points_transactions'
        verbose_name = _('Points Transaction')
        verbose_name_plural = _('Points Transactions')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['transaction_type']),
            models.Index(fields=['order']),
        ]
    
    def __str__(self):
        sign = '+' if self.amount >= 0 else ''
        return f"{self.user.email} - {sign}{self.amount} pts ({self.get_transaction_type_display()})"
    
    @property
    def is_earning(self):
        """Check if this is a points earning transaction"""
        return self.amount > 0
    
    @property
    def is_redemption(self):
        """Check if this is a points redemption transaction"""
        return self.amount < 0


class Reward(models.Model):
    """
    Admin-manageable rewards that users can redeem
    """
    REWARD_TYPES = [
        ('discount_voucher', 'Discount Voucher'),
        ('free_shipping', 'Free Shipping'),
        ('free_product', 'Free Product'),
        ('vip_service', 'VIP Service'),
        ('charity', 'Charity Donation'),
        ('early_access', 'Early Access'),
        ('custom', 'Custom Reward'),
    ]
    
    name = models.CharField(
        max_length=200,
        help_text=_('Reward name (e.g., "50 EGP Discount Voucher")')
    )
    
    description = models.TextField(
        help_text=_('Detailed description of the reward')
    )
    
    reward_type = models.CharField(
        max_length=50,
        choices=REWARD_TYPES,
        default='discount_voucher'
    )
    
    points_required = models.PositiveIntegerField(
        help_text=_('Points required to redeem this reward')
    )
    
    # Optional: Discount amount for voucher rewards
    discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_('Discount amount in EGP (for voucher rewards)')
    )
    
    # Optional: Free product
    free_product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reward_products',
        help_text=_('Product to give for free (for product rewards)')
    )
    
    # Optional: Charity name
    charity_name = models.CharField(
        max_length=200,
        blank=True,
        help_text=_('Charity organization name (for charity donations)')
    )
    
    icon = models.CharField(
        max_length=50,
        default='gift',
        help_text=_('Font Awesome icon name (without fa- prefix)')
    )
    
    is_active = models.BooleanField(
        default=True,
        help_text=_('Whether this reward is currently available')
    )
    
    is_limited_time = models.BooleanField(
        default=False,
        help_text=_('Whether this is a limited-time reward')
    )
    
    start_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_('When this reward becomes available')
    )
    
    end_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_('When this reward expires')
    )
    
    max_redemptions = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=_('Maximum number of times this can be redeemed (total)')
    )
    
    redemption_count = models.PositiveIntegerField(
        default=0,
        help_text=_('Number of times this reward has been redeemed')
    )
    
    tier_required = models.CharField(
        max_length=20,
        choices=[
            ('bronze', 'Bronze'),
            ('silver', 'Silver'),
            ('gold', 'Gold'),
            ('platinum', 'Platinum'),
        ],
        default='bronze',
        help_text=_('Minimum tier required to redeem')
    )
    
    display_order = models.PositiveIntegerField(
        default=0,
        help_text=_('Display order (lower numbers appear first)')
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'rewards'
        verbose_name = _('Reward')
        verbose_name_plural = _('Rewards')
        ordering = ['display_order', 'points_required']
        indexes = [
            models.Index(fields=['is_active', 'display_order']),
            models.Index(fields=['reward_type']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.points_required} pts)"
    
    def is_available(self, user=None):
        """Check if reward is currently available"""
        if not self.is_active:
            return False
        
        # Check date range
        now = timezone.now()
        if self.start_date and now < self.start_date:
            return False
        if self.end_date and now > self.end_date:
            return False
        
        # Check max redemptions
        if self.max_redemptions and self.redemption_count >= self.max_redemptions:
            return False
        
        # Check tier requirement
        if user and hasattr(user, 'reward_account'):
            reward_account = user.reward_account
            tier_order = {'bronze': 0, 'silver': 1, 'gold': 2, 'platinum': 3}
            if tier_order.get(reward_account.tier, 0) < tier_order.get(self.tier_required, 0):
                return False
        
        return True
    
    def can_redeem(self, user):
        """Check if specific user can redeem this reward"""
        if not self.is_available(user):
            return False
        
        # Check if user has enough points
        if hasattr(user, 'reward_account'):
            return user.reward_account.points_balance >= self.points_required
        
        return False


class RewardRedemption(models.Model):
    """
    Track reward redemptions
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired'),
    ]
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reward_redemptions',
        db_index=True
    )
    
    reward = models.ForeignKey(
        Reward,
        on_delete=models.CASCADE,
        related_name='redemptions'
    )
    
    points_spent = models.PositiveIntegerField(
        help_text=_('Points spent on this redemption')
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True
    )
    
    # Generated coupon code (if applicable)
    coupon_code = models.CharField(
        max_length=50,
        blank=True,
        help_text=_('Generated coupon code for this redemption')
    )
    
    # Additional data (JSON)
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text=_('Additional metadata for this redemption')
    )
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'reward_redemptions'
        verbose_name = _('Reward Redemption')
        verbose_name_plural = _('Reward Redemptions')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['reward']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.reward.name} ({self.status})"


class PointsGift(models.Model):
    """
    Track points gifted between users
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('rejected', 'Rejected'),
    ]
    
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='points_gifts_sent',
        db_index=True
    )
    
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='points_gifts_received',
        db_index=True
    )
    
    amount = models.PositiveIntegerField(
        help_text=_('Number of points to gift')
    )
    
    message = models.TextField(
        blank=True,
        help_text=_('Optional message to recipient')
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True
    )
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'points_gifts'
        verbose_name = _('Points Gift')
        verbose_name_plural = _('Points Gifts')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['sender', '-created_at']),
            models.Index(fields=['recipient', 'status']),
        ]
    
    def __str__(self):
        return f"{self.sender.email} → {self.recipient.email}: {self.amount} pts"
    
    def process(self):
        """Process the gift transfer"""
        if self.status != 'pending':
            return False
        
        # Check sender balance
        sender_account = RewardAccount.objects.get(user=self.sender)
        if sender_account.points_balance < self.amount:
            self.status = 'cancelled'
            self.save()
            return False
        
        # Get or create recipient account
        recipient_account, _ = RewardAccount.objects.get_or_create(
            user=self.recipient,
            defaults={'points_balance': 0}
        )
        
        # Transfer points
        sender_account.redeem_points(
            amount=self.amount,
            description=f'Gift to {self.recipient.email}'
        )
        
        recipient_account.add_points(
            amount=self.amount,
            transaction_type='bonus',
            description=f'Gift from {self.sender.email}'
        )
        
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save()
        
        return True


class DailyLoginReward(models.Model):
    """
    Track daily login rewards for users
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='daily_login_rewards',
        db_index=True
    )
    
    login_date = models.DateField(
        db_index=True,
        help_text=_('Date of login')
    )
    
    points_earned = models.PositiveIntegerField(
        default=10,
        help_text=_('Points earned for this login')
    )
    
    streak_day = models.PositiveIntegerField(
        default=1,
        help_text=_('Current streak day (1-7+)')
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'daily_login_rewards'
        verbose_name = _('Daily Login Reward')
        verbose_name_plural = _('Daily Login Rewards')
        ordering = ['-login_date']
        unique_together = ['user', 'login_date']
        indexes = [
            models.Index(fields=['user', '-login_date']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.login_date} (Streak: {self.streak_day})"


from apps.notifications.models import Notification as CoreNotification


class Notification(CoreNotification):
    """
    Proxy to the global notifications model so legacy rewards code keeps working.
    """

    class Meta:
        proxy = True
        app_label = 'rewards'
        verbose_name = _('Notification')
        verbose_name_plural = _('Notifications')

