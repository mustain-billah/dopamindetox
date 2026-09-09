"""Sign in with the email you registered, not a username."""

from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User


class EmailBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        email = (username or kwargs.get("email") or "").strip()
        if not email:
            return None
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            # Hash anyway, so a missing account takes as long as a wrong
            # password — otherwise response time reveals which emails exist.
            User().set_password(password)
            return None
        except User.MultipleObjectsReturned:
            user = User.objects.filter(email__iexact=email).order_by("id").first()
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
