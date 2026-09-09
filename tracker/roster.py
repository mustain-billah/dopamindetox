"""Everyone who said they were joining, with the details they already gave.

These rows are created up front so nobody has to type their name and
department again — they only add an email and a password to claim their place.

To add or correct someone, edit this list and run:

    python manage.py sync_roster

It never touches a row that has already been claimed, and never deletes
anyone, so it is safe to run any time.
"""

#: full name, department, session, is a past student
ROSTER = [
    ("Muhammad Abdur Razzak", "BGE", "2005-06", True),
    ("Mohammad Abdur Rashed", "ESRM", "2003-04", True),
    ("Ziaul Haq", "ESRM", "06-07", True),
    ("Md. Ashikur Rahman", "Chemistry", "2012-13", True),
    ("Md. Mahmudul Hasan Rimon", "TE", "13-14", True),
    ("Mohammad Saiful Islam", "TE", "", True),
    ("Md. Shahadat Hossain", "CSE", "", True),
    ("Md. Shofiqul Islam", "ICT", "", True),
    ("Abid Hasan Nayeem", "MATH", "18-19", True),
    ("Omar Faruk", "PHY", "2013-14", True),
    ("Mohammad Shahin Alam", "BGE", "2013-14", True),
    ("Tawhid Al Hasan", "BMB", "20-21", False),
    ("Mostak Ahmed", "PHY", "22-23", False),
    ("Rakibul Hassan Hasnat", "Pharmacy", "19-20", False),
    ("Rajib Miah", "TEX", "24-25", False),
    ("Nasib Iqbal", "TEX", "24-25", False),
    ("Sabbir Hossen", "TEX", "24-25", False),
    ("Sabbir Hossen", "CPS", "21-22", False),
    ("Md Manik Islam", "BGE", "24-25", False),
]


def sync(participant_model) -> dict:
    """Create anyone missing and fix details on rows nobody has claimed yet.

    Two people are called Sabbir Hossen, so a person is identified by name AND
    department, never by name alone. Takes the model class so a data migration
    can pass its historical version.
    """
    created = updated = 0
    for full_name, dept, session, is_past in ROSTER:
        person, was_created = participant_model.objects.get_or_create(
            full_name=full_name,
            dept=dept,
            defaults={"session": session, "is_past_student": is_past},
        )
        if was_created:
            created += 1
            continue
        # Never rewrite details someone has since corrected for themselves.
        if person.user_id is None and (
            person.session != session or person.is_past_student != is_past
        ):
            person.session = session
            person.is_past_student = is_past
            person.save(update_fields=["session", "is_past_student"])
            updated += 1
    return {"created": created, "updated": updated, "total": participant_model.objects.count()}
