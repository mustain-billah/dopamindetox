from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .forms import EmailLoginForm

urlpatterns = [
    path("", views.today, name="today"),
    path("day/<str:day>/", views.day_view, name="day"),
    path("week/", views.weekly, name="weekly"),
    path("record/", views.my_record, name="my_record"),
    path("board/", views.board, name="board"),
    path("board/<int:pk>/", views.person, name="person"),
    path("rules/", views.rules, name="rules"),
    path("me/", views.profile, name="profile"),
    path("signup/", views.signup, name="signup"),
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="tracker/login.html",
            authentication_form=EmailLoginForm,
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
]
