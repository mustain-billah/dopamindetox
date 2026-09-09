"""Change what somebody can do: compete, help run it, or both.

Competing and reading everyone's log are separate, because somebody can do both.
"""

from django.core.management.base import BaseCommand, CommandError

from tracker.models import Participant


class Command(BaseCommand):
    help = "Set whether someone competes and whether they can read everyone's log."

    def add_arguments(self, parser):
        parser.add_argument("email", help="The email they signed up with.")
        parser.add_argument("--admin", action="store_true",
                            help="Let them open anyone and read what was written.")
        parser.add_argument("--no-admin", action="store_true",
                            help="Take that away.")
        parser.add_argument("--competing", action="store_true",
                            help="Put them on the board, in the running for the prize.")
        parser.add_argument("--not-competing", action="store_true",
                            help="Take them off the board — they only help run it.")

    def handle(self, *args, **options):
        email = options["email"].strip()
        try:
            person = Participant.objects.select_related("user").get(user__email__iexact=email)
        except Participant.DoesNotExist:
            raise CommandError(f"Nobody is signed up with {email}.")

        if options["admin"] and options["no_admin"]:
            raise CommandError("Pick either --admin or --no-admin, not both.")
        if options["competing"] and options["not_competing"]:
            raise CommandError("Pick either --competing or --not-competing, not both.")
        if not any(options[k] for k in ("admin", "no_admin", "competing", "not_competing")):
            self.stdout.write(f"{person.full_name}: {person.role}. Nothing changed — "
                              "pass --admin, --no-admin, --competing or --not-competing.")
            return

        if options["no_admin"] and person.user.is_staff:
            raise CommandError(
                f"{person.full_name} is a Django staff account, which always has "
                "the run of everyone's log. Remove their staff status in /admin/ first."
            )
        if options["competing"] and person.user.is_staff:
            raise CommandError(
                f"{person.full_name} is a Django staff account, which is kept off "
                "the board. Remove their staff status in /admin/ first."
            )

        if options["admin"]:
            person.can_see_everyone = True
        if options["no_admin"]:
            person.can_see_everyone = False
        if options["competing"]:
            person.competes = True
        if options["not_competing"]:
            person.competes = False
        person.save(update_fields=["competes", "can_see_everyone"])

        self.stdout.write(self.style.SUCCESS(f"{person.full_name}: {person.role}."))
