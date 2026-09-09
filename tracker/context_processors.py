"""Challenge dates and prize, available to every template."""

import datetime as dt

from django.conf import settings

from . import services
from .models import total_days


def challenge(request):
    today = dt.date.today()
    start, end = settings.CHALLENGE_START, settings.CHALLENGE_END
    if today < start:
        phase, day_no = "before", 0
    elif today > end:
        phase, day_no = "after", total_days()
    else:
        phase, day_no = "during", services.day_number(today)
    return {
        "challenge_name": settings.CHALLENGE_NAME,
        "start": start,
        "end": end,
        "total_days": total_days(),
        "day_no": day_no,
        "phase": phase,
        "days_left": max(0, (end - today).days),
        "days_to_start": max(0, (start - today).days),
        "prize": settings.CHALLENGE_PRIZE,
        "currency": settings.CHALLENGE_CURRENCY,
    }
