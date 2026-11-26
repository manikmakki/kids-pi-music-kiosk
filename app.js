'use strict';
const $ = id => document.getElementById(id);
let stations = [], frame, selected = Number(localStorage.station || 0), wanted = localStorage.playing === 'true', ready = false, reloadAt = 0, lastControl = 0;
let interactions=0,lastInteraction=0;
document.addEventListener('pointerdown',e=>{if(e.isTrusted){interactions++;lastInteraction=Date.now();}},true);
function say(text) { $('message').textContent = text; }
function command(action) { frame?.contentWindow.postMessage({type:'kids-music-command',action}, 'https://www.iheart.com'); }
function loadStation(index) {
  selected = index; localStorage.station = index; ready = false;
  $('play').disabled = true; $('station-name').textContent = stations[index].name;
  document.querySelectorAll('.station').forEach((b,i) => b.setAttribute('aria-pressed', String(i === index)));
  frame?.remove(); frame = document.createElement('iframe');
  frame.title = stations[index].name + ' on iHeartRadio';
  frame.sandbox = 'allow-scripts allow-same-origin';
  frame.allow = 'autoplay'; frame.referrerPolicy = 'strict-origin-when-cross-origin';
  frame.src = 'https://www.iheart.com' + stations[index].path + '?embed=true&theme=dark';
  $('frame-holder').replaceChildren(frame); reloadAt = Date.now();
  say(navigator.onLine ? 'Getting your music ready…' : 'Waiting for the internet. Your music will reconnect.');
}
window.addEventListener('message', e => {
  if (e.origin !== 'https://www.iheart.com' || e.source !== frame?.contentWindow || e.data?.type !== 'kids-music-status') return;
  if (e.data.ready) { ready = true; $('play').disabled = false; }
  if (e.data.userIntent !== undefined) { wanted = e.data.userIntent; localStorage.playing = wanted; }
  if (ready) command(wanted ? 'play' : 'pause');
  $('play').textContent = wanted ? 'Ⅱ Pause music' : '▶ Play music';
  say(e.data.error ? 'Having trouble connecting. We’ll try again.' : e.data.playing ? 'Enjoy the music.' : wanted ? 'Connecting to your station…' : 'Tap play when you’re ready.');
  if (wanted && e.data.stalled && Date.now() - reloadAt > 90000) loadStation(selected);
  api('/telemetry',{station:selected,wanted,ready,playing:!!e.data.playing,position:e.data.position||0,error:!!e.data.error,interactions,lastInteraction}).catch(()=>{});
});
async function api(path, data) {
  const response = await fetch(path, data ? {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)} : {});
  if (!response.ok) throw new Error('Unavailable');
  return response.json();
}
async function volume(change) {
  try {
    const v = await api('/volume', change ? {change} : null);
    $('volume').textContent = Math.round(v.volume*100)+'%';
    $('louder').disabled = v.volume >= v.maxVolume;
    $('quieter').disabled = v.volume <= 0;
  } catch { $('volume').textContent='—'; }
}
$('play').onclick = () => { wanted = !wanted; localStorage.playing = wanted; command(wanted ? 'play' : 'pause'); $('play').textContent = wanted ? 'Ⅱ Pause music' : '▶ Play music'; };
$('quieter').onclick = () => volume(-0.05); $('louder').onclick = () => volume(0.05);
$('retry').onclick = () => loadStation(selected);
window.addEventListener('online', () => { $('connection').textContent='Reconnecting…'; loadStation(selected); });
window.addEventListener('offline', () => { $('connection').textContent='Waiting for internet'; say('Your music will reconnect when the internet returns.'); });
document.addEventListener('contextmenu', e => e.preventDefault());
document.addEventListener('keydown', e => { if(e.altKey || e.metaKey || e.ctrlKey || /^F\d+$/.test(e.key) || e.key==='Escape') e.preventDefault(); }, true);
setInterval(async () => {
  try { const h = await api('/health'); $('connection').textContent = h.online ? 'Ready to listen' : 'Waiting for internet';
    if(h.control?.id > lastControl) { lastControl=h.control.id; wanted=h.control.playing; localStorage.playing=wanted;
      if(h.control.station!==undefined && h.control.station!==selected)loadStation(h.control.station);
      command(wanted?'play':'pause'); $('play').textContent=wanted?'Ⅱ Pause music':'▶ Play music';
    }
  } catch { say('Reconnecting to your player…'); }
  if (!ready && Date.now()-reloadAt>60000) loadStation(selected);
}, 10000);
fetch('/stations.json').then(r=>r.json()).then(s => { stations=s; if(!s[selected]) selected=0;
  stations.forEach((station,i) => { const b=document.createElement('button'); b.className='station'; b.style.background=station.color;
    const symbol=document.createElement('span'); symbol.className='symbol'; symbol.textContent=station.symbol;
    const name=document.createElement('strong'); name.textContent=station.name;
    const desc=document.createElement('small'); desc.textContent=station.description;
    b.append(symbol,name,desc); b.onclick=()=>loadStation(i); $('stations').append(b); });
  loadStation(selected); volume(); api('/health').catch(()=>{});
}).catch(()=>say('The station menu couldn’t load. Please restart the player.'));
