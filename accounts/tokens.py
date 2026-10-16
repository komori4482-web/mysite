from django.contrib.auth.tokens import PasswordResetTokenGenerator


class ActivationTokenGenerator(PasswordResetTokenGenerator):
    """가입 이메일 인증용 토큰.

    is_active 값이 해시에 들어가서, 인증이 끝나면 같은 링크는 다시 쓸 수 없다.
    유효 시간은 settings.PASSWORD_RESET_TIMEOUT 을 따른다.
    """
    key_salt = "accounts.tokens.ActivationTokenGenerator"

    def _make_hash_value(self, user, timestamp):
        return f"{user.pk}{user.is_active}{timestamp}"


account_activation_token = ActivationTokenGenerator()