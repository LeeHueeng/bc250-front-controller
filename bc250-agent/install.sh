#!/usr/bin/env bash
# BC250(리눅스, systemd) 에서 root 로 실행:  sudo ./install.sh <토큰>
# 토큰 = 컨트롤러 secrets.yaml 의 bc250_agent_token 값
set -euo pipefail
TOKEN="${1:-}"
if [ -z "$TOKEN" ]; then echo "사용법: sudo $0 <bc250_agent_token>"; exit 1; fi
if [ "$(id -u)" -ne 0 ]; then echo "root 로 실행해야 함 (sudo)"; exit 1; fi
DIR="$(cd "$(dirname "$0")" && pwd)"
install -m 755 "$DIR/bc250_agent.py" /usr/local/bin/bc250_agent.py
install -m 644 "$DIR/bc250-agent.service" /etc/systemd/system/bc250-agent.service
printf 'BC250_AGENT_TOKEN=%s\nBC250_AGENT_PORT=8420\n' "$TOKEN" > /etc/bc250-agent.env
chmod 600 /etc/bc250-agent.env
systemctl daemon-reload
systemctl enable --now bc250-agent.service
# 방화벽이 있으면 8420 열기 (없으면 그냥 지나감)
if command -v ufw >/dev/null 2>&1 && ufw status | grep -q "Status: active"; then ufw allow 8420/tcp || true; fi
if command -v firewall-cmd >/dev/null 2>&1 && firewall-cmd --state >/dev/null 2>&1; then firewall-cmd --permanent --add-port=8420/tcp && firewall-cmd --reload || true; fi
sleep 1
echo "--- 상태 ---"; systemctl --no-pager --lines=3 status bc250-agent.service || true
echo "--- 자체 확인: curl http://127.0.0.1:8420/health → ok 가 나와야 함 ---"
curl -s http://127.0.0.1:8420/health || true; echo
echo "컨트롤러 yaml 의 bc250_host 를 이 머신 IP 로 맞추고, 공유기에서 이 IP 를 고정(DHCP 예약)할 것: $(hostname -I 2>/dev/null || true)"
