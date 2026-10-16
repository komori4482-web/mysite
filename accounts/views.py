import smtplib

from django.contrib import messages
from django.contrib.auth import get_user_model, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordChangeView
from django.contrib.messages.views import SuccessMessageMixin
from django.core.mail import send_mail
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.http import require_POST

from .forms import ProfileForm, ResendActivationForm, SignupForm
from .models import Profile
from .tokens import account_activation_token

User = get_user_model()


# ───────────── 회원가입 / 이메일 인증 ─────────────

def _send_activation_email(request, user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = account_activation_token.make_token(user)
    link = request.build_absolute_uri(
        reverse("accounts:activate", args=[uid, token])
    )
    send_mail(
        subject="[Portfolio Board] 이메일 인증을 완료해주세요",
        message=(
            "가입해주셔서 감사합니다.\n"
            "아래 링크를 누르면 가입이 완료됩니다. (링크는 24시간 동안 유효합니다)\n\n"
            f"{link}\n\n"
            "본인이 가입하지 않았다면 이 메일을 무시해주세요."
        ),
        from_email=None,  # settings.DEFAULT_FROM_EMAIL
        recipient_list=[user.email],
    )


def signup(request):
    if request.user.is_authenticated:
        return redirect("boards:post_list")

    if request.method == "POST":
        form = SignupForm(request.POST)

        if form.is_valid():
            with transaction.atomic():
                user = form.save(commit=False)
                user.is_active = False  # 이메일 인증 전까지 로그인 불가
                user.save()
                Profile.objects.create(
                    user=user,
                    nickname=form.cleaned_data["nickname"],
                )
            try:
                _send_activation_email(request, user)
            except (smtplib.SMTPException, OSError):
                user.delete()  # 같은 이메일로 다시 시도할 수 있게 정리
                form.add_error(None, "인증 메일을 보내지 못했어요. 잠시 후 다시 시도해주세요.")
            else:
                return render(
                    request, "accounts/signup_done.html", {"email": user.email}
                )
    else:
        form = SignupForm()

    return render(request, "accounts/signup.html", {"form": form})


def activate(request, uidb64, token):
    try:
        user = User.objects.get(pk=force_str(urlsafe_base64_decode(uidb64)))
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    # last_login 이 없는 계정만 대상: 관리자가 비활성화한(로그인 이력이 있는) 계정은 되살리지 않는다.
    if (
        user is not None
        and user.last_login is None
        and account_activation_token.check_token(user, token)
    ):
        user.is_active = True
        user.save(update_fields=["is_active"])
        messages.success(request, "이메일 인증이 완료되었습니다. 로그인해주세요.")
        return redirect("accounts:login")

    return render(request, "accounts/activation_invalid.html", status=400)


def resend_activation(request):
    if request.method == "POST":
        form = ResendActivationForm(request.POST)
        if form.is_valid():
            user = User.objects.filter(
                email__iexact=form.cleaned_data["email"],
                is_active=False,
                last_login__isnull=True,
            ).first()
            if user:
                try:
                    _send_activation_email(request, user)
                except (smtplib.SMTPException, OSError):
                    pass
            # 가입 여부를 알 수 없도록 항상 같은 화면을 보여준다
            return render(request, "accounts/resend_activation_done.html")
    else:
        form = ResendActivationForm()

    return render(request, "accounts/resend_activation.html", {"form": form})


# ───────────── 로그아웃 / 탈퇴 ─────────────

@require_POST
def logout_view(request):
    logout(request)
    return redirect("boards:post_list")


@login_required
def withdraw(request):
    if request.method == "POST":
        request.user.delete()
        logout(request)
        return redirect("boards:post_list")

    return render(request, "accounts/withdraw.html")


# ───────────── 프로필 ─────────────

def _unique_nickname(base):
    """닉네임이 중복되면 뒤에 숫자를 붙여 유일한 값을 만든다."""
    base = base or "user"
    nickname, n = base[:30], 1
    while Profile.objects.filter(nickname=nickname).exists():
        n += 1
        nickname = f"{base[:25]}{n}"
    return nickname


def get_profile(user):
    """프로필이 없으면(예: createsuperuser 계정) 이메일 앞부분을 닉네임으로 자동 생성."""
    profile, _ = Profile.objects.get_or_create(
        user=user,
        defaults={"nickname": _unique_nickname(user.email.split("@")[0])},
    )
    return profile


@login_required
def profile_detail(request):
    profile = get_profile(request.user)
    return render(request, "accounts/profile_detail.html", {"profile": profile})


@login_required
def profile_update(request):
    profile = get_profile(request.user)

    if request.method == "POST":
        form = ProfileForm(request.POST, request.FILES, instance=profile)

        if form.is_valid():
            form.save()
            messages.success(request, "프로필이 수정되었습니다.")
            return redirect("accounts:profile_detail")
    else:
        form = ProfileForm(instance=profile)

    return render(request, "accounts/profile_update.html", {"form": form})


# ───────────── 비밀번호 변경 ─────────────

class PasswordChange(SuccessMessageMixin, PasswordChangeView):
    template_name = "accounts/password_change.html"
    success_url = reverse_lazy("accounts:profile_detail")
    success_message = "비밀번호가 변경되었습니다."