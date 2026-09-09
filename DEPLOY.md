# Deploy to PythonAnywhere — step by step

For the GitHub repo **[mustain-billah/dopamindetox](https://github.com/mustain-billah/dopamindetox)**
and the PythonAnywhere account **`dopamindetox`**. Final URL:
<https://dopamindetox.pythonanywhere.com>

Run the steps in order. Nothing needs editing — copy, paste, press enter.

---

## Part A — on your Mac (Terminal)

### Step 1 — push to GitHub

The repo is already set up with a first commit. Create the GitHub repo empty —
no README, no .gitignore, since the project has both — and ignore GitHub's
"create a new repository on the command line" snippet, which would add a stray
`# dopamindetox` heading and a pointless commit.

```bash
cd ~/EDGEDjango/dopamindetox
git remote add origin https://github.com/mustain-billah/dopamindetox.git
git push -u origin main
```

If it asks for a password, your GitHub account password will be rejected.
HTTPS pushes need a **personal access token**: GitHub → Settings → Developer
settings → Personal access tokens → Fine-grained → **Repository access: Only
select repositories → dopamindetox** → **Permissions: Contents = Read and
write**. Paste the token where it asks for the password.

### Step 2 — confirm no secrets went up

```bash
git ls-files | grep -E "db.sqlite3|^\.env$" || echo "OK — no database or .env in the repo"
```

Expect `OK`.

---

## Part B — in a PythonAnywhere Bash console

Log in as **dopamindetox** and open **Consoles → Bash**.

### Step 3 — clone the repo

```bash
git clone https://github.com/mustain-billah/dopamindetox.git ~/dopamindetox
```

If the repo is private, use a read-only token:
`git clone https://YOUR_TOKEN@github.com/mustain-billah/dopamindetox.git ~/dopamindetox`
Making the repo public avoids tokens entirely, and there is nothing private in
it — the secret key and everyone's answers live only on the server.

### Step 4 — virtualenv and Django

```bash
mkvirtualenv --python=/usr/bin/python3.13 detox-venv
pip install -r ~/dopamindetox/requirements.txt
```

That creates `/home/dopamindetox/.virtualenvs/detox-venv` — you need that path
in step 7. If `python3.13` is missing, run `ls /usr/bin/python3.*` and use the
highest version that is 3.10 or newer.

### Step 5 — write the `.env` file

One paste. It generates the secret key, writes the file, and prints it back.

```bash
cd ~/dopamindetox
python - <<'ENVEOF'
from pathlib import Path
from django.core.management.utils import get_random_secret_key

env = f"""DJANGO_SECRET_KEY={get_random_secret_key()}
DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=dopamindetox.pythonanywhere.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://dopamindetox.pythonanywhere.com
DJANGO_TIME_ZONE=Asia/Dhaka
CHALLENGE_NAME=Dopamine Detox
CHALLENGE_START=2026-09-11
CHALLENGE_END=2027-01-11
CHALLENGE_PRIZE=10,000
"""
Path.home().joinpath("dopamindetox/.env").write_text(env)
print(env)
ENVEOF
```

The `CHALLENGE_` lines set the window — 11 September 2026 to 11 January 2027,
which is **123 days**. Change them here rather than in the code if the group
agrees on different dates.

**`DJANGO_CSRF_TRUSTED_ORIGINS` is not optional.** Leave it out and every login
and every save fails with a CSRF error: the browser connects over HTTPS while
Django only sees PythonAnywhere's internal plain-HTTP hop. It needs the
`https://` prefix — a bare hostname will not do.

### Step 6 — database and static files

```bash
cd ~/dopamindetox
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic --noinput
```

`migrate` also creates the nineteen people from `tracker/roster.py`, with the
names and departments they already gave — so nobody has to type their details
in again. Check it worked:

```bash
python manage.py shell -c "from tracker.models import Participant; print(Participant.objects.count(), 'people on the list')"
```

Expect `19 people on the list`.

The superuser is your admin login at `/admin/`. You will still claim a place as
a normal participant in step 9.

---

## Part C — in the PythonAnywhere Web tab

### Step 7 — create the web app

1. **Add a new web app**
2. **Manual configuration** — *not* the Django option, which would scaffold a
   fresh project over yours
3. Same Python version as step 4 (3.13)
4. Click through to the end

Then fill in three sections.

**Virtualenv:**

```
/home/dopamindetox/.virtualenvs/detox-venv
```

**Code → Source code:**

```
/home/dopamindetox/dopamindetox
```

**Code → WSGI configuration file** — click the link, select all, delete, paste:

```python
import os
import sys

path = "/home/dopamindetox/dopamindetox"
if path not in sys.path:
    sys.path.insert(0, path)

os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()
```

Save, then go back to the Web tab.

### Step 8 — static files, HTTPS, reload

In **Static files**, add one row:

| URL | Directory |
| --- | --- |
| `/static/` | `/home/dopamindetox/dopamindetox/staticfiles` |

In **Security**, turn on **Force HTTPS**.

Then hit the green **Reload** button. Nothing takes effect until you reload.

---

## Part D — check it, then invite everyone

### Step 9 — try it yourself

<https://dopamindetox.pythonanywhere.com/rules/>

Go to `/signup/`, find your name in the list, add an email and a password.
Fill in today, press **Save**, and check that `/board/` shows you.

Your own name is not on the list — you were organising, not listed as taking
part — so use **My name is not on the list** and type it in, or add yourself to
`tracker/roster.py` and run `python manage.py sync_roster`.

If anything is wrong, the **Error log** link in the Web tab has the traceback.

### Step 9b — set who runs it

You are running this, not competing. Your superuser account is put off the board
automatically the first time you open a page. Razzak competes **and** helps run
it, so give him the second power without taking away the first:

```bash
cd ~/dopamindetox && workon detox-venv
python manage.py set_role m.a.razzak06025@gmail.com --admin
python manage.py roles                    # check who is what
```

`roles` should show you as *runs it, not competing* and Razzak as
*competing · also runs it*. Both of you get an **Open** link beside each person
on the board, showing their whole log including what they wrote. The rules page
tells participants that the organisers can read this.

### Step 10 — send the link

Send the group:

> **https://dopamindetox.pythonanywhere.com/signup/**
>
> Your name is already on the list — find it, then set an email and a password.
> You fill in your own day; nobody else can change it. Everyone can see
> everyone's totals on the board.

Do not create accounts for people. Each person claims their own place, and that
is what makes their row theirs.

If somebody is missing from the list, add them to `tracker/roster.py`, push,
`git pull` on the server, then run `python manage.py sync_roster` and reload.

---

## Running a trial before 11 September

Let the group use the real app first, so they can see real streaks and a real
board and tell you what to change. Edit `~/dopamindetox/.env` to:

```
CHALLENGE_START=2026-08-30
CHALLENGE_END=2026-12-30
CHALLENGE_TEST_MODE=true
CHALLENGE_REAL_START=2026-09-11
```

Reload in the Web tab. Every page now carries a banner saying it is a trial and
the data will be deleted on 11 September. Everything else is genuinely live.

**On 10 September**, put the real dates back:

```
CHALLENGE_START=2026-09-11
CHALLENGE_END=2027-01-11
CHALLENGE_TEST_MODE=false
```

then wipe the trial answers in a Bash console:

```bash
cd ~/dopamindetox
workon detox-venv
python manage.py reset_challenge          # shows what would go
python manage.py reset_challenge --yes    # does it
```

Reload again. Accounts and the roster survive — nobody signs up twice — and
everyone starts the 11th on zero.

---

## Updating later

```bash
cd ~/dopamindetox
git pull
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
```

Then **Reload** in the Web tab.

## The database

Everything — accounts, the roster, everyone's answers — is one SQLite file:

```
/home/dopamindetox/dopamindetox/db.sqlite3
```

**Back it up before deleting anything.** In a Bash console:

```bash
cp ~/dopamindetox/db.sqlite3 ~/detox-backup-$(date +%F).sqlite3
```

Download it from the **Files** tab. Worth doing monthly, before any update, and
always before a delete. To put a backup back:

```bash
cp ~/detox-backup-2026-09-10.sqlite3 ~/dopamindetox/db.sqlite3
```

then **Reload** in the Web tab.

### Deleting a few entries — use the admin

<https://dopamindetox.pythonanywhere.com/admin/tracker/daylog/>

Sign in with the superuser from step 6. You get a searchable, sortable list of
every day: search a name, filter by date down the right-hand side, tick the rows
you want, then choose **Delete selected day logs** and Go. Participants and
weekly notes have the same screens. This is the safest way — you see exactly
what goes before it goes.

### Deleting in bulk — one-line commands

For anything larger, in a Bash console. **These run immediately and cannot be
undone**, so take the backup above first.

```bash
cd ~/dopamindetox && workon detox-venv
```

One person's days, keeping their account:

```bash
python manage.py shell -c "
from tracker.models import DayLog
print(DayLog.objects.filter(participant__full_name='Ziaul Haq').delete())"
```

One date, for everyone:

```bash
python manage.py shell -c "
from tracker.models import DayLog
print(DayLog.objects.filter(date='2026-09-15').delete())"
```

A range of dates:

```bash
python manage.py shell -c "
from tracker.models import DayLog
print(DayLog.objects.filter(date__gte='2026-09-11', date__lte='2026-09-20').delete())"
```

Remove somebody completely — their account and their days — while leaving their
name on the list so they can claim it again:

```bash
python manage.py shell -c "
from tracker.models import Participant, DayLog
p = Participant.objects.get(full_name='Omar Faruk')
user = p.user
p.user = None; p.save()
print(DayLog.objects.filter(participant=p).delete())
user.delete()"
```

Swap `.delete()` for `.count()` on any of these to see how many rows it would
remove before you remove them.

### Wiping everything

```bash
python manage.py reset_challenge          # says what would go
python manage.py reset_challenge --yes    # every day log and weekly note
```

Accounts and the roster survive, so nobody has to sign up twice.

---

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `DisallowedHost` | `DJANGO_ALLOWED_HOSTS` doesn't say `dopamindetox.pythonanywhere.com` |
| CSRF failure on login or save | `DJANGO_CSRF_TRUSTED_ORIGINS` missing, or missing its `https://` |
| Pages load with no styling | Step 6's `collectstatic` not run, or the step 8 mapping is wrong |
| `ModuleNotFoundError: No module named 'config'` | The `path` line in the WSGI file is wrong |
| `ImproperlyConfigured: DJANGO_SECRET_KEY is still the development default` | Working as designed — step 5 didn't run |
| `ImportError: No module named django` | Virtualenv path in step 7 is wrong, or step 4 failed |
| Someone's name is missing from the sign-up list | Add them to `tracker/roster.py`, then `python manage.py sync_roster` |
| "Somebody has just claimed that name" | That name is already taken — log in instead, or ask who took it |
| Wrong day rolls over at the wrong hour | `DJANGO_TIME_ZONE` — it decides when "today" changes |
| Changes don't show up | You didn't hit **Reload** |

## Free-tier limits

- **One web app**, on `dopamindetox.pythonanywhere.com`. Custom domains are
  paid-only.
- **The app expires every three months.** PythonAnywhere emails a link to keep
  it running; miss it and the site goes down mid-challenge with no warning to
  the group. Put a reminder in your calendar now — the challenge runs longer
  than one renewal period, so this **will** come up around December.
- **Outbound internet is restricted to a proxy allowlist.** Doesn't affect this
  app; it makes no outbound requests.
- **A daily CPU-seconds budget**, which twenty people ticking boxes barely
  touches.
