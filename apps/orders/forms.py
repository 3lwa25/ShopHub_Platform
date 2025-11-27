from django import forms
from django.utils import timezone
from apps.orders.models import ShipmentTracking, Order, PaymentTransaction


class CheckoutForm(forms.Form):
    """Collect shipping and payment details during checkout."""
    # Option to use saved address
    use_saved_address = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'use_saved_address'})
    )
    saved_address_id = forms.IntegerField(
        required=False,
        widget=forms.HiddenInput(attrs={'id': 'saved_address_id'})
    )
    
    full_name = forms.CharField(max_length=255, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full Name', 'id': 'id_full_name'}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email Address', 'id': 'id_email'}))
    phone = forms.CharField(max_length=20, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone Number', 'id': 'id_phone'}))
    address_line1 = forms.CharField(max_length=255, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Address Line 1', 'id': 'id_address_line1'}))
    address_line2 = forms.CharField(max_length=255, required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Address Line 2', 'id': 'id_address_line2'}))
    city = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'City', 'id': 'id_city'}))
    state = forms.CharField(max_length=100, required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'State / Province', 'id': 'id_state'}))
    country = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Country', 'id': 'id_country'}))
    postal_code = forms.CharField(max_length=20, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Postal Code', 'id': 'id_postal_code'}))
    
    save_address = forms.BooleanField(
        required=False,
        label="Save this address for future orders",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    payment_method = forms.ChoiceField(
        choices=[
            ('cod', 'Cash on Delivery'),
            ('credit_card', 'Credit / Debit Card (Placeholder)'),
            ('paypal', 'PayPal (Placeholder)'),
        ],
        widget=forms.RadioSelect
    )
    customer_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Order notes (optional)'})
    )


class ShipmentForm(forms.ModelForm):
    """Form for sellers to add shipment tracking."""
    class Meta:
        model = ShipmentTracking
        fields = ['courier_name', 'tracking_number', 'estimated_delivery', 'notes']
        widgets = {
            'courier_name': forms.TextInput(attrs={'class': 'form-control'}),
            'tracking_number': forms.TextInput(attrs={'class': 'form-control'}),
            'estimated_delivery': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class OrderStatusUpdateForm(forms.Form):
    """Form for sellers/admins to update order status."""
    status = forms.ChoiceField(choices=Order.STATUS_CHOICES, widget=forms.Select(attrs={'class': 'form-select'}))
    note = forms.CharField(required=False, widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}))


class TrackingStatusUpdateForm(forms.Form):
    """Form for sellers to update tracking status."""
    tracking_status = forms.ChoiceField(
        choices=[
            ('ordered', 'Ordered'),
            ('confirmed', 'Confirmed'),
            ('on_pack', 'On Pack'),
            ('dispatched', 'Dispatched'),
            ('out_to_delivery', 'Out to Delivery'),
            ('delivered', 'Delivered'),
        ],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    location = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Location (optional)'})
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Additional notes (optional)'})
    )


class PaymentMethodForm(forms.Form):
    """Allow buyers to select a payment method."""
    payment_method = forms.ChoiceField(
        choices=PaymentTransaction.PAYMENT_METHOD_CHOICES,
        widget=forms.RadioSelect
    )


class PaymentDetailsForm(forms.Form):
    """Placeholder payment detail form for card/wallet methods."""
    cardholder_name = forms.CharField(
        max_length=100,
        label="Cardholder Name",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Name on card'})
    )
    card_number = forms.CharField(
        max_length=19,
        label="Card Number",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'XXXX XXXX XXXX XXXX'})
    )
    expiry_month = forms.ChoiceField(
        choices=[(f'{m:02d}', f'{m:02d}') for m in range(1, 13)],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    expiry_year = forms.ChoiceField(
        choices=[(str(year), str(year)) for year in range(timezone.now().year, timezone.now().year + 10)],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    cvv = forms.CharField(
        max_length=4,
        label="CVV",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '123'})
    )
    billing_address = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Billing address (optional)'})
    )


class RefundRequestForm(forms.Form):
    """Placeholder refund request form."""
    reason = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Reason for refund request'}),
        label="Refund Reason"
    )
    amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Amount to refund'})
    )
