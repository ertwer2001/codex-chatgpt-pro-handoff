const status=document.querySelector('#status');
async function show(){const data=await chrome.storage.local.get(['job','paused','relayError']);const j=data.job;status.textContent=JSON.stringify({version:'0.3.1',paused:!!data.paused,relayError:data.relayError,request:j?.request,status:j?.status,detail:j?.detail,error:j?.error,receipt:j?.receipt,files:j?.files},null,2);}
document.querySelector('#arm').onclick=async()=>{await chrome.runtime.sendMessage({type:'resume-auto'});await show();};
document.querySelector('#stop').onclick=async()=>{await chrome.runtime.sendMessage({type:'stop-auto'});await show();};
chrome.storage.onChanged.addListener(show);show();
