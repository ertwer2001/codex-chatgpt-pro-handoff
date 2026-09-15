// Read only the selected request's rendered turn. No cookie/token access or message sending.
let timer; let running=false;
async function scan(){
 if(running)return;running=true;
 try{
  const conversation=location.pathname.match(/^\/c\/([a-f0-9-]{36})$/)?.[1];if(!conversation)return;
  const {job}=await chrome.runtime.sendMessage({type:'jobs',conversation});
  if(!job||job.status!=='watching'||location.pathname!=='/c/'+job.conversation)return;
  const turns=[...document.querySelectorAll('[data-testid^="conversation-turn-"]')];
  const users=turns.filter(t=>t.querySelector('[data-message-author-role="user"]')&&t.innerText.includes('Request-ID: '+job.request));
  if(users.length!==1){await chrome.runtime.sendMessage({type:'diagnostic',request:job.request,detail:turns.length?'等待新請求同步到頁面。':'目前不是聊天訊息畫面。'});syncPage();return;}
  const index=turns.indexOf(users[0]);const answer=turns[index+1];
  if(!answer?.querySelector('[data-message-author-role="assistant"]')){syncPage();return;}
  if(!answer.innerText.includes('Request-ID: '+job.request))return;
  // Completion requires the response action bar, not just a period of quiet streaming.
  if(!answer.querySelector('button[data-testid="copy-turn-action-button"]')){syncPage();return;}
  const links=[...answer.querySelectorAll('a[href]')].filter(a=>a.href.startsWith('https://chatgpt.com/backend-api/estuary/content?')).map(a=>({url:a.href,name:a.getAttribute('download')||a.textContent.trim()}));
  const buttons=[...answer.querySelectorAll('button')];
  const downloadButtons=buttons.filter(b=>['下載檔案','Download file'].includes(b.getAttribute('aria-label')));
  const names=buttons.map(b=>b.getAttribute('aria-label')||'').filter(n=>/^[^\\/\r\n]+\.(html?|pdf|zip|md|txt|csv|json|docx|xlsx|pptx|png|jpe?g|webp)$/i.test(n));
  const payload={request:job.request,conversation:job.conversation,prompt:users[0].querySelector('[data-message-author-role="user"]').innerText,text:answer.querySelector('[data-message-author-role="assistant"]').innerText,attachmentExpected:!!(links.length||names.length||downloadButtons.length||answer.querySelector('[data-testid="library-file-icon"]'))};
  if(!payload.attachmentExpected){await chrome.runtime.sendMessage({type:'text-result',...payload});return;}
  if(!links.length&&names.length===1&&downloadButtons.length===1){
   const result=await chrome.runtime.sendMessage({type:'button-download',...payload,names});
   if(result?.click===true)downloadButtons[0].click();
  }else await chrome.runtime.sendMessage({type:'artifact',...payload,links});
 }catch(e){/* Missing DOM or suspended extension remains pending, never reports success. */}finally{running=false;}
}
new MutationObserver(()=>{clearTimeout(timer);timer=setTimeout(scan,1500);}).observe(document.documentElement,{childList:true,subtree:true,characterData:true});
chrome.runtime.onMessage.addListener(m=>{if(m.type==='scan')scan();});
// Browser throttling may delay this fallback; it never invokes an AI model.
setInterval(scan,5000);scan();
function syncPage(){
 const last=Number(sessionStorage.getItem('pro-inbox-refresh')||0);
 if(Date.now()-last<30000||document.querySelector('#prompt-textarea')?.textContent.trim()||document.querySelector('[data-testid="stop-button"],button[aria-label="停止回應"],button[aria-label="Stop generating"]'))return;
 sessionStorage.setItem('pro-inbox-refresh',String(Date.now()));location.reload();
}
