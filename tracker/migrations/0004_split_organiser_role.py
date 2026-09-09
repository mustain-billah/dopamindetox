"""Split one flag into two: competing, and being allowed to read everyone's log.

They were the same thing, which made it impossible to describe somebody who
competes and also helps run the challenge.
"""

from django.db import migrations, models


def carry_over(apps, schema_editor):
    Participant = apps.get_model("tracker", "Participant")
    # An organiser was, by definition, off the board and able to read the logs.
    Participant.objects.filter(is_organiser=True).update(
        competes=False, can_see_everyone=True
    )


def put_back(apps, schema_editor):
    Participant = apps.get_model("tracker", "Participant")
    Participant.objects.filter(competes=False).update(is_organiser=True)


class Migration(migrations.Migration):
    dependencies = [("tracker", "0003_participant_is_organiser")]

    operations = [
        migrations.AddField(
            model_name="participant",
            name="competes",
            field=models.BooleanField(
                default=True,
                help_text="On the board and in the running for the prize. "
                          "Turn off for someone who only helps run the challenge.",
                verbose_name="Competing",
            ),
        ),
        migrations.AddField(
            model_name="participant",
            name="can_see_everyone",
            field=models.BooleanField(
                default=False,
                help_text="May open any participant and read what they wrote.",
                verbose_name="Can read everyone's log",
            ),
        ),
        migrations.RunPython(carry_over, put_back),
        migrations.RemoveField(model_name="participant", name="is_organiser"),
    ]
