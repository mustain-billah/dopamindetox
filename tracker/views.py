"""Views. Every write is scoped to the signed-in person's own row."""

from __future__ import annotations

import datetime as dt

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from . import services
from .forms import DayLogForm, ProfileForm, SignUpForm, WeeklyNoteForm
from .models import (
    CATEGORIES,
    DayLog,
    Mark,
    Participant,
    WeeklyNote,
    challenge_end,
    challenge_start,
    counts_toward_challenge,
    total_days,
)


def get_participant(request: HttpRequest) -> Participant:
    """This user's profile, made on the spot if they somehow have none.

    A Django staff account runs the challenge rather than competing in it, so it
    is put off the board and given the run of everyone's logs — checked on every
    visit, not only when the profile is made, since staff can be granted later.
    """
    participant = getattr(request.user, "participant", None)
    if participant is None:
        participant = Participant.objects.create(
            user=request.user,
            full_name=request.user.get_full_name() or request.user.username,
            competes=not request.user.is_staff,
            can_see_everyone=request.user.is_staff,
        )
    elif request.user.is_staff and not (participant.can_see_everyone and not participant.competes):
        participant.competes = False
        participant.can_see_everyone = True
        participant.save(update_fields=["competes", "can_see_everyone"])
    return participant


def can_see_everyone(participant: Participant, user) -> bool:
    """Reading other people's notes. Separate from whether they compete."""
    return participant.can_see_everyone or user.is_staff


def signup(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("today")
    form = SignUpForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user, backend="tracker.backends.EmailBackend")
        messages.success(request, "You're in. Fill in today to get started.")
        return redirect("today")
    return render(request, "tracker/signup.html", {"form": form})


@login_required
def today(request: HttpRequest) -> HttpResponse:
    """The daily form, or a waiting page when today is outside the challenge."""
    now = dt.date.today()
    if now < challenge_start() or now > challenge_end():
        return render(
            request,
            "tracker/waiting.html",
            {"participant": get_participant(request), "today_date": now},
        )
    return day_view(request, now.isoformat())


@login_required
def day_view(request: HttpRequest, day: str) -> HttpResponse:
    try:
        date = dt.date.fromisoformat(day)
    except ValueError:
        raise Http404("That is not a date")

    # A day only exists if it is inside the challenge and has already happened.
    if date > dt.date.today():
        messages.error(request, "You cannot fill in a day that has not happened yet.")
        return redirect("today")
    if date < challenge_start():
        messages.error(
            request,
            f"The challenge starts on {challenge_start():%-d %B %Y}. "
            "There is nothing to fill in before then.",
        )
        return redirect("today")
    if date > challenge_end():
        messages.error(
            request, f"The challenge finished on {challenge_end():%-d %B %Y}."
        )
        return redirect("today")

    participant = get_participant(request)
    # Deliberately not get_or_create: every field defaults to "No", so creating
    # the row on a page view would hand out a clean day nobody vouched for.
    log = DayLog.objects.filter(participant=participant, date=date).first() or DayLog(
        participant=participant, date=date
    )
    was_saved = log.pk is not None
    form = DayLogForm(request.POST or None, instance=log)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Saved.")
        return redirect(reverse("day", args=[date.isoformat()]))

    card = services.build_scorecard(participant)
    # Days of the challenge that have already happened, so the breakdown can
    # say how many are still blank. Zero before the challenge starts.
    elapsed = min(max(services.day_number(dt.date.today()), 0), total_days())
    missing = missing_days(card)
    return render(
        request,
        "tracker/day.html",
        {
            "participant": participant,
            "log": log,
            "form": form,
            "date": date,
            "is_today": date == dt.date.today(),
            "was_saved": was_saved,
            "prev_day": date - dt.timedelta(days=1) if date > challenge_start() else None,
            "next_day": date + dt.timedelta(days=1) if date < dt.date.today() else None,
            "card": card,
            "elapsed": elapsed,
            "missed_days": len(missing),
            "missing_days": missing[:12],
            "more_missing": max(0, len(missing) - 12),
            "grid": build_grid(card),
            "marks": Mark,
        },
    )


def build_grid(card: services.Scorecard) -> list[dict]:
    """One cell per day of the challenge, for the calendar strip.

    Past cells carry a link so the grid itself is how you go back and fill in a
    day you missed.
    """
    start, now = challenge_start(), dt.date.today()
    cells = []
    for offset in range(total_days()):
        date = start + dt.timedelta(days=offset)
        cells.append(
            {
                "date": date,
                "status": card.by_date.get(date) or "",
                "future": date > now,
                "is_today": date == now,
                "missing": date <= now and date not in card.by_date,
            }
        )
    return cells


def missing_days(card: services.Scorecard) -> list[dt.date]:
    """Days of the challenge that have happened but were never filled in."""
    start, now = challenge_start(), min(dt.date.today(), challenge_end())
    if now < start:
        return []
    return [
        start + dt.timedelta(days=offset)
        for offset in range((now - start).days + 1)
        if (start + dt.timedelta(days=offset)) not in card.by_date
    ]


@login_required
def weekly(request: HttpRequest) -> HttpResponse:
    participant = get_participant(request)
    week = services.week_number(services.clamp(dt.date.today()))
    note, _ = WeeklyNote.objects.get_or_create(participant=participant, week=week)
    form = WeeklyNoteForm(request.POST or None, instance=note)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Note saved.")
        return redirect("weekly")
    return render(
        request,
        "tracker/weekly.html",
        {"participant": participant, "week": week, "form": form, "notes": participant.notes.all()},
    )


@login_required
def board(request: HttpRequest) -> HttpResponse:
    """Everyone's totals. Read-only — there is nothing here that writes."""
    mine = get_participant(request)
    cards = services.leaderboard()
    return render(
        request,
        "tracker/board.html",
        {
            "cards": cards,
            "totals": services.group_totals(cards),
            "mine": mine,
            "can_see_all": can_see_everyone(mine, request.user),
        },
    )


@login_required
def person(request: HttpRequest, pk: int) -> HttpResponse:
    """One person's whole log, day by day. Only for those allowed to read it."""
    mine = get_participant(request)
    if not can_see_everyone(mine, request.user):
        raise Http404("No such page")

    them = get_object_or_404(Participant, pk=pk)
    card = services.build_scorecard(them)
    days = [
        log for log in them.logs.order_by("-date")
        if counts_toward_challenge(log.date)
    ]
    return render(
        request,
        "tracker/person.html",
        {
            "them": them,
            "card": card,
            "days": days,
            "grid": build_grid(card),
            "categories": CATEGORIES,
        },
    )


@login_required
def profile(request: HttpRequest) -> HttpResponse:
    participant = get_participant(request)
    form = ProfileForm(request.POST or None, instance=participant)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Details updated.")
        return redirect("profile")
    return render(request, "tracker/profile.html", {"form": form, "participant": participant})


def rules(request: HttpRequest) -> HttpResponse:
    return render(request, "tracker/rules.html", {})
