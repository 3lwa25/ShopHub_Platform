"""
Django Admin Configuration for Orders App
Note: Cart admin is in apps.cart.admin
"""
from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html

from apps.common.notifications import (
    notify_payment_receipt,
    notify_payment_refund,
)
from apps.orders.utils import create_or_update_invoice
from .models import Order, OrderItem, ShipmentTracking, PaymentTransaction, Invoice

# Import coupon admin (models are auto-registered via @admin.register decorator)
try:
    from . import coupon_admin  # This will register the models
except ImportError:
    pass


# Cart and CartItem admin are now in apps.cart.admin


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ['subtotal_display']
    fields = ['product', 'variant', 'product_name', 'quantity', 'unit_price', 'subtotal_display', 'status']
    can_delete = False
    
    def subtotal_display(self, obj):
        """Display subtotal safely handling None values"""
        if obj:
            try:
                if obj.unit_price is not None and obj.quantity is not None:
                    subtotal = obj.unit_price * obj.quantity
                    return f"EGP {subtotal:.2f}"
            except (TypeError, AttributeError):
                pass
        return "N/A"
    subtotal_display.short_description = 'Subtotal'


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['order_number', 'buyer', 'total_amount', 'status', 'payment_status', 'created_at']
    list_filter = ['status', 'payment_status', 'created_at', 'currency']
    search_fields = ['order_number', 'buyer__email', 'buyer__username']
    readonly_fields = ['order_number', 'created_at', 'updated_at']
    inlines = [OrderItemInline]
    ordering = ['-created_at']
    actions = ['mark_as_processing', 'mark_as_shipped', 'mark_as_delivered', 'cancel_orders', 'export_to_csv']
    
    fieldsets = (
        ('Order Information', {
            'fields': ('order_number', 'buyer', 'total_amount', 'currency', 'status')
        }),
        ('Payment', {
            'fields': ('payment_method', 'payment_status', 'reward_points_used', 'points_earned')
        }),
        ('Shipping', {
            'fields': ('shipping_address',)
        }),
        ('Notes', {
            'fields': ('customer_notes', 'admin_notes'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def mark_as_processing(self, request, queryset):
        """Mark selected orders as processing"""
        updated = queryset.filter(status='pending').update(status='processing', updated_at=timezone.now())
        self.message_user(request, f'{updated} order(s) marked as processing.')
    mark_as_processing.short_description = 'Mark selected orders as Processing'
    
    def mark_as_shipped(self, request, queryset):
        """Mark selected orders as shipped"""
        updated = queryset.filter(status='processing').update(status='shipped', updated_at=timezone.now())
        self.message_user(request, f'{updated} order(s) marked as shipped.')
    mark_as_shipped.short_description = 'Mark selected orders as Shipped'
    
    def mark_as_delivered(self, request, queryset):
        """Mark selected orders as delivered"""
        updated = queryset.filter(status='shipped').update(status='delivered', updated_at=timezone.now())
        self.message_user(request, f'{updated} order(s) marked as delivered.')
    mark_as_delivered.short_description = 'Mark selected orders as Delivered'
    
    def cancel_orders(self, request, queryset):
        """Cancel selected orders"""
        updated = queryset.exclude(status__in=['delivered', 'cancelled']).update(
            status='cancelled',
            updated_at=timezone.now()
        )
        self.message_user(request, f'{updated} order(s) cancelled.')
    cancel_orders.short_description = 'Cancel selected orders'
    
    def export_to_csv(self, request, queryset):
        """Export selected orders to CSV"""
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="orders_export.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Order Number', 'Buyer', 'Email', 'Total Amount', 'Status', 'Payment Status', 'Created At'])
        
        for order in queryset:
            writer.writerow([
                order.order_number,
                order.buyer.full_name or order.buyer.username,
                order.buyer.email,
                order.total_amount,
                order.status,
                order.payment_status,
                order.created_at.strftime('%Y-%m-%d %H:%M:%S')
            ])
        
        return response
    export_to_csv.short_description = 'Export selected orders to CSV'


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ['order', 'product_name', 'quantity', 'unit_price', 'subtotal', 'status']
    list_filter = ['status', 'created_at']
    search_fields = ['order__order_number', 'product_name', 'product_sku']


@admin.register(ShipmentTracking)
class ShipmentTrackingAdmin(admin.ModelAdmin):
    list_display = ['order', 'courier_name', 'tracking_number', 'current_status', 'estimated_delivery', 'created_at']
    list_filter = ['current_status', 'courier_name', 'created_at']
    search_fields = ['order__order_number', 'tracking_number', 'courier_name']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ['transaction_id', 'order', 'payment_method', 'amount', 'status', 'created_at']
    list_filter = ['payment_method', 'status', 'created_at', 'currency']
    search_fields = ['transaction_id', 'order__order_number', 'order__buyer__email']
    readonly_fields = ['transaction_id', 'gateway_response', 'created_at', 'updated_at', 'completed_at']
    ordering = ['-created_at']
    actions = ['mark_transactions_completed', 'mark_transactions_refunded']

    def mark_transactions_completed(self, request, queryset):
        updated = 0
        for transaction in queryset.select_related('order'):
            if transaction.status == 'completed':
                continue
            transaction.status = 'completed'
            transaction.completed_at = timezone.now()
            transaction.save(update_fields=['status', 'completed_at', 'updated_at'])

            order = transaction.order
            order.payment_status = 'completed'
            order.payment_method = transaction.payment_method
            if order.status in ['CREATED', 'PENDING_PAYMENT']:
                order.status = 'PAID'
            order.save(update_fields=['payment_status', 'payment_method', 'status', 'updated_at'])

            invoice, pdf_content = create_or_update_invoice(order, mark_paid=True)
            notify_payment_receipt(
                order,
                transaction,
                attachments=[(f"{invoice.invoice_number}.pdf", pdf_content, "application/pdf")],
            )
            updated += 1
        self.message_user(request, f"{updated} transaction(s) marked as completed.")
    mark_transactions_completed.short_description = "Mark selected transactions as completed"

    def mark_transactions_refunded(self, request, queryset):
        updated = 0
        for transaction in queryset.select_related('order'):
            if transaction.status == 'refunded':
                continue
            transaction.status = 'refunded'
            transaction.refund_amount = transaction.amount
            transaction.refunded_at = timezone.now()
            transaction.save(update_fields=['status', 'refund_amount', 'refunded_at', 'updated_at'])

            order = transaction.order
            order.payment_status = 'refunded'
            if order.status not in ['RETURN_REQUESTED', 'RETURNED']:
                order.status = 'RETURNED'
            order.save(update_fields=['payment_status', 'status', 'updated_at'])

            invoice, pdf_content = create_or_update_invoice(order, mark_paid=False)
            notify_payment_refund(
                order,
                transaction,
                attachments=[(f"{invoice.invoice_number}.pdf", pdf_content, "application/pdf")],
            )
            updated += 1
        self.message_user(request, f"{updated} transaction(s) marked as refunded.")
    mark_transactions_refunded.short_description = "Mark selected transactions as refunded"


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ['invoice_number', 'order', 'total_amount', 'is_paid', 'issue_date', 'download_link']
    list_filter = ['is_paid', 'issue_date', 'created_at']
    search_fields = ['invoice_number', 'order__order_number', 'order__buyer__email']
    readonly_fields = [
        'invoice_number',
        'order',
        'issue_date',
        'due_date',
        'subtotal',
        'tax_amount',
        'shipping_amount',
        'discount_amount',
        'total_amount',
        'is_paid',
        'paid_at',
        'created_at',
        'updated_at',
        'pdf_file',
    ]
    ordering = ['-created_at']

    def download_link(self, obj):
        if obj.pdf_file:
            return format_html('<a href="{}" target="_blank">Download PDF</a>', obj.pdf_file.url)
        return "-"
    download_link.short_description = "Invoice PDF"

