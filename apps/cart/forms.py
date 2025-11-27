"""
Forms for Shopping Cart
"""
from django import forms
from django.core.validators import MinValueValidator
from .models import CartItem


class AddToCartForm(forms.Form):
    """Form for adding a product to cart"""
    product_id = forms.IntegerField(widget=forms.HiddenInput())
    quantity = forms.IntegerField(
        min_value=1,
        initial=1,
        validators=[MinValueValidator(1)],
        widget=forms.NumberInput(attrs={
            'class': 'form-control form-control-sm',
            'min': '1',
            'style': 'max-width: 80px;'
        })
    )


class UpdateQuantityForm(forms.Form):
    """Form for updating cart item quantity"""
    cart_item_id = forms.IntegerField(widget=forms.HiddenInput())
    quantity = forms.IntegerField(
        min_value=1,
        validators=[MinValueValidator(1)],
        widget=forms.NumberInput(attrs={
            'class': 'form-control form-control-sm quantity-input',
            'min': '1'
        })
    )

