from typing import Optional, Sequence

from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from apps.notifications.models import Notification as InAppNotification

from .emails import send_templated_email


def _support_email() -> str:
    return getattr(settings, "SUPPORT_EMAIL", getattr(settings, "DEFAULT_FROM_EMAIL", "support@shophub.com"))


def notify_seller_status(user, is_approved: bool, is_verified: bool, reason: Optional[str] = None):
    subject = "Your seller account status has been updated"
    context = {
        "user": user,
        "is_approved": is_approved,
        "is_verified": is_verified,
        "reason": reason,
        "support_email": _support_email(),
    }
    send_templated_email(subject, "emails/seller_status_update.html", context, [user.email])


def notify_product_status(product, is_active: bool, is_featured: Optional[bool] = None, reason: Optional[str] = None):
    seller_user = product.seller.user if product.seller else None
    if not seller_user or not seller_user.email:
        return

    subject = f"Product status updated: {product.title}"
    context = {
        "product": product,
        "is_active": is_active,
        "is_featured": is_featured,
        "reason": reason,
        "support_email": _support_email(),
    }
    send_templated_email(subject, "emails/product_status_update.html", context, [seller_user.email])


def notify_order_confirmation(order):
    """Enhanced order confirmation using new template."""
    buyer = order.buyer
    if not buyer or not buyer.email:
        return
    
    subject = f"Your Shop Hub order is confirmed! - {order.order_number}"
    context = {
        "order": order,
        "buyer": buyer,
        "support_email": _support_email(),
        "order_detail_url": settings.SITE_URL + reverse('orders:buyer_order_detail', args=[order.order_number]),
        "tracking_url": settings.SITE_URL + reverse('orders:buyer_order_tracking', args=[order.order_number]),
    }
    send_templated_email(subject, "emails/buyer_order_confirmation.html", context, [buyer.email])
    
    # Create in-app notification
    InAppNotification.create_notification(
        user=buyer,
        notification_type='order',
        title='Order Confirmed',
        message=f'Your order #{order.order_number} has been confirmed and is being processed.',
        link=f'/orders/my-orders/{order.order_number}/',
    )


def notify_seller_new_order(order, seller_user):
    """Enhanced new order notification using new template."""
    if not seller_user or not seller_user.email:
        return
    
    subject = f"New order received! - {order.order_number}"
    context = {
        "order": order,
        "seller": seller_user,
        "support_email": _support_email(),
        "seller_order_url": settings.SITE_URL + reverse('orders:seller_order_detail', args=[order.order_number]),
    }
    send_templated_email(subject, "emails/seller_order_received.html", context, [seller_user.email])
    
    # Create in-app notification
    InAppNotification.create_notification(
        user=seller_user,
        notification_type='order',
        title='New Order Received',
        message=f'You have received a new order #{order.order_number}.',
        link=f'/orders/seller/{order.order_number}/',
    )


def notify_order_tracking(order, shipment, latest_update):
    buyer = order.buyer
    if not buyer or not buyer.email:
        return

    subject = f"Shipment update for order {order.order_number}"
    context = {
        "order": order,
        "shipment": shipment,
        "latest_update": latest_update,
        "support_email": _support_email(),
        "tracking_url": settings.SITE_URL + reverse('orders:buyer_order_tracking', args=[order.order_number]),
    }
    send_templated_email(subject, "emails/order_tracking_update.html", context, [buyer.email])


def notify_buyer_login(user, login_time, ip_address=None):
    """Notify buyer of new login."""
    if not user or not user.email:
        return
    
    subject = "New login to your Shop Hub account"
    context = {
        "user": user,
        "login_time": login_time,
        "ip_address": ip_address,
        "site_url": settings.SITE_URL,
        "support_email": _support_email(),
    }
    send_templated_email(subject, "emails/buyer_login_notification.html", context, [user.email])


def notify_seller_login(seller, seller_profile, login_time, ip_address=None):
    """Notify seller of new login."""
    if not seller or not seller.email:
        return
    
    subject = "New login to your Shop Hub seller account"
    context = {
        "seller": seller,
        "seller_profile": seller_profile,
        "login_time": login_time,
        "ip_address": ip_address,
        "site_url": settings.SITE_URL,
        "support_email": _support_email(),
    }
    send_templated_email(subject, "emails/seller_login_notification.html", context, [seller.email])


def notify_buyer_order_confirmation(order):
    """Enhanced order confirmation email for buyer."""
    buyer = order.buyer
    if not buyer or not buyer.email:
        return
    
    subject = f"Your Shop Hub order is confirmed! - {order.order_number}"
    context = {
        "order": order,
        "buyer": buyer,
        "support_email": _support_email(),
        "order_detail_url": settings.SITE_URL + reverse('orders:buyer_order_detail', args=[order.order_number]),
        "tracking_url": settings.SITE_URL + reverse('orders:buyer_order_tracking', args=[order.order_number]),
    }
    send_templated_email(subject, "emails/buyer_order_confirmation.html", context, [buyer.email])


def notify_buyer_shipment_dispatched(order, shipment):
    """Notify buyer that shipment has been dispatched."""
    buyer = order.buyer
    if not buyer or not buyer.email:
        return
    
    subject = f"Your shipment has been dispatched! - {order.order_number}"
    context = {
        "order": order,
        "shipment": shipment,
        "buyer": buyer,
        "support_email": _support_email(),
        "order_detail_url": settings.SITE_URL + reverse('orders:buyer_order_detail', args=[order.order_number]),
        "tracking_url": settings.SITE_URL + reverse('orders:buyer_order_tracking', args=[order.order_number]),
    }
    send_templated_email(subject, "emails/buyer_shipment_dispatched.html", context, [buyer.email])
    
    # Create in-app notification
    InAppNotification.create_notification(
        user=buyer,
        notification_type='shipment',
        title='Shipment Dispatched',
        message=f'Your order #{order.order_number} has been dispatched and is on its way.',
        link=f'/orders/my-orders/{order.order_number}/tracking/',
    )


def notify_buyer_out_for_delivery(order):
    """Notify buyer that order is out for delivery."""
    buyer = order.buyer
    if not buyer or not buyer.email:
        return
    
    subject = f"Items from your order {order.order_number} are out for delivery!"
    context = {
        "order": order,
        "buyer": buyer,
        "support_email": _support_email(),
        "order_detail_url": settings.SITE_URL + reverse('orders:buyer_order_detail', args=[order.order_number]),
    }
    send_templated_email(subject, "emails/buyer_out_for_delivery.html", context, [buyer.email])


def notify_buyer_delivery_confirmation(order, shipment, attachments=None):
    """Notify buyer that order has been delivered."""
    buyer = order.buyer
    if not buyer or not buyer.email:
        return
    
    subject = f"Your shipment has been delivered! - {order.order_number}"
    context = {
        "order": order,
        "shipment": shipment,
        "buyer": buyer,
        "support_email": _support_email(),
        "order_detail_url": settings.SITE_URL + reverse('orders:buyer_order_detail', args=[order.order_number]),
    }
    send_templated_email(subject, "emails/buyer_delivery_confirmation.html", context, [buyer.email], attachments=attachments)
    
    # Create in-app notification
    InAppNotification.create_notification(
        user=buyer,
        notification_type='shipment',
        title='Order Delivered',
        message=f'Your order #{order.order_number} has been delivered successfully!',
        link=f'/orders/my-orders/{order.order_number}/',
    )


def notify_seller_order_received(order, seller_user):
    """Enhanced new order notification for seller."""
    if not seller_user or not seller_user.email:
        return
    
    subject = f"New order received! - {order.order_number}"
    context = {
        "order": order,
        "seller": seller_user,
        "support_email": _support_email(),
        "seller_order_url": settings.SITE_URL + reverse('orders:seller_order_detail', args=[order.order_number]),
    }
    send_templated_email(subject, "emails/seller_order_received.html", context, [seller_user.email])


def notify_seller_payment_received(order, transaction, seller_user):
    """Notify seller that payment has been received."""
    if not seller_user or not seller_user.email:
        return
    
    subject = f"Payment received for order {order.order_number}"
    context = {
        "order": order,
        "transaction": transaction,
        "seller": seller_user,
        "seller_profile": seller_user.seller_profile if hasattr(seller_user, 'seller_profile') else None,
        "support_email": _support_email(),
        "seller_order_url": settings.SITE_URL + reverse('orders:seller_order_detail', args=[order.order_number]),
    }
    send_templated_email(subject, "emails/seller_payment_received.html", context, [seller_user.email])
    
    # Create in-app notification
    InAppNotification.create_notification(
        user=seller_user,
        notification_type='payment',
        title='Payment Received',
        message=f'Payment for order #{order.order_number} has been received and approved.',
        link=f'/orders/seller/{order.order_number}/',
    )


def notify_seller_order_status_update(order, seller_user, status_display, message=None):
    """Notify seller of order status update."""
    if not seller_user or not seller_user.email:
        return
    
    subject = f"Order status update - {order.order_number}"
    context = {
        "order": order,
        "seller": seller_user,
        "status_display": status_display,
        "message": message,
        "updated_at": timezone.now(),
        "support_email": _support_email(),
        "seller_order_url": settings.SITE_URL + reverse('orders:seller_order_detail', args=[order.order_number]),
    }
    send_templated_email(subject, "emails/seller_order_status_update.html", context, [seller_user.email])


def notify_payment_receipt(order, transaction, recipients: Optional[Sequence[str]] = None, attachments=None):
    if recipients is None:
        recipients = []
        if order.buyer and order.buyer.email:
            recipients.append(order.buyer.email)
        seller_emails = order.items.values_list('seller__user__email', flat=True)
        recipients.extend([email for email in seller_emails if email])
        recipients = list(set(recipients))

    if not recipients:
        return

    status_display = getattr(transaction, "get_status_display", lambda: transaction.status.title())()
    subject = f"Payment {status_display.lower()} - {order.order_number}"
    context = {
        "order": order,
        "transaction": transaction,
        "support_email": _support_email(),
    }
    send_templated_email(subject, "emails/payment_receipt.html", context, recipients, attachments=attachments)


def notify_invoice_available(order, invoice, recipients: Optional[Sequence[str]] = None, attachments=None):
    if recipients is None:
        recipients = []
        if order.buyer and order.buyer.email:
            recipients.append(order.buyer.email)
        seller_emails = order.items.values_list('seller__user__email', flat=True)
        recipients.extend([email for email in seller_emails if email])
        recipients = list(set(recipients))

    if not recipients:
        return

    subject = f"Invoice available - {order.order_number}"
    context = {
        "order": order,
        "invoice": invoice,
        "support_email": _support_email(),
        "invoice_url": settings.SITE_URL + reverse('orders:invoice_download', args=[order.order_number]),
    }
    send_templated_email(subject, "emails/invoice_notification.html", context, recipients, attachments=attachments)


def notify_support_refund_request(order, amount, reason: str):
    support_email = _support_email()
    if not support_email:
        return

    subject = f"Refund request submitted - Order {order.order_number}"
    context = {
        "order": order,
        "buyer": order.buyer,
        "amount": amount,
        "reason": reason,
        "support_email": support_email,
        "order_detail_url": settings.SITE_URL + reverse('orders:buyer_order_detail', args=[order.order_number]),
    }
    send_templated_email(subject, "emails/support_refund_request.html", context, [support_email])


def notify_payment_refund(order, transaction, recipients: Optional[Sequence[str]] = None, attachments=None):
    if recipients is None:
        recipients = []
        if order.buyer and order.buyer.email:
            recipients.append(order.buyer.email)
        seller_emails = order.items.values_list('seller__user__email', flat=True)
        recipients.extend([email for email in seller_emails if email])
        recipients = list(set(recipients))

    if not recipients:
        return

    subject = f"Payment refunded - {order.order_number}"
    context = {
        "order": order,
        "transaction": transaction,
        "support_email": _support_email(),
    }
    send_templated_email(subject, "emails/payment_refund.html", context, recipients, attachments=attachments)
