"""Utility helpers for the orders app."""
from decimal import Decimal
from collections import defaultdict
from io import BytesIO

from django.db import transaction
from django.utils import timezone
from django.core.files.base import ContentFile

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

from apps.orders.models import Order, OrderItem, Invoice
from apps.cart.models import Cart
from apps.common.notifications import (
    notify_order_confirmation,
    notify_seller_new_order,
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
        
        # Calculate final totals
        order.subtotal_amount = order_total
        order.discount_amount = discount_amount
        order.total_amount = max(Decimal('0.00'), order_total - discount_amount)
        order.points_earned = order.calculate_points_earned()
        
        if checkout_data['payment_status'] == 'completed':
            order.status = 'PAID'
        elif checkout_data['payment_status'] == 'pending':
            order.status = 'PENDING_PAYMENT'
        order.save(update_fields=['subtotal_amount', 'discount_amount', 'total_amount', 'coupon_code', 'points_earned', 'status'])
        
        # Record coupon usage if applied
        if applied_coupon and discount_amount > 0:
            CouponUsage.objects.create(
                coupon=applied_coupon,
                user=request.user if request.user.is_authenticated else None,
                order=order,
                discount_amount=discount_amount
            )
        
        orders_created.append(order)

        # Ensure invoice exists (initially unpaid)
        create_or_update_invoice(order, mark_paid=checkout_data['payment_status'] == 'completed')
        
        # Create tracking sequence
        from apps.orders.models import ShipmentTracking
        import random
        tracking_sequence = generate_tracking_sequence(order)
        ShipmentTracking.objects.create(
            order=order,
            courier_name='Shop Hub Delivery',
            tracking_number=f"{order.order_number}-S{random.randint(1000, 9999)}",
            current_status='ordered',
            history=tracking_sequence,
            estimated_delivery=timezone.now() + timedelta(days=random.randint(2, 5))
        )
        
        # Generate payment summary if transaction exists
        transaction = order.payment_transactions.first()
        if transaction:
            generate_payment_summary(transaction)

    # Clear cart
    cart.items.all().delete()

    return orders_created


def send_order_confirmation_emails(orders):
    """Trigger email notifications for orders and involved sellers."""
    if not orders:
        return

    notified_buyers = set()
    for order in orders:
        if order.buyer and order.buyer.email and order.buyer.email not in notified_buyers:
            notify_order_confirmation(order)
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
    """Generate a PDF binary for the invoice."""
    buffer = BytesIO()
    order = invoice.order
    canvas_obj = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    y = height - 50
    canvas_obj.setFont("Helvetica-Bold", 16)
    canvas_obj.drawString(40, y, f"Invoice {invoice.invoice_number}")
    y -= 30

    canvas_obj.setFont("Helvetica", 11)
    canvas_obj.drawString(40, y, f"Order Number: {order.order_number}")
    y -= 18
    canvas_obj.drawString(40, y, f"Issue Date: {invoice.issue_date.strftime('%Y-%m-%d')}")
    y -= 18
    if invoice.paid_at:
        canvas_obj.drawString(40, y, f"Paid At: {invoice.paid_at.strftime('%Y-%m-%d %H:%M')}")
        y -= 18

    canvas_obj.drawString(40, y, f"Billing To: {order.shipping_address.get('full_name', '')}")
    y -= 18
    canvas_obj.drawString(40, y, f"Email: {order.buyer.email if order.buyer else '-'}")
    y -= 30

    canvas_obj.setFont("Helvetica-Bold", 12)
    canvas_obj.drawString(40, y, "Items")
    y -= 20
    canvas_obj.setFont("Helvetica", 10)

    for item in order.items.all():
        if y < 100:
            canvas_obj.showPage()
            y = height - 50
            canvas_obj.setFont("Helvetica-Bold", 12)
            canvas_obj.drawString(40, y, "Items (contd.)")
            y -= 20
            canvas_obj.setFont("Helvetica", 10)

        canvas_obj.drawString(40, y, f"{item.product_name} (x{item.quantity})")
        canvas_obj.drawRightString(width - 40, y, f"EGP {item.subtotal:.2f}")
        y -= 16

    y -= 20
    canvas_obj.setFont("Helvetica-Bold", 11)
    canvas_obj.drawRightString(width - 40, y, f"Subtotal: EGP {invoice.subtotal:.2f}")
    y -= 16
    canvas_obj.drawRightString(width - 40, y, f"Tax: EGP {invoice.tax_amount:.2f}")
    y -= 16
    canvas_obj.drawRightString(width - 40, y, f"Shipping: EGP {invoice.shipping_amount:.2f}")
    y -= 16
    canvas_obj.drawRightString(width - 40, y, f"Discount: -EGP {invoice.discount_amount:.2f}")
    y -= 16
    canvas_obj.drawRightString(width - 40, y, f"Total: EGP {invoice.total_amount:.2f}")
    y -= 30

    canvas_obj.setFont("Helvetica", 9)
    canvas_obj.drawString(40, y, "Thank you for shopping with Shop Hub!")

    canvas_obj.showPage()
    canvas_obj.save()

    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


def create_or_update_invoice(order: Order, mark_paid: bool = False) -> Invoice:
    """Create or refresh invoice details for an order."""
    defaults = {
        'subtotal': order.total_amount,
        'total_amount': order.total_amount,
        'tax_amount': Decimal('0.00'),
        'shipping_amount': Decimal('0.00'),
        'discount_amount': Decimal('0.00'),
        'is_paid': mark_paid,
        'paid_at': timezone.now() if mark_paid else None,
    }
    invoice, created = Invoice.objects.get_or_create(order=order, defaults=defaults)

    if not created:
        invoice.subtotal = order.total_amount
        invoice.total_amount = order.total_amount
        invoice.tax_amount = Decimal('0.00')
        invoice.shipping_amount = Decimal('0.00')
        invoice.discount_amount = Decimal('0.00')
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
    """Generate random tracking sequence with time intervals."""
    from apps.orders.models import ShipmentTracking
    
    statuses = ['ordered', 'confirmed', 'on_pack', 'dispatched', 'out_to_delivery', 'delivered']
    
    current_time = timezone.now()
    sequence = []
    
    for i, status in enumerate(statuses):
        # Random time interval: 1-6 hours for each step
        hours = random.randint(1, 6)
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