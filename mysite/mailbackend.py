"""콘솔 메일 백엔드 + 즉시 flush.

Render 같은 호스팅 로그에서는 stdout 이 버퍼링되어 메일 내용이 늦게 나오거나
안 보일 수 있다. SMTP 를 설정하기 전까지 인증 링크를 로그에서 확인하는 용도.
"""
import sys

from django.core.mail.backends.console import EmailBackend as ConsoleEmailBackend


class FlushConsoleEmailBackend(ConsoleEmailBackend):
    def write_message(self, message):
        super().write_message(message)
        self.stream.flush()
        sys.stdout.flush()