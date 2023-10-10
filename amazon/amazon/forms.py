from django import forms

from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from django.contrib.auth.models import User


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ["username", "email", "password1", "password2"]
        app_label = "amazon"


class BuyForm(forms.Form):
    amount = forms.IntegerField(min_value=1, label="amount")
    x = forms.IntegerField(label="delivery X")
    y = forms.IntegerField(label="delivery Y")
    provideups = forms.BooleanField(label="provide ups", required=False)
    upsid = forms.CharField(label="upsid", required=False, initial=None)


class ModifyForm(forms.Form):

    upsid = forms.CharField(label="upsid", required=False, initial=None)


class UPSIdForm(forms.Form):
    upsid = forms.CharField(label="upsid")


class ModifyStatus(forms.Form):
    status = forms.ChoiceField(
        choices=[("delivered", "delivered"), ("canceled", "canceled")]
    )


class comment(forms.Form):
    rate = forms.IntegerField(min_value=1, max_value=10)
    comment = forms.CharField(max_length=1000, required=False, initial=None)

class restockform(forms.Form):
    amount = forms.IntegerField(min_value=1, label="amount")