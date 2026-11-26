#!/bin/bash
set -euo pipefail
[[ $EUID == 0 ]] || { echo 'Use sudo for this command.'; exit 1; }
[[ $# == 1 ]] || exit 2
case "$1" in
  refresh)
    # Read the fixed asset list as pi, so this cannot copy root-only files.
    # Every destination is fixed and root-owned; all code runs as music.
    stage=$(mktemp -d)
    trap 'rm -rf "$stage"' EXIT
    for f in server.py index.html style.css app.js stations.json extension/manifest.json extension/player.js extension/player.css extension/background.js; do
      mkdir -p "$stage/$(dirname "$f")"
      runuser -u pi -- /bin/cat "/home/pi/pi-kiosk/$f" >"$stage/$f"
    done
    runuser -u pi -- /bin/cat /home/pi/pi-kiosk/session.sh >"$stage/session.sh"
    for f in server.py index.html style.css app.js stations.json extension/manifest.json extension/player.js extension/player.css extension/background.js; do
      install -m 644 "$stage/$f" "/opt/kids-music/$f"
    done
    install -m 755 "$stage/session.sh" /usr/local/bin/kids-music-session
    echo 'Player files refreshed. Restart the kiosk to load them.'
    ;;
  status)
    systemctl status lightdm --no-pager || true
    loginctl list-sessions
    pgrep -a -u music 'cage|chromium|python3' || true
    tail -40 /home/music/.local/state/kids-music/session.log 2>/dev/null || true
    tail -40 /home/music/.local/state/kids-music/browser.log 2>/dev/null || true
    python3 -I - <<'PY'
import urllib.request
try: print('Player diagnostics:',urllib.request.urlopen('http://127.0.0.1:8765/diagnostics',timeout=3).read().decode())
except Exception as e: print('Player not responding:',e)
PY
    music_uid=$(id -u music)
    runuser -u music -- env XDG_RUNTIME_DIR="/run/user/$music_uid" wpctl status || true
    ;;
  activate)
    install -m 644 /var/lib/kids-music/lightdm.conf /etc/lightdm/lightdm.conf.d/90-kids-music.conf
    install -m 644 /var/lib/kids-music/chromium-policy.json /etc/chromium/policies/managed/kids-music.json
    install -m 644 /var/lib/kids-music/wifi.conf /etc/NetworkManager/conf.d/90-kids-music-wifi.conf
    install -m 644 /var/lib/kids-music/polkit.rules /etc/polkit-1/rules.d/49-kids-music.rules
    python3 -I - <<'PY'
import configparser
p=configparser.ConfigParser(interpolation=None,strict=False)
p.read('/etc/lightdm/lightdm.conf')
q=configparser.ConfigParser(interpolation=None)
q.read('/var/lib/kids-music/lightdm.conf')
for key,value in q['Seat:*'].items(): p['Seat:*'][key]=value
with open('/etc/lightdm/lightdm.conf','w') as f:p.write(f,space_around_delimiters=False)
PY
    touch /var/lib/kids-music/active
    systemctl enable --now kids-music-maintenance.timer
    systemctl disable --now getty@tty1.service
    systemctl restart lightdm
    ;;
  restart) systemctl restart lightdm ;;
  test-browser-recovery) pkill -TERM -u music -x chromium || true ;;
  reboot) systemctl reboot ;;
  maintenance)
    if [[ -f /var/lib/kids-music/active ]]; then systemctl reboot; fi
    ;;
  rollback)
    systemctl disable --now kids-music-maintenance.timer
    install -m 644 /var/lib/kids-music/original-lightdm.conf /etc/lightdm/lightdm.conf
    rm -f /etc/lightdm/lightdm.conf.d/90-kids-music.conf
    rm -f /etc/chromium/policies/managed/kids-music.json
    rm -f /etc/NetworkManager/conf.d/90-kids-music-wifi.conf
    rm -f /etc/polkit-1/rules.d/49-kids-music.rules
    rm -f /var/lib/kids-music/active
    systemctl enable getty@tty1.service
    systemctl restart lightdm
    echo 'Original desktop restored. Kiosk files and backups are retained.'
    ;;
  *) echo 'Usage: kids-kiosk-admin {status|activate|restart|refresh|test-browser-recovery|reboot|rollback}'; exit 2 ;;
esac
