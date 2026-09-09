"""Tests for the winner rule, email login, and the ownership boundary."""

from __future__ import annotations

import datetime as dt

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from . import services
from .models import DayLog, Mark, Participant, WeeklyNote, total_days

START = dt.date(2026, 9, 11)
END = dt.date(2027, 1, 11)

# A window that actually contains today, for the tests that drive the daily
# form. The real challenge starts on 11 September 2026, so a test that posts
# to "today" needs a running challenge, not the real dates.
LIVE_START = dt.date.today() - dt.timedelta(days=30)
LIVE_END = LIVE_START + dt.timedelta(days=122)


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
    def order_of(self, *names, today=None):
        """Ranking restricted to the people this test made.

        The roster migration pre-creates everyone in the real group, so the
        board always holds more rows than a test set up itself.
        """
        wanted = set(names)
        return [
            c.participant.full_name
            for c in services.leaderboard(today=today)
            if c.participant.full_name in wanted
        ]

    def test_whoever_stayed_away_the_whole_time_is_first(self):
        pure = self.join("Pure", "pure@example.com")
        work = self.join("Work", "work@example.com")
        broke = self.join("Broke", "broke@example.com")
        for offset in range(5):
            d = START + dt.timedelta(days=offset)
            self.log(pure, d)
            self.log(work, d, youtube="W")
            self.log(broke, d, facebook="Y" if offset == 0 else "N")
        self.assertEqual(
            self.order_of("Pure", "Work", "Broke", today=START + dt.timedelta(days=4)),
            ["Pure", "Work", "Broke"],
        )

    def test_fewer_work_days_wins_when_nobody_broke_the_rule(self):
        few = self.join("Few", "few@example.com")
        many = self.join("Many", "many@example.com")
        for offset in range(6):
            d = START + dt.timedelta(days=offset)
            self.log(few, d, youtube="W" if offset < 2 else "N")
            self.log(many, d, youtube="W" if offset < 5 else "N")
        self.assertEqual(
            self.order_of("Few", "Many", today=START + dt.timedelta(days=5)), ["Few", "Many"]
        )

    def test_filling_in_more_days_settles_a_remaining_tie(self):
        keen = self.join("Keen", "keen@example.com")
        quiet = self.join("Quiet", "quiet@example.com")
        for offset in range(5):
            self.log(keen, START + dt.timedelta(days=offset))
        self.log(quiet, START)
        self.assertEqual(
            self.order_of("Keen", "Quiet", today=START + dt.timedelta(days=4)), ["Keen", "Quiet"]
        )

    def test_group_totals_count_the_whole_list_not_just_the_active(self):
        a, b = self.join("A", "a@example.com"), self.join("B", "b@example.com")
        self.log(a, START, said_no=2)
        self.log(b, START, news="Y", said_no=1)
        totals = services.group_totals(services.leaderboard(today=START))
        self.assertEqual(totals["people"], Participant.objects.count())
        self.assertEqual(totals["joined"], 2)
        self.assertEqual(totals["on_track"], 1)
        self.assertNotIn("said_no", totals)  # a self-reported number, not a group figure


class AccountTests(Base):
    def test_someone_not_on_the_list_can_still_add_themselves(self):
        response = self.client.post(
            reverse("signup"),
            {"who": "", "full_name": "Md Manik Islam", "email": "Manik@Example.com",
             "dept": "BGE", "session": "24-25", "password": "detox-pass-2026"},
        )
        self.assertRedirects(response, reverse("today"))
        user = User.objects.get(email="manik@example.com")
        self.assertEqual(user.participant.full_name, "Md Manik Islam")
        self.assertEqual(user.participant.where, "BGE (24-25)")

    def test_the_same_email_cannot_join_twice(self):
        self.join("First", "taken@example.com")
        response = self.client.post(
            reverse("signup"),
            {"who": "", "full_name": "Second", "email": "taken@example.com",
             "password": "detox-pass-2026"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already signed up")
        self.assertEqual(User.objects.filter(email__iexact="taken@example.com").count(), 1)

    def test_a_short_password_is_refused(self):
        response = self.client.post(
            reverse("signup"),
            {"who": "", "full_name": "Short", "email": "short@example.com", "password": "abc"},
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


@override_settings(CHALLENGE_START=LIVE_START, CHALLENGE_END=LIVE_END)
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
        self.assertContains(response, "Not counted yet")
        self.assertEqual(services.build_scorecard(self.me).clean_days, 0)

    def test_the_day_counts_once_you_press_save(self):
        day = dt.date.today().isoformat()
        self.client.post(reverse("day", args=[day]), self.full_day(said_no=2, instead="walked"))
        self.assertEqual(DayLog.objects.count(), 1)
        self.assertEqual(services.build_scorecard(self.me).clean_days, 1)
        self.assertNotContains(self.client.get(reverse("today")), "Not counted yet")

    def test_saving_only_ever_writes_your_own_row(self):
        day = dt.date.today().isoformat()
        self.client.post(reverse("day", args=[day]),
                         self.full_day(youtube="W", watching="Y", reason="Lab tutorial"))
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
        self.assertContains(response, "Not counted yet")
        self.assertEqual(DayLog.objects.get(participant=self.me).youtube, "Y")

    def test_the_board_shows_everyone_but_can_change_nobody(self):
        self.log(self.other, LIVE_START, news="Y")
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


@override_settings(CHALLENGE_START=LIVE_START, CHALLENGE_END=LIVE_END)
class BreakdownTests(Base):
    """The three day types must add up, and the blank count must be right."""

    def setUp(self):
        super().setUp()
        self.me = self.join("Me", "me@example.com")
        self.client.force_login(self.me.user)

    def test_the_three_kinds_of_day_add_up_to_what_was_filled_in(self):
        for offset, marks in enumerate([{}, {}, {"youtube": "W"}, {"news": "Y"}]):
            self.log(self.me, dt.date.today() - dt.timedelta(days=offset), **marks)
        card = services.build_scorecard(self.me)
        self.assertEqual(card.clean_days + card.work_days + card.used_days, card.logged_days)
        self.assertEqual(card.logged_days, 4)

    @override_settings(CHALLENGE_START=dt.date.today() - dt.timedelta(days=9),
                       CHALLENGE_END=dt.date.today() + dt.timedelta(days=10))
    def test_not_filled_in_counts_only_days_that_have_happened(self):
        for offset in range(3):
            self.log(self.me, dt.date.today() - dt.timedelta(days=offset))
        response = self.client.get(reverse("today"))
        # Ten days have passed, three are filled in, so seven are blank —
        # the ten days still ahead must not be counted as missed.
        self.assertEqual(response.context["elapsed"], 10)
        self.assertEqual(response.context["missed_days"], 7)

    @override_settings(CHALLENGE_START=dt.date.today() + dt.timedelta(days=5),
                       CHALLENGE_END=dt.date.today() + dt.timedelta(days=100))
    def test_before_the_start_there_is_no_day_page_at_all(self):
        response = self.client.get(reverse("today"))
        self.assertTemplateUsed(response, "tracker/waiting.html")
        self.assertNotIn("missed_days", response.context)

    def test_the_day_page_no_longer_says_streak_clean_or_said_no(self):
        response = self.client.get(reverse("today"))
        body = response.content.decode()
        for gone in ["Times you said no", "Clean days", ">Streak<"]:
            self.assertNotIn(gone, body)
        for wanted in ["Days in a row", "Times you stopped yourself",
                       "nothing at all", "only for study or work", "you slipped"]:
            self.assertIn(wanted, body)


@override_settings(CHALLENGE_START=START, CHALLENGE_END=END)
class RosterTests(TestCase):
    """Everyone who said they were joining exists before anyone signs up."""

    def test_the_migration_created_the_whole_roster(self):
        from .roster import ROSTER
        self.assertEqual(Participant.objects.count(), len(ROSTER))
        self.assertEqual(Participant.objects.filter(user__isnull=True).count(), len(ROSTER))

    def test_both_people_called_sabbir_hossen_are_separate_rows(self):
        both = Participant.objects.filter(full_name="Sabbir Hossen").order_by("dept")
        self.assertEqual(both.count(), 2)
        self.assertEqual([p.where for p in both], ["CPS (21-22)", "TEX (24-25)"])

    def test_details_carry_the_department_and_session_they_gave(self):
        razzak = Participant.objects.get(full_name="Muhammad Abdur Razzak")
        self.assertEqual(razzak.where, "BGE (2005-06)")
        self.assertTrue(razzak.is_past_student)
        self.assertEqual(razzak.label, "Muhammad Abdur Razzak — BGE (2005-06)")
        current = Participant.objects.get(full_name="Md Manik Islam")
        self.assertFalse(current.is_past_student)

    def test_someone_with_no_session_still_reads_cleanly(self):
        shahadat = Participant.objects.get(full_name="Md. Shahadat Hossain")
        self.assertEqual(shahadat.where, "CSE")

    def test_sync_is_safe_to_run_again(self):
        from .roster import sync
        before = Participant.objects.count()
        result = sync(Participant)
        self.assertEqual(result["created"], 0)
        self.assertEqual(Participant.objects.count(), before)

    def test_sync_never_overwrites_a_claimed_row(self):
        from .roster import sync
        person = Participant.objects.get(full_name="Ziaul Haq")
        user = User.objects.create_user(username="z@example.com", email="z@example.com",
                                        password="detox-pass-2026")
        person.user = user
        person.session = "2006-2007"          # they corrected it themselves
        person.save()
        sync(Participant)
        person.refresh_from_db()
        self.assertEqual(person.session, "2006-2007")


@override_settings(CHALLENGE_START=START, CHALLENGE_END=END)
class ClaimTests(TestCase):
    """Signing up attaches you to the row that already has your details."""

    def claim(self, person, email="me@example.com", **extra):
        data = {"who": person.pk if person else "", "email": email,
                "password": "detox-pass-2026"}
        data.update(extra)
        return self.client.post(reverse("signup"), data)

    def test_picking_your_name_keeps_the_details_you_already_gave(self):
        person = Participant.objects.get(full_name="Mohammad Abdur Rashed")
        response = self.claim(person, "rashed@example.com")
        self.assertRedirects(response, reverse("today"))
        person.refresh_from_db()
        self.assertTrue(person.is_claimed)
        self.assertEqual(person.user.email, "rashed@example.com")
        self.assertEqual(person.where, "ESRM (2003-04)")
        # No second row was invented for the same person.
        self.assertEqual(Participant.objects.filter(full_name="Mohammad Abdur Rashed").count(), 1)

    def test_a_claimed_name_disappears_from_the_list(self):
        person = Participant.objects.get(full_name="Omar Faruk")
        self.claim(person, "omar@example.com")
        self.client.logout()
        response = self.client.get(reverse("signup"))
        self.assertNotContains(response, "Omar Faruk")
        self.assertContains(response, "Nasib Iqbal")

    def test_the_same_name_cannot_be_claimed_twice(self):
        person = Participant.objects.get(full_name="Nasib Iqbal")
        self.claim(person, "first@example.com")
        self.client.logout()
        response = self.claim(person, "second@example.com")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "just claimed that name")
        self.assertEqual(User.objects.filter(email="second@example.com").count(), 0)

    def test_choosing_nobody_and_typing_nothing_is_refused(self):
        response = self.claim(None, "blank@example.com")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pick your name from the list")
        self.assertEqual(User.objects.count(), 0)

    def test_the_signup_page_lists_everyone_who_has_not_claimed(self):
        response = self.client.get(reverse("signup"))
        self.assertContains(response, "Muhammad Abdur Razzak — BGE (2005-06)")
        self.assertContains(response, "19 people on the list")

    def test_the_dropdown_asks_you_to_choose_rather_than_defaulting_to_not_listed(self):
        body = self.client.get(reverse("signup")).content.decode()
        first_option = body.split("<select", 1)[1].split("<option", 2)[1]
        self.assertIn("Choose your name", first_option)


@override_settings(CHALLENGE_START=START, CHALLENGE_END=END)
class BoardWithRosterTests(TestCase):
    def setUp(self):
        super().setUp()
        self.person = Participant.objects.get(full_name="Ziaul Haq")
        user = User.objects.create_user(username="z@example.com", email="z@example.com",
                                        password="detox-pass-2026")
        self.person.user = user
        self.person.save()
        self.client.force_login(user)

    def test_the_board_shows_everyone_including_people_who_have_not_joined(self):
        response = self.client.get(reverse("board"))
        self.assertEqual(len(response.context["cards"]), Participant.objects.count())
        self.assertContains(response, "Not joined yet")
        self.assertContains(response, "has not signed in yet")
        self.assertEqual(response.context["totals"]["joined"], 1)

    def test_someone_who_has_never_signed_in_does_not_top_the_board(self):
        DayLog.objects.create(participant=self.person, date=START,
                              youtube="N", facebook="N", instagram="N",
                              news="Y", other="N", watching="N")
        cards = services.leaderboard(today=START)
        # Ziaul slipped once, but the eighteen people on zero have not started
        # at all, so he still ranks above them.
        self.assertEqual(cards[0].participant.full_name, "Ziaul Haq")
        self.assertFalse(cards[1].has_joined)


class ChallengeWindowViewTests(Base):
    """Nothing can be logged outside 11 Sep 2026 – 11 Jan 2027."""

    def setUp(self):
        super().setUp()
        self.me = self.join("Me", "me@example.com")
        self.client.force_login(self.me.user)

    def full_day(self, **overrides):
        data = {"youtube": "N", "facebook": "N", "instagram": "N", "news": "N",
                "other": "N", "watching": "N", "said_no": 0, "instead": "", "reason": ""}
        data.update(overrides)
        return data

    @override_settings(CHALLENGE_START=dt.date.today() + dt.timedelta(days=2),
                       CHALLENGE_END=dt.date.today() + dt.timedelta(days=124))
    def test_before_it_starts_you_get_a_countdown_not_a_form(self):
        response = self.client.get(reverse("today"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "tracker/waiting.html")
        self.assertContains(response, "2 days to go")
        self.assertNotContains(response, 'name="youtube"')

    @override_settings(CHALLENGE_START=dt.date.today() + dt.timedelta(days=2),
                       CHALLENGE_END=dt.date.today() + dt.timedelta(days=124))
    def test_the_countdown_counts_to_the_start_not_to_the_end(self):
        body = self.client.get(reverse("today")).content.decode()
        self.assertIn("starts in 2 days", body)
        self.assertNotIn("starts in 124 days", body)
    @override_settings(CHALLENGE_START=dt.date.today() - dt.timedelta(days=200),
                       CHALLENGE_END=dt.date.today() - dt.timedelta(days=2))
    def test_after_it_ends_the_form_is_closed(self):
        response = self.client.get(reverse("today"))
        self.assertTemplateUsed(response, "tracker/waiting.html")
        self.assertContains(response, "the four months")
        late = (dt.date.today() - dt.timedelta(days=1)).isoformat()
        self.client.post(reverse("day", args=[late]), self.full_day())
        self.assertEqual(DayLog.objects.count(), 0)

    @override_settings(CHALLENGE_START=dt.date.today() - dt.timedelta(days=3),
                       CHALLENGE_END=dt.date.today() + dt.timedelta(days=119))
    def test_the_first_day_has_no_previous_day_link(self):
        first = (dt.date.today() - dt.timedelta(days=3)).isoformat()
        response = self.client.get(reverse("day", args=[first]))
        self.assertIsNone(response.context["prev_day"])
        self.assertNotContains(response, "Previous day")


class AlreadyFilledInTests(Base):
    """Coming back to a day you have done should say so."""

    def setUp(self):
        super().setUp()
        self.me = self.join("Me", "me@example.com")
        self.client.force_login(self.me.user)

    @override_settings(CHALLENGE_START=dt.date.today() - dt.timedelta(days=3),
                       CHALLENGE_END=dt.date.today() + dt.timedelta(days=119))
    def test_an_empty_day_asks_you_to_save(self):
        response = self.client.get(reverse("today"))
        self.assertContains(response, "Not counted yet")
        self.assertContains(response, ">Save<")
        self.assertNotContains(response, "Filled in already")

    @override_settings(CHALLENGE_START=dt.date.today() - dt.timedelta(days=3),
                       CHALLENGE_END=dt.date.today() + dt.timedelta(days=119))
    def test_a_filled_day_says_so_and_offers_an_update(self):
        self.client.post(
            reverse("day", args=[dt.date.today().isoformat()]),
            {"youtube": "W", "facebook": "N", "instagram": "N", "news": "N",
             "other": "N", "watching": "N", "said_no": 2, "instead": "walked", "reason": "lecture"},
        )
        response = self.client.get(reverse("today"))
        self.assertContains(response, "Filled in already")
        self.assertContains(response, "only for study or work")
        self.assertContains(response, ">Update<")
        self.assertNotContains(response, "Not counted yet")
        # and the answers come back selected, not blank
        self.assertContains(response, 'id="youtube_W" checked')

    @override_settings(CHALLENGE_START=dt.date.today() - dt.timedelta(days=3),
                       CHALLENGE_END=dt.date.today() + dt.timedelta(days=119))
    def test_the_board_no_longer_shows_the_self_reported_counter(self):
        body = self.client.get(reverse("board")).content.decode()
        self.assertNotIn("Times someone stopped themselves", body)
        self.assertNotIn(">Stopped<", body)
        # but it is still on your own page
        self.assertIn("Times you stopped yourself",
                      self.client.get(reverse("today")).content.decode())


@override_settings(CHALLENGE_START=LIVE_START, CHALLENGE_END=LIVE_END)
class TrialRunTests(Base):
    """A trial run is the real app plus an honest banner, and a way to wipe it."""

    def setUp(self):
        super().setUp()
        self.me = self.join("Me", "me@example.com")
        self.client.force_login(self.me.user)

    @override_settings(CHALLENGE_TEST_MODE=True,
                       CHALLENGE_REAL_START=dt.date(2026, 9, 11))
    def test_the_banner_names_the_real_start_date(self):
        response = self.client.get(reverse("today"))
        self.assertContains(response, "Trial run")
        self.assertContains(response, "11 September 2026")

    @override_settings(CHALLENGE_TEST_MODE=False)
    def test_no_banner_once_the_trial_is_over(self):
        self.assertNotContains(self.client.get(reverse("today")), "Trial run")

    def test_reset_clears_the_answers_but_keeps_people_signed_up(self):
        from django.core.management import call_command
        from io import StringIO
        from django.contrib.auth.models import User

        self.log(self.me, LIVE_START)
        self.client.post(reverse("weekly"), {"hardest": "mornings", "easier": "sleep"})
        self.assertEqual(DayLog.objects.count(), 1)
        self.assertEqual(WeeklyNote.objects.count(), 1)
        users_before = User.objects.count()

        out = StringIO()
        call_command("reset_challenge", stdout=out)             # dry run
        self.assertEqual(DayLog.objects.count(), 1)
        self.assertIn("Run again with --yes", out.getvalue())

        call_command("reset_challenge", "--yes", stdout=StringIO())
        self.assertEqual(DayLog.objects.count(), 0)
        self.assertEqual(WeeklyNote.objects.count(), 0)
        self.assertEqual(User.objects.count(), users_before)     # nobody signs up again
        self.me.refresh_from_db()
        self.assertTrue(self.me.is_claimed)
        from .roster import ROSTER
        self.assertGreaterEqual(Participant.objects.count(), len(ROSTER))

    def test_reset_with_accounts_puts_everyone_back_to_unclaimed(self):
        from django.core.management import call_command
        from io import StringIO

        call_command("reset_challenge", "--yes", "--accounts", stdout=StringIO())
        self.me.refresh_from_db()
        self.assertFalse(self.me.is_claimed)
        self.assertEqual(Participant.objects.filter(user__isnull=False).count(), 0)


class MissingDayTests(Base):
    """Forgetting a day should be obvious and one tap to fix."""

    def setUp(self):
        super().setUp()
        self.me = self.join("Me", "me@example.com")
        self.client.force_login(self.me.user)

    WINDOW = dict(CHALLENGE_START=dt.date.today() - dt.timedelta(days=5),
                  CHALLENGE_END=dt.date.today() + dt.timedelta(days=117))

    def full_day(self, **overrides):
        data = {"youtube": "N", "facebook": "N", "instagram": "N", "news": "N",
                "other": "N", "watching": "N", "said_no": 0, "instead": "", "reason": ""}
        data.update(overrides)
        return data

    @override_settings(**WINDOW)
    def test_every_gap_is_listed_with_a_link(self):
        start = dt.date.today() - dt.timedelta(days=5)
        for offset in (0, 2, 5):                       # fill three of the six days
            self.log(self.me, start + dt.timedelta(days=offset))
        response = self.client.get(reverse("today"))
        missing = response.context["missing_days"]
        self.assertEqual(missing, [start + dt.timedelta(days=o) for o in (1, 3, 4)])
        self.assertEqual(response.context["missed_days"], 3)
        for d in missing:
            self.assertContains(response, reverse("day", args=[d.isoformat()]))

    @override_settings(**WINDOW)
    def test_days_still_ahead_are_never_called_missing(self):
        response = self.client.get(reverse("today"))
        self.assertEqual(len(response.context["missing_days"]), 6)   # start..today
        tomorrow = dt.date.today() + dt.timedelta(days=1)
        self.assertNotIn(tomorrow, response.context["missing_days"])

    @override_settings(**WINDOW)
    def test_filling_a_gap_removes_it_from_the_list(self):
        gap = (dt.date.today() - dt.timedelta(days=3))
        self.assertIn(gap, self.client.get(reverse("today")).context["missing_days"])
        self.client.post(reverse("day", args=[gap.isoformat()]), self.full_day(news="Y"))
        response = self.client.get(reverse("today"))
        self.assertNotIn(gap, response.context["missing_days"])
        card = services.build_scorecard(self.me)
        self.assertEqual(card.used_days, 1)          # and it counts, backdated

    @override_settings(**WINDOW)
    def test_past_squares_link_to_their_day_and_future_ones_do_not(self):
        body = self.client.get(reverse("today")).content.decode()
        yesterday = dt.date.today() - dt.timedelta(days=1)
        tomorrow = dt.date.today() + dt.timedelta(days=1)
        self.assertIn('href="' + reverse("day", args=[yesterday.isoformat()]) + '"', body)
        self.assertNotIn('href="' + reverse("day", args=[tomorrow.isoformat()]) + '"', body)

    @override_settings(**WINDOW)
    def test_the_gap_list_is_capped_but_says_how_many_more(self):
        with self.settings(CHALLENGE_START=dt.date.today() - dt.timedelta(days=20),
                           CHALLENGE_END=dt.date.today() + dt.timedelta(days=102)):
            response = self.client.get(reverse("today"))
            self.assertEqual(len(response.context["missing_days"]), 12)
            self.assertEqual(response.context["more_missing"], 9)   # 21 days, 12 shown
            self.assertContains(response, "and 9 more")

    @override_settings(**WINDOW)
    def test_no_gap_list_when_everything_is_filled_in(self):
        start = dt.date.today() - dt.timedelta(days=5)
        for offset in range(6):
            self.log(self.me, start + dt.timedelta(days=offset))
        response = self.client.get(reverse("today"))
        self.assertEqual(response.context["missing_days"], [])
        self.assertNotContains(response, "Days you have not filled in")




@override_settings(CHALLENGE_START=LIVE_START, CHALLENGE_END=LIVE_END)
class RoleTests(Base):
    """Competing and reading everyone's log are separate — somebody can do both."""

    def setUp(self):
        super().setUp()
        # Mustain: runs it, does not compete, and is Django staff.
        self.owner = self.join("Mustain Billah", "owner@example.com")
        self.owner.user.is_staff = True
        self.owner.user.save()
        self.owner.competes = False
        self.owner.can_see_everyone = True
        self.owner.save()
        # Razzak: competes AND helps run it.
        self.razzak = self.join("Muhammad Abdur Razzak", "razzak@example.com", "BGE")
        self.razzak.can_see_everyone = True
        self.razzak.save()
        # An ordinary competitor.
        self.player = self.join("A Player", "player@example.com", "CSE")
        self.log(self.player, LIVE_START, youtube="W", said_no=2)
        DayLog.objects.filter(participant=self.player).update(
            instead="Read 30 pages", reason="Class lecture"
        )

    def test_someone_can_compete_and_still_read_everyone(self):
        self.assertEqual(self.razzak.role, "competing · also runs it")
        names = [c.participant.full_name for c in services.leaderboard()]
        self.assertIn("Muhammad Abdur Razzak", names)     # still on the board
        self.assertNotIn("Mustain Billah", names)         # the other one is not

        self.client.force_login(self.razzak.user)
        response = self.client.get(reverse("person", args=[self.player.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Read 30 pages")
        self.assertContains(response, "Class lecture")

    def test_a_plain_competitor_still_cannot_read_anyone(self):
        self.client.force_login(self.player.user)
        self.assertEqual(
            self.client.get(reverse("person", args=[self.razzak.pk])).status_code, 404
        )
        self.assertNotContains(self.client.get(reverse("board")), "Open</a>")

    def test_the_organiser_note_on_the_board_is_hidden_from_competitors(self):
        """The 'You help run this' line is for organisers, not the whole group."""
        note = "You help run this"
        self.client.force_login(self.player.user)
        self.assertNotContains(self.client.get(reverse("board")), note)
        for who in (self.owner, self.razzak):
            self.client.force_login(who.user)
            self.assertContains(self.client.get(reverse("board")), note)

    def test_open_links_appear_for_both_kinds_of_organiser(self):
        for who in (self.owner, self.razzak):
            self.client.force_login(who.user)
            self.assertContains(
                self.client.get(reverse("board")), "/board/%d/" % self.player.pk
            )

    def test_a_staff_account_is_taken_off_the_board_on_sight(self):
        late = self.join("Late Admin", "late@example.com")
        self.assertIn("Late Admin", [c.participant.full_name for c in services.leaderboard()])
        late.user.is_staff = True
        late.user.save()
        self.client.force_login(late.user)
        self.client.get(reverse("today"))
        late.refresh_from_db()
        self.assertFalse(late.competes)
        self.assertTrue(late.can_see_everyone)
        self.assertNotIn("Late Admin", [c.participant.full_name for c in services.leaderboard()])

    def test_set_role_grants_and_revokes(self):
        from django.core.management import call_command
        from io import StringIO

        helper = self.join("Helper", "helper@example.com")
        call_command("set_role", "helper@example.com", "--admin", stdout=StringIO())
        helper.refresh_from_db()
        self.assertTrue(helper.can_see_everyone)
        self.assertTrue(helper.competes)          # untouched
        self.assertEqual(helper.role, "competing · also runs it")

        call_command("set_role", "helper@example.com", "--not-competing", stdout=StringIO())
        helper.refresh_from_db()
        self.assertEqual(helper.role, "runs it, not competing")

        call_command("set_role", "helper@example.com", "--no-admin", "--competing",
                     stdout=StringIO())
        helper.refresh_from_db()
        self.assertEqual(helper.role, "competing")

    def test_set_role_will_not_fight_the_staff_rule(self):
        from django.core.management import call_command
        from django.core.management.base import CommandError
        for flag in ("--no-admin", "--competing"):
            with self.assertRaises(CommandError):
                call_command("set_role", "owner@example.com", flag)

    def test_set_role_reports_without_changing_when_given_no_flags(self):
        from django.core.management import call_command
        from io import StringIO
        out = StringIO()
        call_command("set_role", "razzak@example.com", stdout=out)
        self.assertIn("Nothing changed", out.getvalue())
        self.razzak.refresh_from_db()
        self.assertTrue(self.razzak.competes and self.razzak.can_see_everyone)

    def test_roles_listing_counts_the_two_things_separately(self):
        from django.core.management import call_command
        from io import StringIO
        out = StringIO()
        call_command("roles", stdout=out)
        text = out.getvalue()
        self.assertIn("competing · also runs it", text)
        self.assertIn("runs it, not competing", text)
        self.assertIn("2 can read everyone's log", text)

    def test_the_rules_page_still_warns_people(self):
        self.client.force_login(self.player.user)
        self.assertContains(self.client.get(reverse("rules")), "can open any participant")


@override_settings(CHALLENGE_START=LIVE_START, CHALLENGE_END=LIVE_END)
class EvidenceTests(Base):
    """"Fine with evidence of official use" — the reason box is the evidence."""

    def setUp(self):
        super().setUp()
        self.me = self.join("Me", "me@example.com")
        self.client.force_login(self.me.user)
        self.url = reverse("day", args=[dt.date.today().isoformat()])

    def answers(self, **overrides):
        data = {"youtube": "N", "facebook": "N", "instagram": "N", "news": "N",
                "other": "N", "watching": "N", "said_no": 0, "instead": "", "reason": ""}
        data.update(overrides)
        return data

    def test_a_study_or_work_day_needs_a_reason(self):
        response = self.client.post(self.url, self.answers(youtube="W"))
        self.assertEqual(response.status_code, 200)          # not saved
        self.assertEqual(DayLog.objects.count(), 0)
        self.assertContains(response, "this is the evidence")

    def test_a_study_or_work_day_saves_once_a_reason_is_given(self):
        response = self.client.post(
            self.url, self.answers(youtube="W", reason="Lab tutorial for the course")
        )
        self.assertEqual(response.status_code, 302)
        log = DayLog.objects.get()
        self.assertEqual(log.youtube, "W")
        self.assertEqual(log.reason, "Lab tutorial for the course")

    def test_whitespace_is_not_evidence(self):
        self.client.post(self.url, self.answers(news="W", reason="   "))
        self.assertEqual(DayLog.objects.count(), 0)

    def test_owning_up_to_a_slip_needs_no_reason(self):
        """Admitting a slip must stay the easy path, not the one with an error."""
        response = self.client.post(self.url, self.answers(facebook="Y"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(DayLog.objects.get().broke_rule)

    def test_a_clean_day_needs_no_reason(self):
        self.assertEqual(self.client.post(self.url, self.answers()).status_code, 302)
        self.assertEqual(DayLog.objects.count(), 1)

    def test_newspapers_now_state_the_work_exception(self):
        response = self.client.get(reverse("today"))
        self.assertContains(response, "industry updates read for a job or official duty")

    def test_the_rules_say_a_work_day_keeps_you_in_the_competition(self):
        response = self.client.get(reverse("rules"))
        self.assertContains(response, "does not put you out of the competition")
        self.assertContains(response, "whoever used none of these at all comes first")


@override_settings(CHALLENGE_START=LIVE_START, CHALLENGE_END=LIVE_END)
class WinnerPriorityTests(Base):
    """The stated rule: work days keep you in, but a pure record is ranked first."""

    def test_a_work_day_beats_a_slip_but_loses_to_a_pure_record(self):
        pure = self.join("Pure", "pure@example.com")
        worked = self.join("Worked", "worked@example.com")
        slipped = self.join("Slipped", "slipped@example.com")
        for offset in range(10):
            d = LIVE_START + dt.timedelta(days=offset)
            self.log(pure, d)
            self.log(worked, d, youtube="W" if offset < 4 else "N")
            self.log(slipped, d, news="Y" if offset == 0 else "N")

        order = [c.participant.full_name for c in services.leaderboard()
                 if c.participant.full_name in {"Pure", "Worked", "Slipped"}]
        self.assertEqual(order, ["Pure", "Worked", "Slipped"])

        by_name = {c.participant.full_name: c for c in services.leaderboard()}
        # everyone who never slipped is still in it, work days or not
        self.assertTrue(by_name["Pure"].on_track)
        self.assertTrue(by_name["Worked"].on_track)
        self.assertFalse(by_name["Slipped"].on_track)
        self.assertEqual(by_name["Worked"].work_days, 4)


@override_settings(CHALLENGE_START=LIVE_START, CHALLENGE_END=LIVE_END)
class NotSavedWarningTests(Base):
    """A refused day must say so at the top, where people actually look."""

    def setUp(self):
        super().setUp()
        self.me = self.join("Me", "me@example.com")
        self.client.force_login(self.me.user)
        self.url = reverse("day", args=[dt.date.today().isoformat()])

    def answers(self, **overrides):
        data = {"youtube": "N", "facebook": "N", "instagram": "N", "news": "N",
                "other": "N", "watching": "N", "said_no": 0, "instead": "", "reason": ""}
        data.update(overrides)
        return data

    def test_a_refused_day_warns_at_the_top_and_beside_the_field(self):
        response = self.client.post(self.url, self.answers(youtube="W"))
        body = response.content.decode()
        self.assertEqual(DayLog.objects.count(), 0)
        # the page-level message, above everything
        self.assertContains(response, "Nothing was saved")
        # the banner in the form header
        self.assertContains(response, "Not saved yet")
        # and still the specific message next to the reason box
        self.assertIn("this is the evidence", body)
        # the warning comes before the reason field, not only after it
        self.assertLess(body.index("Nothing was saved"), body.index('name="reason"'))

    def test_no_warning_when_the_day_saves(self):
        response = self.client.post(
            self.url, self.answers(youtube="W", reason="Lab tutorial"), follow=True
        )
        self.assertContains(response, "Saved.")
        self.assertNotContains(response, "Nothing was saved")
        self.assertNotContains(response, "Not saved yet")




@override_settings(CHALLENGE_START=LIVE_START, CHALLENGE_END=LIVE_END)
class MyRecordTests(Base):
    """Everyone can read their own whole log, the way an organiser reads others."""

    def setUp(self):
        super().setUp()
        self.me = self.join("Me", "me@example.com", "CSE")
        self.other = self.join("Other", "other@example.com", "ICT")
        self.client.force_login(self.me.user)
        self.log(self.me, LIVE_START, youtube="W", said_no=3)
        DayLog.objects.filter(participant=self.me).update(
            instead="Read 30 pages", reason="Lab tutorial"
        )
        self.log(self.me, LIVE_START + dt.timedelta(days=1), news="Y")

    def test_my_record_shows_everything_i_wrote(self):
        response = self.client.get(reverse("my_record"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "My record")
        self.assertContains(response, "Read 30 pages")
        self.assertContains(response, "Lab tutorial")
        self.assertContains(response, "You stopped yourself")
        self.assertTrue(response.context["is_me"])

    def test_my_own_dates_link_back_to_the_day_so_i_can_change_them(self):
        response = self.client.get(reverse("my_record"))
        self.assertContains(response, reverse("day", args=[LIVE_START.isoformat()]))

    def test_my_email_is_not_repeated_at_me(self):
        self.assertNotContains(self.client.get(reverse("my_record")), "me@example.com")

    def test_i_can_open_my_own_record_by_id_as_well(self):
        response = self.client.get(reverse("person", args=[self.me.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["is_me"])

    def test_but_still_not_anybody_elses(self):
        self.assertEqual(
            self.client.get(reverse("person", args=[self.other.pk])).status_code, 404
        )

    def test_an_organiser_reading_someone_else_gets_the_other_wording(self):
        boss = self.join("Boss", "boss@example.com")
        boss.can_see_everyone = True
        boss.save()
        self.client.force_login(boss.user)
        response = self.client.get(reverse("person", args=[self.me.pk]))
        self.assertFalse(response.context["is_me"])
        self.assertContains(response, "because you help run the challenge")
        self.assertContains(response, "me@example.com")

    def test_the_link_is_in_the_navigation_for_everyone(self):
        self.assertContains(self.client.get(reverse("today")), reverse("my_record"))


class NoScreenshotFieldTests(Base):
    """The upload is gone — the free tier has half a gigabyte for everything."""

    def test_the_day_form_carries_no_file_input(self):
        me = self.join("Me", "me@example.com")
        self.client.force_login(me.user)
        with self.settings(CHALLENGE_START=LIVE_START, CHALLENGE_END=LIVE_END):
            body = self.client.get(reverse("today")).content.decode()
        self.assertNotIn('type="file"', body)
        self.assertNotIn("multipart/form-data", body)

    def test_the_model_has_no_evidence_field(self):
        self.assertNotIn("evidence", [f.name for f in DayLog._meta.get_fields()])
