/* Ground track (path over the Earth's surface) on an equirectangular canvas.
   Classic script (no imports, no CDN; node --test can require it).
   Spherical Earth, no precession/nutation/polar motion: up to ~0.2 deg error.
   Charts drawn from this file are labelled "approximate". */
(function(){
'use strict';
var MONTHS={jan:1,feb:2,mar:3,apr:4,may:5,jun:6,jul:7,aug:8,sep:9,oct:10,nov:11,dec:12};
/* "01 Jan 2026 12:00:00.000" (UTCGregorian) -> Julian date. UT1 treated as UTC. */
function parseGmatEpoch(str){
 try{
  var m=/^\s*(\d{1,2})\s+([A-Za-z]{3})\s+(\d{4})\s+(\d{1,2}):(\d{2}):(\d{2})(?:\.(\d{1,3}))?\s*$/.exec(String(str==null?'':str));
  if(!m)return null;
  var day=+m[1],mon=MONTHS[String(m[2]).toLowerCase()],yr=+m[3];
  var hh=+m[4],mi=+m[5],ss=+m[6],ms=m[7]==null?0:+m[7].padEnd(3,'0').slice(0,3);
  if(!(mon>=1&&mon<=12))return null;
  if(![day,yr,hh,mi,ss,ms].every(isFinite))return null;
  if(hh>23||mi>59||ss>60)return null;
  var a=Math.floor((14-mon)/12);
  var y=yr+4800-a,mm=mon+12*a-3;
  var jdn=day+Math.floor((153*mm+2)/5)+365*y+Math.floor(y/4)-Math.floor(y/100)+Math.floor(y/400)-32045;
  return jdn+(hh-12)/24+mi/1440+(ss+ms/1000)/86400;
 }catch(e){return null;}
}
/* IAU 1982 GMST in degrees, normalized to [0,360). */
function gmstDeg(jd){
 try{
  jd=+jd;
  if(!isFinite(jd))return null;
  var g=280.46061837+360.98564736629*(jd-2451545.0);
  g=g%360;
  if(g<0)g+=360;
  return g;
 }catch(e){return null;}
}
/* ECI (km, J2000 equatorial) at Julian date -> {lat,lon} degrees.
   Simple rotation about Z by GMST. lon in [-180,180]. */
function eciToLatLon(x,y,z,jd){
 try{
  x=+x;y=+y;z=+z;
  if(![x,y,z].every(isFinite))return null;
  var r=Math.sqrt(x*x+y*y+z*z);
  if(!(r>0))return null;
  var g=gmstDeg(jd);
  if(g==null)return null;
  var lat=Math.asin(Math.max(-1,Math.min(1,z/r)))*180/Math.PI;
  var lon=((Math.atan2(y,x)*180/Math.PI-g%360)%360+540)%360-180;
  if(lon<=-180)lon+=360;
  return {lat:lat,lon:lon};
 }catch(e){return null;}
}
/* Evenly decimate n points to at most max indices, keeping first and last. */
function decimateIndices(n,max){
 try{
  n=Math.floor(+n);var m=Math.floor(max==null?3000:max);
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
/* Split a longitude track into segments at +/-180 wrap crossings. */
function splitAtWrap(lats,lons){
 var segs=[],curL=[],curN=[];
 try{
  var n=Math.min(lats.length,lons.length);
  for(var i=0;i<n;i++){
   var la=+lats[i],lo=+lons[i];
   if(!isFinite(la)||!isFinite(lo))continue;
   if(curN.length){
    var d=Math.abs(lo-curN[curN.length-1]);
    if(d>180){segs.push({lats:curL,lons:curN});curL=[];curN=[];}
   }
   curL.push(Math.max(-90,Math.min(90,la)));curN.push(lo);
  }
  if(curN.length)segs.push({lats:curL,lons:curN});
 }catch(e){}
 return segs;
}
function esc(s){return String(s==null?'':s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
var BG_FILL='#0a1324';
function drawGrid(g,W,H){
 g.fillStyle=BG_FILL;g.fillRect(0,0,W,H);
 g.strokeStyle='rgba(143,170,220,0.18)';g.lineWidth=1;
 g.beginPath();
 var lo;
 for(lo=-180;lo<=180;lo+=60){var x=(lo+180)/360*W;g.moveTo(x,0);g.lineTo(x,H);}
 var la;
 for(la=-90;la<=90;la+=30){var y=(90-la)/180*H;g.moveTo(0,y);g.lineTo(W,y);}
 g.stroke();
 g.fillStyle='#8296b6';g.font='10px sans-serif';g.textAlign='center';
 for(lo=-180;lo<=180;lo+=60){g.fillText(lo+'°',(lo+180)/360*W,H-4);}
 g.textAlign='left';
 for(la=-60;la<=60;la+=30){g.fillText(la+'°',4,(90-la)/180*H-3);}
}
function drawTrack(g,segs,W,H,color){
 g.strokeStyle=color;g.lineWidth=1.6;
 g.beginPath();
 var started=false;
 for(var s=0;s<segs.length;s++){
  var L=segs[s].lats,N=segs[s].lons;
  for(var i=0;i<N.length;i++){
   var x=(N[i]+180)/360*W,y=(90-L[i])/180*H;
   if(!started||i===0){g.moveTo(x,y);started=true;}else g.lineTo(x,y);
   if(i===N.length-1)started=false;
  }
 }
 g.stroke();
}
function drawMarkers(g,segs,W,H){
 try{
  if(!segs.length||!segs[0].lons.length)return;
  var f0={la:segs[0].lats[0],lo:segs[0].lons[0]};
  var last=segs[segs.length-1];
  var f1={la:last.lats[last.lats.length-1],lo:last.lons[last.lons.length-1]};
  g.fillStyle='#58d4b0';
  g.beginPath();g.arc((f0.lo+180)/360*W,(90-f0.la)/180*H,3,0,Math.PI*2);g.fill();
  g.fillStyle='#ffffff';
  g.beginPath();g.arc((f1.lo+180)/360*W,(90-f1.la)/180*H,3,0,Math.PI*2);g.fill();
 }catch(e){}
}
/* Draw the ground track on a 2D canvas. Never throws; a missing texture
   leaves the lat/lon grid in place. */
function drawGroundTrack(canvas,lats,lons,opts){
 try{
  if(!canvas||typeof canvas.getContext!=='function')return false;
  var g=canvas.getContext('2d');
  if(!g)return false;
  var W=canvas.width||520,H=canvas.height||260;
  opts=opts||{};
  var segs=splitAtWrap(lats||[],lons||[]);
  drawGrid(g,W,H);
  if(segs.length){
   drawTrack(g,segs,W,H,opts.color||'#6faaff');
   drawMarkers(g,segs,W,H);
  }else{
   g.fillStyle='#8296b6';g.textAlign='center';
   g.fillText('No track points',W/2,H/2);
  }
  var img=opts.imageUrl;
  if(img&&typeof Image!=='undefined'){
   try{
    var im=new Image();
    im.onload=function(){
     try{
      g.drawImage(im,0,0,W,H);
      if(segs.length){drawTrack(g,segs,W,H,opts.color||'#6faaff');drawMarkers(g,segs,W,H);}
     }catch(e){}
    };
    im.onerror=function(){};
    im.src=img;
   }catch(e){}
  }
  return true;
 }catch(e){return false;}
}
try{if(typeof module!=='undefined'&&module.exports){module.exports={parseGmatEpoch:parseGmatEpoch,gmstDeg:gmstDeg,eciToLatLon:eciToLatLon,decimateIndices:decimateIndices,splitAtWrap:splitAtWrap,drawGroundTrack:drawGroundTrack};}}catch(e){}
try{if(typeof globalThis!=='undefined'){globalThis.GroundTrack={parseGmatEpoch:parseGmatEpoch,gmstDeg:gmstDeg,eciToLatLon:eciToLatLon,decimateIndices:decimateIndices,splitAtWrap:splitAtWrap,drawGroundTrack:drawGroundTrack};}}catch(e){}
})();
