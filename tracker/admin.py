from django.contrib import admin

from .models import DayLog, Participant, WeeklyNote


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = ("full_name", "dept", "session", "is_past_student", "is_organiser", "user")
    list_filter = ("is_organiser", "is_past_student")
    search_fields = ("full_name", "dept", "user__email")


@admin.register(DayLog)
class DayLogAdmin(admin.ModelAdmin):
    list_display = ("participant", "date", "get_status_display_short", "said_no")
    list_filter = ("date",)
    search_fields = ("participant__full_name",)
    date_hierarchy = "date"


@admin.register(WeeklyNote)
class WeeklyNoteAdmin(admin.ModelAdmin):
    list_display = ("participant", "week", "updated_at")
