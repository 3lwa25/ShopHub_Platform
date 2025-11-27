"""Utility helpers for the orders app."""
from decimal import Decimal
from collections import defaultdict
from io import BytesIO
import textwrap

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.core.files.base import ContentFile

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors

from apps.orders.models import Order, OrderItem, Invoice
from apps.cart.models import Cart
from apps.common.notifications import (
    notify_buyer_order_confirmation,
    notify_seller_order_received,
    notify_invoice_available,
)


def get_cart_for_request(request):
    """Helper to fetch the current cart for the request."""
    if request.user.is_authenticated:
        return Cart.objects.filter(user=request.user).prefetch_related('items__product').first()

    if not request.session.session_key:
        request.session.create()
    session_key = request.session.session_key
    return Cart.objects.filter(session_key=session_key).prefetch_related('items__product').first()


def group_cart_items_by_seller(cart):
    """
    Group cart items by seller profile.
    Returns a dict {seller_profile: [cart_items]}.
    """
    items_by_seller = defaultdict(list)
    for item in cart.items.select_related('product__seller'):
        seller = item.product.seller
        items_by_seller[seller].append(item)
    return items_by_seller


@transaction.atomic
def create_orders_from_cart(request, cart, checkout_data):
    """
    Create order(s) from cart items and return the list of created orders.
    checkout_data should include:
        - shipping_address dict
        - payment_method
        - customer_notes
    """
    orders_created = []
    items_by_seller = group_cart_items_by_seller(cart)

    for seller_profile, cart_items in items_by_seller.items():
        order_total = Decimal('0.00')

        order = Order.objects.create(
            buyer=request.user if request.user.is_authenticated else None,
            total_amount=Decimal('0.00'),  # updated later
            shipping_address=checkout_data['shipping_address'],
            payment_method=checkout_data['payment_method'],
            payment_status=checkout_data['payment_status'],
            customer_notes=checkout_data.get('customer_notes', '')
        )

        for cart_item in cart_items:
            product = cart_item.product
            unit_price = product.price
            subtotal = unit_price * cart_item.quantity
            order_total += subtotal

            OrderItem.objects.create(
                order=order,
                product=product,
                variant=None,  # Variants not stored in cart currently
                seller=seller_profile,
                product_name=product.title,
                product_sku=product.sku,
                unit_price=unit_price,
                quantity=cart_item.quantity
            )

            # Reduce stock
            product.stock = max(0, product.stock - cart_item.quantity)
            product.save(update_fields=['stock'])

        # Apply coupon if provided
        coupon_code = checkout_data.get('coupon_code', '').strip()
        discount_amount = Decimal('0.00')
        applied_coupon = None
        
        if coupon_code:
            try:
                from .coupon_models import Coupon, CouponUsage
                applied_coupon = Coupon.objects.get(code__iexact=coupon_code, is_active=True)
                
                # Validate coupon
                is_valid, error_msg = applied_coupon.is_valid(user=request.user if request.user.is_authenticated else None)
                if is_valid and applied_coupon.can_apply_to_cart(cart_items):
                    if order_total >= applied_coupon.min_order_value:
                        discount_amount = applied_coupon.calculate_discount(order_total, cart_items)
                        order.coupon_code = applied_coupon.code
                        
                        # Increment coupon usage
                        applied_coupon.increment_usage()
                    else:
                        applied_coupon = None
                else:
                    applied_coupon = None
            except Coupon.DoesNotExist:
                applied_coupon = None
        
        # Check if reward points are being used
        reward_points_used = bool(request.session.get('rewards_redemption', {}).get('points', 0))
        
        # Calculate shipping and tax
        from .shipping_utils import calculate_shipping_fee, calculate_order_totals
        
        shipping_fee = calculate_shipping_fee(cart_items, applied_coupon, reward_points_used)
        totals = calculate_order_totals(order_total, shipping_fee, discount_amount)
        
        # Calculate final totals
        order.subtotal_amount = totals['subtotal']
        order.discount_amount = totals['discount']
        order.shipping_amount = totals['shipping']
        order.tax_amount = totals['tax']
        order.total_amount = totals['total']
        order.points_earned = order.calculate_points_earned()
        
        # Always set order status to PENDING_PAYMENT initially - seller will approve payment
        order.status = 'PENDING_PAYMENT'
        order.save(update_fields=['subtotal_amount', 'discount_amount', 'shipping_amount', 'tax_amount', 'total_amount', 'coupon_code', 'points_earned', 'status'])
        
        # Record coupon usage if applied
        if applied_coupon and discount_amount > 0:
            CouponUsage.objects.create(
                coupon=applied_coupon,
                user=request.user if request.user.is_authenticated else None,
                order=order,
                discount_amount=discount_amount
            )
        
        orders_created.append(order)

        # Create PaymentTransaction with random data
        from apps.orders.models import PaymentTransaction, ShipmentTracking
        import random
        import string
        
        payment_method = checkout_data['payment_method']
        transaction_id = f"TXN-{order.order_number}-{''.join(random.choices(string.ascii_uppercase + string.digits, k=8))}"
        
        # Generate random transaction data based on payment method
        if payment_method in ['credit_card', 'paypal']:
            # Random card details for credit card
            card_brands = ['Visa', 'Mastercard', 'American Express']
            card_brand = random.choice(card_brands)
            card_last4 = str(random.randint(1000, 9999))
            gateway_name = 'ShopHub Payment Gateway' if payment_method == 'credit_card' else 'PayPal'
            gateway_transaction_id = f"{gateway_name[:3].upper()}-{''.join(random.choices(string.ascii_uppercase + string.digits, k=12))}"
        else:
            # Cash on Delivery
            card_brand = ''
            card_last4 = ''
            gateway_name = ''
            gateway_transaction_id = ''
        
        transaction = PaymentTransaction.objects.create(
            order=order,
            transaction_id=transaction_id,
            payment_method=payment_method,
            amount=order.total_amount,
            currency=order.currency,
            status='pending',  # Always pending until seller approves
            gateway_name=gateway_name,
            gateway_transaction_id=gateway_transaction_id,
            gateway_response={
                'status': 'pending',
                'method': payment_method,
                'created_at': timezone.now().isoformat(),
            },
            card_last4=card_last4,
            card_brand=card_brand,
            ip_address=request.META.get('REMOTE_ADDR', '127.0.0.1') if hasattr(request, 'META') else '127.0.0.1',
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500] if hasattr(request, 'META') else '',
        )
        
        # Generate payment summary
        generate_payment_summary(transaction)
        
        # Ensure invoice exists (initially unpaid)
        create_or_update_invoice(order, mark_paid=False)
        
        ShipmentTracking.objects.create(
            order=order,
            courier_name='Shop Hub Delivery',
            tracking_number=f"{order.order_number}-S{random.randint(1000, 9999)}",
            current_status='ordered',
            history=[],
            estimated_delivery=timezone.now() + timedelta(days=random.randint(2, 5))
        )

    # Clear cart
    cart.items.all().delete()

    return orders_created


def send_order_confirmation_emails(orders):
    """Trigger email notifications for orders and involved sellers."""
    if not orders:
        return

    from apps.common.notifications import notify_buyer_order_confirmation, notify_seller_order_received
    
    notified_buyers = set()
    for order in orders:
        if order.buyer and order.buyer.email and order.buyer.email not in notified_buyers:
            notify_buyer_order_confirmation(order)
            notified_buyers.add(order.buyer.email)

        seller_users = (
            order.items.select_related('seller__user')
            .values_list('seller__user', flat=True)
            .distinct()
        )
        from apps.accounts.models import User  # imported lazily to avoid circular import

        for seller_user_id in seller_users:
            try:
                seller_user = User.objects.get(pk=seller_user_id)
            except User.DoesNotExist:
                continue
            notify_seller_order_received(order, seller_user)


def generate_invoice_pdf(invoice: Invoice) -> bytes:
    """Generate a branded PDF binary for the invoice."""
    buffer = BytesIO()
    order = invoice.order
    canvas_obj = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    site_url = getattr(settings, 'SITE_URL', 'https://shophub.ai')
    support_email = getattr(settings, 'SUPPORT_EMAIL', getattr(settings, 'DEFAULT_FROM_EMAIL', 'support@shophub.com'))

    y = height - 60
    canvas_obj.setFillColor(colors.HexColor("#1d4ed8"))
    canvas_obj.setFont("Helvetica-Bold", 24)
    canvas_obj.drawString(40, y, "ShopHub")
    canvas_obj.setFillColor(colors.black)
    canvas_obj.setFont("Helvetica", 11)
    canvas_obj.drawString(40, y - 18, "AI-Powered Commerce Platform")
    canvas_obj.drawRightString(width - 40, y, f"Invoice #{invoice.invoice_number}")
    canvas_obj.setFont("Helvetica", 10)
    canvas_obj.drawRightString(width - 40, y - 14, site_url)
    canvas_obj.drawRightString(width - 40, y - 28, support_email)
    canvas_obj.setStrokeColor(colors.HexColor("#1d4ed8"))
    canvas_obj.line(40, y - 36, width - 40, y - 36)
    y -= 60

    canvas_obj.setFont("Helvetica-Bold", 12)
    canvas_obj.drawString(40, y, "Invoice Details")
    canvas_obj.setFont("Helvetica", 10)
    canvas_obj.drawString(40, y - 15, f"Order Number: {order.order_number}")
    canvas_obj.drawString(40, y - 30, f"Issue Date : {invoice.issue_date.strftime('%Y-%m-%d')}")
    if invoice.paid_at:
        canvas_obj.drawString(40, y - 45, f"Paid At     : {invoice.paid_at.strftime('%Y-%m-%d %H:%M')}")
    y -= 70

    shipping = order.shipping_address or {}
    canvas_obj.setFont("Helvetica-Bold", 11)
    canvas_obj.drawString(40, y, "Billing & Shipping")
    canvas_obj.setFont("Helvetica", 10)
    address_lines = [
        shipping.get('full_name') or '',
        shipping.get('address_line1') or '',
        shipping.get('address_line2') or '',
        f"{shipping.get('city', '')}, {shipping.get('state', '')}",
        f"{shipping.get('country', '')} {shipping.get('postal_code', '')}",
        f"Phone: {shipping.get('phone', '-')}",
        f"Email: {order.buyer.email if order.buyer else '-'}",
    ]
    draw_y = y - 18
    for line in address_lines:
        if line.strip():
            canvas_obj.drawString(40, draw_y, line.strip())
            draw_y -= 14
    y = draw_y - 10

    canvas_obj.setFont("Helvetica-Bold", 12)
    canvas_obj.drawString(40, y, "Items")
    y -= 18

    header_y = y
    canvas_obj.setFont("Helvetica-Bold", 10)
    canvas_obj.drawString(40, header_y, "Item")
    canvas_obj.drawString(300, header_y, "Qty")
    canvas_obj.drawString(360, header_y, "Unit Price")
    canvas_obj.drawRightString(width - 40, header_y, "Subtotal")
    canvas_obj.line(40, header_y - 4, width - 40, header_y - 4)
    y = header_y - 20
    canvas_obj.setFont("Helvetica", 10)

    for item in order.items.all():
        if y < 140:
            canvas_obj.showPage()
            canvas_obj.setFont("Helvetica-Bold", 10)
            canvas_obj.drawString(40, height - 60, "Items (contd.)")
            canvas_obj.line(40, height - 64, width - 40, height - 64)
            canvas_obj.setFont("Helvetica", 10)
            y = height - 90

        name_lines = textwrap.wrap(item.product_name or '', width=45) or [item.product_name]
        first_line = True
        for line in name_lines:
            canvas_obj.drawString(40, y, line)
            if first_line:
                canvas_obj.drawRightString(330, y, str(item.quantity))
                canvas_obj.drawRightString(410, y, f"EGP {item.unit_price:.2f}")
                canvas_obj.drawRightString(width - 40, y, f"EGP {item.subtotal:.2f}")
                first_line = False
            y -= 14
        y -= 2

    y -= 6
    canvas_obj.line(40, y, width - 40, y)
    y -= 18
    canvas_obj.setFont("Helvetica", 10)
    canvas_obj.drawRightString(width - 40, y, f"Subtotal: EGP {invoice.subtotal:.2f}")
    y -= 14
    if invoice.discount_amount > 0:
        canvas_obj.drawRightString(width - 40, y, f"Discount: -EGP {invoice.discount_amount:.2f}")
        y -= 14
    canvas_obj.drawRightString(width - 40, y, f"Shipping: EGP {invoice.shipping_amount:.2f}")
    y -= 14
    canvas_obj.drawRightString(width - 40, y, f"Tax (2.5%): EGP {invoice.tax_amount:.2f}")
    y -= 18
    canvas_obj.setFont("Helvetica-Bold", 12)
    canvas_obj.drawRightString(width - 40, y, f"Total Due: EGP {invoice.total_amount:.2f}")
    y -= 30

    warranty_text = (
        "Warranty: ShopHub covers manufacturing defects for 12 months from the delivery date unless a product page "
        "states a different warranty window. Keep this invoice and contact support if you need assistance."
    )
    canvas_obj.setFont("Helvetica-Bold", 11)
    canvas_obj.drawString(40, y, "Warranty & Support")
    y -= 16
    canvas_obj.setFont("Helvetica", 9)
    for line in textwrap.wrap(warranty_text, width=90):
        canvas_obj.drawString(40, y, line)
        y -= 12

    y -= 10
    canvas_obj.setFont("Helvetica-Oblique", 9)
    canvas_obj.drawString(40, y, "Thank you for shopping with ShopHub. Visit us anytime for AI-curated deals.")
    canvas_obj.drawRightString(width - 40, y, site_url)

    canvas_obj.showPage()
    canvas_obj.save()

    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


def create_or_update_invoice(order: Order, mark_paid: bool = False) -> Invoice:
    """Create or refresh invoice details for an order."""
    # Use order's calculated amounts
    defaults = {
        'subtotal': order.subtotal_amount,
        'discount_amount': order.discount_amount,
        'shipping_amount': getattr(order, 'shipping_amount', Decimal('0.00')),
        'tax_amount': getattr(order, 'tax_amount', Decimal('0.00')),
        'total_amount': order.total_amount,
        'is_paid': mark_paid,
        'paid_at': timezone.now() if mark_paid else None,
    }
    invoice, created = Invoice.objects.get_or_create(order=order, defaults=defaults)

    if not created:
        invoice.subtotal = order.subtotal_amount
        invoice.discount_amount = order.discount_amount
        invoice.shipping_amount = getattr(order, 'shipping_amount', Decimal('0.00'))
        invoice.tax_amount = getattr(order, 'tax_amount', Decimal('0.00'))
        invoice.total_amount = order.total_amount
        if mark_paid and not invoice.is_paid:
            invoice.is_paid = True
            invoice.paid_at = timezone.now()

    pdf_content = generate_invoice_pdf(invoice)
    invoice.pdf_file.save(f"{invoice.invoice_number}.pdf", ContentFile(pdf_content), save=False)
    invoice.save()

    if mark_paid:
        notify_invoice_available(order, invoice, attachments=[(f"{invoice.invoice_number}.pdf", pdf_content, "application/pdf")])

    return invoice, pdf_content


import random
from datetime import timedelta


def generate_tracking_sequence(order):
    """Generate tracking sequence in proper order: Ordered -> Confirmed -> On Pack -> Dispatched -> Out to Delivery -> Delivered."""
    from apps.orders.models import ShipmentTracking
    
    # Proper sequence - always in this order
    statuses = ['ordered', 'confirmed', 'on_pack', 'dispatched', 'out_to_delivery', 'delivered']
    
    current_time = timezone.now()
    sequence = []
    
    for i, status in enumerate(statuses):
        # Time intervals: ordered (0), confirmed (1-2h), on_pack (2-4h), dispatched (4-8h), out_to_delivery (8-12h), delivered (12-24h)
        if i == 0:
            # Ordered - start immediately
            hours = 0
        elif i == 1:
            # Confirmed - 1-2 hours after ordered
            hours = random.randint(1, 2)
        elif i == 2:
            # On Pack - 2-4 hours after confirmed
            hours = random.randint(2, 4)
        elif i == 3:
            # Dispatched - 4-8 hours after on pack
            hours = random.randint(4, 8)
        elif i == 4:
            # Out to Delivery - 8-12 hours after dispatched
            hours = random.randint(8, 12)
        else:
            # Delivered - 12-24 hours after out to delivery
            hours = random.randint(12, 24)
        
        current_time += timedelta(hours=hours)
        
        location = get_random_location(status)
        
        sequence.append({
            'status': status,
            'timestamp': current_time.isoformat(),
            'location': location
        })
    
    return sequence


def get_random_location(status):
    """Get random location based on status."""
    locations = {
        'ordered': ['Warehouse', 'Distribution Center', 'Fulfillment Center'],
        'confirmed': ['Processing Center', 'Fulfillment Center', 'Order Processing'],
        'on_pack': ['Packing Station', 'Warehouse', 'Packing Center'],
        'dispatched': ['Shipping Hub', 'Distribution Center', 'Transit Hub'],
        'out_to_delivery': ['Local Delivery Center', 'Courier Station', 'Delivery Hub'],
        'delivered': ['Customer Address', 'Delivery Point', 'Final Destination']
    }
    return random.choice(locations.get(status, ['Unknown Location']))


def generate_payment_summary(transaction):
    """Generate random payment summary with fees."""
    from decimal import Decimal
    
    amount = transaction.amount
    
    # Random platform fee: 2-5%
    platform_fee_percent = Decimal(str(random.uniform(0.02, 0.05)))
    platform_fee = amount * platform_fee_percent
    
    # Random processing fee: 1-3%
    processing_fee_percent = Decimal(str(random.uniform(0.01, 0.03)))
    processing_fee = amount * processing_fee_percent
    
    net_amount = amount - platform_fee - processing_fee
    
    summary = {
        'gross_amount': float(amount),
        'platform_fee': float(platform_fee),
        'platform_fee_percent': round(float(platform_fee_percent * 100), 2),
        'processing_fee': float(processing_fee),
        'processing_fee_percent': round(float(processing_fee_percent * 100), 2),
        'net_amount': float(net_amount),
        'currency': transaction.currency,
    }
    
    transaction.platform_fee = platform_fee
    transaction.processing_fee = processing_fee
    transaction.net_amount = net_amount
    transaction.payment_summary = summary
    transaction.save()
    
    return summary