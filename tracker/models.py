"""One row per person per day. Only its owner can write it."""

from __future__ import annotations

import datetime as dt
from typing import NamedTuple

from django.conf import settings
from django.contrib.auth.models import User
from django.db import models


class Mark(models.TextChoices):
    """What happened with one thing on one day."""

    NO = "N", "No"                    # did not touch it
    TALK = "C", "Communication only"  # messaging apps used as a phone, nothing more
    WORK = "W", "Study or work"       # used it, but only for study or a job
    YES = "Y", "Yes"                  # used it


#: Scoring reads only two of these. YES is a slip, WORK is a study-or-work day,
#: and everything else — NO and TALK alike — is a clean day. TALK exists so that
#: somebody who used no messaging app at all is not made to claim they chatted.
CLEAN_MARKS = (Mark.NO, Mark.TALK)


class Option(NamedTuple):
    """One button on one question."""

    value: str
    label: str


#: What almost every row offers.
DEFAULT_OPTIONS = (
    Option(Mark.NO, "No"),
    Option(Mark.WORK, "Study or work"),
    Option(Mark.YES, "Yes"),
)


class Category(NamedTuple):
    """One question on the daily form.

    `options` names the buttons. Almost every row offers the same three — no,
    only for study or work, yes — but messaging apps are allowed for talking, so
    that row offers its own set instead.
    """

    key: str
    label: str
    help: str
    options: tuple[Option, ...] = DEFAULT_OPTIONS
    #: A second line of help, set apart on its own line where that reads better.
    note: str = ""

    @property
    def values(self) -> list[str]:
        return [o.value for o in self.options]

    @property
    def choices(self) -> list[tuple[str, str]]:
        return [(o.value, o.label) for o in self.options]


CATEGORIES = [
    Category("youtube", "YouTube", "Allowed only for study or work you had to do."),
    Category("facebook", "Facebook",
             "The app itself — feed, Stories, Watch, Marketplace.",
             note="Messenger chat belongs on the messaging row below, not here."),
    Category("instagram", "Instagram, X, LinkedIn", "LinkedIn is allowed for a job search."),
    Category("messaging", "Messaging apps",
             "WhatsApp, Messenger, Telegram.",
             (Option(Mark.NO, "No"),
              Option(Mark.TALK, "Communication only"),
              Option(Mark.YES, "Others")),
             note="Calls, chat and anything a person sent you are fine. Status, "
                  "Channels and forwarded videos are “Others”."),
    Category("news", "Newspapers", "Online and print, sports pages included. News or industry "
                                   "updates read for a job or official duty count as study or work."),
    Category("other", "Other apps", "Reels, TikTok, podcasts, anything similar."),
    Category("watching", "Videos, films, games", "On any device — phone, laptop or PC."),
]
CATEGORY_KEYS = [c.key for c in CATEGORIES]
CATEGORY_BY_KEY = {c.key: c for c in CATEGORIES}


def challenge_start() -> dt.date:
    return getattr(settings, "CHALLENGE_START", dt.date(2026, 9, 11))


def challenge_end() -> dt.date:
    return getattr(settings, "CHALLENGE_END", dt.date(2027, 1, 11))


def total_days() -> int:
    return (challenge_end() - challenge_start()).days + 1


def counts_toward_challenge(day: dt.date) -> bool:
    """Days outside the window are never scored, whatever is in the database."""
    return challenge_start() <= day <= challenge_end()


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
    # Two separate things, because somebody can be both. Razzak competes and
    # also helps run it; Mustain runs it without competing.
    competes = models.BooleanField(
        "Competing", default=True,
        help_text="On the board and in the running for the prize. "
                  "Turn off for someone who only helps run the challenge.",
    )
    can_see_everyone = models.BooleanField(
        "Can read everyone's log", default=False,
        help_text="May open any participant and read what they wrote.",
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["full_name"]

    def __str__(self) -> str:
        return self.label

    @property
    def is_claimed(self) -> bool:
        return self.user_id is not None

    @property
    def role(self) -> str:
        if self.competes and self.can_see_everyone:
            return "competing · also runs it"
        if self.can_see_everyone:
            return "runs it, not competing"
        if not self.is_claimed:
            return "not signed in yet"
        return "competing"

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
    # NO here means "talking only", not "did not open it" — see Category.answers.
    messaging = models.CharField(
        max_length=1, default=Mark.NO,
        choices=[(Mark.NO, "No"), (Mark.TALK, "Communication only"), (Mark.YES, "Others")],
    )
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
        return Mark.NO          # NO and TALK both land here — see CLEAN_MARKS

    def get_status_display_short(self) -> str:
        return {
            Mark.NO: "nothing at all",
            Mark.WORK: "only for study or work",
            Mark.YES: "a slip",
        }[self.status]

    @property
    def broke_rule(self) -> bool:
        return self.status == Mark.YES

    @property
    def is_clean(self) -> bool:
        return self.status == Mark.NO

    def rows(self):
        for c in CATEGORIES:
            value = getattr(self, c.key)
            chosen = next((o.label for o in c.options if o.value == value), value)
            yield {"key": c.key, "label": c.label, "help": c.help, "note": c.note,
                   "options": c.options, "value": value, "answer": chosen}


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
