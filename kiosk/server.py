#!/usr/bin/python3
"""Local-only touchscreen UI, sound controls, and browser watchdog. No pip packages."""
import argparse
import json
import logging
import os
from pathlib import Path
import signal
import shlex
import subprocess
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path(__file__).resolve().parent
MAX_VOLUME = 1.0
STATE = Path(os.environ.get('XDG_STATE_HOME', str(Path.home()/'.local/state'))) / 'kids-music'
STATE.mkdir(parents=True, exist_ok=True)
ORIGIN = 'http://127.0.0.1:8765'
FILES = {'/': ('index.html', 'text/html'), '/app.js': ('app.js', 'text/javascript'),
         '/style.css': ('style.css', 'text/css'), '/stations.json': ('stations.json', 'application/json')}
heartbeat = time.monotonic()
online = False
telemetry = {}
last_report = 0
control = {'id': 0}
audio_lock = threading.Lock()
stopping = threading.Event()

def run(*args):
    return subprocess.run(args, capture_output=True, text=True, timeout=6, check=True).stdout

def saved_volume():
    try:
        return min(MAX_VOLUME, max(0., float((STATE/'volume').read_text())))
    except (ValueError, OSError):
        return .40

def set_volume(value):
    value = round(min(MAX_VOLUME, max(0., value)), 2)
    run('wpctl', 'set-volume', '@DEFAULT_AUDIO_SINK@', str(value))
    run('wpctl', 'set-mute', '@DEFAULT_AUDIO_SINK@', '0')
    temp = STATE/'volume.tmp'
    temp.write_text(str(value))
    temp.replace(STATE/'volume')
    return value

def volume(change=0):
    with audio_lock:
        if change:
            return set_volume(saved_volume() + change)
        return saved_volume()

def configure_audio():
    # IDs change each login, so select the HDMI sink by its device properties.
    for _ in range(20):
        try:
            nodes = json.loads(run('pw-dump'))
            sinks = [n for n in nodes if n.get('info', {}).get('props', {}).get('media.class') == 'Audio/Sink']
            hdmi = [n for n in sinks if 'hdmi' in n['info']['props'].get('node.name', '').lower()]
            if hdmi:
                with audio_lock:
                    run('wpctl', 'set-default', str(hdmi[0]['id']))
                    set_volume(saved_volume())
                logging.info('Selected integrated display audio: %s', hdmi[0]['info']['props'].get('node.name'))
                return
        except (OSError, ValueError, subprocess.SubprocessError):
            pass
        if stopping.wait(3):
            return
    logging.error('HDMI audio was not found; retaining existing audio output')

def connectivity():
    global online
    while not stopping.is_set():
        try:
            with urllib.request.urlopen('https://www.iheart.com/live/kids-club-radio-6551/?embed=true', timeout=8) as r:
                online = r.status == 200
        except Exception:
            online = False
        stopping.wait(30)

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def send(self, status, body, content_type='application/json'):
        if not isinstance(body, bytes):
            body = json.dumps(body).encode()
        self.send_response(status)
        self.send_header('Content-Type', content_type+'; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'strict-origin-when-cross-origin')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-src https://www.iheart.com; connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def valid_host(self):
        return self.headers.get('Host') == '127.0.0.1:8765'

    def do_GET(self):
        global heartbeat
        if not self.valid_host():
            self.send(403, {'error': 'Invalid host'})
        elif self.path in FILES:
            filename, kind = FILES[self.path]
            self.send(200, (ROOT/filename).read_bytes(), kind)
        elif self.path == '/health':
            heartbeat = time.monotonic()
            self.send(200, {'online': online, 'control':control})
        elif self.path == '/volume':
            self.send(200, {'volume': volume(), 'maxVolume': MAX_VOLUME})
        elif self.path == '/diagnostics':
            self.send(200, {'online': online, 'heartbeat_age': round(time.monotonic()-heartbeat,1), 'report_age':round(time.monotonic()-last_report,1) if last_report else None, 'player':telemetry})
        else:
            self.send(404, {'error': 'Not found'})

    def do_POST(self):
        global telemetry, heartbeat, control, last_report
        if not self.valid_host() or self.headers.get('Origin') != ORIGIN or self.path not in ('/volume', '/telemetry', '/control'):
            self.send(403, {'error': 'Forbidden'})
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 1024:
                raise ValueError()
            data = json.loads(self.rfile.read(length))
            if self.path == '/control':
                if not isinstance(data,dict) or type(data.get('playing')) is not bool:
                    raise ValueError()
                if 'station' in data and (type(data['station']) is not int or data['station'] not in (0,1,2)):
                    raise ValueError()
                control = {'id':control['id']+1, 'playing':data['playing'], **({'station':data['station']} if 'station' in data else {})}
                self.send(200, control)
                return
            if self.path == '/telemetry':
                if not isinstance(data, dict) or type(data.get('station')) is not int or data['station'] not in (0,1,2):
                    raise ValueError()
                telemetry = {k:data[k] for k in ('station','wanted','ready','playing','position','error','interactions','lastInteraction') if k in data and type(data[k]) in (int,float,bool)}
                heartbeat = time.monotonic()
                last_report = heartbeat
                self.send(200, {'ok': True})
                return
            change = data['change']
            if isinstance(change, bool) or change not in (-.05, .05):
                raise ValueError()
            self.send(200, {'volume': volume(change), 'maxVolume': MAX_VOLUME})
        except (ValueError, KeyError, TypeError):
            self.send(400, {'error': 'Invalid volume change'})
        except (OSError, subprocess.SubprocessError):
            self.send(503, {'error': 'Audio is starting'})

def terminate(process):
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()

def main():
    global heartbeat, telemetry, control, last_report
    parser = argparse.ArgumentParser()
    parser.add_argument('--supervise', action='store_true')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    server = ThreadingHTTPServer(('127.0.0.1', 8765), Handler)
    server.daemon_threads = True
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stopping.set())
    threading.Thread(target=server.serve_forever, daemon=True).start()
    threading.Thread(target=connectivity, daemon=True).start()
    if args.supervise:
        threading.Thread(target=configure_audio, daemon=True).start()
        cache = Path(os.environ['XDG_RUNTIME_DIR'])/'kids-music-cache'
        cache.mkdir(exist_ok=True)
        # Use only Labwc's compositor, with this panel's mouse-emulated touch.
        # Supplying explicit bindings prevents Labwc loading desktop defaults.
        config = Path.home()/'.config/kids-labwc'
        config.mkdir(parents=True, exist_ok=True)
        blocked = ['W-Return','W-d','W-a','A-F4','A-Tab','A-S-Tab','A-space',
                   'C-l','C-t','C-n','C-S-n','C-S-t','C-w','C-S-w','C-S-Escape',
                   'C-A-Delete','F1','F11','F12']
        keys = ''.join('<keybind key="'+k+'"><action name="None"/></keybind>' for k in blocked)
        (config/'rc.xml').write_text('<labwc_config><core><xwayland>no</xwayland></core>'
            '<keyboard>'+keys+'</keyboard><mouse><context name="Root">'
            '<mousebind button="Right" action="Press"><action name="None"/></mousebind>'
            '</context></mouse><touch mapToOutput="HDMI-A-1" mouseEmulation="yes"/>'
            '<windowRules><windowRule identifier="*" serverDecoration="no" '
            'fixedPosition="yes" skipWindowSwitcher="yes"/></windowRules></labwc_config>')
        (config/'autostart').write_text('#!/bin/sh\n# No desktop applications.\n')
        (config/'shutdown').write_text('#!/bin/sh\n')
        (config/'menu.xml').write_text('<openbox_menu/>')
        (config/'environment').write_text('XKB_DEFAULT_OPTIONS=srvrkeys:none\n')
        browser = ['chromium', '--kiosk', '--ozone-platform=wayland',
                   '--force-device-scale-factor=1.5',
                   '--no-first-run', '--no-default-browser-check', '--disable-session-crashed-bubble',
                   '--disable-pinch', '--overscroll-history-navigation=0', '--disable-sync',
                   '--autoplay-policy=no-user-gesture-required', '--password-store=basic',
                   '--disable-features=TranslateUI', '--disk-cache-size=16777216',
                   '--media-cache-size=16777216', '--disk-cache-dir='+str(cache),
                   '--user-data-dir='+str(Path.home()/'.config/kids-chromium'),
                   '--load-extension='+str(ROOT/'extension'),
                   '--disable-extensions-except='+str(ROOT/'extension'), ORIGIN+'/']
        command = ['labwc', '-C', str(config), '-S', shlex.join(browser)]
        while not stopping.is_set():
            heartbeat = time.monotonic()
            telemetry, control, last_report = {}, {'id':0}, 0
            with open(STATE/'browser.log', 'w') as log:
                process = subprocess.Popen(command, stdout=log, stderr=log, start_new_session=True)
                try:
                    while not stopping.wait(5):
                        if process.poll() is not None:
                            logging.warning('Browser exited; restarting')
                            break
                        if time.monotonic()-heartbeat > 150:
                            logging.warning('Browser stopped responding; restarting')
                            break
                finally:
                    terminate(process)
            stopping.wait(3)
    else:
        stopping.wait()
    server.shutdown()
    server.server_close()

if __name__ == '__main__':
    main()
