# gunicorn -c deploy/gunicorn.conf.py mysite.wsgi:application
import multiprocessing

bind = "unix:/run/portfolio/gunicorn.sock"  # Nginx 와 같은 서버에서 소켓으로 통신
workers = max(2, multiprocessing.cpu_count() * 2 + 1)
timeout = 30
graceful_timeout = 30
max_requests = 1000          # 메모리 누수 방지를 위해 주기적으로 워커 재시작
max_requests_jitter = 100
accesslog = "-"
errorlog = "-"
forwarded_allow_ips = "127.0.0.1"  # Nginx 가 보낸 X-Forwarded-* 만 신뢰