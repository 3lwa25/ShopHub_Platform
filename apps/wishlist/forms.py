"""
Forms for Wishlist
"""
from django import forms
from .models import WishlistItem


class WishlistItemForm(forms.ModelForm):
    """Form for adding/editing wishlist items"""
    
    class Meta:
        model = WishlistItem
        fields = ['notes', 'priority']
        widgets = {
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Add a note about this product (optional)',
            }),
            'priority': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0,
                'max': 10,
                'value': 0
            })
        }
        labels = {
            'notes': 'Notes',
            'priority': 'Priority (0-10)',
        }
        help_texts = {
            'priority': 'Higher numbers appear first in your wishlist',
        }

