importScripts('local-config.js');
async function relay(path,body){
 if(!RELAY)throw Error('本機接收服務尚未配對');
 const r=await fetch(RELAY.url+path,{method:body?'POST':'GET',headers:{Authorization:'Bearer '+RELAY.token,...(body?{'Content-Type':'application/json'}:{})},...(body?{body:JSON.stringify(body)}:{})});
 const data=await r.json();if(!r.ok)throw Error(data.error||'本機接收服務錯誤');return data;
}
async function deliver(job){
 try{const result=await relay('/result',{request:job.request,conversation:job.conversation,prompt:job.prompt,text:job.text,files:job.files.map(f=>f.actualPath||f.filename),attachmentExpected:!!job.attachmentExpected});job.status='received';job.receipt=result.receipt;delete job.error;await chrome.action.setBadgeText({text:'OK'});}
 catch(e){job.status='delivery_pending';job.error=e.message;}
 await chrome.storage.local.set({job});
}
function allowed(raw){try{const u=new URL(raw);return u.origin==='https://chatgpt.com'&&u.pathname==='/backend-api/estuary/content'&&/^file_[a-zA-Z0-9]+$/.test(u.searchParams.get('id')||'');}catch{return false;}}
function nameOf(url,index){const raw=new URL(url).searchParams.get('fn')||('artifact-'+index);return raw.replace(/[^\p{L}\p{N}._-]/gu,'_').slice(0,110)||('artifact-'+index);}
let busy=false;
let reconciling=false;
async function reconcile(){
 if(reconciling||busy)return;reconciling=true;
 try{
 const {job}=await chrome.storage.local.get('job');if(!job)return;
 if(job.status==='delivery_pending')return deliver(job);
 if(job.status!=='downloading')return;
 for(const f of job.files){if(!f.id)continue;const [d]=await chrome.downloads.search({id:f.id});f.state=d?.state||'missing';f.error=d?.error;if(d?.filename)f.actualPath=d.filename;}
 if(job.files.some(f=>['interrupted','missing'].includes(f.state))){job.status='failed';job.error='下載失敗；請檢查瀏覽器。接收器不會關閉安全保護或自動重送。';}
 else if(job.files.length&&job.files.every(f=>f.state==='complete')){
  job.receivedAt=Date.now();await deliver(job);return;
 }await chrome.storage.local.set({job});
 }finally{reconciling=false;}
}
async function handle(m,sender){
 if(m.type==='jobs'){
  if(!sender.tab||sender.url?.split('?')[0]!=='https://chatgpt.com/c/'+m.conversation)return {job:null};
  const {paused,job:old}=await chrome.storage.local.get(['paused','job']);if(paused)return {job:null};
  const pending=(await relay('/jobs')).jobs;
  // Check the registry first: completed/stale cached jobs must not block another project.
  if(old&&old.conversation!==m.conversation&&pending.some(j=>j.request===old.request)&&!['received','stopped'].includes(old.status))return {job:null};
  const jobs=pending.filter(j=>j.conversation===m.conversation);
  if(old&&jobs.some(j=>j.request===old.request)&&!['received','stopped'].includes(old.status)){
   if(old.tabId!==sender.tab.id){old.tabId=sender.tab.id;await chrome.storage.local.set({job:old});}return {job:old};
  }
  if(!jobs.length)return {job:null};
  const next={...jobs[0],tabId:sender.tab.id,status:'watching',files:[],armedAt:Date.now()};await chrome.storage.local.set({job:next});return {job:next};
 }
 if(m.type==='resume-auto'&&!sender.tab){await chrome.storage.local.set({paused:false});return;}
 if(m.type==='stop-auto'&&!sender.tab){await chrome.storage.local.set({paused:true});return;}
 const {job}=await chrome.storage.local.get('job');if(!job)return;
 if(m.type==='retry'){
  // Only the extension popup can retry an explicitly failed job.
  if(sender.tab||job.status!=='failed')return;
  job.status='watching';job.files=[];delete job.error;await chrome.storage.local.set({job});return;
 }
 if(busy||job.status!=='watching'||sender.tab?.id!==job.tabId||sender.url?.split('?')[0]!=='https://chatgpt.com/c/'+job.conversation||m.request!==job.request)return;
 if(m.type==='diagnostic'){job.detail=String(m.detail).slice(0,200);await chrome.storage.local.set({job});return;}
 if(m.conversation!==job.conversation)return;
 if(typeof m.text==='string'&&typeof m.prompt==='string'){job.text=m.text;job.prompt=m.prompt;job.attachmentExpected=!!m.attachmentExpected;}
 if(m.type==='text-result'){
  if(!job.text||!job.prompt||job.attachmentExpected)return;
  busy=true;try{await deliver(job);}finally{busy=false;}return;
 }
 if(m.type==='button-download'){
  if(!Array.isArray(m.names)||m.names.length!==1||!/^[^\\/\r\n]{1,150}\.(html?|pdf|zip|md|txt|csv|json|docx|xlsx|pptx|png|jpe?g|webp)$/i.test(m.names[0]))return;
  job.status='awaiting_browser_download';job.expectedName=m.names[0];job.clickAt=Date.now();job.detail='已辨識附件，等待 Chrome 的實際下載事件。';delete job.error;
  await chrome.storage.local.set({job});return {click:true};
 }
 if(m.type!=='artifact')return;
 busy=true;
 try{
  const links=[...new Set((m.links||[]).map(x=>x.url).filter(allowed))].slice(0,10);
  if(!links.length){job.error='已看到回覆但找不到可直接下載的附件連結；尚未收檔。';await chrome.storage.local.set({job});return;}
  job.status='downloading';job.files=[];await chrome.storage.local.set({job});
  for(let i=0;i<links.length;i++){
   const filename='CodexProInbox/'+job.request+'/'+i+'-'+nameOf(links[i],i);
   const id=await chrome.downloads.download({url:links[i],filename,saveAs:false,conflictAction:'uniquify'});
   job.files.push({id,filename,state:'in_progress'});await chrome.storage.local.set({job});
  }
 }catch(e){job.status='failed';job.error=String(e.message);await chrome.storage.local.set({job});}finally{busy=false;await reconcile();}
}
chrome.runtime.onMessage.addListener((m,s,r)=>{handle(m,s).then(value=>r(value||{ok:true})).catch(async e=>{await chrome.storage.local.set({relayError:e.message});r({error:e.message});});return true;});
chrome.downloads.onDeterminingFilename.addListener((item,suggest)=>{
 (async()=>{
  const {job}=await chrome.storage.local.get('job');
  if(!job||job.status!=='awaiting_browser_download'||Date.now()-job.clickAt>120000||!allowed(item.url)||item.byExtensionId)return suggest();
  const url=new URL(item.url);
  if(url.searchParams.get('fn')!==job.expectedName)return suggest();
  const filename='CodexProInbox/'+job.request+'/'+nameOf(item.url,0);
  job.files=[{id:item.id,filename,state:'in_progress'}];job.status='downloading';
  await chrome.storage.local.set({job});suggest({filename,conflictAction:'uniquify'});await reconcile();
 })().catch(()=>suggest());return true;
});
chrome.downloads.onChanged.addListener(()=>{if(!busy)reconcile();});
chrome.runtime.onStartup.addListener(reconcile);
chrome.alarms.create('reconcile',{periodInMinutes:0.5});
chrome.alarms.onAlarm.addListener(reconcile);
if(typeof module!=='undefined')module.exports={allowed,nameOf};
