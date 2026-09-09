"""Create or refresh the pre-made participant rows from tracker/roster.py."""

from django.core.management.base import BaseCommand

from tracker.models import Participant
from tracker.roster import sync


class Command(BaseCommand):
    help = "Create the people listed in tracker/roster.py, skipping claimed rows."

    def handle(self, *args, **options):
        result = sync(Participant)
        self.stdout.write(
            self.style.SUCCESS(
                f"{result['created']} added, {result['updated']} updated, "
                f"{result['total']} people in total."
            )
        )
