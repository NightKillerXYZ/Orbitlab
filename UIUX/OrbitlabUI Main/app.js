/* ---- Pure result helpers (no DOM): unit-tested with node --test. ---- */
/* Body table mirrors orbitlab_core/bodies.json (radius + mu, the repo's
   single source of truth for central-body constants). Colours are UI-only. */
const BODY_TABLE={
 Earth:{radiusKm:6378.1363,muKm3S2:398600.4415,color:'#5b9dff',hi:'#bfe0ff'},
 Moon:{radiusKm:1737.4,muKm3S2:4902.800066,color:'#a9b6c9',hi:'#eef3fa'},
 Mars:{radiusKm:3389.5,muKm3S2:42828.375214,color:'#e06a4a',hi:'#ffc9a8'},
 Mercury:{radiusKm:2440.53,muKm3S2:22032.080486,color:'#b09a7e',hi:'#e8d9bd'},
 Venus:{radiusKm:6051.8,muKm3S2:324858.598827,color:'#e89a62',hi:'#ffe2b0'},
 Jupiter:{radiusKm:71492,muKm3S2:126712767.857614,color:'#d8a97a',hi:'#ffe9c4'},
 Sun:{radiusKm:695700,muKm3S2:132712440017.74652,color:'#ffae54',hi:'#fff2c9'}
};
function bodyInfo(name){try{const b=BODY_TABLE[name];if(b)return {name:name,radiusKm:b.radiusKm,muKm3S2:b.muKm3S2,color:b.color,hi:b.hi};}catch(e){}return {name:(typeof name==='string'&&name)?name:'unknown',radiusKm:null,muKm3S2:null,color:'#8fa6c8',hi:'#d5e4f7'};}
function numOrNull(x){const n=Number(x);return isFinite(n)?n:null;}
function pointRadiusKm(p){try{const x=+p.x_km,y=+p.y_km,z=+p.z_km;const r=Math.sqrt(x*x+y*y+z*z);return (r>0&&isFinite(r))?r:null;}catch(e){return null;}}
function pointSpeedKms(p){try{const x=+p.vx_km_s,y=+p.vy_km_s,z=+p.vz_km_s;const v=Math.sqrt(x*x+y*y+z*z);return isFinite(v)?v:null;}catch(e){return null;}}
function pointAltKm(p,bodyRadiusKm){try{if(p&&p.altitude_km!=null&&p.altitude_km!==''){const a=+p.altitude_km;if(isFinite(a))return a;}}catch(e){}const r=pointRadiusKm(p);if(r==null||!(bodyRadiusKm>0))return null;return r-bodyRadiusKm;}
function keplerPeriodSecs(aKm,mu){const a=+aKm,m=+mu;if(!(a>0)||!(m>0))return null;const t=2*Math.PI*Math.sqrt(Math.pow(a,3)/m);return isFinite(t)?t:null;}
/* The result carries no period field, so the UI computes T = 2*pi*sqrt(a^3/mu)
   from the experiment echo's semi-major axis (or the telemetry mean when the
   echo is Cartesian) and this body's mu. */
function smaForDisplay(exp,pts){try{const els=exp&&exp.initialOrbit&&exp.initialOrbit.elements;const a=numOrNull(els&&els.semiMajorAxisKm);if(a!=null)return a;}catch(e){}try{const vs=(pts||[]).map(p=>numOrNull(p.semi_major_axis_km)).filter(v=>v!=null&&v>0);if(vs.length)return vs.reduce((x,y)=>x+y,0)/vs.length;}catch(e){}return null;}
function periodText(aKm,mu){const t=keplerPeriodSecs(aKm,mu);if(t==null)return 'n/a';if(t>=172800)return (t/86400).toFixed(2)+' days';if(t>=3600)return (t/3600).toFixed(2)+' hours';if(t>=120)return (t/60).toFixed(1)+' min';return Math.round(t)+' s';}
function fmtKm(x,dec){const n=Number(x);if(!isFinite(n))return 'n/a';const d=(dec==null?1:dec);return n.toLocaleString('en-US',{minimumFractionDigits:d,maximumFractionDigits:d});}
function fmtSecs(s){const t=Number(s);if(!isFinite(t)||t<0)return 'n/a';if(t>=172800)return 'DAY '+(t/86400).toFixed(2);const h=Math.floor(t/3600),m=Math.floor((t%3600)/60),ss=Math.floor(t%60);const p=n=>(n<10?'0':'')+n;return 'T+'+p(h)+':'+p(m)+':'+p(ss);}
/* Body-centred fit: the origin (central body) maps to the card centre and the
   whole path fits with a margin. Returns null when nothing drawable. */
function fitOrbit(pts,W,H,margin){try{
 if(!Array.isArray(pts)||!pts.length)return null;
 let maxR=0;for(const p of pts){const r=pointRadiusKm(p);if(r!=null&&r>maxR)maxR=r;}
 if(!(maxR>0))return null;
 const m=(margin==null?16:margin);
 const scale=Math.min((W-2*m)/(2*maxR),(H-2*m)/(2*maxR));
 const line=[];
 for(const p of pts){const x=+p.x_km,y=+p.y_km;if(!isFinite(x)||!isFinite(y))continue;line.push([W/2+x*scale,H/2-y*scale]);}
 if(!line.length)return null;
 return {cx:W/2,cy:H/2,scale:scale,line:line,maxR:maxR};
}catch(e){return null;}}
function trajectoryStats(pts,bodyRadiusKm){
 const out={n:0,minAlt:null,maxAlt:null,finalAlt:null,minSpeed:null,maxSpeed:null,finalSpeed:null,spanSecs:null};
 try{
  if(!Array.isArray(pts)||!pts.length)return out;
  out.n=pts.length;
  let mnA=Infinity,mxA=-Infinity,mnS=Infinity,mxS=-Infinity,mnt=Infinity,mxt=-Infinity;
  for(const p of pts){
   const a=pointAltKm(p,bodyRadiusKm);if(a!=null){if(a<mnA)mnA=a;if(a>mxA)mxA=a;}
   const v=pointSpeedKms(p);if(v!=null){if(v<mnS)mnS=v;if(v>mxS)mxS=v;}
   const t=+p.elapsed_secs;if(isFinite(t)){if(t<mnt)mnt=t;if(t>mxt)mxt=t;}
  }
  if(isFinite(mnA)){out.minAlt=mnA;out.maxAlt=mxA;}
  if(isFinite(mnS)){out.minSpeed=mnS;out.maxSpeed=mxS;}
  if(isFinite(mnt))out.spanSecs=Math.max(0,mxt-mnt);
  const lp=pts[pts.length-1];
  out.finalAlt=pointAltKm(lp,bodyRadiusKm);
  out.finalSpeed=pointSpeedKms(lp);
 }catch(e){}
 return out;
}
/* ---- End of pure helpers. Everything below touches the DOM. ---- */
const tabs = ['Chat','Understanding','Results','Graph','Physics'];
const panel = document.querySelector('#panelContent');
const composer = document.querySelector('#chatComposer');
const promptInput = document.querySelector('#promptInput');
const toast = document.querySelector('#toast');
let simDay = 0, running = false, speed = 1, speedIndex = 0, completed = false, lastScenario = null;
const speedOptions = [1, 2, 5, 10];
let toastTimer;

/* Live backend wiring (same pattern as orbitlab-live.js). Mock mode keeps the
   original sample content exactly: no network calls when the adapter reports
   mock mode (?mock=1) or when the adapter script is absent. */
function useMock(){try{if(typeof globalThis!=='undefined'&&globalThis.OrbitLabAdapter&&globalThis.OrbitLabAdapter.isMockMode)return globalThis.OrbitLabAdapter.isMockMode();}catch(e){}return true;}
const BACKEND_STAGES=['extract','interpret','verify','validate','compile','simulate','parse','explain'];
let lastResult=null,lastError=null,runEvents=[],runActive=false,runFinished=false,runSlow=false,activeTab='Chat',runTimer=null;
/* Live trajectory replay state (real runs only). */
let animT=0,animPlaying=false,runFit=null,runBodyR=null,runStats=null,curAlt=null,curSpeed=null;function trajSpan(){try{if(runStats&&runStats.spanSecs!=null)return runStats.spanSecs;}catch(e){}const s=teleSpan(trajPts());return (s==null?0:s);}
function fmt1(x){const n=Number(x);return isFinite(n)?n.toFixed(1):'n/a';}
function trajPts(){try{const ps=lastResult&&lastResult.trajectory&&lastResult.trajectory.points;return Array.isArray(ps)?ps:[];}catch(e){return[];}}
function meanSpeed(pts){const v=pts.map(p=>{const vx=+p.vx_km_s||0,vy=+p.vy_km_s||0,vz=+p.vz_km_s||0;return Math.sqrt(vx*vx+vy*vy+vz*vz);}).filter(Number.isFinite);if(!v.length)return null;return v.reduce((a,b)=>a+b,0)/v.length;}
function meanRadiusKm(pts){const r=pts.map(p=>Math.sqrt(Math.pow(+p.x_km||0,2)+Math.pow(+p.y_km||0,2)+Math.pow(+p.z_km||0,2))).filter(x=>x>0&&isFinite(x));if(!r.length)return null;return r.reduce((a,b)=>a+b,0)/r.length;}
function teleSpan(pts){if(!pts.length)return null;let mn=Infinity,mx=-Infinity;pts.forEach(p=>{const e=+p.elapsed_secs;if(isFinite(e)){if(e<mn)mn=e;if(e>mx)mx=e;}});if(!isFinite(mn))return null;return mx-mn;}
function expEls(){try{return (lastResult.experiment.initialOrbit&&lastResult.experiment.initialOrbit.elements)||{};}catch(e){return{};}}
function stageStates(){const s={};BACKEND_STAGES.forEach(k=>{s[k]='pending';});(runEvents||[]).forEach(ev=>{if(!ev||!ev.stage||BACKEND_STAGES.indexOf(ev.stage)<0)return;if(ev.type==='stage_started')s[ev.stage]='active';else if(ev.type==='stage_completed')s[ev.stage]='done';else if(ev.type==='stage_failed')s[ev.stage]='fail';});return s;}
function isClarErr(e){return !!(e&&(e.code==='needs_clarification'||(e.details&&e.details.missing)));}
function errExplanation(e){if(!e)return null;if(e.details&&e.details.explanation)return e.details.explanation;if(e.explanation)return e.explanation;return null;}
function stageCard(){const st=stageStates();const done=BACKEND_STAGES.filter(k=>st[k]==='done').length;const cur=BACKEND_STAGES.find(k=>st[k]==='active'||st[k]==='fail');let h='<div class="chat-result"><strong>'+(runFinished?'Run finished':'Running: step '+done+' of '+BACKEND_STAGES.length+(cur?' - '+cur:''))+'</strong><div class="result-chips">'+BACKEND_STAGES.map(k=>'<span>'+k+(st[k]==='done'?' [ok]':st[k]==='fail'?' [fail]':st[k]==='active'?' [...]':'')+'</span>').join('')+'</div>';if(runSlow&&!runFinished)h+='<div class="result-note">Still simulating - this can take a few minutes.</div>';return h+'</div>';}
function setBusy(on){const inp=document.querySelector('#promptInput');const btn=document.querySelector('#chatForm .send-btn');[inp,btn].forEach(el=>{if(el){try{el.disabled=!!on;}catch(e){}}});}
function setLiveStatus(text){const el=document.querySelector('.live-status');if(el)el.innerHTML='<i></i> '+escapeHtml(text);}
function refreshExportState(){const has=trajPts().length>0;const tip=has?'Download run telemetry as CSV':'Run a scenario first - no telemetry yet';const top=document.querySelector('#exportBtn');if(top){try{top.disabled=!has;}catch(e){}top.setAttribute('title',tip);}const re=document.querySelector('#resultsExport');if(re){try{re.disabled=!has;}catch(e){}re.setAttribute('title',tip);}}

function showToast(message){toast.textContent=message;toast.classList.add('show');clearTimeout(toastTimer);toastTimer=setTimeout(()=>toast.classList.remove('show'),2400)}
function renderTime(){
  const value=`DAY ${simDay.toFixed(2)}`;
  document.querySelector('#simTime').textContent=value;
  const progress=Math.min(simDay/224.7,1)*100;document.querySelector('#timelineFill').style.width=`${Math.max(progress,2)}%`;document.querySelector('#timelineKnob').style.left=`${Math.max(progress,2)}%`;
  const angle=(simDay/224.7)*360;document.querySelector('#venusPlanet').style.transform=`translate(-50%,-50%) rotate(${angle}deg) translateX(130px)`;
}
function setRunning(value){running=value;document.querySelector('#runText').textContent=value?'RUNNING':'PAUSED';document.querySelector('#runIndicator').parentElement.classList.toggle('running',value);document.querySelector('#venusPlanet').classList.toggle('playing',value);document.querySelector('#playBtn').textContent=value?'Ⅱ':'▶';document.querySelector('#playBtn').setAttribute('aria-label',value?'Pause simulation':'Play simulation')}
function completeObjective(){if(completed)return;completed=true;const ring=document.querySelector('.progress-ring span');if(ring)ring.innerHTML='3<span class="ring-slash">/</span>5';const progressLabel=document.querySelector('.mission-progress>div+div span');if(progressLabel)progressLabel.textContent='3 of 5 steps complete';showToast('Mission progress updated · +50 XP')}
setInterval(()=>{if(running){simDay+=speed*0.12;if(simDay>=224.7){simDay=0;completeObjective()}renderTime();}if(animPlaying&&lastResult){const span=trajSpan();if(span>0){animT+=span/600*speed;if(animT>=span){animT=span;animPlaying=false;syncPlayBtn();}drawCraft();updateTelemetry();}}},100);

const content={
 Chat:`<div class="welcome-assistant"><div class="assistant-avatar">✦</div><div class="assistant-message"><p><b>Welcome back, Alex.</b> Ready to explore?</p><p>Venus takes about 225 Earth days to orbit the Sun. Try a scenario or ask me what you notice.</p></div></div><div class="suggestion-label">QUICK START</div><button class="suggestion" data-prompt="What keeps Venus in orbit around the Sun?"><span>✧</span> What keeps Venus in orbit?</button><button class="suggestion" data-prompt="What would happen if Venus moved twice as fast?"><span>↗</span> What if Venus moved twice as fast?</button><button class="suggestion" data-prompt="Compare Venus's orbit with Earth's orbit."><span>◎</span> Compare Venus and Earth</button>${lastScenario?scenarioMarkup(lastScenario):''}`,
 Understanding:`<div class="understanding-card"><div class="assistant-avatar">✦</div><div><div class="section-kicker">THE BIG IDEA</div><h3>Falling around the Sun</h3></div></div><p class="panel-copy">An orbit is a continuous fall. Venus moves forward while the Sun’s gravity pulls it inward, so its path bends into a loop instead of a straight line.</p><div class="mini-diagram"><div class="mini-sun"></div><div class="mini-orbit"></div><div class="mini-venus"></div><span>forward motion</span><span>gravity</span></div><div class="fact-block"><span class="fact-number">01</span><p><b>Inertia</b><br>Venus keeps moving forward through space.</p></div><div class="fact-block"><span class="fact-number">02</span><p><b>Gravity</b><br>The Sun continuously changes Venus’s direction.</p></div><button class="panel-cta" data-tab="Chat">Ask a follow-up <span>↗</span></button>`,
 Results:`<div class="result-header"><div class="assistant-avatar">✦</div><div><div class="section-kicker">LATEST RUN</div><h3>${lastScenario?'Scenario complete':'Baseline orbit'}</h3></div><span class="result-badge">${lastScenario?'SIMULATED':'READY'}</span></div><p class="panel-copy">${lastScenario?escapeHtml(lastScenario.prompt):'Venus is following a stable, nearly circular orbit around the Sun.'}</p><div class="result-metrics"><div><small>ORBITAL PERIOD</small><b>${lastScenario?lastScenario.period:'224.7'} <i>days</i></b></div><div><small>ORBIT SHAPE</small><b>${lastScenario?lastScenario.shape:'Near circular'}</b></div><div><small>ORBITAL SPEED</small><b>${lastScenario?lastScenario.velocity:'35.0'} <i>km/s</i></b></div><div><small>OUTCOME</small><b class="outcome">${lastScenario?lastScenario.outcome:'Stable orbit'}</b></div></div><div class="result-note"><span>✧</span> ${lastScenario?'Try changing one variable at a time to compare outcomes.':'Run a scenario in Chat to see how changing speed or gravity affects the orbit.'}</div><button class="panel-cta" id="resultsExport">Export run data <span>↧</span></button>`,
 Graph:`<div class="graph-heading"><div class="section-kicker">ORBITAL DATA</div><h3>Distance from the Sun</h3><p>Distance (AU) across one Venus year</p></div><div class="chart-wrap"><div class="chart-y"><span>0.74</span><span>0.72</span><span>0.70</span></div><svg class="chart" viewBox="0 0 260 150" role="img" aria-label="Distance from the Sun remains nearly constant throughout Venus's orbit"><defs><linearGradient id="chartFill" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#579bff" stop-opacity=".25"/><stop offset="1" stop-color="#579bff" stop-opacity="0"/></linearGradient></defs><path d="M0 29H260M0 75H260M0 121H260" stroke="#25344d" stroke-dasharray="3 4"/><path d="M0 72 C22 63 42 69 62 74 S102 84 124 75 S166 65 188 72 S230 82 260 68 L260 130 L0 130Z" fill="url(#chartFill)"/><path d="M0 72 C22 63 42 69 62 74 S102 84 124 75 S166 65 188 72 S230 82 260 68" fill="none" stroke="#6faaff" stroke-width="2"/><circle cx="124" cy="75" r="3" fill="#d8e9ff"/></svg></div><div class="chart-x"><span>DAY 0</span><span>DAY 56</span><span>DAY 112</span><span>DAY 169</span><span>DAY 225</span></div><div class="chart-legend"><i></i> Venus · Sun distance <b>0.72 AU avg.</b></div><div class="result-note"><span>✧</span> Venus’s low eccentricity means its distance changes very little.</div>`,
 Physics:`<div class="section-kicker">THE PHYSICS</div><h3 class="physics-title">A balance of motion</h3><p class="panel-copy">Gravity supplies the inward acceleration that continually turns Venus’s velocity toward the Sun.</p><div class="equation-card"><small>NEWTON’S LAW OF GRAVITATION</small><div class="equation">F <span>=</span> G <span class="fraction"><i>m₁m₂</i><b>r²</b></span></div><p>Force grows with mass and decreases with the square of distance.</p></div><div class="physics-values"><div><span>Sun’s mass</span><b>1.989 × 10³⁰ kg</b></div><div><span>Mean orbital radius</span><b>108.2 million km</b></div><div><span>Orbital velocity</span><b>35.0 km/s</b></div></div><div class="result-note"><span>✧</span> If Venus moved faster at the same distance, its path would stretch outward.</div>`
};
function escapeHtml(s){return s.replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function scenarioMarkup(run){return `<div class="chat-result"><strong>Scenario simulated</strong>Changing Venus’s orbital speed gives a ${run.outcome.toLowerCase()}.<div class="result-chips"><span>${run.velocity} km/s</span><span>${run.period} day period</span></div></div>`}
function renderTab(tab){activeTab=tab;document.querySelectorAll('.tab').forEach(b=>b.classList.toggle('active',b.dataset.tab===tab));let html=null;if(!useMock())html=liveBody(tab);panel.innerHTML=(html===null||html===undefined)?content[tab]:html;composer.style.display=tab==='Chat'?'block':'none';panel.scrollTop=0;refreshExportState();}
function axisTickT(t,span){if(span>=172800)return (t/86400).toFixed(1)+'d';if(span>=7200)return (t/3600).toFixed(1)+'h';return Math.round(t)+'s';}
function chartSVG(title,unit,times,vals,color){
 const W=260,H=150,L=44,R=8,T=12,B=22;
 try{
  const n=Math.min(times.length,vals.length);
  if(!n)return '<div class="result-note">No data.</div>';
  let mn=Infinity,mx=-Infinity,any=false;
  for(let i=0;i<n;i++){const raw=vals[i];if(raw==null||raw==='')continue;const v=+raw;if(isFinite(v)){any=true;if(v<mn)mn=v;if(v>mx)mx=v;}}
  if(!any)return '<div class="result-note">No data.</div>';
  if(mx===mn){mn-=1;mx+=1;}
  const t0=+times[0]||0,t1=+times[n-1]||0;const span=Math.max(t1-t0,1e-9);
  const X=t=>L+(+t-t0)/span*(W-L-R);
  const Y=v=>T+(1-(+v-mn)/(mx-mn))*(H-T-B);
  let line='';
  for(let i=0;i<n;i++){const raw=vals[i];if(raw==null||raw==='')continue;const t=+times[i],v=+raw;if(!isFinite(t)||!isFinite(v))continue;line+=X(t).toFixed(1)+','+Y(v).toFixed(1)+' ';}
  if(!line.trim())return '<div class="result-note">No data.</div>';
  const mid=(mn+mx)/2,yl=v=>fmtKm(v,1)+' '+unit;
  return '<svg class="chart" viewBox="0 0 260 150" role="img" aria-label="'+escapeHtml(title)+'">'
   +'<path d="M'+L+' '+T+'H'+(W-R)+'M'+L+' '+T+'V'+(H-B)+'M'+L+' '+(H-B)+'H'+(W-R)+'" stroke="#25344d" fill="none"/>'
   +'<text x="'+(L-3)+'" y="'+(T+8)+'" text-anchor="end" font-size="7" fill="#8296b6">'+escapeHtml(yl(mx))+'</text>'
   +'<text x="'+(L-3)+'" y="'+(Y(mid)+3).toFixed(1)+'" text-anchor="end" font-size="7" fill="#8296b6">'+escapeHtml(yl(mid))+'</text>'
   +'<text x="'+(L-3)+'" y="'+(H-B)+'" text-anchor="end" font-size="7" fill="#8296b6">'+escapeHtml(yl(mn))+'</text>'
   +'<text x="'+L+'" y="'+(H-6)+'" font-size="7" fill="#8296b6">'+escapeHtml(axisTickT(t0,span))+'</text>'
   +'<text x="'+(W-R)+'" y="'+(H-6)+'" text-anchor="end" font-size="7" fill="#8296b6">'+escapeHtml(axisTickT(t1,span))+'</text>'
   +'<text x="'+((L+W-R)/2).toFixed(1)+'" y="'+(H-6)+'" text-anchor="middle" font-size="6" fill="#5d6c87">elapsed time</text>'
   +'<polyline points="'+line.trim()+'" fill="none" stroke="'+color+'" stroke-width="1.5"/></svg>';
 }catch(e){return '<div class="result-note">No data.</div>';}
}
function liveBody(tab){
  if(!lastResult&&!lastError&&!runActive)return null;
  if(tab==='Chat'){
    let h=stageCard();
    if(lastResult){const els=expEls();const sp=meanSpeed(trajPts());const span=teleSpan(trajPts());h+='<div class="chat-result"><strong>Run complete</strong> '+escapeHtml(((lastResult.experiment&&lastResult.experiment.centralBody)||'Orbit')+' orbit'+(els.semiMajorAxisKm!=null?', a '+fmt1(els.semiMajorAxisKm)+' km':'')+(els.eccentricity!=null?', e '+els.eccentricity:''))+'.<div class="result-chips"><span>'+(sp===null?'n/a':fmt1(sp)+' km/s')+'</span><span>'+(span===null?'n/a':Math.round(span)+' s telemetry')+'</span></div></div>';}
    else if(lastError){
      if(isClarErr(lastError)){const m=(lastError.details&&lastError.details.missing)||[];h+='<div class="chat-result"><strong>More information needed</strong> '+escapeHtml('This request needs: '+m.join(', ')+'. Add the details and send again.')+'</div>';}
      else{const ex=errExplanation(lastError);h+='<div class="chat-result"><strong>Run failed at '+escapeHtml(lastError.stage||'unknown')+'</strong> '+escapeHtml(lastError.message||'The run did not finish.')+(ex?'<div class="result-note">'+escapeHtml(ex)+'</div>':'<div class="result-note">No explanation was returned for this failure.</div>');}
    }
    else if(runActive){h+='<div class="result-note">Contacting the backend and streaming stage events.</div>';}
    return h;
  }
  if(tab==='Results'){
    if(!lastResult&&!lastError)return null;
    if(lastError){return '<div class="result-header"><div class="assistant-avatar">i</div><div><div class="section-kicker">LATEST RUN</div><h3>Run failed</h3></div><span class="result-badge">FAILED</span></div><p class="panel-copy">'+escapeHtml((lastError.stage||'unknown')+': '+(lastError.message||'The run did not finish.'))+'</p>';}
    const els=expEls();const sp=meanSpeed(trajPts());const warns=lastResult.warnings||[];
    const rBody=runBodyName(),rInfo=bodyInfo(rBody);
    const rStats=trajectoryStats(trajPts(),rInfo.radiusKm);
    const finTxt=(rStats.finalAlt==null&&rStats.finalSpeed==null)?'n/a':('alt '+fmtKm(rStats.finalAlt,1)+' km, '+fmt1(rStats.finalSpeed)+' km/s');
    const warnList=(warns.length?warns.slice(0,8).map(w=>'<div class="result-note"><span>!</span> '+escapeHtml(String(w))+'</div>').join('')+(warns.length>8?'<div class="result-note">+'+(warns.length-8)+' more</div>':''):'<div class="result-note">No warnings.</div>');
    return '<div class="result-header"><div class="assistant-avatar">i</div><div><div class="section-kicker">LATEST RUN</div><h3>Run complete</h3></div><span class="result-badge">LIVE DATA</span></div><p class="panel-copy">'+escapeHtml('Backend run finished. Telemetry points: '+trajPts().length+'.')+'</p><div class="result-metrics"><div><small>ORBITAL PERIOD</small><b>'+escapeHtml(periodText(smaForDisplay(lastResult.experiment,trajPts()),rInfo.muKm3S2))+'</b></div><div><small>ORBIT SHAPE</small><b>'+escapeHtml(els.eccentricity==null?'n/a':(+els.eccentricity<0.05?'Near circular':'Elliptical'))+'</b></div><div><small>ORBITAL SPEED</small><b>'+escapeHtml(sp===null?'n/a':fmt1(sp))+' <i>km/s</i></b></div><div><small>OUTCOME</small><b class="outcome">Stable orbit - run complete</b></div></div><div class="result-metrics"><div><small>MIN ALTITUDE</small><b>'+escapeHtml(rStats.minAlt==null?'n/a':fmtKm(rStats.minAlt,1)+' km')+'</b></div><div><small>MAX ALTITUDE</small><b>'+escapeHtml(rStats.maxAlt==null?'n/a':fmtKm(rStats.maxAlt,1)+' km')+'</b></div><div><small>MIN SPEED</small><b>'+escapeHtml(rStats.minSpeed==null?'n/a':fmt1(rStats.minSpeed)+' km/s')+'</b></div><div><small>MAX SPEED</small><b>'+escapeHtml(rStats.maxSpeed==null?'n/a':fmt1(rStats.maxSpeed)+' km/s')+'</b></div></div><div class="result-note"><span>o </span>'+escapeHtml('Final state: '+finTxt+'. Telemetry points: '+trajPts().length+'.')+'</div>'+warnList+'<button class="panel-cta" id="resultsExport">Export run data <span>></span></button>';
  }
  if(tab==='Graph'){
    if(!lastResult)return null;
    const pts=trajPts();
    if(!pts.length)return '<div class="graph-heading"><div class="section-kicker">ORBITAL DATA</div><h3>Run trajectory</h3><p>no trajectory returned</p></div><div class="result-note">The backend returned no telemetry points.</div>';
    const gBody=runBodyName(),gInfo=bodyInfo(gBody);
    const gT=pts.map(p=>+p.elapsed_secs||0);
    const gA=pts.map(p=>pointAltKm(p,gInfo.radiusKm));
    const gS=pts.map(p=>pointSpeedKms(p));
    return '<div class="graph-heading"><div class="section-kicker">ORBITAL DATA</div><h3>Run trajectory · '+escapeHtml(gBody)+'</h3><p>'+escapeHtml(pts.length+' telemetry points')+'</p></div>'
     +'<div class="section-kicker">ALTITUDE vs TIME</div>'+chartSVG('Altitude vs time','km',gT,gA,'#6faaff')
     +'<div class="section-kicker">SPEED vs TIME</div>'+chartSVG('Speed vs time','km/s',gT,gS,'#58d4b0')
     +'<div class="chart-legend"><i></i> Live run <b>'+escapeHtml(pts.length+' points')+'</b></div>';
  }
  if(tab==='Physics'){
    let h=content.Physics;
    if(lastResult){const els=expEls();const prop=(lastResult.experiment&&lastResult.experiment.propagation)||{};h+='<div class="result-note"><span>o </span>Latest run</div><div class="physics-values"><div><span>Integrator</span><b>'+escapeHtml(prop.integrator||'n/a')+'</b></div><div><span>Stop condition</span><b>'+escapeHtml(prop.stopCondition?(prop.stopCondition.type+' '+prop.stopCondition.value):'n/a')+'</b></div><div><span>Semi-major axis</span><b>'+escapeHtml(els.semiMajorAxisKm==null?'n/a':fmt1(els.semiMajorAxisKm)+' km')+'</b></div></div><div class="panel-copy">'+escapeHtml(lastResult.explanation||'No explanation returned.')+'</div>'+(lastResult.explanationSource==='fallback'?'<div class="result-note"><span>o </span>Automatic summary (the AI explainer was unavailable).</div>':'');}
    else if(lastError){const ex=errExplanation(lastError);h+='<div class="result-note"><span>o </span>Latest run failed</div><div class="panel-copy">'+escapeHtml(ex||'No explanation was returned for this failure.')+'</div>';}
    return h;
  }
  if(tab==='Understanding'){
    let h=content.Understanding;
    if(lastResult){const els=expEls();const sc=(lastResult.experiment&&lastResult.experiment.spacecraft)||{};const propU=(lastResult.experiment&&lastResult.experiment.propagation)||{};const mansU=(lastResult.experiment&&lastResult.experiment.maneuvers)||[];const fmU=(lastResult.experiment&&lastResult.experiment.forceModel)||{};h+='<div class="result-note"><span>o </span>Latest run</div><div class="physics-values"><div><span>Central body</span><b>'+escapeHtml((lastResult.experiment&&lastResult.experiment.centralBody)||'n/a')+'</b></div><div><span>Semi-major axis</span><b>'+escapeHtml(els.semiMajorAxisKm==null?'n/a':fmt1(els.semiMajorAxisKm)+' km')+'</b></div><div><span>Eccentricity</span><b>'+escapeHtml(els.eccentricity==null?'n/a':String(els.eccentricity))+'</b></div><div><span>Dry mass</span><b>'+escapeHtml(sc.dryMassKg==null?'n/a':Number(sc.dryMassKg).toFixed(1)+' kg')+'</b></div></div><div class="physics-values"><div><span>Duration</span><b>'+escapeHtml(stopText(propU))+'</b></div><div><span>Maneuvers</span><b>'+escapeHtml(manText(mansU))+'</b></div><div><span>Forces</span><b>'+escapeHtml(forceText(fmU))+'</b></div></div>'+(lastResult.explanation?'<div class="panel-copy">'+escapeHtml(lastResult.explanation)+'</div>':'')+(lastResult.explanationSource==='fallback'?'<div class="result-note"><span>o </span>Automatic summary (the AI explainer was unavailable).</div>':'');}
    return h;
  }
  return null;
}
/* ---- Real-run rendering (main card, drawing, replay, titles). ---- */
function visEl(){try{return document.querySelector('#orbitVisual');}catch(e){return null;}}
function sampleDecoHidden(hide){const vis=visEl();if(!vis)return;vis.querySelectorAll('.orbit-path,.orbit-label,.distance-line,.distance-label,.earth-planet,.mars-planet,.sun-glow,.sun-core,.orbit-axis,.scale-label,#venusPlanet').forEach(el=>{try{el.style.display=hide?'none':'';}catch(e){}});}
function clearRunDrawing(){try{const vis=visEl();if(!vis)return;['runOrbit','noTraj'].forEach(id=>{const el=vis.querySelector('#'+id);if(el)el.remove();});}catch(e){}}
function stopText(prop){try{const s=prop&&prop.stopCondition;if(!s||!s.type)return 'n/a';return s.value==null?String(s.type):(s.type+' '+s.value);}catch(e){return 'n/a';}}
function manText(mans){try{if(!Array.isArray(mans)||!mans.length)return 'none';return mans.slice(0,4).map(m=>{const t=m&&(m.type||'maneuver');const tr=m&&(m.trigger&&m.trigger.condition);let d=String(t);if(tr)d+=' @'+tr;try{const tgt=m&&(m.targetObjectives&&m.targetObjectives.targetOrbitRadiusKm);if(tgt!=null)d+=' to '+fmtKm(tgt,1)+' km';}catch(e){}try{const v=m&&(m.burnVector&&m.burnVector.deltaVVectorKmS);if(Array.isArray(v)&&v.length===3){const n=v.map(Number);if(n.every(isFinite))d+=' dv '+Math.sqrt(n[0]*n[0]+n[1]*n[1]+n[2]*n[2]).toFixed(3)+' km/s';}}catch(e){}return d;}).join('; ');}catch(e){return 'n/a';}}
function forceText(fm){try{if(!fm||typeof fm!=='object')return 'n/a';const p=[];if(fm.gravityDegree!=null&&fm.gravityOrder!=null)p.push(fm.gravityDegree+'x'+fm.gravityOrder);if(Array.isArray(fm.pointMasses)&&fm.pointMasses.length)p.push(fm.pointMasses.slice(0,4).join('+'));try{if(fm.atmosphericDrag)p.push('drag '+(fm.atmosphericDrag.enabled?'on':'off'));}catch(e){}if(fm.solarRadiationPressure===true)p.push('SRP on');else if(fm.solarRadiationPressure===false)p.push('SRP off');return p.length?p.join(', '):'n/a';}catch(e){return 'n/a';}}
function runBodyName(){try{const b=lastResult&&lastResult.experiment&&lastResult.experiment.centralBody;return (typeof b==='string'&&b)?b:'unknown';}catch(e){return 'unknown';}}
function applyRunTitles(body){
 try{document.querySelectorAll('.breadcrumbs b').forEach(el=>{el.textContent=body+' orbit';});}catch(e){}
 try{const h=document.querySelector('.welcome-row h1');if(h)h.innerHTML=escapeHtml(body)+' in <span>Motion</span>';const lead=document.querySelector('.welcome-row p');if(lead)lead.textContent='Live results: a spacecraft path around '+body+'.';}catch(e){}
 try{const sub=document.querySelector('.card-subtitle');if(sub)sub.textContent='Live run · spacecraft around '+body;}catch(e){}
 try{
  const chips=document.querySelectorAll('.suggestion');
  const defs=[['What keeps the spacecraft in orbit around '+body+'?','What keeps the spacecraft in orbit around '+body+'?'],['What if the spacecraft moved twice as fast?','What would happen if the spacecraft around '+body+' moved twice as fast?'],['How does eccentricity change the orbit?','How does orbital eccentricity change the path around '+body+'?']];
  chips.forEach((c,i)=>{if(i<defs.length){c.setAttribute('data-prompt',defs[i][1]);const tx=c.childNodes;c.innerHTML='<span>'+(i===0?'✧':i===1?'↗':'◎')+'</span> '+escapeHtml(defs[i][0]);}});
 }catch(e){}
 try{const tl=document.querySelector('.card-topline');if(tl){let b=tl.querySelector('#runBadge');if(!b){b=document.createElement('span');b.id='runBadge';b.className='result-badge';const tg=tl.querySelector('.view-toggle');if(tg)tg.before(b);else tl.appendChild(b);}b.textContent='LIVE DATA';}}catch(e){}
}
function renderStatCards(body,info,els,stats,aKm){
 try{
  const row=document.querySelector('.telemetry-row');if(!row)return;
  row.style.gridTemplateColumns='repeat(5,1fr)';
  const ecc=(els&&els.eccentricity==null)?'n/a':String(els?els.eccentricity:'n/a');
  const inc=(els&&els.inclinationDeg==null)?'n/a':(Number(els.inclinationDeg).toFixed(2)+'°');
  row.innerHTML='<div><small>ORBITAL PERIOD</small><b>'+escapeHtml(periodText(aKm,info.muKm3S2))+'</b></div><div><small>PERIAPSIS ALT</small><b>'+escapeHtml(stats.minAlt==null?'n/a':fmtKm(stats.minAlt,1)+' km')+'</b></div><div><small>APOAPSIS ALT</small><b>'+escapeHtml(stats.maxAlt==null?'n/a':fmtKm(stats.maxAlt,1)+' km')+'</b></div><div><small>ECCENTRICITY</small><b>'+escapeHtml(ecc)+'</b></div><div><small>INCLINATION</small><b>'+escapeHtml(inc)+'</b></div>';
 }catch(e){}
}
function renderRealRun(){
 const vis=visEl();if(!vis||!lastResult)return;
 clearRunDrawing();
 sampleDecoHidden(true);
 const body=runBodyName(),info=bodyInfo(body),pts=trajPts();
 const exp=lastResult.experiment||{},els=(exp.initialOrbit&&exp.initialOrbit.elements)||{};
 const aKm=smaForDisplay(exp,pts);
 runBodyR=info.radiusKm;runStats=trajectoryStats(pts,runBodyR);
 runFit=fitOrbit(pts,300,200,16);
 applyRunTitles(body);
 renderStatCards(body,info,els,runStats,aKm);
 animT=0;animPlaying=pts.length>0;curAlt=null;curSpeed=null;syncPlayBtn();
 if(!runFit){
  const d=document.createElement('div');d.id='noTraj';d.className='result-note';d.style.cssText='position:absolute;inset:auto 9px 30px 9px;text-align:center;';d.textContent='no trajectory returned';
  vis.appendChild(d);
 }else{
  const NS='http://www.w3.org/2000/svg';
  const svg=document.createElementNS(NS,'svg');
  svg.id='runOrbit';svg.setAttribute('viewBox','0 0 300 200');svg.setAttribute('preserveAspectRatio','xMidYMid meet');
  svg.setAttribute('role','img');svg.setAttribute('aria-label','Spacecraft trajectory around '+body);
  svg.style.cssText='position:absolute;inset:0;width:100%;height:100%;';
  const discR=Math.max(5,Math.min(30,(Math.min(300,200)/2-16)*(info.radiusKm&&runFit.maxR?info.radiusKm/runFit.maxR:0)||6));
  const halo=document.createElementNS(NS,'circle');
  halo.setAttribute('cx',runFit.cx);halo.setAttribute('cy',runFit.cy);halo.setAttribute('r',discR+5);halo.setAttribute('fill','none');halo.setAttribute('stroke',info.hi);halo.setAttribute('stroke-opacity','0.25');halo.setAttribute('stroke-width','1.5');
  const disc=document.createElementNS(NS,'circle');
  disc.setAttribute('cx',runFit.cx);disc.setAttribute('cy',runFit.cy);disc.setAttribute('r',discR);disc.setAttribute('fill',info.color);disc.setAttribute('fill-opacity','0.9');
  svg.appendChild(halo);svg.appendChild(disc);
  if(runFit.line.length>1){
   const pl=document.createElementNS(NS,'polyline');
   pl.setAttribute('points',runFit.line.map(q=>q[0].toFixed(1)+','+q[1].toFixed(1)).join(' '));
   pl.setAttribute('fill','none');pl.setAttribute('stroke','#6faaff');pl.setAttribute('stroke-width','1.5');
   svg.appendChild(pl);
  }else{
   const dot=document.createElementNS(NS,'circle');
   dot.setAttribute('cx',runFit.line[0][0]);dot.setAttribute('cy',runFit.line[0][1]);dot.setAttribute('r','2.5');dot.setAttribute('fill','#6faaff');
   svg.appendChild(dot);
  }
  const craft=document.createElementNS(NS,'circle');
  craft.id='runCraft';craft.setAttribute('r','3');craft.setAttribute('fill','#ffffff');craft.setAttribute('stroke','#6faaff');craft.setAttribute('stroke-width','1.5');
  svg.appendChild(craft);
  vis.appendChild(svg);
 }
 try{const cap=document.querySelector('.visual-caption span:not(.caption-dot)');if(cap)cap.textContent=body.toUpperCase();}catch(e){}
 drawCraft();updateTelemetry();
}
function drawCraft(){
 try{
  const svg=document.querySelector('#runOrbit');const pts=trajPts();
  if(!svg||!runFit||!pts.length){curAlt=null;curSpeed=null;return;}
  const span=trajSpan();const t=Math.max(0,Math.min(span,animT));
  let i=0;while(i<pts.length-1){const nt=+pts[i+1].elapsed_secs;if(!(nt<=t))break;i++;}
  const a=pts[i],b=pts[Math.min(i+1,pts.length-1)];
  const t0=(+a.elapsed_secs)||0,t1=(+b.elapsed_secs)||0;
  const f=(t1>t0)?Math.max(0,Math.min(1,(t-t0)/(t1-t0))):0;
  const x=(+a.x_km||0)+(((+b.x_km||0)-(+a.x_km||0))*f),y=(+a.y_km||0)+(((+b.y_km||0)-(+a.y_km||0))*f);
  const vx=(+a.vx_km_s||0)+(((+b.vx_km_s||0)-(+a.vx_km_s||0))*f),vy=(+a.vy_km_s||0)+(((+b.vy_km_s||0)-(+a.vy_km_s||0))*f),vz=(+a.vz_km_s||0)+(((+b.vz_km_s||0)-(+a.vz_km_s||0))*f);
  const craft=svg.querySelector('#runCraft');
  if(craft){craft.setAttribute('cx',(runFit.cx+x*runFit.scale).toFixed(1));craft.setAttribute('cy',(runFit.cy-y*runFit.scale).toFixed(1));}
  const r=Math.sqrt(x*x+y*y);
  curAlt=(r>0&&runBodyR>0)?(r-runBodyR):(pointAltKm(a,runBodyR));
  const v=Math.sqrt(vx*vx+vy*vy+vz*vz);curSpeed=isFinite(v)?v:pointSpeedKms(a);
  const cap=document.querySelector('#captionSpeed');if(cap)cap.textContent=(curSpeed==null?'n/a':fmt1(curSpeed)+' km/s');
  const st=document.querySelector('#simTime');if(st)st.textContent=fmtSecs(t);
  try{const fr=span>0?(t/span):0;const tf=document.querySelector('#timelineFill'),tk=document.querySelector('#timelineKnob');if(tf)tf.style.width=Math.max(fr*100,2)+'%';if(tk)tk.style.left=Math.max(fr*100,2)+'%';}catch(e2){}
 }catch(e){}
}
function syncPlayBtn(){try{const b=document.querySelector('#playBtn');if(b){b.textContent=animPlaying?'Ⅱ':'▶';b.setAttribute('aria-label',animPlaying?'Pause trajectory replay':'Play trajectory replay');}const rt=document.querySelector('#runText');if(rt)rt.textContent=animPlaying?'RUNNING':'PAUSED';}catch(e){}}
function runScenarioMock(prompt){const lower=String(prompt).toLowerCase();let velocity='35.0',period='224.7',shape='Near circular',outcome='Stable orbit';if(/twice|double|faster|speed up|2x/.test(lower)){velocity='70.0';period='112.4';shape='Highly elliptical';outcome='Wider orbit';if(/escape|escape velocity/.test(lower))outcome='Escape trajectory'}else if(/slower|half|reduce|less speed/.test(lower)){velocity='17.5';period='449.4';shape='Tight spiral';outcome='Falls toward Sun'}else if(/gravity|stronger|increase/.test(lower)){velocity='35.0';period='158.9';shape='Tighter orbit';outcome='Stable, closer orbit'}else if(/earth|compare/.test(lower)){velocity='29.8';period='365.3';shape='Near circular';outcome='Earth: stable orbit'}lastScenario={prompt,velocity,period,shape,outcome};renderTab('Chat');completeObjective();panel.scrollTop=panel.scrollHeight;showToast('Scenario simulated · Results updated')}
document.querySelectorAll('.tab').forEach(btn=>btn.addEventListener('click',()=>renderTab(btn.dataset.tab)));
function setLiveStatusSafe(t){try{setLiveStatus(t);}catch(e){}}
function updateTelemetry(){
 if(!lastResult)return;
 const cap=document.querySelector('#captionSpeed');
 if(cap)cap.textContent=(curSpeed==null?'n/a':fmt1(curSpeed)+' km/s');
 const st=document.querySelector('#simTime');
 if(st)st.textContent=(trajPts().length?fmtSecs(animT):'n/a');
 const sm=document.querySelector('#speedMetric');
 if(sm)sm.innerHTML=(curSpeed==null?'n/a':fmt1(curSpeed)+' <span>km/s</span>');
}
function runScenario(prompt){
  if(useMock()){runScenarioMock(prompt);return;}
  if(runActive)return;
  const text=String(prompt==null?'':prompt).trim();
  if(!text){showToast('Please describe a mission first');const pi=document.querySelector('#promptInput');if(pi)pi.focus();return;}
  const prevResult=lastResult;
  lastResult=null;lastError=null;runEvents=[];runActive=true;runFinished=false;runSlow=false;
  runFit=null;runStats=null;animT=0;animPlaying=false;curAlt=null;curSpeed=null;syncPlayBtn();clearRunDrawing();
  setBusy(true);setLiveStatusSafe('SIMULATION RUNNING');
  clearTimeout(runTimer);
  runTimer=setTimeout(()=>{if(!runFinished){runSlow=true;if(activeTab==='Chat')renderTab('Chat');showToast('Still simulating - this can take a few minutes');}},60000);
  const adapter=globalThis.OrbitLabAdapter;
  const finish=ok=>{runFinished=true;runActive=false;clearTimeout(runTimer);setBusy(false);setLiveStatusSafe(ok?'SIMULATION COMPLETE':'RUN FAILED');if(ok&&lastResult)renderRealRun();renderTab(activeTab);updateTelemetry();refreshExportState();if(ok)completeObjective();};
  adapter.runExperiment(text,ev=>{runEvents.push(ev);if(activeTab==='Chat')renderTab('Chat');})
    .then(out=>{if(out&&out.error){lastError=out.error;if(prevResult){lastResult=prevResult;renderRealRun();}showToast('Run failed: '+(out.error.message||'unknown error'));}else if(out&&out.result){lastResult=out.result;showToast('Run complete - Results updated');}finish(!!(out&&out.result));})
    .catch(()=>{const base=(adapter&&adapter.getApiBase)?adapter.getApiBase():'the configured address';lastError={stage:'unknown',code:'cannot_reach',message:'Cannot reach the server at '+base+' - is the backend running?'};showToast('Cannot reach the server');finish(false);});
}
document.querySelector('#chatForm').addEventListener('submit',e=>{e.preventDefault();const prompt=promptInput.value.trim();if(!prompt){runScenario('');return;}runScenario(prompt);promptInput.value=''});
document.querySelectorAll('.suggestion').forEach(btn=>btn.addEventListener('click',()=>runScenario(btn.dataset.prompt)));
document.querySelector('#playBtn').addEventListener('click',()=>{if(lastResult&&trajPts().length){animPlaying=!animPlaying;if(animPlaying)completeObjective();syncPlayBtn();showToast(animPlaying?'Trajectory replay running':'Trajectory replay paused');return;}setRunning(!running);if(running)completeObjective()});
document.querySelector('#resetBtn').addEventListener('click',()=>{if(lastResult&&trajPts().length){animT=0;animPlaying=false;syncPlayBtn();drawCraft();updateTelemetry();showToast('Trajectory replay reset');return;}simDay=0;renderTime();setRunning(false);showToast('Simulation reset')});
document.querySelector('#speedBtn').addEventListener('click',()=>{speedIndex=(speedIndex+1)%speedOptions.length;speed=speedOptions[speedIndex];document.querySelector('#speedBtn').innerHTML=`${speed}× <span>⌄</span>`;showToast(`Simulation speed: ${speed}×`)});
document.querySelector('#timelineKnob').parentElement.addEventListener('click',e=>{const rect=e.currentTarget.getBoundingClientRect();const f=Math.max(0,Math.min(1,((e.clientX-rect.left)/rect.width)));if(lastResult&&trajSpan()>0){animT=f*trajSpan();drawCraft();updateTelemetry();return;}simDay=Math.max(0,Math.min(224.7,f*224.7));renderTime()});
document.querySelectorAll('.view-toggle button').forEach(btn=>btn.addEventListener('click',()=>{document.querySelectorAll('.view-toggle button').forEach(b=>b.classList.toggle('active',b===btn));document.querySelector('#orbitVisual').classList.toggle('view-3d',btn.dataset.view==='3D')}));
function exportSampleCSV(){const rows=[['day','venus_distance_au','orbital_speed_km_s','simulation_speed','mission'],...Array.from({length:16},(_,i)=>{const day=+(i*224.7/15).toFixed(2);const distance=+(0.723*(1-0.007*Math.cos(i/15*Math.PI*2))).toFixed(4);return[day,distance,35.0,speed,'Venus in Motion']})];const csv=rows.map(row=>row.map(v=>`"${String(v).replaceAll('"','""')}"`).join(',')).join('\r\n');const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download='orbitlab-venus-telemetry.csv';a.click();URL.revokeObjectURL(url);showToast('Telemetry CSV downloaded')}
function downloadCsv(text,name){try{const url=URL.createObjectURL(new Blob([text],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download=name;document.body.appendChild(a);a.click();setTimeout(()=>{URL.revokeObjectURL(url);a.remove();},500);}catch(e){}}
function exportCSV(){
  if(useMock()){exportSampleCSV();return;}
  const pts=trajPts();
  if(!pts.length){showToast('Run a scenario first - no telemetry yet');return;}
  const rows=[['elapsed_secs','x_km','y_km','z_km','vx_km_s','vy_km_s','vz_km_s','altitude_km']];
  pts.forEach(q=>{rows.push([q.elapsed_secs,q.x_km,q.y_km,q.z_km,q.vx_km_s,q.vy_km_s,q.vz_km_s,q.altitude_km].map(v=>v==null?'':v).join(','));});
  downloadCsv(rows.join('\r\n'),'orbitlab-telemetry.csv');showToast('Telemetry CSV downloaded');
}
document.querySelector('#exportBtn').addEventListener('click',exportCSV);
const appShell=document.querySelector('.app-shell');
const sidebarToggle=document.querySelector('#toggleSidebar');
const panelCollapseToggle=document.querySelector('#panelCollapseBtn');
const maxViewToggle=document.querySelector('#toggleMaxView');
function setSidebarCollapsed(collapsed){appShell.classList.toggle('sidebar-collapsed',collapsed);sidebarToggle.setAttribute('aria-expanded',String(!collapsed));sidebarToggle.setAttribute('aria-label',collapsed?'Expand navigation':'Collapse navigation');sidebarToggle.title=collapsed?'Expand navigation':'Collapse navigation';sidebarToggle.textContent=collapsed?'›':'‹'}
function setAssistantCollapsed(collapsed){appShell.classList.toggle('chat-collapsed',collapsed);panelCollapseToggle.textContent=collapsed?'‹':'›';panelCollapseToggle.setAttribute('aria-label',collapsed?'Expand assistant panel':'Collapse assistant panel');panelCollapseToggle.title=collapsed?'Expand assistant panel':'Collapse assistant panel'}
sidebarToggle.addEventListener('click',()=>setSidebarCollapsed(!appShell.classList.contains('sidebar-collapsed')));
panelCollapseToggle.addEventListener('click',()=>setAssistantCollapsed(!appShell.classList.contains('chat-collapsed')));
maxViewToggle.addEventListener('click',()=>{const active=appShell.classList.toggle('simulation-maximized');maxViewToggle.setAttribute('aria-pressed',String(active));maxViewToggle.innerHTML=active?'<span>×</span> Exit Max View':'<span>⛶</span> Max View';maxViewToggle.title=active?'Return to mission workspace':'Expand orbital simulation'});
document.querySelector('#shareBtn').addEventListener('click',async()=>{try{await navigator.clipboard.writeText(location.href);showToast('Mission link copied')}catch{showToast('You can share this mission from the browser address bar')}});
document.querySelector('#tryScenario').addEventListener('click',()=>{renderTab('Chat');promptInput.value='What if Venus moved twice as fast?';promptInput.focus()});
document.querySelectorAll('[data-tab-link]').forEach(btn=>btn.addEventListener('click',()=>renderTab(btn.dataset.tabLink)));
document.querySelector('#addMission').addEventListener('click',()=>showToast('Mission library is coming soon'));
document.querySelectorAll('.mission-link').forEach(btn=>btn.addEventListener('click',()=>{document.querySelectorAll('.mission-link').forEach(x=>x.classList.remove('selected'));btn.classList.add('selected');showAppPage('missions');if(btn.dataset.mission!=='venus')showToast(`${btn.querySelector('b').textContent} selected · Preview mission`)}));
const secondaryPage=document.querySelector('#secondaryPage');
const pageData={
 home:{kicker:'YOUR LEARNING SPACE',title:'Ready for takeoff, Alex?',lead:'Pick up where you left off or explore something new.',body:`<div class="page-stats"><article class="page-stat"><small>LEARNING STREAK</small><b>4 <i>days</i></b><span>One more day to beat your best</span></article><article class="page-stat"><small>MISSIONS IN PROGRESS</small><b>2</b><span>Keep your momentum going</span></article><article class="page-stat"><small>EXPLORER LEVEL</small><b>08</b><span>1,240 / 1,500 XP to Level 9</span><div class="page-progress"><i style="width:82%"></i></div></article></div><div class="page-section-heading"><div><small>JUMP BACK IN</small><h2>Your active missions</h2></div><span class="page-tag">THIS WEEK</span></div><div class="page-grid two-col"><article class="content-card featured-page-card"><div class="page-card-icon venus-mini"></div><div class="page-card-copy"><small>ORBITAL MECHANICS · 2 OF 5 STEPS</small><h3>Venus in Motion</h3><p>See how gravity guides a planet around the Sun.</p></div><button class="page-button" data-action="missions">Resume mission <span>→</span></button></article><article class="content-card"><div class="page-card-top"><span class="page-icon blue-icon">✦</span><span class="page-tag">NEW</span></div><small>INTERPLANETARY TRAVEL</small><h3>Mars Transfer</h3><p>Plan a route across the inner solar system.</p><button class="page-text-button" data-action="coming">Preview mission <span>↗</span></button></article></div><div class="page-section-heading compact-heading"><div><small>RECENT ACTIVITY</small><h2>Look how far you’ve come</h2></div></div><div class="activity-list"><div><span class="activity-dot"></span><p><b>Venus in Motion</b><small>Simulation completed · Today</small></p><strong>+50 XP</strong></div><div><span class="activity-dot cyan"></span><p><b>Gravity basics</b><small>Lesson completed · Yesterday</small></p><strong>+30 XP</strong></div></div>`},
 learn:{kicker:'LEARN',title:'Build your space science skills',lead:'Short, hands-on lessons make big ideas easier to understand.',body:`<div class="page-stats"><article class="page-stat"><small>LESSONS COMPLETED</small><b>6 <i>/ 18</i></b><span>Your learning path is underway</span></article><article class="page-stat"><small>TIME LEARNED</small><b>2.4 <i>hrs</i></b><span>Across 3 learning paths</span></article><article class="page-stat"><small>SKILL LEVEL</small><b>Explorer</b><span>Next milestone: Astronaut</span><div class="page-progress"><i style="width:46%"></i></div></article></div><div class="page-section-heading"><div><small>YOUR LEARNING PATHS</small><h2>Choose a topic to explore</h2></div><span class="page-tag">3 PATHS</span></div><div class="page-grid three-col"><article class="content-card path-card"><div class="path-symbol blue-icon">◎</div><small>2 OF 5 LESSONS</small><h3>Orbital Mechanics</h3><p>Discover why planets trace curved paths through space.</p><div class="page-progress"><i style="width:40%"></i></div><button class="page-button" data-action="missions">Continue learning <span>→</span></button></article><article class="content-card path-card"><div class="path-symbol purple-icon">✦</div><small>1 OF 4 LESSONS</small><h3>Planetary Science</h3><p>Explore the worlds that make up our solar system.</p><div class="page-progress"><i style="width:25%"></i></div><button class="page-button" data-action="coming">Open path <span>→</span></button></article><article class="content-card path-card"><div class="path-symbol orange-icon">↗</div><small>0 OF 3 LESSONS</small><h3>Rocket Science</h3><p>Learn how spacecraft travel between planets.</p><div class="page-progress"><i style="width:4%"></i></div><button class="page-button" data-action="coming">Start path <span>→</span></button></article></div><div class="page-section-heading compact-heading"><div><small>UP NEXT</small><h2>Recommended for you</h2></div></div><div class="lesson-row"><span class="lesson-number">03</span><div><b>Why do planets stay in orbit?</b><small>Orbital Mechanics · 8 min</small></div><span class="lesson-label">NEXT LESSON</span><button class="round-arrow" data-action="missions" aria-label="Open lesson">→</button></div>`},
 challenges:{kicker:'CHALLENGES',title:'A little curiosity goes a long way',lead:'Try a new space science challenge and earn XP as you go.',body:`<div class="challenge-banner"><div><span class="page-tag">DAILY CHALLENGE · 12 HRS LEFT</span><h2>Change one thing. Observe everything.</h2><p>Run a Venus scenario at a different speed and describe what changes.</p><button class="page-button" data-action="missions">Start challenge <span>→</span></button></div><div class="challenge-emblem">✦</div></div><div class="page-section-heading"><div><small>MORE WAYS TO EXPLORE</small><h2>Challenges for you</h2></div><span class="page-tag">+ XP REWARDS</span></div><div class="page-grid three-col"><article class="content-card challenge-card"><div class="page-card-top"><span class="page-icon blue-icon">◉</span><span class="xp-chip">+100 XP</span></div><small>ORBITAL MECHANICS</small><h3>Orbit detective</h3><p>Spot the difference between a circular and elliptical orbit.</p><div class="challenge-progress-label"><span>2 of 4 clues</span><b>50%</b></div><div class="page-progress"><i style="width:50%"></i></div><button class="page-text-button" data-action="missions">Continue challenge <span>→</span></button></article><article class="content-card challenge-card"><div class="page-card-top"><span class="page-icon purple-icon">✧</span><span class="xp-chip">+150 XP</span></div><small>SOLAR SYSTEM</small><h3>Planet lineup</h3><p>Put the inner planets in order from the Sun.</p><div class="challenge-progress-label"><span>Not started</span><b>0%</b></div><div class="page-progress"><i style="width:3%"></i></div><button class="page-text-button" data-action="coming">Take the challenge <span>→</span></button></article><article class="content-card challenge-card"><div class="page-card-top"><span class="page-icon orange-icon">↗</span><span class="xp-chip">+200 XP</span></div><small>SPACEFLIGHT</small><h3>Mission planner</h3><p>Choose a launch window for a trip to Mars.</p><div class="challenge-progress-label"><span>Not started</span><b>0%</b></div><div class="page-progress"><i style="width:3%"></i></div><button class="page-text-button" data-action="coming">Take the challenge <span>→</span></button></article></div>`},
 progress:{kicker:'YOUR PROGRESS',title:'Every mission moves you forward',lead:'Your effort is adding up. Here’s a snapshot of your journey.',body:`<div class="progress-overview"><div class="level-orb"><span>08</span><small>LEVEL</small></div><div class="level-copy"><small>SPACE EXPLORER</small><h2>You’re building great momentum, Alex.</h2><p>260 XP until your next level. Keep learning and exploring.</p><div class="page-progress"><i style="width:82%"></i></div><span>1,240 / 1,500 XP</span></div><div class="streak-summary"><span class="streak-mark">✦</span><b>4 days</b><small>current streak</small></div></div><div class="page-stats"><article class="page-stat"><small>MISSIONS COMPLETED</small><b>8</b><span>Across 3 space topics</span></article><article class="page-stat"><small>TIME IN ORBIT</small><b>3.6 <i>hrs</i></b><span>Curiosity well spent</span></article><article class="page-stat"><small>XP EARNED</small><b>1,240</b><span>Top 18% this month</span></article></div><div class="page-section-heading"><div><small>SKILLS YOU’RE GROWING</small><h2>Your explorer toolkit</h2></div><span class="page-tag">4 SKILLS</span></div><div class="content-card skill-card"><div class="skill-row"><span class="skill-icon blue-icon">◎</span><div><b>Orbital mechanics</b><small>Confident · 4 missions</small></div><strong>78%</strong><div class="page-progress"><i style="width:78%"></i></div></div><div class="skill-row"><span class="skill-icon purple-icon">✧</span><div><b>Planetary science</b><small>Growing · 3 lessons</small></div><strong>54%</strong><div class="page-progress"><i style="width:54%"></i></div></div><div class="skill-row"><span class="skill-icon orange-icon">↗</span><div><b>Spaceflight</b><small>Getting started · 1 activity</small></div><strong>26%</strong><div class="page-progress"><i style="width:26%"></i></div></div></div>`}
};
function showAppPage(page){const isMission=page==='missions',config=pageData[page]||pageData.home;appShell.classList.toggle('alt-page',!isMission);appShell.classList.remove('simulation-maximized');document.querySelectorAll('.nav-item').forEach(a=>a.classList.toggle('active',a.getAttribute('href')===`#${page}`));const crumb=page==='home'?'Home':page==='missions'?'My missions':config.title;document.querySelector('.breadcrumbs span:first-child').textContent=crumb;document.querySelector('.breadcrumbs .crumb-slash').style.display=isMission?'':'none';document.querySelector('.breadcrumbs b').textContent=isMission?'Venus in Motion':'';if(!isMission)secondaryPage.innerHTML=`<div class="page-intro"><div><div class="section-kicker">${config.kicker}</div><h1>${config.title}</h1><p>${config.lead}</p></div><div class="page-date"><span class="live-dot"></span> YOUR ORBIT IS LOOKING GOOD</div></div>${config.body}`;secondaryPage.scrollTop=0}
document.querySelectorAll('.nav-item').forEach(a=>a.addEventListener('click',e=>{e.preventDefault();showAppPage(a.getAttribute('href').slice(1))}));
secondaryPage.addEventListener('click',e=>{const action=e.target.closest('[data-action]')?.dataset.action;if(action==='missions')showAppPage('missions');else if(action==='coming')showToast('This activity is a sample preview and is easy to customize')});
panel.addEventListener('click',e=>{const sug=e.target.closest('.suggestion');if(sug&&sug.dataset.prompt){renderTab('Chat');runScenario(sug.dataset.prompt);return;}const tab=e.target.closest('[data-tab]');if(tab)renderTab(tab.dataset.tab);if(e.target.closest('#resultsExport'))exportCSV()});
document.querySelector('#exportBtn').setAttribute('title','Download sample Venus orbit telemetry as CSV');
const globalDate=document.querySelector('#globalDate');
function renderGlobalDate(){const now=new Date();globalDate.children[0].textContent=new Intl.DateTimeFormat(undefined,{weekday:'short',day:'2-digit',month:'short',year:'numeric'}).format(now);globalDate.children[1].textContent=new Intl.DateTimeFormat(undefined,{hour:'2-digit',minute:'2-digit'}).format(now);}
try{(function(){const tl=document.querySelector('.card-topline');if(!tl||tl.querySelector('#runBadge'))return;const b=document.createElement('span');b.id='runBadge';b.className='result-badge';b.textContent='SAMPLE';const tg=tl.querySelector('.view-toggle');if(tg)tg.before(b);else tl.appendChild(b);})();}catch(e){}
try{(function(){let q='';try{q=(typeof location!=='undefined'&&location.search)||'';}catch(e){}if(/(^|[?&])fixture=1(&|$)/.test(q)&&!useMock()){fetch('/sample-result').then(r=>{if(!r.ok)throw new Error('sample '+r.status);return r.json();}).then(job=>{const res=job&&(job.result||job);if(!res||!res.experiment)throw new Error('bad sample');lastResult=res;runFinished=true;setLiveStatusSafe('SIMULATION COMPLETE');renderRealRun();renderTab(activeTab);updateTelemetry();refreshExportState();showToast('Sample run loaded - Results updated');}).catch(err=>{showToast('Could not load sample result');});}})();}catch(e){}
renderTab('Chat');renderTime();renderGlobalDate();showAppPage('home');
setInterval(renderGlobalDate,60000);
/* Node test hook (browser ignores this: no `module` global). */
try{if(typeof module!=='undefined'&&module.exports){module.exports={BODY_TABLE: BODY_TABLE,bodyInfo:bodyInfo,numOrNull:numOrNull,pointRadiusKm:pointRadiusKm,pointSpeedKms:pointSpeedKms,pointAltKm:pointAltKm,keplerPeriodSecs:keplerPeriodSecs,smaForDisplay:smaForDisplay,periodText:periodText,fmtKm:fmtKm,fmtSecs:fmtSecs,fitOrbit:fitOrbit,trajectoryStats:trajectoryStats,axisTickT:axisTickT,chartSVG:chartSVG,stopText:stopText,manText:manText,forceText:forceText,escapeHtml:escapeHtml,liveBody:liveBody,__test__:{setResult:function(r){lastResult=r;},setError:function(e){lastError=e;},getResult:function(){return lastResult;},render:renderRealRun,draw:drawCraft,clear:clearRunDrawing,update:updateTelemetry,anim:function(t){animT=t;}}};}}catch(e){}
