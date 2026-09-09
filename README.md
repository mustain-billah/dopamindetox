# Dopamine Detox

A tracker for a group challenge: stay off social media, videos and newspapers
for four months, and whoever lasts the whole way wins the prize.

**11 September 2026 to 11 January 2027 — 123 days.**

Everyone who said they were joining is **already on the list** with the name,
department and session they gave. Signing up means finding your name and
setting an email and password — nobody types their details in twice. That
email is how you log in, and you fill in your own day; nobody else can touch
it. The board shows everyone's totals to everyone, because the
point is encouragement, not surveillance — there is no way to check what
anyone actually did, and the challenge says so out loud.

## What it does

- **Claim your place** — the sign-up page lists everyone who has not claimed
  yet. Pick your name, add an email and a password, done. Anyone not on the
  list can still add themselves.
- **Today** — six questions, each answered **No**, **Study or work**, or
  **Yes**. Plus how many times you stopped yourself, what you did instead, and a
  reason if you used something. A **study or work** answer will not save without
  that reason — the group agreed those uses are fine "with evidence", and the
  note is the evidence. A slip needs no reason: owning up should be the easy
  path, not the one with a form error attached. A refused day says so at the top of
  the page as well as beside the field, so nobody walks away thinking it saved.
- **Before it starts, and after it ends**, the daily page is a countdown or a
  closing note instead of a form. Days outside the window cannot be filled in.
- **Coming back to a day you have done** says so plainly, shows what it counted
  as, and the button reads Update rather than Save.
- **A day only counts once you press Save.** Opening the page changes nothing —
  every field defaults to "No", so creating the row on a page view would hand
  out a clean day nobody vouched for.
- **Everyone** — the board shows the whole list from day one, including people
  who have not signed in yet, so you can see who is still missing. Ordered by
  fewest slips, then fewest study-or-work days, then most days filled in.
  Anyone who has not started ranks below everyone who has, so an empty row
  never sits at the top on zeroes. That is the group's own rule:
  using YouTube for a class is allowed, but someone with no such days is ahead
  of someone who has them.
- **This week** — two lines a week, so four months leave a record.
- **My record** — one page with every day you have filled in and everything you
  wrote, the same view the organisers get of you. Click a date to change it.
- **Missed a day?** The page lists every gap as a tappable date, and every past
  square in the grid links to that day, so filling one in is one tap rather than
  clicking "Previous day" over and over. There is no deadline on backfilling —
  the challenge runs on honesty, not on locking the form.
- **All 123 days** — a colour grid of the whole challenge, clickable.

## Run it locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python manage.py migrate
python manage.py runserver
```

Open <http://127.0.0.1:8000/rules/>, then sign up at `/signup/`.

`python manage.py createsuperuser` gets you into `/admin/`.

## Deploying

See **[DEPLOY.md](DEPLOY.md)** — a numbered walkthrough for the free
PythonAnywhere account, with the free-tier limits and a troubleshooting table.

## Trial run

To let the group use the real app before the real start, point
`CHALLENGE_START` at a date already past and set `CHALLENGE_TEST_MODE=true`.
Everything then behaves exactly as it will for real — streaks, the board, the
grid — and a banner on every page says the data will be deleted, naming the
real start date from `CHALLENGE_REAL_START`.

When the trial is done, put the real dates back, turn the flag off, and wipe
the answers:

```bash
python manage.py reset_challenge          # says what would go, deletes nothing
python manage.py reset_challenge --yes    # deletes every day log and weekly note
```

Accounts and the roster survive, so nobody signs up twice. `--accounts` also
unclaims every place, which is rarely what you want.

## Who can do what

Two separate things, because one person can be both:

- **Competing** — on the board, in the running for the prize.
- **Can read everyone's log** — may open any participant from the board and see
  their whole record, including what they wrote in *what you did instead* and
  *reason*.

So Mustain runs it without competing; Razzak competes **and** helps run it; the
other seventeen just compete. The rules page tells participants that the people
organising can read what they write, because they should know before they write
it.

**Superuser is a different thing again.** Django's `is_staff` / `is_superuser`
is the key to `/admin/`, the raw database editor. A staff account is also put
off the board and given the run of the logs — checked on every page load, so an
account granted staff later is caught the next time it is used.

```bash
python manage.py roles                                   # who is what

python manage.py set_role someone@example.com --admin            # can read everyone
python manage.py set_role someone@example.com --no-admin
python manage.py set_role someone@example.com --not-competing    # off the board
python manage.py set_role someone@example.com --competing
```

Flags combine, and the two settings are independent — `--admin` on its own
leaves somebody competing. `set_role` refuses to fight the staff rule rather
than making a change the next page load would undo.

```
Mustain Billah          runs it, not competing    mustainbillahx@gmail.com · django staff
Muhammad Abdur Razzak   competing · also runs it  m.a.razzak06025@gmail.com
Ziaul Haq               competing                 ziaul@example.com

19 on the board (17 of them not signed in yet), 2 can read everyone's log.
```

## The roster

`tracker/roster.py` holds the group as name, department, session and whether
they are a past student. A data migration creates them on the first `migrate`,
so the list is there before anyone signs up.

To add or correct someone, edit that file and run:

```bash
python manage.py sync_roster
```

It never touches a row somebody has already claimed and never deletes anyone,
so it is safe to run any time. Two people are called Sabbir Hossen, so a person
is matched on name **and** department, never name alone.

## Settings

Everything is read from the environment, and `config/settings.py` also loads a
`.env` file next to `manage.py`. Copy `.env.example` and edit.

| Variable | Default | What it does |
| --- | --- | --- |
| `CHALLENGE_START` | `2026-09-11` | First day |
| `CHALLENGE_END` | `2027-01-11` | Last day |
| `CHALLENGE_PRIZE` | `10,000` | Shown on the rules page and the board |
| `DJANGO_TIME_ZONE` | `Asia/Dhaka` | Decides when "today" rolls over |

With `DEBUG` off the app refuses to start on the development secret key rather
than running insecurely.

## How the scoring works

`tracker/services.py` holds all of it and touches no database, so every rule is
testable on its own.

- Every filled-in day is exactly one of three: **nothing at all** (every answer
  No), **only for study or work** (the worst answer is that), or **slipped**
  (anything is Yes). The day page shows them as one breakdown, in the same
  colours as the calendar below it.
- **Days in a row** counts days without a Yes. A study-or-work day keeps it.
  A day you have not filled in yet does not reset it — you may simply not have
  got to it — but a real gap does.
- **Ranking** is fewest slips, then fewest study-or-work days, then most days
  filled in.

## Tests

```bash
python manage.py test
```

31 tests cover the scoring, the streak edge cases, email login, and the
ownership boundary — including that the board page contains no control that
could edit anyone.
