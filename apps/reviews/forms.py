"""
Forms for Product Reviews
"""
from django import forms
from django.core.exceptions import ValidationError
from .models import Review, ReviewImage
from apps.orders.models import OrderItem


class ReviewForm(forms.ModelForm):
    """Form for writing/editing product reviews"""
    
    rating = forms.IntegerField(
        widget=forms.HiddenInput(),
        min_value=1,
        max_value=5
    )
    
    class Meta:
        model = Review
        fields = ['rating', 'title', 'body', 'order_item']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Write a headline for your review',
                'maxlength': 255
            }),
            'body': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 6,
                'placeholder': 'Share your experience with this product...',
            }),
            'order_item': forms.HiddenInput(),
        }
        labels = {
            'title': 'Review Title',
            'body': 'Your Review',
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.product = kwargs.pop('product', None)
        super().__init__(*args, **kwargs)
        
        # Make order_item optional if not provided
        if 'order_item' in self.fields:
            self.fields['order_item'].required = False
    
    def clean_order_item(self):
        order_item = self.cleaned_data.get('order_item')
        if order_item:
            # Verify that order_item belongs to the user
            if order_item.order.buyer != self.user:
                raise ValidationError("This order item doesn't belong to you.")
            # Verify that order_item matches the product
            if self.product and order_item.product != self.product:
                raise ValidationError("Order item doesn't match this product.")
        return order_item


class ReviewImageForm(forms.ModelForm):
    """Form for uploading review images"""
    
    class Meta:
        model = ReviewImage
        fields = ['image', 'caption']
        widgets = {
            'image': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
            'caption': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Optional caption',
                'maxlength': 255
            })
        }


class ReviewImageFormSet(forms.BaseInlineFormSet):
    """Formset for multiple review images"""
    pass


class SellerResponseForm(forms.Form):
    """Form for sellers to respond to reviews"""
    
    response = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Write a response to this review...',
        }),
        label='Your Response',
        max_length=1000,
        help_text='Maximum 1000 characters'
    )

