"""
Forms for Product Catalog
"""
from django import forms
from django.forms import inlineformset_factory
from django.utils.text import slugify
from apps.products.models import Category, Product, ProductImage, ProductVariant


class ProductSearchForm(forms.Form):
    query = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Search products...', 'class': 'form-control'})
    )


class ProductFilterForm(forms.Form):
    min_price = forms.DecimalField(
        max_digits=10, decimal_places=2, required=False,
        widget=forms.NumberInput(attrs={'placeholder': 'Min Price', 'class': 'form-control form-control-sm'})
    )
    max_price = forms.DecimalField(
        max_digits=10, decimal_places=2, required=False,
        widget=forms.NumberInput(attrs={'placeholder': 'Max Price', 'class': 'form-control form-control-sm'})
    )
    category = forms.ModelChoiceField(
        queryset=Category.objects.filter(is_active=True).order_by('name'),
        required=False,
        empty_label='All Categories',
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    rating = forms.IntegerField(
        required=False,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'},
                            choices=[('', 'Any Rating')] + [(i, f'{i} Stars & Up') for i in range(5, 0, -1)])
    )
    in_stock = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    sort_by = forms.ChoiceField(
        choices=[
            ('newest', 'Newest First'),
            ('price_asc', 'Price: Low to High'),
            ('price_desc', 'Price: High to Low'),
            ('rating_desc', 'Rating: High to Low'),
            ('popularity', 'Popularity') # Placeholder for future popularity logic
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )


class ProductForm(forms.ModelForm):
    """Form used by sellers to manage their products."""

    class Meta:
        model = Product
        exclude = ['seller', 'slug', 'rating', 'review_count', 'created_at', 'updated_at', 'vto_enabled', 'category_path']
        widgets = {
            'category': forms.Select(attrs={'class': 'form-select'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'sku': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'price': forms.NumberInput(attrs={'class': 'form-control'}),
            'compare_at_price': forms.NumberInput(attrs={'class': 'form-control'}),
            'stock': forms.NumberInput(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'is_featured': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'low_stock_threshold': forms.NumberInput(attrs={'class': 'form-control'}),
            'attributes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'meta_title': forms.TextInput(attrs={'class': 'form-control'}),
            'meta_description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'meta_keywords': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def clean_sku(self):
        sku = self.cleaned_data.get('sku')
        if not sku:
            sku = slugify(self.cleaned_data.get('title', ''))[:80]
        return sku.upper()


class ProductImageForm(forms.ModelForm):
    class Meta:
        model = ProductImage
        fields = ['image', 'alt_text', 'is_primary', 'display_order']
        widgets = {
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'alt_text': forms.TextInput(attrs={'class': 'form-control'}),
            'is_primary': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'display_order': forms.NumberInput(attrs={'class': 'form-control'}),
        }


class ProductVariantForm(forms.ModelForm):
    class Meta:
        model = ProductVariant
        fields = ['variant_sku', 'size', 'color', 'price_adjustment', 'stock']
        widgets = {
            'variant_sku': forms.TextInput(attrs={'class': 'form-control'}),
            'size': forms.TextInput(attrs={'class': 'form-control'}),
            'color': forms.TextInput(attrs={'class': 'form-control'}),
            'price_adjustment': forms.NumberInput(attrs={'class': 'form-control'}),
            'stock': forms.NumberInput(attrs={'class': 'form-control'}),
        }


ProductImageFormSet = inlineformset_factory(
    Product,
    ProductImage,
    form=ProductImageForm,
    extra=1,
    can_delete=True
)

ProductVariantFormSet = inlineformset_factory(
    Product,
    ProductVariant,
    form=ProductVariantForm,
    extra=1,
    can_delete=True
)

