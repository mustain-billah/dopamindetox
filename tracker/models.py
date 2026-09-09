"""One row per person per day. Only its owner can write it."""

from __future__ import annotations

import datetime as dt

from django.conf import settings
from django.contrib.auth.models import User
from django.db import models


class Mark(models.TextChoices):
    """What happened with one thing on one day."""

    NO = "N", "No"                    # did not touch it
    WORK = "W", "Study or work"       # used it, but only for study or a job
    YES = "Y", "Yes"                  # used it


#: key, label shown on the page, one line of help
CATEGORIES = [
    ("youtube", "YouTube", "Allowed only for study or work you had to do."),
    ("facebook", "Facebook", "No exceptions agreed for this one."),
    ("instagram", "Instagram, X, LinkedIn", "LinkedIn is allowed for a job search."),
    ("news", "Newspapers", "Online and print, sports pages included."),
    ("other", "Other apps", "Reels, TikTok, Telegram channels, podcasts, anything similar."),
    ("watching", "Videos, films, games", "On any device — phone, laptop or PC."),
]
CATEGORY_KEYS = [key for key, _, _ in CATEGORIES]


def challenge_start() -> dt.date:
    return getattr(settings, "CHALLENGE_START", dt.date(2026, 9, 11))


def challenge_end() -> dt.date:
    return getattr(settings, "CHALLENGE_END", dt.date(2027, 1, 11))


def total_days() -> int:
    return (challenge_end() - challenge_start()).days + 1


class Participant(models.Model):
    """A person in the challenge.

    Everyone who said they were joining is created up front from the roster,
    with the name and department they already gave. `user` stays empty until
    that person claims their place with an email and password, so nobody has
    to type their details in twice.
    """

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="participant",
        null=True, blank=True,
    )
    full_name = models.CharField("Name", max_length=120)
    dept = models.CharField("Department", max_length=60, blank=True,
                            help_text="For example: BGE")
    session = models.CharField("Session", max_length=20, blank=True,
                               help_text="For example: 2005-06")
    is_past_student = models.BooleanField("Past student", default=False)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["full_name"]

    def __str__(self) -> str:
        return self.label

    @property
    def is_claimed(self) -> bool:
        return self.user_id is not None

    @property
    def where(self) -> str:
        """Department and session as one string, e.g. "BGE (2005-06)"."""
        if self.dept and self.session:
            return f"{self.dept} ({self.session})"
        return self.dept or self.session or ""

    @property
    def label(self) -> str:
        where = self.where
        return f"{self.full_name} — {where}" if where else self.full_name


class DayLog(models.Model):
    """What one person did on one day."""

    participant = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name="logs")
    date = models.DateField(db_index=True)

    youtube = models.CharField(max_length=1, choices=Mark.choices, default=Mark.NO)
    facebook = models.CharField(max_length=1, choices=Mark.choices, default=Mark.NO)
    instagram = models.CharField(max_length=1, choices=Mark.choices, default=Mark.NO)
    news = models.CharField(max_length=1, choices=Mark.choices, default=Mark.NO)
    other = models.CharField(max_length=1, choices=Mark.choices, default=Mark.NO)
    watching = models.CharField(max_length=1, choices=Mark.choices, default=Mark.NO)

    said_no = models.PositiveSmallIntegerField("Times you stopped yourself", default=0)
    instead = models.CharField("What you did instead", max_length=200, blank=True)
    reason = models.CharField("Reason", max_length=200, blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date"]
        constraints = [
            models.UniqueConstraint(fields=["participant", "date"], name="one_log_per_day")
        ]

    def __str__(self) -> str:
        return f"{self.participant} — {self.date} ({self.get_status_display_short()})"

    @property
    def marks(self) -> list[str]:
        return [getattr(self, key) for key in CATEGORY_KEYS]

    @property
    def status(self) -> str:
        """Y if any rule was broken, W if only study or work use, else N."""
        marks = self.marks
        if Mark.YES in marks:
            return Mark.YES
        if Mark.WORK in marks:
            return Mark.WORK
        return Mark.NO

    def get_status_display_short(self) -> str:
        return {Mark.NO: "clean", Mark.WORK: "study or work", Mark.YES: "used"}[self.status]

    @property
    def broke_rule(self) -> bool:
        return self.status == Mark.YES

    @property
    def is_clean(self) -> bool:
        return self.status == Mark.NO

    def rows(self):
        for key, label, help_text in CATEGORIES:
            yield {"key": key, "label": label, "help": help_text, "value": getattr(self, key)}


class WeeklyNote(models.Model):
    """Two lines a week, so the four months leave a record."""

    participant = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name="notes")
    week = models.PositiveSmallIntegerField()
    hardest = models.CharField("What was hardest", max_length=300, blank=True)
    easier = models.CharField("What got easier", max_length=300, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["week"]
        constraints = [
            models.UniqueConstraint(fields=["participant", "week"], name="one_note_per_week")
        ]

    def __str__(self) -> str:
        return f"{self.participant} — week {self.week}"
