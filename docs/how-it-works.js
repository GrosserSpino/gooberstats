const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const playerRow=p=>`<div class="mini-player"><span class="player-dot">${esc(p.name[0]?.toUpperCase()||'?')}</span><b>${esc(p.name)}</b><span>${p.wins} W</span></div>`;
function dayCard(day){const heat=Math.min(1,day.lobbyBonus/45);return `<article class="day-card" style="--bonus:${heat}"><header><div><h3>${esc(day.day)}</h3><span>${esc(day.date)} · ${esc(day.time)}</span></div><strong class="bonus-pill">+${Number(day.lobbyBonus).toFixed(1)}%</strong></header><div class="mini-players">${day.topPlayers.map(playerRow).join('')}</div><small>${day.players} observed players · ${day.games} games</small></article>`}
fetch('./data/method.json?v=20260820-rebuild1').then(r=>r.json()).then(data=>{
  window.gooberMethodData=data;
  const comparison=document.querySelector('#day-comparison');
  if(data.examples?.length>=2)comparison.innerHTML=`${dayCard(data.examples[0])}<div class="versus">VS</div>${dayCard(data.examples[1])}`;
  else comparison.innerHTML='<div class="empty">No matching comparison windows are available yet.</div>';
  document.querySelector('#coverage-value-bottom').textContent=`${data.coveragePct}%`;
}).catch(error=>{console.error(error);document.querySelector('#day-comparison').innerHTML='<div class="empty">The example data could not be loaded.</div>'});
