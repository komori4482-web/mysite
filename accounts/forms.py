from django import forms
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile

from .models import Profile

User = get_user_model()

MAX_PROFILE_IMAGE = 5 * 1024 * 1024  # 5MB


class SignupForm(UserCreationForm):
    nickname = forms.CharField(max_length=30, label="닉네임")
    field_order = ["email", "nickname", "password1", "password2"]

    class Meta:
        model = User
        fields = ("email",)

    def clean_nickname(self):
        nickname = self.cleaned_data["nickname"]
        if Profile.objects.filter(nickname=nickname).exists():
            raise forms.ValidationError("이미 사용 중인 닉네임입니다.")
        return nickname


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ("nickname", "bio", "profile_image")

    def clean_profile_image(self):
        image = self.cleaned_data.get("profile_image")
        # 새로 올린 파일만 검사 (기존 파일 유지/삭제는 그대로 통과)
        if isinstance(image, UploadedFile) and image.size > MAX_PROFILE_IMAGE:
            raise forms.ValidationError("프로필 이미지는 5MB 이하만 올릴 수 있어요.")
        return image


class ResendActivationForm(forms.Form):
    email = forms.EmailField(label="이메일")


class CustomLoginForm(AuthenticationForm):
    login_error_code = None  # 템플릿에서 읽는 값

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "이메일"  # 필드 이름은 username 그대로

    def clean(self):
        username = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")

        if username and password:
            self.user_cache = authenticate(
                self.request, username=username, password=password,
            )

            if self.user_cache is None:
                user = User.objects.filter(
                    **{User.USERNAME_FIELD: username}
                ).first()

                if user is None:
                    code = "invalid_username"
                    msg = "존재하지 않는 아이디입니다."
                elif not user.is_active:
                    code = "inactive"
                    msg = "이메일 인증이 완료되지 않았거나 사용할 수 없는 계정입니다."
                else:
                    code = "invalid_password"
                    msg = "비밀번호가 맞지 않습니다."

                self.login_error_code = code
                raise ValidationError(msg, code=code)

            self.confirm_login_allowed(self.user_cache)

        return self.cleaned_data