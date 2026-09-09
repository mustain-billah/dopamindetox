"""Scoring, kept out of the views so the winner rule can be tested on its own."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from .models import Mark, Participant, challenge_end, challenge_start, counts_toward_challenge


def clamp(day: dt.date) -> dt.date:
    return min(max(day, challenge_start()), challenge_end())


def day_number(day: dt.date) -> int:
    """1 on the first day of the challenge."""
    return (day - challenge_start()).days + 1


def week_number(day: dt.date) -> int:
    return max(1, (day - challenge_start()).days // 7 + 1)


@dataclass
class Scorecard:
    participant: Participant
    clean_days: int = 0
    work_days: int = 0
    used_days: int = 0
    said_no: int = 0
    streak: int = 0
    by_date: dict[dt.date, str] = field(default_factory=dict)

    @property
    def logged_days(self) -> int:
        return self.clean_days + self.work_days + self.used_days

    @property
    def on_track(self) -> bool:
        """Has never broken a rule — the group's test for winning."""
        return self.used_days == 0

    @property
    def has_joined(self) -> bool:
        return self.participant.is_claimed

    @property
    def rank_key(self) -> tuple:
        """Whoever stayed away the whole time comes first.

        Anyone who has filled in at least one day ranks above anyone who has
        not — otherwise a person who never signed in would sit at the top on
        zeroes. After that: breaking a rule counts against you first; using
        something for study or work is allowed, but a day with nothing at all
        still ranks above it; filling in more days settles what is left. Among
        people who have not started, those who have at least joined come first.
        """
        return (
            0 if self.logged_days else 1,
            self.used_days,
            self.work_days,
            -self.logged_days,
            0 if self.has_joined else 1,
            self.participant.full_name,
        )


def build_scorecard(participant: Participant, logs=None, today: dt.date | None = None) -> Scorecard:
    today = today or dt.date.today()
    logs = list(logs if logs is not None else participant.logs.all())
    card = Scorecard(participant=participant)

    # Practice days — anything logged before the challenge starts — are kept in
    # the database but never scored, so testing the app cannot inflate a total.
    for log in logs:
        if not counts_toward_challenge(log.date):
            continue
        status = log.status
        card.by_date[log.date] = status
        card.said_no += log.said_no
        if status == Mark.YES:
            card.used_days += 1
        elif status == Mark.WORK:
            card.work_days += 1
        else:
            card.clean_days += 1

    # Streak: days in a row without breaking a rule, counting back from today.
    # An unlogged today does not reset it — you may simply not have filled it in.
    cursor = today
    if card.by_date.get(cursor) is None:
        cursor = today - dt.timedelta(days=1)
    while True:
        status = card.by_date.get(cursor)
        if status is None or status == Mark.YES:
            break
        card.streak += 1
        cursor -= dt.timedelta(days=1)
    return card


def leaderboard(today: dt.date | None = None) -> list[Scorecard]:
    today = today or dt.date.today()
    cards = [
        build_scorecard(p, p.logs.all(), today=today)
        for p in Participant.objects.select_related("user").prefetch_related("logs")
    ]
    cards.sort(key=lambda c: c.rank_key)
    return cards


def group_totals(cards: list[Scorecard]) -> dict:
    return {
        "people": len(cards),
        "joined": sum(1 for c in cards if c.has_joined),
        "on_track": sum(1 for c in cards if c.on_track and c.logged_days),
        "clean_days": sum(c.clean_days for c in cards),
    }
