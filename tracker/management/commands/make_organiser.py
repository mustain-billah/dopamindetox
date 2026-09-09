"""Turn an account into an organiser: off the board, and able to read the notes."""

from django.core.management.base import BaseCommand, CommandError

from tracker.models import Participant


class Command(BaseCommand):
    help = "Make the person with this email an organiser (or --undo it)."

    def add_arguments(self, parser):
        parser.add_argument("email", help="The email they signed up with.")
        parser.add_argument("--undo", action="store_true", help="Make them a competitor again.")

    def handle(self, *args, **options):
        email = options["email"].strip()
        try:
            person = Participant.objects.get(user__email__iexact=email)
        except Participant.DoesNotExist:
            raise CommandError(f"Nobody is signed up with {email}.")
        person.is_organiser = not options["undo"]
        person.save(update_fields=["is_organiser"])
        role = "a competitor again" if options["undo"] else "an organiser"
        self.stdout.write(self.style.SUCCESS(f"{person.full_name} is now {role}."))
