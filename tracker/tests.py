"""Tests for the winner rule, email login, and the ownership boundary."""

from __future__ import annotations

import datetime as dt

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from . import services
from .models import DayLog, Mark, Participant, total_days

START = dt.date(2026, 9, 11)
END = dt.date(2027, 1, 11)


@override_settings(CHALLENGE_START=START, CHALLENGE_END=END)
class Base(TestCase):
    def join(self, name, email, dept=""):
        user = User.objects.create_user(username=email, email=email, password="detox-pass-2026")
        return Participant.objects.create(user=user, full_name=name, dept=dept)

    def log(self, participant, date, **marks):
        fields = dict.fromkeys(
            ["youtube", "facebook", "instagram", "news", "other", "watching"], "N"
        )
        said_no = marks.pop("said_no", 0)
        fields.update(marks)
        return DayLog.objects.create(
            participant=participant, date=date, said_no=said_no, **fields
        )


class WindowTests(Base):
    def test_the_challenge_is_123_days(self):
        self.assertEqual(total_days(), 123)
        self.assertEqual(services.day_number(START), 1)
        self.assertEqual(services.day_number(END), 123)

    def test_weeks_start_at_one(self):
        self.assertEqual(services.week_number(START), 1)
        self.assertEqual(services.week_number(START + dt.timedelta(days=6)), 1)
        self.assertEqual(services.week_number(START + dt.timedelta(days=7)), 2)


class DayStatusTests(Base):
    def test_no_to_everything_is_a_clean_day(self):
        log = self.log(self.join("A", "a@example.com"), START)
        self.assertEqual(log.status, Mark.NO)
        self.assertTrue(log.is_clean)
        self.assertFalse(log.broke_rule)

    def test_study_or_work_use_does_not_break_the_rule(self):
        log = self.log(self.join("B", "b@example.com"), START, youtube="W")
        self.assertEqual(log.status, Mark.WORK)
        self.assertFalse(log.broke_rule)
        self.assertFalse(log.is_clean)

    def test_one_yes_breaks_the_day_even_beside_a_work_use(self):
        log = self.log(self.join("C", "c@example.com"), START, youtube="W", facebook="Y")
        self.assertEqual(log.status, Mark.YES)
        self.assertTrue(log.broke_rule)

    def test_counts_split_across_the_three_kinds_of_day(self):
        p = self.join("D", "d@example.com")
        self.log(p, START)
        self.log(p, START + dt.timedelta(days=1), instagram="W")
        self.log(p, START + dt.timedelta(days=2), news="Y")
        card = services.build_scorecard(p, today=START + dt.timedelta(days=2))
        self.assertEqual((card.clean_days, card.work_days, card.used_days), (1, 1, 1))
        self.assertEqual(card.logged_days, 3)
        self.assertFalse(card.on_track)


class StreakTests(Base):
    def test_a_work_day_keeps_the_streak_but_a_yes_ends_it(self):
        p = self.join("E", "e@example.com")
        for offset, marks in enumerate([{}, {"youtube": "W"}, {}, {}]):
            self.log(p, START + dt.timedelta(days=offset), **marks)
        self.assertEqual(services.build_scorecard(p, today=START + dt.timedelta(days=3)).streak, 4)
        self.log(p, START + dt.timedelta(days=4), facebook="Y")
        self.assertEqual(services.build_scorecard(p, today=START + dt.timedelta(days=4)).streak, 0)

    def test_a_day_you_have_not_filled_in_yet_does_not_reset_it(self):
        p = self.join("F", "f@example.com")
        self.log(p, START)
        self.log(p, START + dt.timedelta(days=1))
        self.assertEqual(services.build_scorecard(p, today=START + dt.timedelta(days=2)).streak, 2)

    def test_a_gap_of_two_days_does_end_it(self):
        p = self.join("G", "g@example.com")
        self.log(p, START)
        self.assertEqual(services.build_scorecard(p, today=START + dt.timedelta(days=3)).streak, 0)


class LeaderboardTests(Base):
    def test_whoever_stayed_away_the_whole_time_is_first(self):
        pure = self.join("Pure", "pure@example.com")
        work = self.join("Work", "work@example.com")
        broke = self.join("Broke", "broke@example.com")
        for offset in range(5):
            d = START + dt.timedelta(days=offset)
            self.log(pure, d)
            self.log(work, d, youtube="W")
            self.log(broke, d, facebook="Y" if offset == 0 else "N")
        cards = services.leaderboard(today=START + dt.timedelta(days=4))
        self.assertEqual([c.participant.full_name for c in cards], ["Pure", "Work", "Broke"])

    def test_fewer_work_days_wins_when_nobody_broke_the_rule(self):
        few = self.join("Few", "few@example.com")
        many = self.join("Many", "many@example.com")
        for offset in range(6):
            d = START + dt.timedelta(days=offset)
            self.log(few, d, youtube="W" if offset < 2 else "N")
            self.log(many, d, youtube="W" if offset < 5 else "N")
        cards = services.leaderboard(today=START + dt.timedelta(days=5))
        self.assertEqual([c.participant.full_name for c in cards], ["Few", "Many"])
        self.assertTrue(all(c.on_track for c in cards))

    def test_filling_in_more_days_settles_a_remaining_tie(self):
        keen = self.join("Keen", "keen@example.com")
        quiet = self.join("Quiet", "quiet@example.com")
        for offset in range(5):
            self.log(keen, START + dt.timedelta(days=offset))
        self.log(quiet, START)
        cards = services.leaderboard(today=START + dt.timedelta(days=4))
        self.assertEqual([c.participant.full_name for c in cards], ["Keen", "Quiet"])

    def test_group_totals(self):
        a, b = self.join("A", "a@example.com"), self.join("B", "b@example.com")
        self.log(a, START, said_no=2)
        self.log(b, START, news="Y", said_no=1)
        totals = services.group_totals(services.leaderboard(today=START))
        self.assertEqual((totals["people"], totals["on_track"], totals["said_no"]), (2, 1, 3))


class AccountTests(Base):
    def test_signup_creates_the_account_and_logs_you_in(self):
        response = self.client.post(
            reverse("signup"),
            {"full_name": "Md Manik Islam", "email": "Manik@Example.com",
             "dept": "BGE (24-25)", "password": "detox-pass-2026"},
        )
        self.assertRedirects(response, reverse("today"))
        user = User.objects.get(email="manik@example.com")
        self.assertEqual(user.participant.full_name, "Md Manik Islam")
        self.assertEqual(user.participant.dept, "BGE (24-25)")

    def test_the_same_email_cannot_join_twice(self):
        self.join("First", "taken@example.com")
        response = self.client.post(
            reverse("signup"),
            {"full_name": "Second", "email": "taken@example.com", "password": "detox-pass-2026"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already signed up")
        self.assertEqual(User.objects.filter(email__iexact="taken@example.com").count(), 1)

    def test_a_short_password_is_refused(self):
        response = self.client.post(
            reverse("signup"),
            {"full_name": "Short", "email": "short@example.com", "password": "abc"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.filter(email="short@example.com").count(), 0)

    def test_login_with_email_lands_on_today(self):
        self.join("Faruk", "faruk@example.com")
        response = self.client.post(
            reverse("login"), {"username": "faruk@example.com", "password": "detox-pass-2026"}
        )
        self.assertRedirects(response, reverse("today"))

    def test_login_is_case_insensitive_and_rejects_a_wrong_password(self):
        self.join("Omar", "omar@example.com")
        good = self.client.post(
            reverse("login"), {"username": "OMAR@example.com", "password": "detox-pass-2026"}
        )
        self.assertEqual(good.status_code, 302)
        self.client.logout()
        bad = self.client.post(
            reverse("login"), {"username": "omar@example.com", "password": "wrong-one"}
        )
        self.assertEqual(bad.status_code, 200)
        self.assertContains(bad, "do not match")

    def test_an_unknown_email_does_not_sign_anyone_in(self):
        response = self.client.post(
            reverse("login"), {"username": "nobody@example.com", "password": "detox-pass-2026"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)


class OwnershipTests(Base):
    def setUp(self):
        super().setUp()
        self.me = self.join("Me", "me@example.com", "CSE")
        self.other = self.join("Other", "other@example.com", "ICT")
        self.client.force_login(self.me.user)

    def full_day(self, **overrides):
        data = {"youtube": "N", "facebook": "N", "instagram": "N", "news": "N",
                "other": "N", "watching": "N", "said_no": 0, "instead": "", "reason": ""}
        data.update(overrides)
        return data

    def test_every_page_needs_a_login(self):
        self.client.logout()
        for name in ["today", "board", "weekly", "profile"]:
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 302, name)
            self.assertIn(reverse("login"), response["Location"], name)

    def test_opening_the_page_does_not_create_a_clean_day(self):
        response = self.client.get(reverse("today"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(DayLog.objects.count(), 0)
        self.assertContains(response, "not counted yet")
        self.assertEqual(services.build_scorecard(self.me).clean_days, 0)

    def test_the_day_counts_once_you_press_save(self):
        day = dt.date.today().isoformat()
        self.client.post(reverse("day", args=[day]), self.full_day(said_no=2, instead="walked"))
        self.assertEqual(DayLog.objects.count(), 1)
        self.assertEqual(services.build_scorecard(self.me).clean_days, 1)
        self.assertNotContains(self.client.get(reverse("today")), "not counted yet")

    def test_saving_only_ever_writes_your_own_row(self):
        day = dt.date.today().isoformat()
        self.client.post(reverse("day", args=[day]), self.full_day(youtube="W", watching="Y"))
        mine = DayLog.objects.get(participant=self.me)
        self.assertEqual((mine.youtube, mine.watching), ("W", "Y"))
        self.assertFalse(DayLog.objects.filter(participant=self.other).exists())

    def test_someone_else_signing_in_sees_their_own_empty_day(self):
        day = dt.date.today().isoformat()
        self.client.post(reverse("day", args=[day]), self.full_day(youtube="Y"))
        self.client.force_login(self.other.user)
        response = self.client.get(reverse("day", args=[day]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(DayLog.objects.filter(participant=self.other).exists())
        self.assertContains(response, "not counted yet")
        self.assertEqual(DayLog.objects.get(participant=self.me).youtube, "Y")

    def test_the_board_shows_everyone_but_can_change_nobody(self):
        self.log(self.other, START, news="Y")
        body = self.client.get(reverse("board")).content.decode()
        self.assertIn("Other", body)
        for marker in ['name="youtube"', 'name="said_no"', "/day/"]:
            self.assertNotIn(marker, body)
        self.assertEqual(body.count("<form"), 1)  # only the nav's log-out button
        self.assertIn('action="/logout/"', body)

    def test_a_future_day_is_refused(self):
        tomorrow = (dt.date.today() + dt.timedelta(days=1)).isoformat()
        self.assertRedirects(self.client.get(reverse("day", args=[tomorrow])), reverse("today"))

    def test_a_nonsense_date_is_a_404(self):
        self.assertEqual(self.client.get(reverse("day", args=["not-a-date"])).status_code, 404)

    def test_saving_twice_updates_rather_than_duplicates(self):
        day = dt.date.today().isoformat()
        self.client.post(reverse("day", args=[day]), self.full_day(said_no=1))
        self.client.post(reverse("day", args=[day]), self.full_day(said_no=5))
        self.assertEqual(DayLog.objects.filter(participant=self.me).count(), 1)
        self.assertEqual(DayLog.objects.get(participant=self.me).said_no, 5)

    def test_a_past_day_can_still_be_filled_in(self):
        yesterday = (dt.date.today() - dt.timedelta(days=1)).isoformat()
        self.client.post(reverse("day", args=[yesterday]), self.full_day(facebook="Y"))
        self.assertEqual(DayLog.objects.get(participant=self.me).facebook, "Y")

    def test_weekly_note_is_kept_per_week(self):
        self.assertEqual(self.client.post(
            reverse("weekly"), {"hardest": "mornings", "easier": "sleeping"}
        ).status_code, 302)
        self.assertEqual(self.me.notes.get().hardest, "mornings")

    def test_rules_are_readable_without_an_account(self):
        self.client.logout()
        response = self.client.get(reverse("rules"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nobody")
        self.assertContains(response, "123 days")
