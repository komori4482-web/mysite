from django.contrib.auth import views as auth_views
from django.contrib.auth.views import LoginView
from django.urls import path, reverse_lazy

from . import views
from .forms import CustomLoginForm

app_name = "accounts"

urlpatterns = [
    path("signup/", views.signup, name="signup"),
    path("activate/resend/", views.resend_activation, name="resend_activation"),
    path("activate/<uidb64>/<token>/", views.activate, name="activate"),
    path("login/", LoginView.as_view(
        authentication_form=CustomLoginForm,
        template_name="accounts/login.html",
        redirect_authenticated_user=True,
    ), name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("withdraw/", views.withdraw, name="withdraw"),
    path("profile/", views.profile_detail, name="profile_detail"),
    path("profile/update/", views.profile_update, name="profile_update"),

    # 비밀번호 변경 (로그인 상태)
    path("password/change/", views.PasswordChange.as_view(), name="password_change"),

    # 비밀번호 재설정 (이메일 링크)
    path("password/reset/", auth_views.PasswordResetView.as_view(
        template_name="accounts/password_reset_form.html",
        email_template_name="accounts/password_reset_email.txt",
        subject_template_name="accounts/password_reset_subject.txt",
        success_url=reverse_lazy("accounts:password_reset_done"),
    ), name="password_reset"),
    path("password/reset/done/", auth_views.PasswordResetDoneView.as_view(
        template_name="accounts/password_reset_done.html",
    ), name="password_reset_done"),
    path("password/reset/complete/", auth_views.PasswordResetCompleteView.as_view(
        template_name="accounts/password_reset_complete.html",
    ), name="password_reset_complete"),
    path("password/reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(
        template_name="accounts/password_reset_confirm.html",
        success_url=reverse_lazy("accounts:password_reset_complete"),
    ), name="password_reset_confirm"),
]