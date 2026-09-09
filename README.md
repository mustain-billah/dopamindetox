# Dopamine Detox

A tracker for a group challenge: stay off social media, videos and newspapers
for four months, and whoever lasts the whole way wins the prize.

**11 September 2026 to 11 January 2027 — 123 days.**

Everyone signs up with their own email. You fill in your own day and nobody
else can touch it. The board shows everyone's totals to everyone, because the
point is encouragement, not surveillance — there is no way to check what
anyone actually did, and the challenge says so out loud.

## What it does

- **Today** — six questions, each answered **No**, **Study or work**, or
  **Yes**. Plus how many times you said no to an urge, what you did instead,
  and a reason if you used something.
- **A day only counts once you press Save.** Opening the page changes nothing —
  every field defaults to "No", so creating the row on a page view would hand
  out a clean day nobody vouched for.
- **Everyone** — the board, ordered by fewest days used, then fewest
  study-or-work days, then most days filled in. That is the group's own rule:
  using YouTube for a class is allowed, but someone with no such days is ahead
  of someone who has them.
- **This week** — two lines a week, so four months leave a record.
- **All 123 days** — a colour grid of the whole challenge.

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

- A day is **clean** if every answer is No, **study or work** if the worst
  answer is that, and **used** if anything is Yes.
- **Streak** counts days in a row without a Yes. A study-or-work day keeps it.
  A day you have not filled in yet does not reset it — you may simply not have
  got to it — but a real gap does.
- **Ranking** is fewest used days, then fewest study-or-work days, then most
  days filled in.

## Tests

```bash
python manage.py test
```

31 tests cover the scoring, the streak edge cases, email login, and the
ownership boundary — including that the board page contains no control that
could edit anyone.
