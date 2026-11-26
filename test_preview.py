"""Integration check against a running local preview and chromedriver on :9515."""
import base64
import json
from pathlib import Path
import time
import urllib.error
import urllib.request

BASE='http://127.0.0.1:9515'
def call(path, data=None, method=None):
    req=urllib.request.Request(BASE+path,data=json.dumps(data).encode() if data is not None else None,headers={'Content-Type':'application/json'},method=method)
    result=json.load(urllib.request.urlopen(req,timeout=60))['value']
    if isinstance(result,dict) and 'error' in result: raise AssertionError(result)
    return result

for headers,body in [({'Origin':'https://www.iheart.com'}, {'change':.05}), ({'Origin':'http://127.0.0.1:8765'}, {'change':.9})]:
    req=urllib.request.Request('http://127.0.0.1:8765/volume',data=json.dumps(body).encode(),headers={**headers,'Content-Type':'application/json'})
    try: urllib.request.urlopen(req); raise AssertionError('Invalid request accepted')
    except urllib.error.HTTPError as e: assert e.code in (400,403)

extension=str(Path('kiosk/extension').resolve())
session=call('/session',{'capabilities':{'alwaysMatch':{'browserName':'chrome','goog:chromeOptions':{'args':['--headless=new','--no-sandbox','--disable-dev-shm-usage','--window-size=1024,768','--autoplay-policy=no-user-gesture-required','--load-extension='+extension,'--disable-extensions-except='+extension]}}}})['sessionId']
Path('/tmp/pi-kiosk-preview-session').write_text(session)
base='/session/'+session
def js(script):return call(base+'/execute/sync',{'script':script,'args':[]})
call(base+'/url',{'url':'http://127.0.0.1:8765/'})
for _ in range(30):
    if js('return !document.getElementById("play").disabled'):break
    time.sleep(1)
assert js('return document.querySelectorAll(".station").length')==3
assert js('return !document.getElementById("play").disabled'),'Widget extension did not become ready'
frame=call(base+'/element',{'using':'css selector','value':'iframe'})
call(base+'/frame',{'id':frame})
assert js('return document.querySelector("iframe")===null')
assert js('return getComputedStyle(document.querySelector("a")).pointerEvents')=='none'
assert js('return getComputedStyle(document.querySelector("[data-test=share-button]")).display')=='none'
js('document.querySelector("a").click();return true')
assert len(call(base+'/window/handles'))==1,'Widget opened an outbound window'
call(base+'/frame',{'id':None})
js('document.getElementById("play").click();return true')
call(base+'/frame',{'id':frame})
playing=False
for _ in range(25):
    playing=js('return Array.from(document.querySelectorAll("audio,video")).some(m=>!m.paused&&m.readyState>=2&&m.currentTime>1)')
    if playing:break
    time.sleep(1)
assert playing,'Stream did not play'
print('Playback running inside restricted widget')
call(base+'/frame',{'id':None})
Path('preview.png').write_bytes(base64.b64decode(call(base+'/screenshot')))
js('document.getElementById("play").click();return true')
call(base+'/frame',{'id':frame})
paused=False
for _ in range(10):
    paused=js('return Array.from(document.querySelectorAll("audio,video")).every(m=>m.paused)')
    if paused:break
    time.sleep(1)
assert paused,'Pause failed'
call(base+'/frame',{'id':None})
js('document.querySelectorAll(".station")[1].click();return true')
assert js('return document.querySelector("iframe").src.includes("disney-resorts-radio-9414")')
assert js('return document.querySelectorAll(".station[aria-pressed=true]").length')==1
try:
    call(base+'/window/new',{'type':'tab'})
except urllib.error.HTTPError as e:
    # The extension can close the forbidden tab before WebDriver resolves it.
    assert e.code in (404,500)
    print('Forbidden tab closed during WebDriver creation:',json.load(e)['value']['error'])
time.sleep(2)
handles=call(base+'/window/handles')
assert len(handles)==1,'Extra tab was not closed'
call(base+'/window',{'handle':handles[0]})
call(base+'/url',{'url':'about:blank'})
time.sleep(2)
assert call(base+'/url')=='http://127.0.0.1:8765/','Top-level navigation escaped the player'
assert js('return document.querySelector("footer").getBoundingClientRect().bottom<=innerHeight'),'Controls require scrolling'
request=urllib.request.Request('http://127.0.0.1:8765/control',data=json.dumps({'playing':True,'station':2}).encode(),headers={'Origin':'http://127.0.0.1:8765','Content-Type':'application/json'})
urllib.request.urlopen(request).read()
time.sleep(12)
assert js('return document.querySelector("iframe").src.includes("iheartfamily-preschool")'),'Maintenance station control failed'
print('PASS: station selection, extension, playback, pause, navigation restrictions, maintenance control, layout, and API rejection checks')
