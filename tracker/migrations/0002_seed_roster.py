"""Create everyone who said they were joining, so nobody signs up from scratch."""

from django.db import migrations

from tracker.roster import sync


def seed(apps, schema_editor):
    sync(apps.get_model("tracker", "Participant"))


def unseed(apps, schema_editor):
    """Remove only the pre-made rows nobody has claimed."""
    Participant = apps.get_model("tracker", "Participant")
    Participant.objects.filter(user__isnull=True).delete()


class Migration(migrations.Migration):
    dependencies = [("tracker", "0001_initial")]
    operations = [migrations.RunPython(seed, unseed)]
