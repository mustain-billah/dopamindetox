"""Views. Every write is scoped to the signed-in person's own row."""

from __future__ import annotations

import datetime as dt

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from . import services
from .forms import DayLogForm, ProfileForm, SignUpForm, WeeklyNoteForm
from .models import (
    DayLog,
    Mark,
    Participant,
    WeeklyNote,
    challenge_end,
    challenge_start,
    counts_toward_challenge,
    practice_from,
    total_days,
)


def get_participant(request: HttpRequest) -> Participant:
    participant = getattr(request.user, "participant", None)
    if participant is None:
        participant = Participant.objects.create(
            user=request.user,
            full_name=request.user.get_full_name() or request.user.username,
        )
    return participant


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
    """The daily form, or the closing page once the challenge is over.

    Before the start day the form is still shown, clearly marked as practice, so
    the group can try the app out. Practice answers are saved but never scored.
    """
    now = dt.date.today()
    if now > challenge_end():
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
    if date < practice_from():
        messages.error(
            request,
            f"That is too long ago. The challenge starts on {challenge_start():%-d %B %Y}.",
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
            "is_practice": not counts_toward_challenge(date),
            "prev_day": date - dt.timedelta(days=1) if date > practice_from() else None,
            "next_day": date + dt.timedelta(days=1) if date < dt.date.today() else None,
            "card": card,
            "elapsed": elapsed,
            "missed_days": max(0, elapsed - card.logged_days),
            "grid": build_grid(card),
            "marks": Mark,
        },
    )


def build_grid(card: services.Scorecard) -> list[dict]:
    """One cell per day of the challenge, for the calendar strip."""
    start, now = challenge_start(), dt.date.today()
    return [
        {
            "date": start + dt.timedelta(days=offset),
            "status": card.by_date.get(start + dt.timedelta(days=offset)) or "",
            "future": start + dt.timedelta(days=offset) > now,
            "is_today": start + dt.timedelta(days=offset) == now,
        }
        for offset in range(total_days())
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
    cards = services.leaderboard()
    return render(
        request,
        "tracker/board.html",
        {"cards": cards, "totals": services.group_totals(cards), "mine": get_participant(request)},
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
