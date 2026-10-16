from django.contrib.auth import get_user_model
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from unittest import mock
import re
import smtplib

from .models import Profile
from .tokens import account_activation_token

User = get_user_model()
PW = "Str0ng-Pass-2026!"


def make_user(email="user@example.com", nickname="tester", active=True, password=PW, **extra):
    user = User.objects.create_user(email=email, password=password, is_active=active, **extra)
    Profile.objects.create(user=user, nickname=nickname)
    return user


def link_from_mail(message, path_part):
    m = re.search(r"https?://\S*" + path_part + r"\S*", message.body)
    assert m, message.body
    return m.group(0)


class SignupAndActivationTests(TestCase):
    def signup(self, **over):
        data = {
            "email": "new@example.com",
            "nickname": "newbie",
            "password1": PW,
            "password2": PW,
        }
        data.update(over)
        return self.client.post(reverse("accounts:signup"), data)

    def test_signup_creates_inactive_user_and_sends_mail(self):
        r = self.signup()
        self.assertEqual(r.status_code, 200)
        user = User.objects.get(email="new@example.com")
        self.assertFalse(user.is_active)
        self.assertEqual(user.profile.nickname, "newbie")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["new@example.com"])

    def test_cannot_login_before_activation(self):
        self.signup()
        ok = self.client.login(email="new@example.com", password=PW)
        self.assertFalse(ok)
        r = self.client.post(
            reverse("accounts:login"), {"username": "new@example.com", "password": PW}
        )
        self.assertEqual(r.context["form"].login_error_code, "inactive")

    def test_activation_link_activates_once(self):
        self.signup()
        link = link_from_mail(mail.outbox[0], "/accounts/activate/")
        r = self.client.get(link)
        self.assertRedirects(r, reverse("accounts:login"))
        self.assertTrue(User.objects.get(email="new@example.com").is_active)
        # 같은 링크 재사용 불가
        r = self.client.get(link)
        self.assertEqual(r.status_code, 400)

    def test_tampered_token_rejected(self):
        self.signup()
        user = User.objects.get(email="new@example.com")
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        r = self.client.get(reverse("accounts:activate", args=[uid, "bad-token"]))
        self.assertEqual(r.status_code, 400)
        user.refresh_from_db()
        self.assertFalse(user.is_active)

    def test_admin_disabled_account_is_not_reactivated(self):
        user = make_user(active=False)
        user.last_login = user.date_joined  # 한 번 로그인한 적 있는 계정 = 관리자가 비활성화한 것
        user.save()
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = account_activation_token.make_token(user)
        r = self.client.get(reverse("accounts:activate", args=[uid, token]))
        self.assertEqual(r.status_code, 400)
        user.refresh_from_db()
        self.assertFalse(user.is_active)

    def test_duplicate_nickname_and_email_rejected(self):
        make_user()
        r = self.signup(nickname="tester")
        self.assertContains(r, "이미 사용 중인 닉네임")
        r = self.signup(email="user@example.com")
        self.assertEqual(User.objects.filter(email="user@example.com").count(), 1)
        self.assertEqual(len(mail.outbox), 0)

    def test_password_policy(self):
        for bad in ["short1!", "1234567890", "password1234"]:
            r = self.signup(password1=bad, password2=bad)
            self.assertEqual(r.status_code, 200)
            self.assertFalse(User.objects.filter(email="new@example.com").exists(), bad)

    def test_mail_failure_rolls_back_user(self):
        with mock.patch("accounts.views.send_mail", side_effect=smtplib.SMTPException):
            r = self.signup()
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(email="new@example.com").exists())
        # 같은 이메일로 다시 시도 가능
        r = self.signup()
        self.assertTrue(User.objects.filter(email="new@example.com").exists())

    def test_resend_only_for_pending_accounts_and_hides_existence(self):
        make_user(email="pending@example.com", nickname="p", active=False)
        make_user(email="active@example.com", nickname="a", active=True)
        url = reverse("accounts:resend_activation")

        r1 = self.client.post(url, {"email": "pending@example.com"})
        r2 = self.client.post(url, {"email": "active@example.com"})
        r3 = self.client.post(url, {"email": "nobody@example.com"})

        self.assertEqual([r.status_code for r in (r1, r2, r3)], [200, 200, 200])
        self.assertTemplateUsed(r2, "accounts/resend_activation_done.html")
        self.assertTemplateUsed(r3, "accounts/resend_activation_done.html")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["pending@example.com"])


class LoginLogoutTests(TestCase):
    def setUp(self):
        self.user = make_user()

    def test_login_error_codes(self):
        url = reverse("accounts:login")
        r = self.client.post(url, {"username": "user@example.com", "password": "wrong-pass-123"})
        self.assertEqual(r.context["form"].login_error_code, "invalid_password")
        r = self.client.post(url, {"username": "ghost@example.com", "password": PW})
        self.assertEqual(r.context["form"].login_error_code, "invalid_username")

    def test_login_success_redirects(self):
        r = self.client.post(
            reverse("accounts:login"), {"username": "user@example.com", "password": PW}
        )
        self.assertRedirects(r, reverse("boards:post_list"), fetch_redirect_response=False)

    def test_logout_requires_post(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("accounts:logout")).status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)
        self.client.post(reverse("accounts:logout"))
        self.assertNotIn("_auth_user_id", self.client.session)


class PasswordTests(TestCase):
    def setUp(self):
        self.user = make_user()

    def test_change_requires_login(self):
        r = self.client.get(reverse("accounts:password_change"))
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse("accounts:login"), r["Location"])

    def test_change_success_and_old_password_check(self):
        self.client.force_login(self.user)
        url = reverse("accounts:password_change")
        new = "An0ther-Str0ng-Pw!"

        r = self.client.post(url, {"old_password": "nope", "new_password1": new, "new_password2": new})
        self.assertEqual(r.status_code, 200)  # 오류로 폼 재표시
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(PW))

        r = self.client.post(url, {"old_password": PW, "new_password1": new, "new_password2": new})
        self.assertRedirects(r, reverse("accounts:profile_detail"), fetch_redirect_response=False)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(new))

    def test_change_enforces_policy(self):
        self.client.force_login(self.user)
        r = self.client.post(
            reverse("accounts:password_change"),
            {"old_password": PW, "new_password1": "abc12345", "new_password2": "abc12345"},
        )
        self.assertEqual(r.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(PW))

    def test_reset_flow(self):
        r = self.client.post(reverse("accounts:password_reset"), {"email": "user@example.com"})
        self.assertRedirects(r, reverse("accounts:password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)

        link = link_from_mail(mail.outbox[0], "/accounts/password/reset/")
        r = self.client.get(link, follow=True)  # 토큰을 세션에 저장하고 set-password 로 리다이렉트
        self.assertTrue(r.context["validlink"])

        new = "Reset-Str0ng-Pw-1!"
        r = self.client.post(r.request["PATH_INFO"], {"new_password1": new, "new_password2": new})
        self.assertRedirects(r, reverse("accounts:password_reset_complete"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(new))

        # 사용한 링크는 다시 못 쓴다
        r = self.client.get(link, follow=True)
        self.assertFalse(r.context["validlink"])

    def test_reset_does_not_reveal_unknown_email(self):
        r = self.client.post(reverse("accounts:password_reset"), {"email": "ghost@example.com"})
        self.assertRedirects(r, reverse("accounts:password_reset_done"))
        self.assertEqual(len(mail.outbox), 0)


class AccountPermissionTests(TestCase):
    def test_login_required_pages(self):
        for name in ("profile_detail", "profile_update", "withdraw", "password_change"):
            r = self.client.get(reverse(f"accounts:{name}"))
            self.assertEqual(r.status_code, 302, name)
            self.assertIn(reverse("accounts:login"), r["Location"], name)

    def test_withdraw_deletes_user(self):
        user = make_user()
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("accounts:withdraw")).status_code, 200)
        self.assertTrue(User.objects.filter(pk=user.pk).exists())  # GET 은 삭제하지 않는다
        self.client.post(reverse("accounts:withdraw"))
        self.assertFalse(User.objects.filter(pk=user.pk).exists())

    def test_superuser_without_profile_gets_one(self):
        admin = User.objects.create_superuser(email="root@example.com", password=PW)
        self.client.force_login(admin)
        r = self.client.get(reverse("accounts:profile_detail"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(admin.profile.nickname, "root")

    def test_profile_image_size_limit(self):
        user = make_user()
        self.client.force_login(user)
        big = SimpleUploadedFile("big.png", b"x" * (5 * 1024 * 1024 + 1), content_type="image/png")
        r = self.client.post(
            reverse("accounts:profile_update"),
            {"nickname": "tester", "bio": "", "profile_image": big},
        )
        self.assertEqual(r.status_code, 200)  # 저장되지 않고 폼 재표시
        user.profile.refresh_from_db()
        self.assertFalse(user.profile.profile_image)


class CsrfTests(TestCase):
    def test_post_without_csrf_token_is_rejected(self):
        client = Client(enforce_csrf_checks=True)
        user = make_user()
        client.force_login(user)
        r = client.post(reverse("accounts:withdraw"))
        self.assertEqual(r.status_code, 403)
        self.assertTrue(User.objects.filter(pk=user.pk).exists())