"""Order management views."""
from decimal import Decimal
from datetime import timedelta
import random

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.decorators import not_seller, buyer_required, approved_seller_required
from apps.common.notifications import (
    notify_payment_receipt,
    notify_order_tracking,
    notify_buyer_order_confirmation,
    notify_seller_order_received,
    notify_buyer_shipment_dispatched,
    notify_buyer_out_for_delivery,
    notify_buyer_delivery_confirmation,
    notify_seller_payment_received,
    notify_invoice_available,
)
from apps.orders.forms import (
    CheckoutForm,
    ShipmentForm,
    OrderStatusUpdateForm,
    PaymentMethodForm,
    PaymentDetailsForm,
    RefundRequestForm,
    TrackingStatusUpdateForm,
)
from apps.orders.models import Order, OrderItem, ShipmentTracking, PaymentTransaction, Invoice
from apps.orders.utils import (
    get_cart_for_request,
    create_orders_from_cart,
    send_order_confirmation_emails,
    create_or_update_invoice,
)
from apps.notifications.services import broadcast_payment_approval


def infer_card_brand(card_number: str) -> str:
    digits = card_number.replace(' ', '')
    if not digits:
        return 'Card'
    if digits.startswith('4'):
        return 'Visa'
    if any(digits.startswith(str(prefix)) for prefix in range(51, 56)):
        return 'Mastercard'
    if digits.startswith(('34', '37')):
        return 'American Express'
    if digits.startswith('6'):
        return 'Discover'
    return 'Card'

@not_seller
@login_required
def checkout_view(request):
    """Display checkout form and process orders."""
    cart = get_cart_for_request(request)
    if not cart or cart.items.count() == 0:
        messages.info(request, 'Your cart is empty. Add items before proceeding to checkout.')
        return redirect('cart:cart_view')

    cart_items = cart.items.select_related('product', 'product__seller__user').prefetch_related('product__images')

    if request.method == 'POST':
        form = CheckoutForm(request.POST)
        if form.is_valid():
            # Check if using saved address
            saved_address_id = form.cleaned_data.get('saved_address_id')
            if saved_address_id and request.user.is_authenticated:
                from apps.accounts.models import ShippingAddress
                try:
                    saved_address = ShippingAddress.objects.get(id=saved_address_id, user=request.user)
                    shipping_address = saved_address.to_dict()
                    shipping_address['email'] = request.user.email
                except ShippingAddress.DoesNotExist:
                    # Fall back to form data
                    shipping_address = {
                        'full_name': form.cleaned_data['full_name'],
                        'email': form.cleaned_data['email'],
                        'phone': form.cleaned_data['phone'],
                        'address_line1': form.cleaned_data['address_line1'],
                        'address_line2': form.cleaned_data['address_line2'],
                        'city': form.cleaned_data['city'],
                        'state': form.cleaned_data['state'],
                        'country': form.cleaned_data['country'],
                        'postal_code': form.cleaned_data['postal_code'],
                    }
            else:
                shipping_address = {
                    'full_name': form.cleaned_data['full_name'],
                    'email': form.cleaned_data['email'],
                    'phone': form.cleaned_data['phone'],
                    'address_line1': form.cleaned_data['address_line1'],
                    'address_line2': form.cleaned_data['address_line2'],
                    'city': form.cleaned_data['city'],
                    'state': form.cleaned_data['state'],
                    'country': form.cleaned_data['country'],
                    'postal_code': form.cleaned_data['postal_code'],
                }
            
            # Save shipping address if user is authenticated and wants to save (and not using saved address)
            if request.user.is_authenticated and form.cleaned_data.get('save_address') and not saved_address_id:
                from apps.accounts.models import ShippingAddress
                ShippingAddress.objects.create(
                    user=request.user,
                    full_name=shipping_address['full_name'],
                    phone=shipping_address['phone'],
                    address_line1=shipping_address['address_line1'],
                    address_line2=shipping_address.get('address_line2', ''),
                    city=shipping_address['city'],
                    state=shipping_address.get('state', ''),
                    country=shipping_address['country'],
                    postal_code=shipping_address.get('postal_code', ''),
                    is_default=not ShippingAddress.objects.filter(user=request.user).exists()
                )

            payment_method = form.cleaned_data['payment_method']
            # Always set payment status to pending initially - seller will approve later
            payment_status = 'pending'

            # Get coupon code from session if applied
            coupon_code = request.session.get('applied_coupon_code', '').strip()
            
            checkout_data = {
                'shipping_address': shipping_address,
                'payment_method': payment_method,
                'payment_status': payment_status,
                'customer_notes': form.cleaned_data.get('customer_notes', ''),
                'coupon_code': coupon_code,
            }
            
            # Clear coupon from session after use
            if coupon_code:
                del request.session['applied_coupon_code']

            with transaction.atomic():
                orders = create_orders_from_cart(request, cart, checkout_data)
                send_order_confirmation_emails(orders)

            request.session['recent_order_numbers'] = [order.order_number for order in orders]
            return redirect('orders:checkout_success')
    else:
        initial = {}
        saved_addresses = []
        if request.user.is_authenticated:
            initial['full_name'] = request.user.full_name
            initial['email'] = request.user.email
            # Get saved shipping addresses
            from apps.accounts.models import ShippingAddress
            saved_addresses = ShippingAddress.objects.filter(user=request.user).order_by('-is_default', '-created_at')
            # Pre-fill with default address if exists
            default_address = saved_addresses.filter(is_default=True).first()
            if default_address:
                addr_dict = default_address.to_dict()
                initial.update({
                    'full_name': addr_dict['full_name'],
                    'email': addr_dict['email'],
                    'phone': addr_dict['phone'],
                    'address_line1': addr_dict['address_line1'],
                    'address_line2': addr_dict['address_line2'],
                    'city': addr_dict['city'],
                    'state': addr_dict['state'],
                    'country': addr_dict['country'],
                    'postal_code': addr_dict['postal_code'],
                })
        form = CheckoutForm(initial=initial)

    cart_total = sum((item.subtotal for item in cart_items), Decimal('0.00'))
    
    # Get applied coupon if any
    applied_coupon_code = request.session.get('applied_coupon_code', '')
    applied_coupon = None
    discount_amount = Decimal('0.00')
    
    # Get saved addresses for template
    saved_addresses = []
    if request.user.is_authenticated:
        from apps.accounts.models import ShippingAddress
        saved_addresses = ShippingAddress.objects.filter(user=request.user).order_by('-is_default', '-created_at')
    
    if applied_coupon_code:
        try:
            from apps.orders.coupon_models import Coupon
            applied_coupon = Coupon.objects.get(code__iexact=applied_coupon_code, is_active=True)
            is_valid, _ = applied_coupon.is_valid(user=request.user)
            if is_valid and applied_coupon.can_apply_to_cart(cart_items):
                if cart_total >= applied_coupon.min_order_value:
                    discount_amount = applied_coupon.calculate_discount(cart_total, cart_items)
                else:
                    applied_coupon = None
            else:
                applied_coupon = None
        except:
            applied_coupon = None
    
    final_total = max(Decimal('0.00'), cart_total - discount_amount)

    context = {
        'form': form,
        'cart_items': cart_items,
        'cart_total': cart_total,
        'saved_addresses': saved_addresses,
        'applied_coupon': applied_coupon,
        'discount_amount': discount_amount,
        'final_total': final_total,
    }
    return render(request, 'orders/checkout.html', context)


@login_required
def checkout_success_view(request):
    """Display confirmation after successful checkout."""
    order_numbers = request.session.pop('recent_order_numbers', [])
    if not order_numbers:
        return redirect('orders:buyer_orders')

    orders = Order.objects.filter(order_number__in=order_numbers).prefetch_related('items__product__images')
    context = {'orders': orders}
    return render(request, 'orders/checkout_success.html', context)


@buyer_required
@login_required
def buyer_orders_view(request):
    """List orders for the authenticated buyer."""
    orders = Order.objects.filter(buyer=request.user).prefetch_related('items__product', 'shipments').order_by('-created_at')

    status_filter = request.GET.get('status')
    if status_filter:
        orders = orders.filter(status=status_filter)

    context = {
        'orders': orders,
        'status_filter': status_filter,
        'order_status_choices': Order.STATUS_CHOICES,
    }
    return render(request, 'orders/buyer/order_list.html', context)


@buyer_required
@login_required
def buyer_order_detail_view(request, order_number):
    """Display details for a single order."""
    from apps.reviews.models import Review
    
    # Allow admin users to view any order
    if request.user.is_admin_user:
        order = get_object_or_404(
            Order.objects.prefetch_related('items__product__images', 'items__product__reviews', 'shipments'), 
            order_number=order_number
        )
    else:
        order = get_object_or_404(
            Order.objects.prefetch_related('items__product__images', 'items__product__reviews', 'shipments'), 
            order_number=order_number, 
            buyer=request.user
        )
    
    # Get user reviews for products in this order - attach to items
    if request.user.is_authenticated:
        product_ids = [item.product.id for item in order.items.all() if item.product]
        reviews = Review.objects.filter(buyer=request.user, product_id__in=product_ids)
        review_dict = {review.product_id: review for review in reviews}
        
        # Attach review to each order item
        for item in order.items.all():
            if item.product and item.product.id in review_dict:
                item.user_review = review_dict[item.product.id]
            else:
                item.user_review = None
    
    # Get payment transaction and summary
    transaction = order.payment_transactions.first()
    payment_summary = None
    if transaction and transaction.payment_summary:
        payment_summary = transaction.payment_summary
    elif transaction:
        # Generate payment summary if not exists
        from apps.orders.utils import generate_payment_summary
        payment_summary = generate_payment_summary(transaction)
    
    try:
        invoice = order.invoice
    except Invoice.DoesNotExist:
        invoice = None
    
    context = {
        'order': order,
        'transaction': transaction,
        'payment_summary': payment_summary,
        'invoice': invoice,
    }
    return render(request, 'orders/buyer/order_detail.html', context)


@buyer_required
@login_required
def buyer_order_tracking_view(request, order_number):
    """Show shipment tracking for an order."""
    from apps.orders.models import ShipmentTracking
    
    order = get_object_or_404(Order.objects.prefetch_related('shipments'), order_number=order_number, buyer=request.user)
    
    # Process shipments to organize tracking steps in proper order
    shipments_processed = []
    status_order = ['ordered', 'confirmed', 'on_pack', 'dispatched', 'out_to_delivery', 'delivered']
    
    for shipment in order.shipments.all():
        history_entries = shipment.history if isinstance(shipment.history, list) else []
        seller_updates = [
            event for event in history_entries
            if isinstance(event, dict) and event.get('status') and event.get('updated_by') == 'seller'
        ]
        history_dict = {event.get('status'): event for event in seller_updates}

        shipment_completed = order.status == 'DELIVERED' or shipment.current_status == 'delivered'
        forced_current = 'delivered' if shipment_completed else shipment.current_status
        
        # Build ordered list of tracking steps
        tracking_steps = []
        for status in status_order:
            event = history_dict.get(status)
            is_completed = event is not None
            if shipment_completed and not event:
                event = {
                    'status': status,
                    'timestamp': order.updated_at.isoformat(),
                    'location': shipment.courier_name or 'ShopHub Logistics',
                    'notes': 'Auto-completed because the order is delivered.',
                }
                is_completed = True

            tracking_steps.append({
                'status': status,
                'status_display': status.replace('_', ' ').title(),
                'event': event,
                'is_completed': is_completed,
                'is_current': status == forced_current,
            })
        
        shipments_processed.append({
            'shipment': shipment,
            'tracking_steps': tracking_steps,
            'current_status_display': forced_current.replace('_', ' ').title(),
            'current_status_code': forced_current,
        })
    
    context = {
        'order': order,
        'shipments_processed': shipments_processed,
    }
    return render(request, 'orders/buyer/order_tracking.html', context)


@buyer_required
@login_required
def payment_method_view(request, order_number):
    """Allow buyers to select a payment method."""
    order = get_object_or_404(Order, order_number=order_number, buyer=request.user)
    support_email = getattr(settings, 'SUPPORT_EMAIL', getattr(settings, 'DEFAULT_FROM_EMAIL', 'support@shophub.com'))

    if order.payment_status == 'completed':
        messages.info(request, 'This order has already been paid.')
        return redirect('orders:buyer_order_detail', order_number=order_number)

    if request.method == 'POST':
        form = PaymentMethodForm(request.POST)
        if form.is_valid():
            method = form.cleaned_data['payment_method']
            request.session['pending_payment_method'] = method
            request.session['pending_payment_order'] = order_number

            if method == 'cod':
                import random
                import string
                transaction_id = f"TXN-{order.order_number}-{''.join(random.choices(string.ascii_uppercase + string.digits, k=8))}"
                
                transaction = PaymentTransaction.objects.create(
                    order=order,
                    transaction_id=transaction_id,
                    payment_method=method,
                    amount=order.total_amount,
                    currency=order.currency,
                    status='pending',
                    gateway_name='Cash on Delivery',
                    gateway_response={'timestamp': timezone.now().isoformat()},
                    ip_address=request.META.get('REMOTE_ADDR'),
                    user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
                )
                
                # Generate payment summary
                from apps.orders.utils import generate_payment_summary
                generate_payment_summary(transaction)
                order.payment_method = method
                order.payment_status = 'pending'
                order.status = 'PENDING_PAYMENT'
                order.save(update_fields=['payment_method', 'payment_status', 'status', 'updated_at'])
                invoice, pdf_content = create_or_update_invoice(order, mark_paid=False)
                notify_payment_receipt(
                    order,
                    transaction,
                    attachments=[(f"{invoice.invoice_number}.pdf", pdf_content, "application/pdf")],
                )
                messages.success(request, 'Cash on Delivery selected. Please prepare payment upon delivery.')
                context = {
                    'order': order,
                    'transaction': transaction,
                    'payment_method': method,
                    'status': 'pending',
                    'support_email': support_email,
                }
                return render(request, 'orders/payment/payment_result.html', context)

            return redirect('orders:payment_process', order_number=order_number)
    else:
        initial_method = order.payment_method or request.session.get('pending_payment_method')
        initial_data = {'payment_method': initial_method} if initial_method else None
        form = PaymentMethodForm(initial=initial_data)

    context = {
        'order': order,
        'form': form,
        'support_email': support_email,
    }
    return render(request, 'orders/payment/payment_method.html', context)


@buyer_required
@login_required
def payment_process_view(request, order_number):
    """Simulate payment processing for non-COD methods."""
    order = get_object_or_404(Order, order_number=order_number, buyer=request.user)
    method = request.session.get('pending_payment_method')
    support_email = getattr(settings, 'SUPPORT_EMAIL', getattr(settings, 'DEFAULT_FROM_EMAIL', 'support@shophub.com'))

    if not method or method == 'cod':
        return redirect('orders:payment_method', order_number=order_number)

    if request.method == 'POST':
        form = PaymentDetailsForm(request.POST)
        if form.is_valid():
            card_number = form.cleaned_data['card_number']
            import random
            import string
            transaction_id = f"TXN-{order.order_number}-{''.join(random.choices(string.ascii_uppercase + string.digits, k=8))}"
            
            transaction = PaymentTransaction.objects.create(
                order=order,
                transaction_id=transaction_id,
                payment_method=method,
                amount=order.total_amount,
                currency=order.currency,
                status='pending',  # Pending until seller approves
                gateway_name='ShopHub Sandbox Gateway',
                gateway_transaction_id=f"SIM-{timezone.now().strftime('%Y%m%d%H%M%S')}",
                gateway_response={
                    'status': 'pending',
                    'processed_at': timezone.now().isoformat(),
                },
                card_last4=card_number.replace(' ', '')[-4:],
                card_brand=infer_card_brand(card_number),
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
            )
            
            # Generate payment summary
            from apps.orders.utils import generate_payment_summary
            generate_payment_summary(transaction)

            order.payment_method = method
            order.payment_status = 'completed'
            order.status = 'PAID'
            order.save(update_fields=['payment_method', 'payment_status', 'status', 'updated_at'])

            invoice, pdf_content = create_or_update_invoice(order, mark_paid=True)
            notify_payment_receipt(
                order,
                transaction,
                attachments=[(f"{invoice.invoice_number}.pdf", pdf_content, "application/pdf")],
            )

            request.session.pop('pending_payment_method', None)
            request.session.pop('pending_payment_order', None)

            context = {
                'order': order,
                'transaction': transaction,
                'payment_method': method,
                'status': 'completed',
            }
            return render(request, 'orders/payment/payment_result.html', context)
    else:
        form = PaymentDetailsForm()

    context = {
        'order': order,
        'form': form,
        'payment_method': method,
        'support_email': support_email,
    }
    return render(request, 'orders/payment/payment_process.html', context)


@buyer_required
@login_required
def buyer_payment_history_view(request):
    """Display payment transactions for the buyer."""
    transactions = (
        PaymentTransaction.objects
        .filter(order__buyer=request.user)
        .select_related('order', 'order__buyer')
        .order_by('-created_at')
    )
    context = {'transactions': transactions}
    return render(request, 'orders/payment/payment_history.html', context)


@approved_seller_required
def seller_payment_history_view(request):
    """Display payment transactions relevant to a seller."""
    seller_profile = request.user.seller_profile
    transactions = (
        PaymentTransaction.objects.filter(order__items__seller=seller_profile)
        .select_related('order')
        .order_by('-created_at')
        .distinct()
    )

    transaction_rows = []
    for txn in transactions:
        seller_items = txn.order.items.filter(seller=seller_profile)
        seller_subtotal = sum(item.subtotal for item in seller_items)
        
        # Get or generate payment summary
        payment_summary = None
        if txn.payment_summary:
            payment_summary = txn.payment_summary
        elif txn.status == 'completed':
            # Generate payment summary if not exists
            from apps.orders.utils import generate_payment_summary
            payment_summary = generate_payment_summary(txn)
        
        transaction_rows.append({
            'transaction': txn,
            'seller_subtotal': seller_subtotal,
            'item_count': seller_items.count(),
            'payment_summary': payment_summary,
        })

    context = {
        'transactions': transaction_rows,
        'seller_profile': seller_profile,
    }
    return render(request, 'orders/payment/seller_payment_history.html', context)


@buyer_required
@login_required
def request_refund_view(request, order_number):
    """Placeholder refund request form."""
    order = get_object_or_404(Order, order_number=order_number, buyer=request.user)

    if request.method == 'POST':
        form = RefundRequestForm(request.POST)
        if form.is_valid():
            amount = form.cleaned_data['amount']
            reason = form.cleaned_data['reason']

            note_entry = (
                f"\n[Refund Request - {timezone.now():%Y-%m-%d %H:%M}] "
                f"Amount: EGP {amount} | Reason: {reason}\n"
            )
            order.admin_notes = (order.admin_notes or '') + note_entry
            order.status = 'RETURN_REQUESTED'
            order.save(update_fields=['admin_notes', 'status', 'updated_at'])

            from apps.common.notifications import notify_support_refund_request

            notify_support_refund_request(order, amount, reason)

            messages.success(request, 'Your refund request has been submitted. Our support team will contact you soon.')
            return redirect('orders:buyer_order_detail', order_number=order_number)
    else:
        form = RefundRequestForm(initial={'amount': order.total_amount})

    context = {'order': order, 'form': form}
    return render(request, 'orders/payment/refund_request.html', context)


@login_required
def invoice_download_view(request, order_number):
    """Allow buyers, related sellers, or admins to download invoice PDF."""
    order = get_object_or_404(Order, order_number=order_number)
    user = request.user

    has_access = False
    if user.is_superuser or user.is_staff:
        has_access = True
    elif order.buyer_id == user.id:
        has_access = True
    elif getattr(user, 'is_seller', False):
        has_access = order.items.filter(seller__user=user).exists()

    if not has_access:
        raise Http404

    try:
        invoice = order.invoice
    except Invoice.DoesNotExist:
        invoice, _ = create_or_update_invoice(order, mark_paid=order.payment_status == 'completed')

    if not invoice.pdf_file:
        invoice, _ = create_or_update_invoice(order, mark_paid=order.payment_status == 'completed')

    if not invoice.pdf_file:
        raise Http404('Invoice not available yet.')

    return FileResponse(invoice.pdf_file.open('rb'), as_attachment=True, filename=f"{invoice.invoice_number}.pdf")


@approved_seller_required
def seller_orders_view(request):
    """List orders that include the seller's products."""
    seller_profile = request.user.seller_profile
    orders = Order.objects.filter(items__seller=seller_profile).distinct().prefetch_related('items__product__images', 'buyer').order_by('-created_at')

    status_filter = request.GET.get('status')
    if status_filter:
        orders = orders.filter(status=status_filter)

    context = {
        'orders': orders,
        'status_filter': status_filter,
        'order_status_choices': Order.STATUS_CHOICES,
    }
    return render(request, 'orders/seller/order_list.html', context)


@approved_seller_required
def seller_order_detail_view(request, order_number):
    """Detail view for sellers with ability to update status and add shipments."""
    seller_profile = request.user.seller_profile
    # Get order by order_number (should be unique) and check if seller has items in it
    order = get_object_or_404(
        Order.objects.prefetch_related('items__product__images', 'shipments', 'buyer'),
        order_number=order_number
    )
    
    # Check if this seller has any items in this order
    seller_items = order.items.filter(seller=seller_profile).select_related('product')
    if not seller_items.exists():
        from django.http import Http404
        raise Http404("Order not found or you don't have access to this order.")
    
    # Check if order is delivered - if so, make it read-only
    is_delivered = order.status == 'DELIVERED'
    transaction = order.payment_transactions.order_by('-created_at').first()
    try:
        invoice = order.invoice
    except Invoice.DoesNotExist:
        invoice = None
    
    status_form = OrderStatusUpdateForm(initial={'status': order.status})
    shipment_form = ShipmentForm()
    tracking_form = TrackingStatusUpdateForm()
    if order.shipments.exists():
        current_tracking_status = order.shipments.latest('created_at').current_status
        tracking_form = TrackingStatusUpdateForm(initial={'tracking_status': current_tracking_status})

    if request.method == 'POST':
        if 'approve_payment' in request.POST:
            if order.payment_status == 'completed':
                messages.info(request, 'This order is already marked as paid.')
                return redirect('orders:seller_order_detail', order_number=order.order_number)

            if transaction:
                transaction.status = 'completed'
                transaction.save(update_fields=['status', 'updated_at'])

            order.payment_status = 'completed'
            if order.status in ['CREATED', 'PENDING_PAYMENT']:
                order.status = 'PAID'
            order.save(update_fields=['payment_status', 'status', 'updated_at'])

            invoice, pdf_content = create_or_update_invoice(order, mark_paid=True)
            invoice_attachments = [
                (f"{invoice.invoice_number}.pdf", pdf_content, "application/pdf")
            ]

            notify_invoice_available(order, invoice, attachments=invoice_attachments)
            if transaction:
                notify_payment_receipt(order, transaction, attachments=invoice_attachments)
                notify_seller_payment_received(order, transaction, request.user)
            broadcast_payment_approval(order, transaction, approver=request.user)

            messages.success(request, 'Payment approved. Buyers and sellers received the updated invoice.')
            return redirect('orders:seller_order_detail', order_number=order.order_number)

        if is_delivered:
            messages.warning(request, 'Order is already delivered. No further updates are allowed.')
            return redirect('orders:seller_order_detail', order_number=order.order_number)

        if 'update_tracking_status' in request.POST:
            tracking_form = TrackingStatusUpdateForm(request.POST)
            if tracking_form.is_valid() and order.shipments.exists():
                shipment = order.shipments.latest('created_at')
                new_tracking_status = tracking_form.cleaned_data['tracking_status']
                location = tracking_form.cleaned_data.get('location', '')
                notes = tracking_form.cleaned_data.get('notes', '')
                
                # Add status update to tracking history
                shipment.add_status_update(new_tracking_status, location=location, notes=notes)
                
                # Update order status based on tracking status
                status_mapping = {
                    'ordered': 'PENDING_PAYMENT',
                    'confirmed': 'PAID',
                    'on_pack': 'PROCESSING',
                    'dispatched': 'SHIPPED',
                    'out_to_delivery': 'OUT_FOR_DELIVERY',
                    'delivered': 'DELIVERED',
                }
                if new_tracking_status in status_mapping:
                    order.status = status_mapping[new_tracking_status]
                    order.save(update_fields=['status', 'updated_at'])
                
                messages.success(request, f'Tracking status updated to {new_tracking_status.replace("_", " ").title()}')
                return redirect('orders:seller_order_detail', order_number=order.order_number)
        elif 'update_status' in request.POST:
            status_form = OrderStatusUpdateForm(request.POST)
            shipment_form = ShipmentForm()
            if status_form.is_valid():
                new_status = status_form.cleaned_data['status']
                note = status_form.cleaned_data['note']
                order.status = new_status
                order.admin_notes = (order.admin_notes or '') + f"\n[{timezone.now():%Y-%m-%d %H:%M}] Seller note: {note}"
                order.save(update_fields=['status', 'admin_notes', 'updated_at'])
                if new_status in ['SHIPPED', 'OUT_FOR_DELIVERY', 'DELIVERED'] and order.shipments.exists():
                    latest_update = {
                        'status': order.get_status_display(),
                        'timestamp': timezone.now(),
                        'location': None,
                        'notes': note,
                    }
                    notify_order_tracking(order, order.shipments.latest('created_at'), latest_update)
                if new_status == 'DELIVERED' and order.shipments.exists():
                    shipment = order.shipments.latest('created_at')
                    shipment.delivered_at = timezone.now()
                    shipment.save(update_fields=['delivered_at'])
                    invoice, pdf_content = create_or_update_invoice(order, mark_paid=order.payment_status == 'completed')
                    delivery_attachments = [
                        (f"{invoice.invoice_number}.pdf", pdf_content, "application/pdf")
                    ]
                    notify_buyer_delivery_confirmation(order, shipment, attachments=delivery_attachments)
                messages.success(request, f'Order status updated to {order.get_status_display()}')
                return redirect('orders:seller_order_detail', order_number=order.order_number)
        elif 'create_shipment' in request.POST:
            shipment_form = ShipmentForm(request.POST)
            status_form = OrderStatusUpdateForm(initial={'status': order.status})
            if shipment_form.is_valid():
                # Check if shipment already exists for this order
                existing_shipment = order.shipments.first()
                
                if existing_shipment:
                    # Update existing shipment
                    existing_shipment.courier_name = shipment_form.cleaned_data['courier_name']
                    existing_shipment.tracking_number = shipment_form.cleaned_data['tracking_number']
                    existing_shipment.estimated_delivery = shipment_form.cleaned_data.get('estimated_delivery')
                    existing_shipment.notes = shipment_form.cleaned_data.get('notes', '')
                    existing_shipment.save()
                    shipment = existing_shipment
                    messages.success(request, 'Shipment updated successfully.')
                else:
                    # Create new shipment
                    shipment = shipment_form.save(commit=False)
                    shipment.order = order
                    shipment.current_status = 'ordered'
                    shipment.save()
                    shipment.add_status_update('ordered', location=None, notes=shipment.notes or '')
                    messages.success(request, 'Shipment created successfully.')
                
                # Update order status if not already shipped
                if order.status not in ['SHIPPED', 'OUT_FOR_DELIVERY', 'DELIVERED']:
                    order.status = 'SHIPPED'
                    order.save(update_fields=['status', 'updated_at'])
                
                latest_update = {
                    'status': shipment.current_status,
                    'timestamp': timezone.now(),
                    'location': shipment.courier_name,
                    'notes': shipment.notes or '',
                }
                notify_order_tracking(order, shipment, latest_update)
                return redirect('orders:seller_order_detail', order_number=order.order_number)
    item_status_choices = OrderItem._meta.get_field('status').choices
    context = {
        'order': order,
        'seller_items': seller_items,
        'status_form': status_form,
        'shipment_form': shipment_form,
        'tracking_form': tracking_form,
        'item_status_choices': item_status_choices,
        'has_shipment': order.shipments.exists(),
        'current_shipment': order.shipments.latest('created_at') if order.shipments.exists() else None,
        'is_delivered': is_delivered,
        'invoice': invoice,
        'transaction': transaction,
    }
    return render(request, 'orders/seller/order_detail.html', context)


@approved_seller_required
@require_POST
def seller_update_order_item_status(request, order_number, item_id):
    """Allow seller to update status of individual order item."""
    seller_profile = request.user.seller_profile
    
    # First, get the order item directly with proper filtering
    order_item = get_object_or_404(
        OrderItem,
        pk=item_id,
        seller=seller_profile,
        order__order_number=order_number
    )
    
    # Get the order from the order_item to avoid MultipleObjectsReturned
    order = order_item.order
    new_status = request.POST.get('status')
    if new_status not in dict(OrderItem._meta.get_field('status').choices):
        messages.error(request, 'Invalid status selected.')
        return redirect('orders:seller_order_detail', order_number=order.order_number)

    order_item.status = new_status
    order_item.save(update_fields=['status', 'updated_at'])
    messages.success(request, f'Item status updated to {order_item.get_status_display()}')
    return redirect('orders:seller_order_detail', order_number=order.order_number)


@login_required
def approve_payment_view(request, order_id):
    """Approve payment and generate invoice (Admin/Seller only)."""
    from apps.accounts.decorators import admin_required
    from apps.orders.utils import create_or_update_invoice
    from apps.common.notifications import notify_payment_receipt
    
    order = get_object_or_404(Order, id=order_id)
    
    # Check permissions
    if not (request.user.is_admin_user or 
            (request.user.is_seller and order.items.filter(seller=request.user.seller_profile).exists())):
        messages.error(request, 'You do not have permission to approve this payment.')
        return redirect('orders:buyer_orders')
    
    if request.method == 'POST':
        # Update payment status
        order.payment_status = 'completed'
        order.save(update_fields=['payment_status', 'updated_at'])
        
        # Generate payment summary if transaction exists
        transaction = order.payment_transactions.first()
        if transaction:
            from apps.orders.utils import generate_payment_summary
            generate_payment_summary(transaction)
        
        # Generate invoice
        invoice, pdf_content = create_or_update_invoice(order, mark_paid=True)
        
        # Send invoice email to buyer
        notify_payment_receipt(
            order,
            transaction,
            recipients=[order.buyer.email] if order.buyer and order.buyer.email else [],
            attachments=[(f"{invoice.invoice_number}.pdf", pdf_content, "application/pdf")]
        )
        
        # Send payment received email to sellers
        from apps.common.notifications import notify_seller_payment_received
        seller_users = order.items.select_related('seller__user').values_list('seller__user', flat=True).distinct()
        from apps.accounts.models import User
        for seller_user_id in seller_users:
            try:
                seller_user = User.objects.get(pk=seller_user_id)
                notify_seller_payment_received(order, transaction, seller_user)
            except User.DoesNotExist:
                continue
        
        messages.success(request, f'Payment approved and invoice sent to {order.buyer.email}')
        return redirect('orders:buyer_order_detail', order_number=order.order_number)
    
    context = {
        'order': order,
        'transaction': order.payment_transactions.first(),
    }
    return render(request, 'orders/approve_payment.html', context)


@login_required
@approved_seller_required
def seller_order_tracking_view(request, order_number):
    """Enhanced order tracking for seller with status sequence."""
    from apps.orders.utils import get_random_location
    
    seller_profile = request.user.seller_profile
    order = get_object_or_404(Order, order_number=order_number)
    
    # Get or create tracking
    tracking, created = ShipmentTracking.objects.get_or_create(
        order=order,
        defaults={
            'courier_name': 'Shop Hub Delivery',
            'tracking_number': f"{order.order_number}-S{random.randint(1000, 9999)}",
            'current_status': 'ordered',
            'history': [],
            'estimated_delivery': timezone.now() + timedelta(days=random.randint(2, 5))
        }
    )
    
    if not isinstance(tracking.history, list):
        tracking.history = []
        tracking.save(update_fields=['history', 'updated_at'])
    
    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status in dict(ShipmentTracking.STATUS_CHOICES):
            tracking.current_status = new_status
            tracking.history.append({
                'status': new_status,
                'timestamp': timezone.now().isoformat(),
                'location': get_random_location(new_status),
                'updated_by': 'seller'
            })
            tracking.save()
            
            # Send appropriate email based on status
            from apps.common.notifications import (
                notify_buyer_shipment_dispatched,
                notify_buyer_out_for_delivery,
                notify_buyer_delivery_confirmation
            )
            
            if new_status == 'dispatched':
                notify_buyer_shipment_dispatched(order, tracking)
            elif new_status == 'out_to_delivery':
                notify_buyer_out_for_delivery(order)
            elif new_status == 'delivered':
                tracking.delivered_at = timezone.now()
                tracking.save()
                invoice, pdf_content = create_or_update_invoice(order, mark_paid=order.payment_status == 'completed')
                delivery_attachments = [
                    (f"{invoice.invoice_number}.pdf", pdf_content, "application/pdf")
                ]
                notify_buyer_delivery_confirmation(order, tracking, attachments=delivery_attachments)
            
            messages.success(request, f'Status updated to {new_status.replace("_", " ").title()}')
            return redirect('orders:seller_order_tracking', order_number=order_number)
    
    # Get status progression
    statuses = ['ordered', 'confirmed', 'on_pack', 'dispatched', 'out_to_delivery', 'delivered']
    current_index = statuses.index(tracking.current_status) if tracking.current_status in statuses else 0
    
    context = {
        'order': order,
        'tracking': tracking,
        'statuses': statuses,
        'current_index': current_index,
    }
    return render(request, 'orders/seller_order_tracking.html', context)
