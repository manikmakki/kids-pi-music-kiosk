'use strict';
if (new URL(location.href).searchParams.get('embed') === 'true' && window.parent !== window) {
  let desired = false, changed = Date.now(), lastTime = -1, lastClick = 0;
  const media = () => document.querySelector('audio,video');
  const button = () => document.querySelector('[data-test="play-button"]');
  function intent(playing) { desired=playing; changed=Date.now(); report(playing); }
  function report(userIntent) {
    const m=media();
    if(m && !m.paused && m.currentTime!==lastTime) { changed=Date.now(); lastTime=m.currentTime; }
    const data={type:'kids-music-status',ready:!!button(),playing:!!m&&!m.paused&&m.readyState>=2,position:m?.currentTime||0,error:!!m?.error,stalled:desired&&Date.now()-changed>45000};
    if(userIntent!==undefined) data.userIntent=userIntent;
    window.parent.postMessage(data,'http://127.0.0.1:8765');
  }
  function apply(force=false) {
    const b=button(), m=media(), label=b?.getAttribute('aria-label')?.toLowerCase() || '';
    // On a Pi, connection setup can outlast the button's loading animation.
    // Re-clicking Play too soon can cancel a stream that is still buffering.
    if (!b || (!force && Date.now()-lastClick<30000)) return;
    if(desired && m && !m.paused) return;
    if ((desired && label==='play') || (!desired && (label==='pause'||label==='stop'))) { lastClick=Date.now(); b.click(); }
  }
  window.addEventListener('message',e=>{
    if(e.origin!=='http://127.0.0.1:8765'||e.source!==window.parent||e.data?.type!=='kids-music-command')return;
    const next=e.data.action==='play', change=next!==desired;
    if(change){desired=next;changed=Date.now();} apply(change);
  });
  document.addEventListener('click', e=>{
    if(e.target.closest('a,[data-test="share-button"]')) { e.preventDefault();e.stopImmediatePropagation();return; }
    if(e.isTrusted && e.target.closest('[data-test="play-button"]')) intent(!desired);
  },true);
  document.addEventListener('contextmenu',e=>e.preventDefault());
  document.addEventListener('keydown',e=>{if(e.altKey||e.ctrlKey||e.metaKey||/^F\d+$/.test(e.key)||e.key==='Escape')e.preventDefault();},true);
  setInterval(()=>{apply();report();},2000);
}
