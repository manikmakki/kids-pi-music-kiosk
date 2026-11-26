#!/bin/sh
# A login session containing only the kiosk, never an interactive shell.
export XDG_SESSION_TYPE=wayland
export XDG_CURRENT_DESKTOP=labwc
export XDG_RUNTIME_DIR="/run/user/$(id -u)"
export DBUS_SESSION_BUS_ADDRESS="unix:path=$XDG_RUNTIME_DIR/bus"
mkdir -p "$HOME/.local/state/kids-music"
systemctl --user start pipewire.socket pipewire-pulse.socket wireplumber.service
trap 'exit 0' TERM INT HUP
while :; do
    /usr/bin/python3 /opt/kids-music/server.py --supervise >>"$HOME/.local/state/kids-music/session.log" 2>&1
    sleep 3
done
