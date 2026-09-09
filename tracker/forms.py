"""Sign-up, log-in, and the daily form."""

from __future__ import annotations

from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.db import transaction

from .models import CATEGORY_KEYS, DayLog, Mark, Participant, WeeklyNote


class SignUpForm(forms.Form):
    """Claim a place that already exists, or add yourself if you are not listed.

    Everyone who said they were joining is already in the list with the name
    and department they gave, so almost everybody only picks their name and
    sets an email and password.
    """

    who = forms.ModelChoiceField(
        label="Find your name",
        queryset=Participant.objects.none(),
        required=False,
        empty_label="Choose your name…",
        # The queryset holds only unclaimed people, so a name that has just
        # been taken lands here. Django's stock wording is unhelpful.
        error_messages={
            "invalid_choice": "Somebody has just claimed that name. Please log in instead."
        },
    )
    email = forms.EmailField(label="Email")
    password = forms.CharField(
        label="Password", widget=forms.PasswordInput, min_length=8,
        help_text="At least 8 characters.",
    )
    full_name = forms.CharField(label="Name", max_length=120, required=False)
    dept = forms.CharField(label="Department", max_length=60, required=False)
    session = forms.CharField(label="Session", max_length=20, required=False)
    is_past_student = forms.BooleanField(label="I am a past student", required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        unclaimed = Participant.objects.filter(user__isnull=True).order_by("full_name")
        self.fields["who"].queryset = unclaimed
        self.fields["who"].label_from_instance = lambda p: p.label
        self.unclaimed_count = unclaimed.count()

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("That email is already signed up. Log in instead.")
        return email

    def clean(self):
        cleaned = super().clean()
        person = cleaned.get("who")
        if person is None and "who" not in self.errors and not (cleaned.get("full_name") or "").strip():
            self.add_error(
                "full_name",
                "Pick your name from the list, or type it here if it is not there.",
            )
        return cleaned

    @transaction.atomic
    def save(self) -> User:
        data = self.cleaned_data
        person = data.get("who")
        if person is not None:
            # Re-read inside the transaction so two people cannot claim one row.
            person = Participant.objects.select_for_update().get(pk=person.pk)
            if person.is_claimed:
                raise forms.ValidationError("Somebody has just claimed that name.")
            display_name = person.full_name
        else:
            display_name = data["full_name"].strip()

        user = User.objects.create_user(
            username=data["email"][:150],
            email=data["email"],
            password=data["password"],
            first_name=display_name[:150],
        )
        if person is not None:
            person.user = user
            person.save(update_fields=["user"])
        else:
            Participant.objects.create(
                user=user,
                full_name=display_name,
                dept=data.get("dept", "").strip(),
                session=data.get("session", "").strip(),
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
    """The daily answers.

    A study-or-work answer needs a reason: the group agreed those uses are fine
    "with evidence of official use", and this box is the evidence. A slip needs
    no reason — owning up should be the easy path, not the one with a form
    error attached.
    """

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

    def clean(self):
        cleaned = super().clean()
        marks = [cleaned.get(key) for key in CATEGORY_KEYS]
        if Mark.WORK in marks and not (cleaned.get("reason") or "").strip():
            self.add_error(
                "reason",
                "Say what the study or work was — the group agreed these uses "
                "are fine with evidence, and this is the evidence.",
            )
        return cleaned


class WeeklyNoteForm(forms.ModelForm):
    class Meta:
        model = WeeklyNote
        fields = ["hardest", "easier"]
        widgets = {"hardest": forms.TextInput(), "easier": forms.TextInput()}


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Participant
        fields = ["full_name", "dept", "session", "is_past_student"]
