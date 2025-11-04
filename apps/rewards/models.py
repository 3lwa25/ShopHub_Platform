"""
Rewards System Models for Shop Hub
"""
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from apps.orders.models import Order


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

