'use strict';
const HOME='http://127.0.0.1:8765/';
const paths=new Set(['/live/kids-club-radio-6551/','/live/disney-resorts-radio-9414/','/live/iheartfamily-preschool-9775/']);
async function singleTab() {
  const tabs=await chrome.tabs.query({});
  const main=tabs.find(t=>t.url===HOME)||tabs[0];
  if(!main)return;
  if(main.url!==HOME) await chrome.tabs.update(main.id,{url:HOME});
  for(const tab of tabs) if(tab.id!==main.id) await chrome.tabs.remove(tab.id).catch(()=>{});
}
chrome.tabs.onCreated.addListener(()=>singleTab().catch(()=>{}));
chrome.tabs.onUpdated.addListener((id,change)=>{
  if(change.url && change.url!==HOME) chrome.tabs.update(id,{url:HOME}).catch(()=>{});
});
function navigation(event) {
  if(event.frameId===0) {
    if(event.url!==HOME) chrome.tabs.update(event.tabId,{url:HOME}).catch(()=>{});
    return;
  }
  try {
    const url=new URL(event.url);
    if(url.origin==='https://www.iheart.com' && paths.has(url.pathname) && url.searchParams.get('embed')==='true')return;
  } catch {}
  // Reset to the saved station if the widget tries to navigate elsewhere.
  chrome.tabs.update(event.tabId,{url:HOME}).catch(()=>{});
}
chrome.webNavigation.onCommitted.addListener(navigation);
chrome.webNavigation.onHistoryStateUpdated.addListener(navigation);
singleTab().catch(()=>{});
