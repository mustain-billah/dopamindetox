"""Sign-up, log-in, and the daily form."""

from __future__ import annotations

from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User

from .models import CATEGORY_KEYS, DayLog, Participant, WeeklyNote


class SignUpForm(forms.Form):
    full_name = forms.CharField(label="Your name", max_length=120)
    email = forms.EmailField(label="Email")
    dept = forms.CharField(
        label="Department and session", max_length=80, required=False,
        help_text="For example: BGE (2005-06)",
    )
    is_past_student = forms.BooleanField(label="I am a past student", required=False)
    password = forms.CharField(
        label="Password", widget=forms.PasswordInput, min_length=8,
        help_text="At least 8 characters.",
    )

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("That email is already signed up. Log in instead.")
        return email

    def save(self) -> User:
        data = self.cleaned_data
        user = User.objects.create_user(
            username=data["email"][:150],
            email=data["email"],
            password=data["password"],
            first_name=data["full_name"][:150],
        )
        Participant.objects.create(
            user=user,
            full_name=data["full_name"],
            dept=data.get("dept", ""),
            is_past_student=data.get("is_past_student", False),
        )
        return user


class EmailLoginForm(AuthenticationForm):
    username = forms.EmailField(label="Email", widget=forms.EmailInput(attrs={"autofocus": True}))
    password = forms.CharField(label="Password", widget=forms.PasswordInput)

    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": "That email and password do not match.",
    }


class DayLogForm(forms.ModelForm):
    class Meta:
        model = DayLog
        fields = CATEGORY_KEYS + ["said_no", "instead", "reason"]
        widgets = {
            "said_no": forms.NumberInput(attrs={"min": 0, "max": 99}),
            "instead": forms.TextInput(
                attrs={"placeholder": "Read 30 pages, walked after Maghrib, slept early"}
            ),
            "reason": forms.TextInput(
                attrs={"placeholder": "If you used something, say why in a few words"}
            ),
        }


class WeeklyNoteForm(forms.ModelForm):
    class Meta:
        model = WeeklyNote
        fields = ["hardest", "easier"]
        widgets = {"hardest": forms.TextInput(), "easier": forms.TextInput()}


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Participant
        fields = ["full_name", "dept", "is_past_student"]
