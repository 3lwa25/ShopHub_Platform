"""
Shipping and Tax Calculation Utilities
"""
from decimal import Decimal
from django.conf import settings


# Shipping fee range (EGP)
SHIPPING_FEE_MIN = Decimal('10.00')
SHIPPING_FEE_MAX = Decimal('50.00')

# Tax rate (2.5%)
TAX_RATE = Decimal('0.025')


def calculate_shipping_fee(cart_items, applied_coupon=None, reward_points_used=False):
    """
    Calculate shipping fee for cart items.
    
    Rules:
    - Base shipping: 10-50 EGP (based on cart total)
    - Free shipping if:
      * Any product has high sale (discount >= 30%)
      * Any product is a best seller
      * Using reward points redemption
      * Coupon type is 'free_shipping'
    
    Args:
        cart_items: QuerySet or list of CartItem objects
        applied_coupon: Coupon object if applied
        reward_points_used: Boolean if reward points are being used
    
    Returns:
        Decimal: Shipping fee (0.00 if free shipping applies)
    """
    if not cart_items:
        return Decimal('0.00')
    
    # Check for free shipping conditions
    has_free_shipping = False
    
    # Check if coupon provides free shipping
    if applied_coupon and applied_coupon.discount_type == 'free_shipping':
        has_free_shipping = True
    
    # Check if reward points are being used (free shipping benefit)
    if reward_points_used:
        has_free_shipping = True
    
    # Check products for high sale or best seller
    if not has_free_shipping:
        for item in cart_items:
            product = item.product
            # High sale: discount >= 30%
            if product.is_on_sale and product.discount_percentage >= 30:
                has_free_shipping = True
                break
            # Best seller
            if hasattr(product, 'is_best_seller') and product.is_best_seller:
                has_free_shipping = True
                break
    
    if has_free_shipping:
        return Decimal('0.00')
    
    # Calculate base shipping based on cart total
    cart_total = sum(item.subtotal for item in cart_items)
    
    # Shipping fee scales with cart total
    # Small orders (0-100 EGP): 50 EGP
    # Medium orders (100-500 EGP): 30 EGP
    # Large orders (500+ EGP): 10 EGP
    if cart_total < Decimal('100.00'):
        shipping_fee = SHIPPING_FEE_MAX
    elif cart_total < Decimal('500.00'):
        shipping_fee = Decimal('30.00')
    else:
        shipping_fee = SHIPPING_FEE_MIN
    
    return shipping_fee


def calculate_tax(subtotal, shipping_fee=Decimal('0.00')):
    """
    Calculate tax (2.5%) on subtotal + shipping.
    
    Args:
        subtotal: Decimal - Subtotal before tax
        shipping_fee: Decimal - Shipping fee
    
    Returns:
        Decimal: Tax amount
    """
    taxable_amount = subtotal + shipping_fee
    tax_amount = taxable_amount * TAX_RATE
    return tax_amount.quantize(Decimal('0.01'))


def calculate_order_totals(subtotal, shipping_fee, discount_amount=Decimal('0.00')):
    """
    Calculate all order totals including tax.
    
    Args:
        subtotal: Decimal - Subtotal before discounts
        shipping_fee: Decimal - Shipping fee
        discount_amount: Decimal - Discount amount
    
    Returns:
        dict: {
            'subtotal': Decimal,
            'discount': Decimal,
            'shipping': Decimal,
            'tax': Decimal,
            'total': Decimal
        }
    """
    # Apply discount to subtotal
    subtotal_after_discount = max(Decimal('0.00'), subtotal - discount_amount)
    
    # Calculate tax on (subtotal_after_discount + shipping)
    tax_amount = calculate_tax(subtotal_after_discount, shipping_fee)
    
    # Total = subtotal_after_discount + shipping + tax
    total = subtotal_after_discount + shipping_fee + tax_amount
    
    return {
        'subtotal': subtotal,
        'discount': discount_amount,
        'shipping': shipping_fee,
        'tax': tax_amount,
        'total': total.quantize(Decimal('0.01'))
    }

