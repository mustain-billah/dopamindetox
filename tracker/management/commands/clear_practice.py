"""Delete the practice days people filled in before the challenge started."""

from django.core.management.base import BaseCommand

from tracker.models import DayLog, challenge_start


class Command(BaseCommand):
    help = "Remove day logs from before the challenge start date."

    def add_arguments(self, parser):
        parser.add_argument(
            "--yes", action="store_true",
            help="Actually delete. Without it, only counts what would go.",
        )

    def handle(self, *args, **options):
        start = challenge_start()
        stale = DayLog.objects.filter(date__lt=start)
        count = stale.count()
        if not count:
            self.stdout.write(self.style.SUCCESS("No practice days to remove."))
            return
        if not options["yes"]:
            self.stdout.write(
                f"{count} practice day(s) before {start:%-d %B %Y}. "
                "Run again with --yes to delete them."
            )
            return
        stale.delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {count} practice day(s)."))
