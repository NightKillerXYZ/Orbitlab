/* GMAT-style 3D orbit view. three.js is vendored at vendor/three (no CDN).
   Classic script (no static imports, so node --test can require it);
   three.js loads lazily via dynamic import(), injectable for tests. */
(function(){
'use strict';
/* Radius table for the 3D scene (km). */
var BODY_RADII_KM={Earth:6378.137,Moon:1737.4,Mars:3396.2,Mercury:2439.7,Venus:6051.8,Jupiter:71492,Sun:695700};
/* UI-only body colours (used when no texture file is present). */
var BODY_COLORS={Earth:0x4d8dff,Moon:0x9aa3b2,Mars:0xd4694e,Mercury:0x9c8d7d,Venus:0xe0a05e,Jupiter:0xd8b083,Sun:0xffb14e};
var AXIS_COLORS={x:0xff5a5a,y:0x58d4b0,z:0x4d8dff};
var MAX_LINE_POINTS=5000;

function bodyRadiusKm(name){try{var r=BODY_RADII_KM[name];if(typeof r==='number'&&isFinite(r)&&r>0)return r;}catch(e){}return null;}
function bodyColorHex(name){try{var c=BODY_COLORS[name];if(typeof c==='number')return c;}catch(e){}return 0x8fa6c8;}
/* Texture file read for a central body (lowercase name + .jpg). */
function textureFileFor(body){return 'assets/textures/'+String(body==null?'':body).toLowerCase()+'.jpg';}
/* Evenly decimate to at most max points, always keeping first and last. */
function decimatePoints(pts,max){
 try{
  var n=Array.isArray(pts)?pts.length:0;
  var m=(max==null?MAX_LINE_POINTS:max);
  if(!n)return [];
  if(n<=m)return pts.slice();
  if(m<=1)return [pts[0]];
  if(m===2)return [pts[0],pts[n-1]];
  var out=[];
  for(var i=0;i<m;i++){out.push(pts[Math.round(i*(n-1)/(m-1))]);}
  return out;
 }catch(e){return [];}
}
function clamp01(f){f=Number(f);if(!isFinite(f))return 0;return f<0?0:f>1?1:f;}
/* Interpolated [x,y,z] at elapsed time t from parallel time/position arrays. */
function sampleAtTimes(times,xs,ys,zs,t){
 try{
  var n=Math.min(times.length,xs.length,ys.length,zs.length);
  if(!n)return null;
  var tt=Number(t);
  if(!isFinite(tt))tt=Number(times[0])||0;
  if(tt<=Number(times[0]))return [+xs[0],+ys[0],+zs[0]];
  if(tt>=Number(times[n-1]))return [+xs[n-1],+ys[n-1],+zs[n-1]];
  var i=0;
  while(i<n-2&&Number(times[i+1])<=tt)i++;
  var t0=Number(times[i]),t1=Number(times[i+1]);
  var f=(t1>t0)?(tt-t0)/(t1-t0):0;
  return [+xs[i]+((+xs[i+1])-(+xs[i]))*f,+ys[i]+((+ys[i+1])-(+ys[i]))*f,+zs[i]+((+zs[i+1])-(+zs[i]))*f];
 }catch(e){return null;}
}
function countAtOrBefore(times,t){
 try{
  var n=0;
  for(var i=0;i<times.length;i++){if(Number(times[i])<=t)n++;else break;}
  return n;
 }catch(e){return 0;}
}
async function loadThree(deps){
 if(deps&&deps.THREE&&deps.OrbitControls)return deps;
 var THREE=await import('./vendor/three/three.module.min.js');
 var oc=await import('./vendor/three/OrbitControls.js');
 return {THREE:THREE,OrbitControls:oc.OrbitControls};
}
/* Body material: textured when assets/textures/<body>.jpg loads, otherwise a
   plain shaded sphere. A missing texture never throws. */
async function bodyMaterial(THREE,body){
 var color=bodyColorHex(body);
 try{
  var loader=new THREE.TextureLoader();
  var tex=await loader.loadAsync(textureFileFor(body));
  try{if(tex&&THREE.SRGBColorSpace!=null)tex.colorSpace=THREE.SRGBColorSpace;}catch(e){}
  return new THREE.MeshStandardMaterial({map:tex,roughness:0.95,metalness:0});
 }catch(e){
  try{return new THREE.MeshStandardMaterial({color:color,roughness:0.9,metalness:0.05});}catch(e2){return null;}
 }
}
function makeTextSprite(THREE,label,colorHex,sizeKm){
 try{
  var c=document.createElement('canvas');c.width=128;c.height=64;
  var g=c.getContext('2d');
  g.font='28px sans-serif';g.textAlign='center';g.textBaseline='middle';
  g.fillStyle=colorHex;g.fillText(String(label),64,34);
  var tex=new THREE.CanvasTexture(c);
  var mat=new THREE.SpriteMaterial({map:tex,transparent:true,depthTest:false});
  var sp=new THREE.Sprite(mat);
  sp.scale.set(sizeKm,sizeKm/2,1);
  return sp;
 }catch(e){return null;}
}
function createView3D(container,deps){
 var S={ready:false,dead:false,frac:0,tele:[],body:'',maxR:1,line:[],times:[],
        THREE:null,Orbit:null,renderer:null,scene:null,camera:null,controls:null,
        world:null,craft:null,travel:null,full:null};
 var api={setResult:setResult,setProgress:setProgress,dispose:dispose,ready:null};
 api.ready=init().catch(function(){/* never reject: without telemetry the panel keeps the old look */});
 async function init(){
  var L=await loadThree(deps);
  if(S.dead)return;
  var THREE=L.THREE;S.THREE=THREE;S.Orbit=L.OrbitControls;
  var w=1,h=1;
  try{w=container.clientWidth||1;h=container.clientHeight||1;}catch(e){}
  try{
   S.renderer=new THREE.WebGLRenderer({antialias:true});
  }catch(e){return;}
  try{S.renderer.setPixelRatio(1);}catch(e){}
  try{S.renderer.setSize(w,h);}catch(e){}
  try{
   var cv=S.renderer.domElement;
   cv.id='view3dCanvas';
   cv.style.cssText='position:absolute;inset:0;width:100%;height:100%;display:block;';
   S.canvasEl=cv;
   container.appendChild(cv);
  }catch(e){}
  try{
   S.scene=new THREE.Scene();
   S.scene.background=new THREE.Color(0x000000);
   S.camera=new THREE.PerspectiveCamera(45,w/h,0.1,1e12);
   S.scene.add(new THREE.AmbientLight(0xffffff,0.9));
   var sun=new THREE.DirectionalLight(0xffffff,1.6);
   sun.position.set(1,0.6,0.8);
   S.scene.add(sun);
   S.controls=new S.Orbit(S.camera,cv);
   S.controls.enableDamping=true;
   S.controls.dampingFactor=0.08;
   S.controls.addEventListener('change',render);
  }catch(e){}
  try{frame();}catch(e){}
  S.ready=true;
  try{applyAll();}catch(e){}
  try{render();}catch(e){}
  try{
   if(typeof ResizeObserver!=='undefined'&&container){
    S.ro=new ResizeObserver(function(){try{resize();}catch(e){}});
    try{S.ro.observe(container);}catch(e){}
   }else if(typeof window!=='undefined'&&window.addEventListener){
    S.onWinResize=function(){try{resize();}catch(e){}};
    window.addEventListener('resize',S.onWinResize);
   }
  }catch(e){}
 }
 function resize(){
  if(!S.ready||S.dead||!S.renderer||!S.camera)return;
  var w=1,h=1;
  try{w=container.clientWidth||1;h=container.clientHeight||1;}catch(e){}
  try{
   S.camera.aspect=w/h;S.camera.updateProjectionMatrix();
   S.renderer.setSize(w,h);render();
  }catch(e){}
 }
 function clearWorld(){
  var THREE=S.THREE;
  if(!THREE||!S.scene||!S.world)return;
  try{
   S.scene.remove(S.world);
   S.world.traverse(function(o){
    try{if(o.geometry&&o.geometry.dispose)o.geometry.dispose();}catch(e){}
    try{
     var mats=Array.isArray(o.material)?o.material:[o.material];
     mats.forEach(function(mm){
      try{if(mm&&mm.map&&mm.map.dispose)mm.map.dispose();}catch(e){}
      try{if(mm&&mm.dispose)mm.dispose();}catch(e){}
     });
    }catch(e){}
   });
  }catch(e){}
  S.world=null;S.craft=null;S.travel=null;S.full=null;
 }
 async function applyAll(){
  var THREE=S.THREE;
  if(!THREE||!S.scene||S.dead)return;
  clearWorld();
  var pts=S.tele,body=S.body;
  var R=bodyRadiusKm(body);
  if(R==null)R=6378.137;
  var maxR=0;
  for(var i=0;i<pts.length;i++){
   var r=Math.sqrt(pts[i][0]*pts[i][0]+pts[i][1]*pts[i][1]+pts[i][2]*pts[i][2]);
   if(isFinite(r)&&r>maxR)maxR=r;
  }
  if(!(maxR>0))maxR=R*1.2;
  S.maxR=maxR;
  var idx=[];
  for(var k=0;k<pts.length;k++)idx.push(k);
  var keep=decimatePoints(idx,MAX_LINE_POINTS);
  S.line=[];S.times=[];
  for(var j=0;j<keep.length;j++){S.line.push(pts[keep[j]]);S.times.push(S.lineTimes[keep[j]]);}
  var world=new THREE.Group();
  S.world=world;
  try{S.scene.add(world);}catch(e){}
  var i2;
  try{ /* stars: a few hundred static random points */
   var sn=400,sr=maxR*10;
   var sp=new Float32Array(sn*3);
   for(i2=0;i2<sn;i2++){
    var th=Math.random()*Math.PI*2,ph=Math.acos(2*Math.random()-1);
    sp[i2*3]=sr*Math.sin(ph)*Math.cos(th);
    sp[i2*3+1]=sr*Math.sin(ph)*Math.sin(th);
    sp[i2*3+2]=sr*Math.cos(ph);
   }
   var sg=new THREE.BufferGeometry();
   sg.setAttribute('position',new THREE.Float32BufferAttribute(sp,3));
   world.add(new THREE.Points(sg,new THREE.PointsMaterial({color:0xaac4e8,size:Math.max(1,maxR*0.004),sizeAttenuation:true})));
  }catch(e){}
  try{ /* central body at true radius, same frame as telemetry (no transform) */
   var mat=await bodyMaterial(THREE,body);
   if(mat){
    S.bodyMesh=new THREE.Mesh(new THREE.SphereGeometry(R,48,32),mat);
    world.add(S.bodyMesh);
   }
  }catch(e){}
  try{ /* trajectory line (dim) + travelled part (bright) sharing positions */
   if(S.line.length>1){
    var arr=new Float32Array(S.line.length*3);
    for(i2=0;i2<S.line.length;i2++){arr[i2*3]=S.line[i2][0];arr[i2*3+1]=S.line[i2][1];arr[i2*3+2]=S.line[i2][2];}
    var fullG=new THREE.BufferGeometry();
    fullG.setAttribute('position',new THREE.Float32BufferAttribute(arr,3));
    S.full=new THREE.Line(fullG,new THREE.LineBasicMaterial({color:0x3a5a8c}));
    var trG=new THREE.BufferGeometry();
    trG.setAttribute('position',new THREE.Float32BufferAttribute(arr.slice(),3));
    S.travel=new THREE.Line(trG,new THREE.LineBasicMaterial({color:0x6faaff}));
    world.add(S.full);world.add(S.travel);
   }else if(S.line.length===1){
    var dg=new THREE.BufferGeometry();
    dg.setAttribute('position',new THREE.Float32BufferAttribute(new Float32Array(S.line[0]),3));
    S.full=new THREE.Points(dg,new THREE.PointsMaterial({color:0x6faaff,size:Math.max(1,maxR*0.01)}));
    world.add(S.full);
   }
  }catch(e){}
  try{ /* spacecraft marker */
   var cr=Math.max(maxR*0.004,R*0.01);
   S.craft=new THREE.Mesh(new THREE.SphereGeometry(cr,16,12),new THREE.MeshBasicMaterial({color:0xffffff}));
   world.add(S.craft);
  }catch(e){}
  try{ /* X/Y/Z axes sized to 1.5x max orbit radius, with labels */
   var A=1.5*maxR;
   var axes=[['x',AXIS_COLORS.x,[1,0,0]],['y',AXIS_COLORS.y,[0,1,0]],['z',AXIS_COLORS.z,[0,0,1]]];
   for(i2=0;i2<axes.length;i2++){
    var nm=axes[i2][0],col=axes[i2][1],d=axes[i2][2];
    var ag=new THREE.BufferGeometry();
    ag.setAttribute('position',new THREE.Float32BufferAttribute(new Float32Array([-d[0]*A,-d[1]*A,-d[2]*A,d[0]*A,d[1]*A,d[2]*A]),3));
    world.add(new THREE.Line(ag,new THREE.LineBasicMaterial({color:col})));
    var hex='#'+('000000'+col.toString(16)).slice(-6);
    var sp2=makeTextSprite(THREE,nm.toUpperCase(),hex,Math.max(maxR*0.12,1));
    if(sp2){sp2.position.set(d[0]*A*1.06,d[1]*A*1.06,d[2]*A*1.06);world.add(sp2);}
   }
  }catch(e){}
  try{ /* auto-framing camera */
   var dist=maxR*3.0;
   S.camera.position.set(dist*0.62,dist*0.42,dist*0.62);
   S.camera.near=Math.max(dist/1000,maxR*0.001);
   S.camera.far=dist*100;
   S.camera.updateProjectionMatrix();
   S.controls.target.set(0,0,0);
   S.controls.update();
  }catch(e){}
  try{applyProgress();}catch(e){}
 }
 function applyProgress(){
  if(!S.ready||S.dead||!S.THREE)return;
  var f=clamp01(S.frac);
  var p=null;
  try{
   if(S.lineTimes.length&&S.line.length){
    var t0=S.lineTimes[0],t1=S.lineTimes[S.lineTimes.length-1];
    var t=t0+(Math.max(t1-t0,0))*f;
    var xs=[],ys=[],zs=[];
    for(var i=0;i<S.line.length;i++){xs.push(S.line[i][0]);ys.push(S.line[i][1]);zs.push(S.line[i][2]);}
    p=sampleAtTimes(S.lineTimes,xs,ys,zs,t);
    if(S.travel){
     var c=countAtOrBefore(S.lineTimes,t);
     try{S.travel.geometry.setDrawRange(0,Math.max(c,1));}catch(e){}
    }
   }
  }catch(e){p=null;}
  try{
   if(S.craft&&p){S.craft.position.set(p[0],p[1],p[2]);}
  }catch(e){}
 }
 function render(){try{if(S.renderer&&S.scene&&S.camera)S.renderer.render(S.scene,S.camera);}catch(e){}}
 function setResult(telemetry,centralBody){
  try{
   S.tele=[];
   if(Array.isArray(telemetry)){
    for(var i=0;i<telemetry.length;i++){
     var q=telemetry[i];
     var x=+q.x_km,y=+q.y_km,z=+q.z_km;
     if(isFinite(x)&&isFinite(y)&&isFinite(z))S.tele.push([x,y,z]);
    }
   }
   S.lineTimes=[];
   if(Array.isArray(telemetry)){
    for(var j=0;j<telemetry.length;j++){
     var e=+((telemetry[j]||{}).elapsed_secs);
     S.lineTimes.push(isFinite(e)?e:j);
    }
   }
   /* keep only samples that had finite positions, aligned with lineTimes */
   if(S.lineTimes.length!==S.tele.length){
    var lt=[];
    if(Array.isArray(telemetry)){
     for(var k=0;k<telemetry.length;k++){
      var r=telemetry[k];
      if(isFinite(+r.x_km)&&isFinite(+r.y_km)&&isFinite(+r.z_km)){
       var ee=+(r.elapsed_secs);lt.push(isFinite(ee)?ee:k);
      }
     }
    }
    S.lineTimes=lt;
   }
   S.body=(typeof centralBody==='string'&&centralBody)?centralBody:'';
   if(S.ready&&!S.dead){applyAll().then(function(){render();}).catch(function(){});}
  }catch(e){}
 }
 function setProgress(f){
  try{
   S.frac=clamp01(f);
   if(S.ready&&!S.dead){applyProgress();render();}
  }catch(e){}
 }
 function dispose(){
  try{
   S.dead=true;S.ready=false;
   try{if(S.ro&&S.ro.disconnect)S.ro.disconnect();}catch(e){}
   try{if(S.onWinResize&&typeof window!=='undefined')window.removeEventListener('resize',S.onWinResize);}catch(e){}
   try{if(S.controls&&S.controls.dispose)S.controls.dispose();}catch(e){}
   try{clearWorld();}catch(e){}
   try{if(S.renderer&&S.renderer.dispose)S.renderer.dispose();}catch(e){}
   try{
    if(S.canvasEl&&S.canvasEl.parentNode===container){try{container.removeChild(S.canvasEl);}catch(e){}}
    S.canvasEl=null;
   }catch(e){}
   S.renderer=null;S.scene=null;S.camera=null;S.controls=null;
  }catch(e){}
 }
 return api;
}
try{if(typeof module!=='undefined'&&module.exports){module.exports={BODY_RADII_KM:BODY_RADII_KM,BODY_COLORS:BODY_COLORS,textureFileFor:textureFileFor,decimatePoints:decimatePoints,clamp01:clamp01,sampleAtTimes:sampleAtTimes,countAtOrBefore:countAtOrBefore,bodyRadiusKm:bodyRadiusKm,bodyColorHex:bodyColorHex,createView3D:createView3D};}}catch(e){}
try{if(typeof globalThis!=='undefined')globalThis.createView3D=createView3D;}catch(e){}
})();
