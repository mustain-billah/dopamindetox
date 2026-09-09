"""Show who is competing, who is organising, and who has not signed in."""

from django.core.management.base import BaseCommand

from tracker.models import Participant


class Command(BaseCommand):
    help = "List everyone with their role, so it is clear who is on the board."

    def handle(self, *args, **options):
        people = Participant.objects.select_related("user").order_by(
            "competes", "-can_see_everyone", "full_name"
        )
        if not people:
            self.stdout.write("Nobody on the list yet.")
            return

        width = max(len(p.full_name) for p in people)
        on_board = admins = waiting = 0
        for person in people:
            if person.competes:
                on_board += 1
            if person.can_see_everyone:
                admins += 1
            if not person.is_claimed:
                waiting += 1
            staff = " · django staff" if person.user and person.user.is_staff else ""
            email = person.user.email if person.user else "—"
            self.stdout.write(f"{person.full_name:<{width}}  {person.role:<24} {email}{staff}")

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"{on_board} on the board ({waiting} of them not signed in yet), "
            f"{admins} can read everyone's log."
        ))
