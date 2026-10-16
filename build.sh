#!/usr/bin/env bash

set -o errexit

python -m pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate

# 관리자 계정 생성/복구 (Render 무료 플랜은 Shell 이 없으므로)
# 환경변수 DJANGO_SUPERUSER_EMAIL / DJANGO_SUPERUSER_PASSWORD 가 있을 때만 실행한다.
#  - 계정이 없으면 새로 만들고
#  - 이미 있으면(일반 가입 계정 포함) 관리자 권한 + 활성화 + 비밀번호를 환경변수 값으로 맞춘다.
if [[ -n "${DJANGO_SUPERUSER_EMAIL:-}" && -n "${DJANGO_SUPERUSER_PASSWORD:-}" ]]; then
python manage.py shell <<'PY'
import os
from django.contrib.auth import get_user_model

User = get_user_model()
email = os.environ["DJANGO_SUPERUSER_EMAIL"].strip()
password = os.environ["DJANGO_SUPERUSER_PASSWORD"]

user = User.objects.filter(email__iexact=email).first()
if user is None:
    User.objects.create_superuser(email=email, password=password)
    print(f"[관리자] 새로 생성: {email}")
else:
    user.email = email  # 대소문자까지 환경변수 값과 똑같이 맞춘다 (로그인 시 일치해야 함)
    user.is_staff = True
    user.is_superuser = True
    user.is_active = True
    user.set_password(password)
    user.save()
    print(f"[관리자] 기존 계정을 관리자로 갱신: {email}")
PY
else
  echo "[관리자] DJANGO_SUPERUSER_EMAIL / DJANGO_SUPERUSER_PASSWORD 가 설정되지 않아 건너뜀"
fi