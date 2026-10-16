"""
mysite/settings.py  (개발 / 운영 겸용)

모든 민감한 값과 환경별 값은 환경변수(.env)에서 읽는다.
개발: .env 없이도 DEBUG=True 로 동작
운영: DJANGO_DEBUG=False + DJANGO_SECRET_KEY + DJANGO_ALLOWED_HOSTS 필수
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# .env 파일이 있으면 읽는다 (python-dotenv). 이미 설정된 환경변수는 덮어쓰지 않는다.
try:
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


def env_list(name, default=""):
    return [v.strip() for v in os.environ.get(name, default).split(",") if v.strip()]


# ───────────── 핵심 보안 설정 ─────────────
# Render 가이드의 DEBUG / SECRET_KEY 이름도 함께 지원한다 (DJANGO_ 접두사가 우선).
DEBUG = env_bool("DJANGO_DEBUG", env_bool("DEBUG", True))

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY") or os.environ.get("SECRET_KEY", "")
if not SECRET_KEY:
    if DEBUG:
        # 개발 전용 임시 키. 운영에서는 절대 사용되지 않는다.
        SECRET_KEY = "dev-only-insecure-key-do-not-use-in-production"
    else:
        from django.core.exceptions import ImproperlyConfigured

        raise ImproperlyConfigured("DJANGO_SECRET_KEY 환경변수를 설정하세요.")

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost" if DEBUG else "")
# HTTPS 도메인을 쓸 때 필수. 예: https://example.com,https://www.example.com
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

# Render 가 자동으로 넣어주는 호스트명 (예: mysite.onrender.com)
RENDER_EXTERNAL_HOSTNAME = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)
    CSRF_TRUSTED_ORIGINS.append(f"https://{RENDER_EXTERNAL_HOSTNAME}")

# ───────────── 앱 ─────────────
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "accounts",
    "boards",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # 정적 파일 서빙 (Render)
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",  # CSRF 보호 (끄지 말 것)
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "mysite.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "mysite.wsgi.application"

# ───────────── 데이터베이스 ─────────────
# 기본은 SQLite(개발). 운영은 DB_ENGINE=postgres 로 PostgreSQL 사용을 권장한다.
if os.environ.get("DATABASE_URL"):
    # Render PostgreSQL (Internal Database URL)
    import dj_database_url

    DATABASES = {
        "default": dj_database_url.config(conn_max_age=600, conn_health_checks=True)
    }
elif os.environ.get("DB_ENGINE", "sqlite").lower() == "postgres":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ["DB_NAME"],
            "USER": os.environ["DB_USER"],
            "PASSWORD": os.environ["DB_PASSWORD"],
            "HOST": os.environ.get("DB_HOST", "127.0.0.1"),
            "PORT": os.environ.get("DB_PORT", "5432"),
            "CONN_MAX_AGE": 60,
            "CONN_HEALTH_CHECKS": True,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
            "OPTIONS": {"timeout": 20},
        }
    }

# ───────────── 인증 / 비밀번호 정책 ─────────────
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "boards:post_list"
LOGOUT_REDIRECT_URL = "boards:post_list"

# 이메일 인증 / 비밀번호 재설정 링크 유효 시간 (초) = 24시간
PASSWORD_RESET_TIMEOUT = 60 * 60 * 24

# ───────────── 이메일 ─────────────
# 개발: 메일 내용이 서버 콘솔에 출력된다. 운영: .env 에 SMTP 정보를 넣으면 자동으로 SMTP 사용.
if os.environ.get("EMAIL_HOST"):
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = os.environ["EMAIL_HOST"]
    EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
    EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
    EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
    EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
    EMAIL_TIMEOUT = 10
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "Portfolio Board <noreply@example.com>")
SERVER_EMAIL = DEFAULT_FROM_EMAIL

# ───────────── 국제화 ─────────────
LANGUAGE_CODE = "ko-kr"
TIME_ZONE = "Asia/Seoul"
USE_I18N = True
USE_TZ = True

# ───────────── 정적 / 미디어 파일 ─────────────
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"  # collectstatic 결과물 (WhiteNoise / Nginx 가 서빙)
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"  # 사용자 업로드 (Nginx 가 서빙)

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        # 개발(DEBUG=True)에서는 manifest 없이 동작, 운영에서는 압축 + 해시 파일명
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        if DEBUG
        else "whitenoise.storage.CompressedManifestStaticFilesStorage"
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ───────────── 업로드 제한 ─────────────
# 요청 본문 전체 한도: 첨부 5개 × 10MB + 여유. (Nginx client_max_body_size 도 맞춰야 한다)
DATA_UPLOAD_MAX_MEMORY_SIZE = 60 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024  # 이보다 큰 파일은 디스크 임시 파일로 처리
DATA_UPLOAD_MAX_NUMBER_FILES = 20

# ───────────── 운영 보안 (DEBUG=False 일 때만 적용) ─────────────
if not DEBUG:
    # Nginx 가 HTTPS 를 끝내고 gunicorn 으로 넘길 때 원래 프로토콜을 알려준다.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

    # 인증서를 붙이기 전 임시로 HTTP 로 확인할 때만 DJANGO_FORCE_HTTPS=False
    _https = env_bool("DJANGO_FORCE_HTTPS", True)
    SECURE_SSL_REDIRECT = _https
    SESSION_COOKIE_SECURE = _https
    CSRF_COOKIE_SECURE = _https
    SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_HSTS_SECONDS", "3600")) if _https else 0
    # HTTPS 가 안정적으로 동작하는 것을 확인한 뒤 아래 두 값과 HSTS_SECONDS(31536000)를 올린다.
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("DJANGO_HSTS_SUBDOMAINS", False)
    SECURE_HSTS_PRELOAD = env_bool("DJANGO_HSTS_PRELOAD", False)

    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "same-origin"
    X_FRAME_OPTIONS = "DENY"

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

# ───────────── 로깅 ─────────────
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"std": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "std"}},
    "root": {"handlers": ["console"], "level": os.environ.get("DJANGO_LOG_LEVEL", "INFO")},
}