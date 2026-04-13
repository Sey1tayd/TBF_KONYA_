from django import forms
from django.contrib.auth.models import User
from .models import UserProfile, Availability


class LoginForm(forms.Form):
    username = forms.CharField(label='Kullanici Adi', max_length=150)
    password = forms.CharField(label='Sifre', widget=forms.PasswordInput)


class AvailabilityForm(forms.Form):
    """Haftalik musaitlik formu - tarihler dinamik olarak view'dan gelir."""
    pass


class UserProfileForm(forms.ModelForm):
    first_name = forms.CharField(label='Ad', max_length=30)
    last_name = forms.CharField(label='Soyad', max_length=30)

    class Meta:
        model = UserProfile
        fields = ['phone']
        labels = {
            'phone': 'Telefon',
        }
