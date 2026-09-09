"""Wipe everyone's answers so the challenge can begin from nothing.

Use this after a trial run: it clears every day log and weekly note while
leaving the accounts and the roster alone, so nobody has to sign up again.
"""

from django.core.management.base import BaseCommand

from tracker.models import DayLog, Participant, WeeklyNote


class Command(BaseCommand):
    help = "Delete all day logs and weekly notes, keeping accounts and the roster."

    def add_arguments(self, parser):
        parser.add_argument(
            "--yes", action="store_true",
            help="Actually delete. Without it, only reports what would go.",
        )
        parser.add_argument(
            "--accounts", action="store_true",
            help="Also unclaim every place, so everyone signs up again. Rarely wanted.",
        )

    def handle(self, *args, **options):
        days = DayLog.objects.count()
        notes = WeeklyNote.objects.count()
        claimed = Participant.objects.filter(user__isnull=False).count()

        if not options["yes"]:
            self.stdout.write(f"Would delete {days} day log(s) and {notes} weekly note(s).")
            if options["accounts"]:
                self.stdout.write(f"Would also unclaim {claimed} place(s).")
            self.stdout.write("Run again with --yes to do it.")
            return

        DayLog.objects.all().delete()
        WeeklyNote.objects.all().delete()
        message = f"Deleted {days} day log(s) and {notes} weekly note(s)."

        if options["accounts"]:
            from django.contrib.auth.models import User

            Participant.objects.update(user=None)
            removed = User.objects.filter(is_superuser=False).delete()[0]
            message += f" Unclaimed {claimed} place(s) and removed {removed} account(s)."

        self.stdout.write(self.style.SUCCESS(message))
