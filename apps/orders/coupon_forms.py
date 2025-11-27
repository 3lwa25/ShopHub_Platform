"""
Coupon Forms
"""
from django import forms
from .coupon_models import Coupon


class CouponApplyForm(forms.Form):
    """Form for applying coupon code"""
    coupon_code = forms.CharField(
        max_length=50,
        label='Coupon Code',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter coupon code',
            'autocomplete': 'off'
        })
    )
    
    def clean_coupon_code(self):
        """Validate coupon code"""
        code = self.cleaned_data.get('coupon_code', '').strip().upper()
        if not code:
            raise forms.ValidationError('Please enter a coupon code.')
        return code

