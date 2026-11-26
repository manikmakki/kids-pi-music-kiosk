#!/bin/bash
# Stage the kiosk. It is activated separately after inspection.
set -euo pipefail
[[ $EUID == 0 ]] || { echo 'Run this installer with sudo.'; exit 1; }
SOURCE=$(cd -- "$(dirname -- "$0")" && pwd)
BACKUP="/var/backups/kids-music/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP" /var/lib/kids-music
tar -czf "$BACKUP/config.tgz" --ignore-failed-read /etc/lightdm /etc/chromium/policies /etc/NetworkManager/conf.d /etc/apt/apt.conf.d /etc/polkit-1/rules.d /etc/systemd/system/getty@tty1.service.d 2>/dev/null || [[ $? == 1 ]]
echo "Backup: $BACKUP/config.tgz"
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y labwc chromium python3 pipewire pipewire-pulse wireplumber unattended-upgrades
id music >/dev/null 2>&1 || useradd --create-home --shell /bin/bash --comment 'Kids music kiosk' music
usermod -aG audio,video,render music
install -d -m 755 /opt/kids-music /opt/kids-music/extension
for f in server.py index.html style.css app.js stations.json; do install -m 644 "$SOURCE/$f" "/opt/kids-music/$f"; done
for f in manifest.json player.js player.css background.js; do install -m 644 "$SOURCE/extension/$f" "/opt/kids-music/extension/$f"; done
install -m 755 "$SOURCE/session.sh" /usr/local/bin/kids-music-session
install -m 755 "$SOURCE/admin.sh" /usr/local/sbin/kids-kiosk-admin
install -d /usr/share/wayland-sessions /etc/lightdm/lightdm.conf.d /etc/chromium/policies/managed /etc/NetworkManager/conf.d /etc/polkit-1/rules.d
if [[ ! -f /var/lib/kids-music/original-lightdm.conf ]]; then
    cp -a /etc/lightdm/lightdm.conf /var/lib/kids-music/original-lightdm.conf
fi
cat >/usr/share/wayland-sessions/kids-music.desktop <<'EOF'
[Desktop Entry]
Name=Kids Music
Comment=Dedicated touchscreen music player
Exec=/usr/local/bin/kids-music-session
Type=Application
DesktopNames=labwc
EOF
# Staging leaves the current autologin untouched until the admin activate step.
cat >/var/lib/kids-music/lightdm.conf <<'EOF'
[Seat:*]
autologin-user=music
autologin-user-timeout=0
autologin-session=kids-music
user-session=kids-music
allow-user-switching=false
allow-guest=false
greeter-hide-users=true
greeter-show-manual-login=false
EOF
# Chromium reads machine-wide root-owned policy files. They also restrict the
# administrator's Chromium while active. Rollback restores normal browsing.
python3 -I - "$SOURCE/stations.json" <<'PY'
import json,sys
stations=json.load(open(sys.argv[1]))
policy={
 'URLBlocklist':['*'],
 'URLAllowlist':['http://127.0.0.1:8765/']+['https://www.iheart.com'+s['path'] for s in stations],
 'DeveloperToolsAvailability':2, 'DownloadRestrictions':3,
 'PrintingEnabled':False, 'BrowserSignin':0, 'SyncDisabled':True,
 'PasswordManagerEnabled':False, 'BrowserGuestModeEnabled':False,
 'BrowserAddPersonEnabled':False, 'IncognitoModeAvailability':1,
 'DefaultPopupsSetting':2, 'DefaultNotificationsSetting':2,
 'DefaultGeolocationSetting':2, 'AudioCaptureAllowed':False,
 'VideoCaptureAllowed':False, 'TranslateEnabled':False,
 'AutofillAddressEnabled':False, 'AutofillCreditCardEnabled':False,
 'HideCrashRestoreBubble':True, 'BackgroundModeEnabled':False,
 'DefaultBrowserSettingEnabled':False,
}
json.dump(policy,open('/var/lib/kids-music/chromium-policy.json','w'),indent=2)
PY
cat >/var/lib/kids-music/wifi.conf <<'EOF'
[connection]
wifi.powersave=2
EOF
cat >/var/lib/kids-music/polkit.rules <<'EOF'
polkit.addRule(function(action, subject) {
    if (subject.user == "music") return polkit.Result.NO;
});
EOF
cat >/etc/apt/apt.conf.d/52kids-music-updates <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
Unattended-Upgrade::Origins-Pattern {
    "origin=Debian,codename=${distro_codename},label=Debian";
    "origin=Debian,codename=${distro_codename}-security,label=Debian-Security";
    "origin=Raspberry Pi Foundation,codename=${distro_codename}";
};
Unattended-Upgrade::Automatic-Reboot "false";
EOF
cat >/etc/sudoers.d/kids-music-maintenance <<'EOF'
pi ALL=(root) NOPASSWD: /usr/local/sbin/kids-kiosk-admin status, /usr/local/sbin/kids-kiosk-admin activate, /usr/local/sbin/kids-kiosk-admin restart, /usr/local/sbin/kids-kiosk-admin refresh, /usr/local/sbin/kids-kiosk-admin test-browser-recovery, /usr/local/sbin/kids-kiosk-admin reboot, /usr/local/sbin/kids-kiosk-admin rollback
EOF
chmod 440 /etc/sudoers.d/kids-music-maintenance
visudo -cf /etc/sudoers.d/kids-music-maintenance
cat >/etc/systemd/system/kids-music-maintenance.service <<'EOF'
[Unit]
Description=Refresh the kids music appliance after automatic updates
[Service]
Type=oneshot
ExecStart=/usr/local/sbin/kids-kiosk-admin maintenance
EOF
cat >/etc/systemd/system/kids-music-maintenance.timer <<'EOF'
[Unit]
Description=Weekly overnight maintenance for the music player
[Timer]
OnCalendar=Sun *-*-* 04:15:00 America/New_York
RandomizedDelaySec=10m
Persistent=false
[Install]
WantedBy=timers.target
EOF
systemctl daemon-reload
cat >/etc/logrotate.d/kids-music <<'EOF'
/home/music/.local/state/kids-music/session.log {
    weekly
    rotate 2
    maxsize 1M
    missingok
    notifempty
    copytruncate
    su music music
}
EOF
systemctl enable apt-daily.timer apt-daily-upgrade.timer
echo 'Kiosk staged. The existing desktop is still running.'
echo 'Activate with: sudo /usr/local/sbin/kids-kiosk-admin activate'
