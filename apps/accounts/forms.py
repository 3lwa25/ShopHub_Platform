"""
Forms for User Authentication and Profile Management
"""
from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.core.exceptions import ValidationError
from .models import User, SellerProfile


class UserRegistrationForm(UserCreationForm):
    """
    User registration form with role selection.
    """
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your email address',
            'autocomplete': 'email'
        }),
        required=True
    )
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Choose a username',
            'autocomplete': 'username'
        }),
        required=True
    )
    full_name = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Full name',
            'autocomplete': 'name'
        }),
        required=True
    )
    phone = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Phone number (optional)',
            'autocomplete': 'tel'
        }),
        required=False
    )
    role = forms.ChoiceField(
        choices=[(role, label) for role, label in User.ROLE_CHOICES if role != 'admin'],
        widget=forms.Select(attrs={
            'class': 'form-select'
        }),
        initial='buyer',
        help_text='Buyers can shop, Sellers can list products. Admin accounts can only be created by superusers.'
    )
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Create a password',
            'autocomplete': 'new-password',
            'id': 'id_password1'
        }),
        help_text='Password must be at least 8 characters long.'
    )
    password2 = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm your password',
            'autocomplete': 'new-password',
            'id': 'id_password2'
        })
    )
    
    class Meta:
        model = User
        fields = ['email', 'username', 'full_name', 'phone', 'role', 'password1', 'password2']
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError('A user with this email already exists.')
        return email
    
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise ValidationError('A user with this username already exists.')
        return username
    
    def clean_role(self):
        """Ensure admin role cannot be set through registration form"""
        role = self.cleaned_data.get('role')
        if role == 'admin':
            raise ValidationError('Admin accounts can only be created by system administrators.')
        return role
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.full_name = self.cleaned_data['full_name']
        role = self.cleaned_data['role']
        # Double-check: prevent admin role assignment
        if role == 'admin':
            role = 'buyer'  # Default to buyer as fallback
        user.role = role
        if self.cleaned_data.get('phone'):
            user.phone = self.cleaned_data['phone']
        
        if commit:
            user.save()
        return user


class UserLoginForm(AuthenticationForm):
    """
    User login form.
    """
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Email or username',
            'autocomplete': 'username'
        }),
        label='Email or Username'
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Password',
            'autocomplete': 'current-password',
            'id': 'id_password'
        })
    )
    remember_me = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        label='Remember me'
    )


class UserProfileForm(forms.ModelForm):
    """
    Form for editing user profile.
    """
    class Meta:
        model = User
        fields = ['username', 'email', 'full_name', 'first_name', 'last_name', 'phone', 'avatar']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'username'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'autocomplete': 'email'}),
            'full_name': forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'name'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'given-name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'family-name'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'tel'}),
            'avatar': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*', 'id': 'id_avatar'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make username and email editable
        if self.instance and self.instance.pk:
            self.fields['username'].required = True
            self.fields['email'].required = True
    
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if username:
            # Check if username is already taken by another user
            existing_user = User.objects.filter(username=username).exclude(pk=self.instance.pk).first()
            if existing_user:
                raise forms.ValidationError('This username is already taken. Please choose another.')
        return username
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            # Check if email is already taken by another user
            existing_user = User.objects.filter(email=email).exclude(pk=self.instance.pk).first()
            if existing_user:
                raise forms.ValidationError('This email is already taken. Please choose another.')
        return email


class SellerProfileForm(forms.ModelForm):
    """
    Form for creating/editing seller profile.
    """
    class Meta:
        model = SellerProfile
        fields = [
            'business_name', 'business_registration_number',
            'business_email', 'business_phone', 'business_address'
        ]
        widgets = {
            'business_name': forms.TextInput(attrs={'class': 'form-control'}),
            'business_registration_number': forms.TextInput(attrs={'class': 'form-control'}),
            'business_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'business_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'business_address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3
            }),
        }

