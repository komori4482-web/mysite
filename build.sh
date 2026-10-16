#!/usr/bin/env bash

set -o errexit

python -m pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate

# 관리자 계정 자동 생성 (Render 무료 플랜은 Shell 이 없으므로)
# DJANGO_SUPERUSER_EMAIL / DJANGO_SUPERUSER_PASSWORD 환경변수가 있을 때만 시도하고,
# 이미 존재하면 오류가 나지만 배포는 계속 진행한다.
if [[ -n "${DJANGO_SUPERUSER_EMAIL:-}" && -n "${DJANGO_SUPERUSER_PASSWORD:-}" ]]; then
  python manage.py createsuperuser --noinput || echo "관리자 계정이 이미 있거나 생성에 실패했습니다. (무시하고 계속)"
fi