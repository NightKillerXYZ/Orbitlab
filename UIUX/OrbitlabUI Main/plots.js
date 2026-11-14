/* Dependency-free SVG time-series charts (no CDN, no imports).
   Classic script (no static imports, so node --test can require it).
   Colours come from existing CSS variables (var(--blue) etc.) so light and
   dark themes both work; each var() carries a hex fallback. */
(function(){
'use strict';
var MAX_POINTS=1500;
/* mu table for element + Hohmann computation (km^3/s^2). */
var MU_KM3_S2={Earth:398600.4418,Moon:4902.800066,Mars:42828.37362,Mercury:22031.78,Venus:324858.592,Jupiter:126712764.1,Sun:132712440018};
var REGISTRY={};
var CHART_SEQ=0;

function bodyMu(body){try{var m=MU_KM3_S2[body];if(typeof m==='number'&&isFinite(m)&&m>0)return m;}catch(e){}return null;}
/* Evenly decimate n points to at most max indices, always keeping first+last. */
function decimateIndices(n,max){
 try{
  n=Math.floor(+n);
  var m=Math.floor(max==null?MAX_POINTS:max);
  if(!(n>0))return [];
  if(!(m>0))return [0];
  if(n<=m){var all=[];for(var i=0;i<n;i++)all.push(i);return all;}
  if(m===1)return [0];
  if(m===2)return [0,n-1];
  var out=[];
  for(var k=0;k<m;k++)out.push(Math.round(k*(n-1)/(m-1)));
  return out;
 }catch(e){return [];}
}
/* Most readable time unit for a span in seconds. */
function chooseTimeUnit(spanSecs){
 var s=Number(spanSecs);
 if(!isFinite(s)||s<0)s=0;
 if(s<120)return {div:1,unit:'s',fmt:function(v){return String(Math.round(v));}};
 if(s<7200)return {div:60,unit:'min',fmt:function(v){return (v).toFixed(1);}};
 if(s<172800)return {div:3600,unit:'h',fmt:function(v){return (v).toFixed(2);}};
 return {div:86400,unit:'d',fmt:function(v){return (v).toFixed(2);}};
}
function fmtY(v,unit){
 try{
  var n=Number(v);if(!isFinite(n))return 'n/a';
  var a=Math.abs(n),s;
  if(a>=10000)s=n.toLocaleString('en-US',{minimumFractionDigits:1,maximumFractionDigits:1});
  else s=String(Number(n.toPrecision(4)));
  return unit?s+' '+unit:s;
 }catch(e){return 'n/a';}
}
/* Classical elements from position/velocity vectors and mu (km, km/s).
   a via vis-viva, e via the eccentricity vector. Null when uncomputable. */
function orbitalElementsKm(rx,ry,rz,vx,vy,vz,mu){
 try{
  rx=+rx;ry=+ry;rz=+rz;vx=+vx;vy=+vy;vz=+vz;mu=+mu;
  if(![rx,ry,rz,vx,vy,vz,mu].every(isFinite)||!(mu>0))return null;
  var r2=rx*rx+ry*ry+rz*rz;
  if(!(r2>0))return null;
  var r=Math.sqrt(r2);
  var v2=vx*vx+vy*vy+vz*vz;
  var energy=v2/2-mu/r;
  if(!(isFinite(energy))||energy===0)return null;
  var a=-mu/(2*energy);
  if(!(a>0))return null;
  var rdv=rx*vx+ry*vy+rz*vz;
  var ex=((v2-mu/r)*rx-rdv*vx)/mu;
  var ey=((v2-mu/r)*ry-rdv*vy)/mu;
  var ez=((v2-mu/r)*rz-rdv*vz)/mu;
  var e=Math.sqrt(ex*ex+ey*ey+ez*ez);
  if(!isFinite(e)||e<0)return null;
  return {a:a,e:e};
 }catch(err){return null;}
}
/* Impulsive Hohmann between circular coplanar orbits of radii r1 -> r2. */
function hohmannEstimate(r1Km,r2Km,mu){
 try{
  r1Km=+r1Km;r2Km=+r2Km;mu=+mu;
  if(![r1Km,r2Km,mu].every(isFinite)||!(r1Km>0)||!(r2Km>0)||!(mu>0))return null;
  var at=(r1Km+r2Km)/2;
  var dv1=Math.sqrt(mu/r1Km)*(Math.sqrt(2*r2Km/(r1Km+r2Km))-1);
  var dv2=Math.sqrt(mu/r2Km)*(1-Math.sqrt(2*r1Km/(r1Km+r2Km)));
  var transfer=Math.PI*Math.sqrt(Math.pow(at,3)/mu);
  if(![dv1,dv2,transfer].every(isFinite))return null;
  return {dv1:dv1,dv2:dv2,total:Math.abs(dv1)+Math.abs(dv2),transferSecs:transfer,semiTransfer:at};
 }catch(err){return null;}
}
function esc(s){return String(s==null?'':s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
function clamp01(f){f=Number(f);if(!isFinite(f))return 0;return f<0?0:f>1?1:f;}
/* Line chart. times in seconds; values numeric. Returns an SVG string and
   registers hover data under a generated id. Points decimated to <=maxPts. */
function lineChartSVG(opts){
 try{
  opts=opts||{};
  var title=opts.title||'series',unit=opts.unit||'';
  var times=Array.isArray(opts.times)?opts.times:[];
  var vals=Array.isArray(opts.vals)?opts.vals:[];
  var color=opts.color||'var(--blue,#4d8dff)';
  var W=opts.width||260,H=opts.height||150;
  var L=46,R=10,T=12,B=22;
  var n=Math.min(times.length,vals.length);
  var id='lc'+(++CHART_SEQ);
  if(!n)return '<div class="result-note">No data.</div>';
  var idx=decimateIndices(n,opts.maxPts==null?MAX_POINTS:opts.maxPts);
  var tx=[],vx=[];
  for(var k=0;k<idx.length;k++){var t=+times[idx[k]],v=+vals[idx[k]];if(isFinite(t)&&isFinite(v)){tx.push(t);vx.push(v);}}
  if(!tx.length)return '<div class="result-note">No data.</div>';
  var t0=tx[0],t1=tx[tx.length-1];
  var span=Math.max(t1-t0,1e-9);
  var mn=Infinity,mx=-Infinity,kk;
  for(kk=0;kk<vx.length;kk++){if(vx[kk]<mn)mn=vx[kk];if(vx[kk]>mx)mx=vx[kk];}
  if(mx===mn){mn-=1;mx+=1;}
  var tu=chooseTimeUnit(span);
  var X=function(t){return L+(+t-t0)/span*(W-L-R);};
  var Y=function(v){return T+(1-(+v-mn)/(mx-mn))*(H-T-B);};
  var line='';
  var px=[],py=[];
  for(kk=0;kk<tx.length;kk++){var Xk=X(tx[kk]),Yk=Y(vx[kk]);px.push(Xk);py.push(Yk);line+=Xk.toFixed(1)+','+Yk.toFixed(1)+' ';}
  var mid=(mn+mx)/2;
  var ft=function(t){return tu.fmt((+t-t0)/tu.div);};
  var s='<svg class="chart" viewBox="0 0 '+W+' '+H+'" role="img" aria-label="'+esc(title)+'">'
   +'<path d="M'+L+' '+T+'H'+(W-R)+'M'+L+' '+T+'V'+(H-B)+'M'+L+' '+(H-B)+'H'+(W-R)+'" style="stroke:var(--line,#25344d)" fill="none"/>'
   +'<text x="'+(L-3)+'" y="'+(T+8)+'" text-anchor="end" font-size="7" style="fill:var(--muted,#8296b6)">'+esc(fmtY(mx,unit))+'</text>'
   +'<text x="'+(L-3)+'" y="'+(Y(mid)+3).toFixed(1)+'" text-anchor="end" font-size="7" style="fill:var(--muted,#8296b6)">'+esc(fmtY(mid,unit))+'</text>'
   +'<text x="'+(L-3)+'" y="'+(H-B)+'" text-anchor="end" font-size="7" style="fill:var(--muted,#8296b6)">'+esc(fmtY(mn,unit))+'</text>'
   +'<text x="'+L+'" y="'+(H-6)+'" font-size="7" style="fill:var(--muted,#8296b6)">'+esc(ft(t0))+'</text>'
   +'<text x="'+(W-R)+'" y="'+(H-6)+'" text-anchor="end" font-size="7" style="fill:var(--muted,#8296b6)">'+esc(ft(t1))+'</text>'
   +'<text x="'+((L+W-R)/2).toFixed(1)+'" y="'+(H-6)+'" text-anchor="middle" font-size="6" style="fill:var(--muted,#5d6c87)">elapsed time ('+esc(tu.unit)+')</text>'
   +'<polyline points="'+line.trim()+'" fill="none" style="stroke:'+esc(color)+';stroke-width:1.5"/>';
  s+='<g id="'+id+'-ro" visibility="hidden"><circle id="'+id+'-dot" r="3" style="fill:var(--text,#edf2ff)"/><text id="'+id+'-txt" font-size="8" style="fill:var(--text,#edf2ff)">'
   +'</text></g>';
  s+='<rect x="'+L+'" y="'+T+'" width="'+(W-L-R)+'" height="'+(H-T-B)+'" fill="transparent" onmousemove="Plots.hover(event,\''+id+'\')" onmouseleave="Plots.leave(\''+id+'\')"/>';
  s+='</svg>';
  REGISTRY[id]={times:tx,vals:vx,px:px,py:py,tu:tu,unit:unit,W:W,L:L,R:R};
  return s;
 }catch(e){return '<div class="result-note">No data.</div>';}
}
function hoverResolve(id,frac){
 var d=REGISTRY[id];
 if(!d||!d.times.length)return null;
 var f=clamp01(frac);
 var i=Math.round(f*(d.times.length-1));
 return {i:i,t:d.times[i],v:d.vals[i],x:d.px[i],y:d.py[i],tu:d.tu,unit:d.unit};
}
function hover(evt,id){
 try{
  var r={left:0,width:1};
  try{
   if(evt&&evt.currentTarget&&evt.currentTarget.getBoundingClientRect)r=evt.currentTarget.getBoundingClientRect();
  }catch(e){}
  var cx=(evt&&(evt.clientX==null?evt.pageX:evt.clientX))||0;
  var f=((+cx)-(+r.left||0))/(+r.width||1);
  var p=hoverResolve(id,f);
  if(!p)return false;
  var doc=null;
  try{doc=typeof document!=='undefined'?document:null;}catch(e){}
  if(!doc||!doc.querySelector)return false;
  var g=doc.querySelector('#'+id+'-ro'),dot=doc.querySelector('#'+id+'-dot'),txt=doc.querySelector('#'+id+'-txt');
  if(!g||!dot||!txt)return false;
  try{g.setAttribute('visibility','visible');}catch(e){try{g.style.visibility='visible';}catch(e2){}}
  try{dot.setAttribute('cx',p.x.toFixed(1));dot.setAttribute('cy',p.y.toFixed(1));}catch(e){}
  var label='t='+p.tu.fmt((+p.t-(+REGISTRY[id].times[0]))/p.tu.div)+' '+p.tu.unit+', '+fmtY(p.v,p.unit);
  try{txt.textContent=label;}catch(e){try{txt.innerHTML=label;}catch(e2){}}
  try{txt.setAttribute('x',(p.x+6).toFixed(1));txt.setAttribute('y',(p.y-6).toFixed(1));}catch(e){}
  return true;
 }catch(e){return false;}
}
function leave(id){
 try{
  var doc=null;
  try{doc=typeof document!=='undefined'?document:null;}catch(e){}
  if(!doc||!doc.querySelector)return false;
  var g=doc.querySelector('#'+id+'-ro');
  if(!g)return false;
  try{g.setAttribute('visibility','hidden');}catch(e){try{g.style.visibility='hidden';}catch(e2){}}
  return true;
 }catch(e){return false;}
}
function __resetForTests(){for(var k in REGISTRY){if(Object.prototype.hasOwnProperty.call(REGISTRY,k))delete REGISTRY[k];}CHART_SEQ=0;}
try{if(typeof module!=='undefined'&&module.exports){module.exports={MAX_POINTS:MAX_POINTS,MU_KM3_S2:MU_KM3_S2,bodyMu:bodyMu,decimateIndices:decimateIndices,chooseTimeUnit:chooseTimeUnit,fmtY:fmtY,orbitalElementsKm:orbitalElementsKm,hohmannEstimate:hohmannEstimate,lineChartSVG:lineChartSVG,hover:hover,leave:leave,hoverResolve:hoverResolve,__registry:REGISTRY,__resetForTests:__resetForTests};}}catch(e){}
try{if(typeof globalThis!=='undefined'){globalThis.Plots={bodyMu:bodyMu,decimateIndices:decimateIndices,chooseTimeUnit:chooseTimeUnit,fmtY:fmtY,orbitalElementsKm:orbitalElementsKm,hohmannEstimate:hohmannEstimate,lineChartSVG:lineChartSVG,hover:hover,leave:leave};}}catch(e){}
})();
