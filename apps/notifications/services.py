"""
Utility helpers for broadcasting in-app notifications.
"""
from django.urls import reverse

from .models import Notification


def broadcast_payment_approval(order, transaction, approver=None):
    """
    Notify stakeholders that a payment has been approved.
    Currently notifies the buyer (sellers already receive a dedicated alert via email + their own notification hook).
    """
    if not order:
        return

    buyer = getattr(order, "buyer", None)
    if buyer:
        link = reverse('orders:buyer_order_detail', args=[order.order_number])
        caption = "Payment Approved"
        approver_name = getattr(approver, "full_name", None) or getattr(approver, "email", "Seller")
        message = (
            f"Payment for order #{order.order_number} has been approved"
            f"{' by ' + approver_name if approver_name else ''}. "
            "Your updated invoice is ready to download."
        )
        Notification.create_notification(
            user=buyer,
            title=caption,
            message=message,
            notification_type='payment',
            link=link,
            metadata={'order_number': order.order_number, 'transaction_id': getattr(transaction, 'transaction_id', None)},
        )

