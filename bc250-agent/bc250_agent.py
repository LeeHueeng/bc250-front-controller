#!/usr/bin/env python3
"""BC250 종료 에이전트 — 전면 컨트롤러(ESP32, bc250-front-st7789.yaml)가 정상 종료를 요청하는 아주 작은 HTTP 서버.

  GET  /health    → 200 "ok"              컨트롤러가 "OS 아직 살아 있나" 확인용 (토큰 불필요)
  POST /shutdown  → 200 "shutting down"   → 1초 뒤 `systemctl poweroff`   (헤더 X-Token 필수)
  POST /reboot    → 200 "rebooting"       → 1초 뒤 `systemctl reboot`     (헤더 X-Token 필수)

환경변수  BC250_AGENT_TOKEN  필수 — 컨트롤러 secrets.yaml 의 bc250_agent_token 과 같은 값. 없거나 다르면 403.
          BC250_AGENT_PORT   기본 8420 (컨트롤러 yaml substitutions bc250_agent_port 와 같아야 함)
          BC250_AGENT_BIND   기본 0.0.0.0
표준 라이브러리만 사용. root 로 돌려야 poweroff 가 됨 → bc250-agent.service 참고. 설치는 docs/wiring-guide-st7789.html 11장.
"""
import hmac
import http.server
import os
import subprocess
import sys
import threading
import time

TOKEN = os.environ.get("BC250_AGENT_TOKEN", "")
PORT = int(os.environ.get("BC250_AGENT_PORT", "8420"))
BIND = os.environ.get("BC250_AGENT_BIND", "0.0.0.0")

ACTIONS = {
    "/shutdown": (["systemctl", "poweroff"], "shutting down"),
    "/reboot": (["systemctl", "reboot"], "rebooting"),
}


def _run_later(cmd, delay=1.0):
    """응답을 먼저 보내고 잠시 뒤 실행 — 컨트롤러가 2xx 를 받은 뒤에 네트워크가 내려가도록."""
    def _go():
        time.sleep(delay)
        subprocess.call(cmd)
    threading.Thread(target=_go, daemon=True).start()


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "bc250-agent/1.0"

    def _send(self, code, body):
        data = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _authorized(self):
        given = self.headers.get("X-Token", "")
        return bool(TOKEN) and hmac.compare_digest(given, TOKEN)

    def do_GET(self):
        if self.path == "/health":
            return self._send(200, "ok")
        self._send(404, "not found")

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length:
            self.rfile.read(length)  # 본문은 안 씀
        action = ACTIONS.get(self.path)
        if action is None:
            return self._send(404, "not found")
        if not self._authorized():
            print(f"거부: {self.path} from {self.client_address[0]} (토큰 불일치)", flush=True)
            return self._send(403, "forbidden")
        cmd, msg = action
        print(f"실행: {' '.join(cmd)} (요청: {self.client_address[0]})", flush=True)
        self._send(200, msg)
        _run_later(cmd)

    def log_message(self, fmt, *args):  # journald 로 한 줄씩
        print(f"{self.client_address[0]} {fmt % args}", flush=True)


def main():
    if not TOKEN:
        print("BC250_AGENT_TOKEN 이 비어 있음 — /etc/bc250-agent.env 를 확인. 종료 요청은 전부 403 으로 거부됨", file=sys.stderr, flush=True)
    srv = http.server.ThreadingHTTPServer((BIND, PORT), Handler)
    print(f"bc250-agent listening on {BIND}:{PORT}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
