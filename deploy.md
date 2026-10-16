# 배포 순서 (Ubuntu + Nginx + gunicorn + PostgreSQL)

## 1. 서버 준비
```bash
sudo apt update && sudo apt install -y python3-venv python3-dev nginx postgresql libpq-dev certbot
sudo -u postgres psql -c "CREATE USER portfolio WITH PASSWORD '강력한비밀번호';"
sudo -u postgres psql -c "CREATE DATABASE portfolio OWNER portfolio;"
```

## 2. 코드와 환경
```bash
sudo mkdir -p /srv/portfolio && sudo chown deploy:deploy /srv/portfolio
cd /srv/portfolio            # 여기에 프로젝트 파일 복사 (git clone 등)
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env && chmod 600 .env     # 값 채우기 (SECRET_KEY, 도메인, DB, 메일)
```

## 3. 초기화
```bash
set -a; source .env; set +a
.venv/bin/python manage.py migrate
.venv/bin/python manage.py collectstatic --noinput
.venv/bin/python manage.py createsuperuser
.venv/bin/python manage.py check --deploy      # 경고 0개가 목표
mkdir -p media && sudo chgrp -R www-data media && sudo chmod -R g+rX media
```
> 업로드 폴더(`media/`)는 gunicorn(deploy 사용자)이 쓰고 Nginx(www-data)가 읽어야 합니다.
> 새 하위 폴더도 읽히도록 `chmod g+s media` 를 권장합니다.

## 4. 서비스 등록
```bash
sudo cp deploy/portfolio.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now portfolio
sudo cp deploy/nginx.conf /etc/nginx/sites-available/portfolio   # 도메인 수정
sudo ln -s /etc/nginx/sites-available/portfolio /etc/nginx/sites-enabled/
```

## 5. HTTPS
인증서가 없으면 nginx.conf 의 443 블록에서 nginx -t 가 실패합니다. 처음에는 80 블록만 두고:
```bash
sudo certbot certonly --webroot -w /var/www/certbot -d example.com -d www.example.com
sudo nginx -t && sudo systemctl reload nginx
```
HTTPS 가 확인되면 `.env` 의 `DJANGO_HSTS_SECONDS` 를 3600 → 86400 → 31536000 으로 단계적으로 올립니다.

## 6. 업데이트 배포
```bash
git pull && .venv/bin/pip install -r requirements.txt
set -a; source .env; set +a
.venv/bin/python manage.py migrate && .venv/bin/python manage.py collectstatic --noinput
sudo systemctl reload portfolio
```

## 7. 백업
- DB: `pg_dump -U portfolio portfolio > backup_$(date +%F).sql` (cron 으로 매일)
- 업로드: `media/` 폴더를 함께 백업

## 오류 확인
- `sudo journalctl -u portfolio -f` (앱 로그)
- `sudo tail -f /var/log/nginx/error.log`