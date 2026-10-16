# accounts/models.py
from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra):
        if not email:
            raise ValueError("이메일은 필수입니다.")
        user = self.model(email=self.normalize_email(email), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        return self._create_user(email, password, **extra)


class User(AbstractUser):
    username = None                      # username 제거
    email = models.EmailField("이메일", unique=True)

    USERNAME_FIELD = "email"             # 이메일로 로그인
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        db_table = "accounts_user"
        verbose_name = "회원"
        verbose_name_plural = "회원 목록"


class Profile(models.Model):
    """
    회원 프로필 CRUD 대상 모델
    회원 탈퇴 시 프로필도 함께 삭제된다.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile",
        verbose_name="회원",
    )
    nickname = models.CharField(
        "닉네임",
        max_length=30,
        unique=True,
    )
    bio = models.TextField(
        "자기소개",
        blank=True,
    )
    profile_image = models.ImageField(
        "프로필 이미지",
        upload_to="profile_images/%Y/%m/",
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(
        "생성일",
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        "수정일",
        auto_now=True,
    )

    class Meta:
        db_table = "accounts_profile"
        verbose_name = "회원 프로필"
        verbose_name_plural = "회원 프로필 목록"

    def __str__(self):
        return self.nickname