# Pi touchscreen music player

Target: `pi@192.x.y.z`, Raspberry Pi 3 B+, Debian 13 arm64.

The `kiosk/` directory contains the complete installer and application. It uses
distribution Chromium, a minimal Labwc compositor, PipeWire and Python's standard library. The UI
embeds the official iHeart player for Kids Club, Disney Resorts and Preschool;
it does not use undocumented stream endpoints or an old Electron runtime.

## Install and activate

The installer requires one authenticated sudo invocation on the Pi:

```sh
sudo bash /home/pi/pi-kiosk/install.sh
```

This stages the application under `/opt/kids-music`, creates the unprivileged
`music` account, backs up configuration under `/var/backups/kids-music`, enables
automatic distribution updates, and installs a root-owned maintenance helper.
It leaves the existing desktop running. The helper has a narrow sudo rule for
`pi` covering status, activation, restart, player-file refresh, a browser
recovery test, reboot and rollback. Refresh reads a fixed set of application
assets as `pi` and copies them to fixed root-owned destinations; it cannot
replace the privileged maintenance helper or installer.

Then activate:

```sh
sudo /usr/local/sbin/kids-kiosk-admin activate
```

Activation changes the LightDM login to the dedicated kiosk session, applies Chromium
navigation policies, prevents polkit privilege prompts for the music account,
disables Wi-Fi power saving on the next network activation, and disables the
existing tty1 login. It closes the existing desktop session. SSH administration
as `pi` remains available.

Chromium policies are machine-wide: the administrator's Chromium is restricted
too while the kiosk is active. The iframe sandbox and extension block outgoing
links, sharing, context menus and browser keyboard shortcuts. Labwc runs with
no desktop, panels or launchers; explicit bindings suppress its desktop defaults.
Mouse emulation maps the TSTP touchscreen onto HDMI-A-1. The XKB option
`srvrkeys:none` removes virtual-terminal-switch keysyms (verified against the
default Ctrl+Alt+F2 mapping). This is a child-resistant interface, not
protection against someone dismantling or booting different media on the Pi.

## Recovery and maintenance

The player remembers the chosen station, playing/paused intent and volume. It
reconnects after an internet interruption, reloads stalled playback, restarts a
crashed browser and replaces an unresponsive browser after 150 seconds without
a UI heartbeat. The session wrapper restarts the Python supervisor if needed.
Browser cache is limited and lives in the session's RAM-backed runtime directory.
HDMI audio is chosen by device properties, avoiding changing device IDs; volume
starts at 40% and can be adjusted up to 100%. The current setting is remembered.
The bottom play/pause button is the only visible playback control. The middle
station card is compact, and bottom controls are enlarged for touch (80 px tall
with 104 px-wide volume buttons at the Pi's effective 1280 × 720 layout).

Automatic distribution updates run daily. While the kiosk is active, a weekly
reboot on Sunday between **4:15 and 4:25 a.m. America/New_York** loads updated
software and clears long-lived browser state. Missed reboots are not run late.
The iHeart service and internet connection are external dependencies.

```sh
sudo /usr/local/sbin/kids-kiosk-admin status
sudo /usr/local/sbin/kids-kiosk-admin restart
sudo /usr/local/sbin/kids-kiosk-admin refresh
sudo /usr/local/sbin/kids-kiosk-admin rollback
```

Rollback restores the original LightDM configuration and desktop login, removes
kiosk browser/network/polkit policies, re-enables tty1 login and disables the
weekly reboot. It retains application files, the dedicated account, automatic
distribution updates and backups.

Logs: `/home/music/.local/state/kids-music/{session,browser}.log`.
The browser log is replaced each restart. Session logs are rotated by logrotate
after installation. The local control server listens only on `127.0.0.1:8765`.
Volume changes require same-origin POSTs with bounded input; it accepts no URLs,
commands or arbitrary paths from the touchscreen interface.

## Verification

Local integration test: start `kiosk/server.py` and chromedriver on port 9515,
then run `python3 test_preview.py`. It checks the three-station menu, extension
loading, actual stream progress, pause, outbound popup prevention, and rejected
cross-origin/malformed control requests. A screenshot is saved as `preview.png`.
Final device verification must also cover audio routing, a cold boot, browser
recovery, and the actual touchscreen. Integrated-speaker audibility requires a
person beside the Pi to confirm.

`backups/pi-before.tgz` contains the initial desktop/boot/browser-session backup.
It may include private browsing information and should not be published.

## Device verification, 2026-11-26

- Dedicated `music` login, minimal compositor and browser started automatically.
- Integrated-speaker sound and display were confirmed by the owner.
- Reboot returned at the same address and resumed the selected station.
- Deliberate Chromium termination produced a new browser process and fresh,
  advancing playback reports. Slow startup/buffering can take about a minute.
- Fresh-boot operation used roughly 525–555 MiB RAM with about 350–380 MiB
  available; swap pressure was substantially lower after reboot.
- No recurring Wi-Fi errors or power/thermal throttling were seen after reboot.
- Local browser checks covered all three streams, pause, reconnect after a
  simulated network interruption, navigation restrictions and maintenance API.
- Touchscreen operation was confirmed by the owner with the deployed Labwc
  session, mouse emulation and HDMI mapping. Sound, display and touch checks
  are complete.
- The revised layout retained the station row, reduced the middle card from
  444 to 229 px, and enlarged bottom buttons from 64 to 80 px tall at 1280 × 720.
  Browser checks confirmed playback and pause with the duplicate control hidden.
  After deployment, Preschool resumed and the saved 70% volume was retained;
  the volume API reports the new 100% ceiling. An isolated volume check covered
  reaching 100% and clamping both ends without changing the device's sound.

Sources:

- [iHeart's supported embed player](https://help.iheart.com/hc/en-us/articles/115000879272-How-do-I-add-iHeartRadio-to-my-website)
- [Labwc configuration and touch emulation](https://labwc.github.io/labwc-config.5.html)
- [Chromium URL restrictions](https://support.google.com/chrome/a/answer/7532419)
