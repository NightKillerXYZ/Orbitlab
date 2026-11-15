/* GMAT-style 3D orbit view. three.js vendored at vendor/three (no CDN).
   Classic script (no static imports, so node --test can require it);
   three.js loads lazily via dynamic import(), injectable for tests.
   Behaviour mirrors GMAT's OrbitView: black background, screen-fixed stars,
   red progressive track (zero-magnitude segments skipped), labelled X/Y/Z
   axes with arrowheads, textured central body with name, spacecraft marker
   with name, "Show full path" toggle (default off), Reset view button. */
(function(){
'use strict';
var BODY_RADII_KM={Earth:6378.137,Moon:1737.4,Mars:3396.2,Mercury:2439.7,Venus:6051.8,Jupiter:71492,Sun:695700};
var BODY_COLORS={Earth:0x4d8dff,Moon:0x9aa3b2,Mars:0xd4694e,Mercury:0x9c8d7d,Venus:0xe0a05e,Jupiter:0xd8b083,Sun:0xffb14e};
var TRACK_COLOR=0xff0000;
var LABEL_FRAC=0.04; /* label sprites are rescaled every frame to this fraction of camera distance (screen-fixed text) */
/* Earth texture alignment. Verified against the vendored three.js r160 SphereGeometry
   source (x = -r*cos(u*2PI)*sinT, y = r*cosT, z = r*sin(u*2PI)*sinT, uv = (u,1-v)):
   u = 0.5 is the equirectangular image centre = longitude 0, giving phi = PI and
   x = +r*sinT, i.e. longitude 0 faces +X at zero mesh rotation. The geometry is
   additionally baked with rotateX(+PI/2) for Earth only (three spheres are Y-up;
   the scene is Z-up), which maps +Y to +Z while leaving lon 0 on +X (lon 90E maps
   to +Y, matching atan2(y,x)). Hence no angular offset is needed: */
var EARTH_TEX_OFFSET_DEG=0;
function norm360(d){try{d=Number(d);if(!isFinite(d))return 0;d=d%360;if(d<0)d+=360;return d;}catch(e){return 0;}}
/* Texture longitude (deg, equirectangular) -> mesh-frame angle from +X (deg). */
function earthTexAngleDeg(lonDeg){try{var l=+lonDeg;if(!isFinite(l))return null;return norm360(l+EARTH_TEX_OFFSET_DEG);}catch(e){return null;}}
/* Inertial-frame spin of the Earth mesh (deg): GMST at the epoch plus elapsed
   telemetry time, so the texture agrees with the ground track's eciToLatLon
   (lon = atan2(y,x) - GMST). gmstDegFn is GroundTrack.gmstDeg (same helper). */
function earthSpinDeg(jd,gmstDegFn){try{jd=+jd;if(!isFinite(jd))return null;var g=(typeof gmstDegFn==='function')?gmstDegFn(jd):null;if(g==null||!isFinite(+g))return null;return norm360(+g+EARTH_TEX_OFFSET_DEG);}catch(e){return null;}}
var FAINT_OPACITY=0.22;
var MAX_LINE_POINTS=5000;
var STAR_COUNT=400;
function bodyRadiusKm(name){try{var r=BODY_RADII_KM[name];if(typeof r==='number'&&isFinite(r)&&r>0)return r;}catch(e){return null;}return null;}
function bodyColorHex(name){try{var c=BODY_COLORS[name];if(typeof c==='number')return c;}catch(e){return 0x8fa6c8;}return 0x8fa6c8;}
/* Texture file read for a central body (lowercase name + .jpg). */
function textureFileFor(body){return 'assets/textures/'+String(body==null?'':body).toLowerCase()+'.jpg';}
/* Optional 3D spacecraft model (may not exist; never throws). */
function modelFileFor(){return 'assets/models/spacecraft.3ds';}
/* Evenly decimate to at most max points, keeping first and last. */
function decimatePoints(pts,max){
 try{
  var n=Array.isArray(pts)?pts.length:0;
  var m=(max==null?MAX_LINE_POINTS:max);
  if(!n)return [];
  if(n<=m)return pts.slice();
  if(m<=1)return [pts[0]];
  if(m===2)return [pts[0],pts[n-1]];
  var out=[];
  for(var i=0;i<m;i++)out.push(pts[Math.round(i*(n-1)/(m-1))]);
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
/* Split decimated points into runs, dropping exact-zero samples so no drawn
   segment ever has an endpoint at the origin (GMAT skips zero-magnitude points). */
function splitRuns(pts,times){
 var runs=[],cp=[],ct=[];
 try{
  var n=Math.min(Array.isArray(pts)?pts.length:0,Array.isArray(times)?times.length:0);
  for(var i=0;i<n;i++){
   var p=pts[i]||[0,0,0];
   var x=+p[0]||0,y=+p[1]||0,z=+p[2]||0;
   if(!(x*x+y*y+z*z>0)){
    if(cp.length>1)runs.push({pts:cp,times:ct});
    cp=[];ct=[];
    continue;
   }
   cp.push([x,y,z]);ct.push(times[i]);
  }
  if(cp.length>1)runs.push({pts:cp,times:ct});
 }catch(e){}
 return runs;
}
async function loadThree(deps){
 if(deps&&deps.THREE&&deps.OrbitControls)return {THREE:deps.THREE,OrbitControls:deps.OrbitControls,TDSLoader:(deps&&deps.TDSLoader)||null};
 var THREE=await import('./vendor/three/three.module.min.js');
 var oc=await import('./vendor/three/OrbitControls.js');
 var TDS=null;
 try{var tm=await import('./vendor/three/TDSLoader.js');TDS=(tm&&tm.TDSLoader)||null;}catch(e){TDS=null;}
 return {THREE:THREE,OrbitControls:oc.OrbitControls,TDSLoader:TDS};
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
function makeTextSprite(THREE,label,colorCss,sizeKm){
 try{
  var c=document.createElement('canvas');c.width=128;c.height=64;
  var g=c.getContext('2d');
  g.font='28px sans-serif';g.textAlign='center';g.textBaseline='middle';
  g.fillStyle=colorCss;g.fillText(String(label),64,34);
  var tex=new THREE.CanvasTexture(c);
  var mat=new THREE.SpriteMaterial({map:tex,transparent:true,depthTest:false});
  var sp=new THREE.Sprite(mat);
  sp.scale.set(sizeKm,sizeKm/2,1);
  return sp;
 }catch(e){return null;}
}
function createView3D(container,deps){
 var S={ready:false,dead:false,frac:0,tele:[],lineTimes:[],line:[],runs:[],body:'',maxR:1,
        THREE:null,Orbit:null,TDSLoader:null,renderer:null,scene:null,camera:null,controls:null,
        world:null,craft:null,craftLabel:null,bodyLabel:null,bodyMesh:null,single:null,
        model:null,modelBase:0,modelLoading:false,loadToken:0,stars:null,
        showFull:false,spacecraftName:'',bodyName:'',curPos:null,labels:[],epochJD:null,gmstFn:null,uiBox:null,canvasEl:null,ro:null,onWinResize:null};
 function clearRunObjects(){
 try{
  if(S.world&&S.scene){
   try{S.scene.remove(S.world);}catch(e){}
   try{
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
  }
 }catch(e){}
 S.world=null;S.craft=null;S.craftLabel=null;S.bodyLabel=null;S.bodyMesh=null;S.labels=[];
 S.runs=[];S.single=null;S.model=null;S.modelBase=0;S.modelLoading=false;S.loadToken=(S.loadToken||0)+1;
}

 var api={setResult:setResult,setProgress:setProgress,dispose:dispose,ready:null};
 api.ready=init().catch(function(){/* never reject: without telemetry the panel keeps its old look */});
 function frameCamera(){
  try{
   if(!S.camera||!S.controls||!(S.maxR>0))return;
   var dist=S.maxR*3.0;
   if(S.camera.up&&S.camera.up.set)S.camera.up.set(0,0,1);
   S.camera.position.set(dist*0.68,-dist*0.68,dist*0.22);
   S.camera.near=Math.max(dist/1000,S.maxR*0.001);
   S.camera.far=dist*100;
   S.camera.updateProjectionMatrix();
   if(S.controls.target&&S.controls.target.set)S.controls.target.set(0,0,0);
   S.controls.update();
  }catch(e){}
 }
 function resetView(){try{frameCamera();render();}catch(e){}}
 function applyFaint(){
  try{
   for(var i=0;i<S.runs.length;i++){
    var r=S.runs[i];
    if(r&&r.faint)r.faint.visible=!!S.showFull;
   }
  }catch(e){}
 }
 function ensureUI(){
  try{
   var old=null;
   try{old=(container&&container.querySelector)?container.querySelector('#view3dUI'):null;}catch(e){old=null;}
   if(old)return old;
   var box=document.createElement('div');
   box.id='view3dUI';
   box.style.cssText='position:absolute;top:8px;right:8px;z-index:5;display:flex;gap:8px;align-items:center;font:400 9px sans-serif;color:#aab8d0;background:rgba(10,18,32,.78);border:1px solid rgba(113,151,207,.25);border-radius:6px;padding:4px 8px;';
   var lab=document.createElement('label');
   lab.style.cssText='display:flex;gap:4px;align-items:center;cursor:pointer;white-space:nowrap;';
   var cb=document.createElement('input');
   cb.type='checkbox';cb.checked=!!S.showFull;
   if(cb.addEventListener)cb.addEventListener('change',function(){S.showFull=!!cb.checked;try{applyFaint();}catch(e){}try{render();}catch(ee){}});
   var cap=document.createElement('span');
   cap.textContent='Show full path';
   lab.appendChild(cb);lab.appendChild(cap);
   var btn=document.createElement('button');
   btn.type='button';btn.textContent='Reset view';
   btn.style.cssText='font:inherit;color:inherit;background:transparent;border:1px solid rgba(113,151,207,.4);border-radius:4px;padding:2px 8px;cursor:pointer;white-space:nowrap;';
   if(btn.addEventListener)btn.addEventListener('click',function(){try{resetView();}catch(e){}});
   box.appendChild(lab);box.appendChild(btn);
   container.appendChild(box);
   return box;
  }catch(e){return null;}
 }
 async function init(){
  var L=await loadThree(deps);
  if(S.dead)return;
  var THREE=L.THREE;S.THREE=THREE;S.Orbit=L.OrbitControls;S.TDSLoader=L.TDSLoader||null;
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
   if(cv.addEventListener)cv.addEventListener('dblclick',function(){try{resetView();}catch(e){}});
  }catch(e){}
  try{
   S.scene=new THREE.Scene();
   S.scene.background=new THREE.Color(0x000000);
   S.camera=new THREE.PerspectiveCamera(45,w/h,0.1,1e12);
   if(S.camera.up&&S.camera.up.set)S.camera.up.set(0,0,1);
   S.scene.add(new THREE.AmbientLight(0xffffff,0.9));
   var sun=new THREE.DirectionalLight(0xffffff,1.6);
   sun.position.set(1,0.6,0.8);
   S.scene.add(sun);
   S.controls=new S.Orbit(S.camera,cv);
   S.controls.enableDamping=true;
   S.controls.dampingFactor=0.08;
   if(S.controls.addEventListener)S.controls.addEventListener('change',render);
  }catch(e){}
  try{ensureUI();}catch(e){}
  try{frameCamera();}catch(e){}
  S.ready=true;
  try{await applyAll();}catch(e){}
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
 function applyAll(){
  var THREE=S.THREE;
  if(!THREE||!S.scene||S.dead)return Promise.resolve();
  clearRunObjects();
  var pts=S.tele,body=S.body;
  var R=bodyRadiusKm(body);
  if(R==null)R=6378.137;
  var maxR=0,i;
  for(i=0;i<pts.length;i++){
   var rr=Math.sqrt(pts[i][0]*pts[i][0]+pts[i][1]*pts[i][1]+pts[i][2]*pts[i][2]);
   if(isFinite(rr)&&rr>maxR)maxR=rr;
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
  try{ /* stars: screen-fixed (follow the camera, constant pixel size) */
   var sn=STAR_COUNT,sr=Math.max(maxR*10,1);
   var sp=new Float32Array(sn*3);
   for(i=0;i<sn;i++){
    var th=Math.random()*Math.PI*2,ph=Math.acos(2*Math.random()-1);
    sp[i*3]=sr*Math.sin(ph)*Math.cos(th);
    sp[i*3+1]=sr*Math.sin(ph)*Math.sin(th);
    sp[i*3+2]=sr*Math.cos(ph);
   }
   var sg=new THREE.BufferGeometry();
   sg.setAttribute('position',new THREE.Float32BufferAttribute(sp,3));
   S.stars=new THREE.Points(sg,new THREE.PointsMaterial({color:0xaac4e8,size:2,sizeAttenuation:false,transparent:true,opacity:0.9,depthWrite:false}));
   try{S.stars.frustumCulled=false;}catch(e){}
   try{if(S.camera)S.stars.position.copy(S.camera.position);}catch(e){}
   world.add(S.stars);
  }catch(e){}
  try{ /* central body at true radius, same frame as telemetry (no transform) */
   (function(){
    var matP;
    try{matP=bodyMaterial(THREE,body);}catch(e){matP=null;}
    return Promise.resolve(matP).then(function(mat){
     if(S.dead||!S.world)return;
     if(mat){
            var bgeo=new THREE.SphereGeometry(R,48,32);
       try{if(body==='Earth'&&bgeo&&bgeo.rotateX)bgeo.rotateX(Math.PI/2);}catch(e){}
       S.bodyMesh=new THREE.Mesh(bgeo,mat);
      try{world.add(S.bodyMesh);}catch(e){}
      try{
       var lbl=makeTextSprite(THREE,S.bodyName||body||'body','#00FF00',Math.max(maxR*0.04,0.001));
       if(lbl){lbl.position.set(R*1.25,R*0.15,0);world.add(lbl);S.bodyLabel=lbl;S.labels.push(lbl);}
      }catch(e){}
     }
     try{applyProgress();}catch(e){}
     try{render();}catch(e){}
    }).catch(function(){});
   })();
  }catch(e){}
  try{ /* trajectory: bright travelled part per run + faint full-path copies */
   var split=splitRuns(S.line,S.times);
   for(var s=0;s<split.length;s++){
    (function(run){
     var arr=new Float32Array(run.pts.length*3),a2;
     for(a2=0;a2<run.pts.length;a2++){arr[a2*3]=run.pts[a2][0];arr[a2*3+1]=run.pts[a2][1];arr[a2*3+2]=run.pts[a2][2];}
     var g=new THREE.BufferGeometry();
     g.setAttribute('position',new THREE.Float32BufferAttribute(arr,3));
     var bright=new THREE.Line(g,new THREE.LineBasicMaterial({color:TRACK_COLOR,linewidth:2}));
     var g2=new THREE.BufferGeometry();
     g2.setAttribute('position',new THREE.Float32BufferAttribute(arr.slice(),3));
     var faint=new THREE.Line(g2,new THREE.LineBasicMaterial({color:TRACK_COLOR,transparent:true,opacity:FAINT_OPACITY}));
     faint.visible=!!S.showFull;
     try{world.add(bright);world.add(faint);}catch(e){}
     S.runs.push({pts:run.pts,times:run.times,bright:bright,faint:faint});
    })(split[s]);
   }
   if(!S.runs.length&&S.line.length===1){
    var dg=new THREE.BufferGeometry();
    dg.setAttribute('position',new THREE.Float32BufferAttribute(new Float32Array(S.line[0]),3));
    S.single=new THREE.Points(dg,new THREE.PointsMaterial({color:TRACK_COLOR,size:Math.max(1,maxR*0.01)}));
    try{world.add(S.single);}catch(e){}
   }
  }catch(e){}
  try{ /* spacecraft marker + red name label */
   var cr=Math.max(maxR*0.02,R*0.02);
   S.craft=new THREE.Mesh(new THREE.SphereGeometry(cr,16,12),new THREE.MeshBasicMaterial({color:0xffffff}));
   world.add(S.craft);
   try{
    var cl=makeTextSprite(THREE,S.spacecraftName||'Spacecraft','#FF0000',Math.max(maxR*0.035,0.001));
    if(cl){cl.position.set(cr*3,cr*3,0);world.add(cl);S.craftLabel=cl;S.labels.push(cl);}
   }catch(e){}
  }catch(e){}
  try{ /* X/Y/Z axes sized to 1.5x max orbit radius, with arrowheads + labels */
   var A=1.5*maxR;
   var axes=[['X',0xff0000,[1,0,0]],['Y',0x00ff00,[0,1,0]],['Z',0x4d8dff,[0,0,1]]];
   for(var q=0;q<axes.length;q++){
    (function(nm,col,d){
     try{
      var dv=new THREE.Vector3(d[0],d[1],d[2]);
      var ov=new THREE.Vector3(0,0,0);
      var ax=new THREE.ArrowHelper(dv,ov,A,col,Math.max(A*0.06,0.001),Math.max(A*0.025,0.001));
      world.add(ax);
      var hex='#'+('000000'+col.toString(16)).slice(-6);
      var lb=makeTextSprite(THREE,nm,hex,Math.max(maxR*0.05,0.001));
      if(lb){lb.position.set(d[0]*A*1.06,d[1]*A*1.06,d[2]*A*1.06);world.add(lb);S.labels.push(lb);}
     }catch(e){}
    })(axes[q][0],axes[q][1],axes[q][2]);
   }
  }catch(e){}
  try{frameCamera();}catch(e){}
  try{applyProgress();}catch(e){}
  try{tryLoadModel();}catch(e){}
  return Promise.resolve();
 }
 function tryLoadModel(){
  if(S.model||S.modelLoading||S.dead)return;
  var TDS=S.TDSLoader;
  if(!TDS)return;
  S.modelLoading=true;
  var token=S.loadToken;
  try{
   var loader=new TDS();
   var pr=null;
   try{pr=loader.loadAsync(modelFileFor());}catch(e){pr=null;}
   if(!pr||!pr.then){S.modelLoading=false;return;}
   pr.then(function(obj){
    if(S.dead||token!==S.loadToken||!obj){S.modelLoading=false;return;}
    var okMesh=false;
    try{
     if(obj&&obj.updateMatrixWorld)obj.updateMatrixWorld(true);
     var vc=0;
     if(obj&&obj.traverse)obj.traverse(function(o){
      try{
       if(o&&o.isMesh&&o.geometry&&o.geometry.getAttribute){
        var pa=o.geometry.getAttribute('position');
        if(pa&&pa.count>0)vc+=pa.count;
       }
      }catch(e){}
     });
     okMesh=vc>0;
    }catch(e){okMesh=false;}
    if(!okMesh){S.modelLoading=false;return;}
    var base=1;
    try{
     if(S.THREE&&S.THREE.Box3){
      var box=new S.THREE.Box3().setFromObject(obj);
      var sz=new S.THREE.Vector3();
      box.getSize(sz);
      var cen=new S.THREE.Vector3();
      try{box.getCenter(cen);}catch(e){}
      base=Math.max(Math.abs(sz.x),Math.abs(sz.y),Math.abs(sz.z))/2;
      try{if(obj.position&&obj.position.sub)obj.position.sub(cen);}catch(e){}
     }
    }catch(e){base=1;}
    if(!(base>0))base=1;
    S.model=obj;S.modelBase=base;
    try{if(S.craft)S.craft.visible=false;}catch(e){}
    try{if(S.world)S.world.add(obj);}catch(e){}
    S.modelLoading=false;
    try{applyProgress();}catch(e){}
    try{render();}catch(e){}
   }).catch(function(){S.modelLoading=false;});
  }catch(e){S.modelLoading=false;}
 }  /* Earth-only spin: rotates the Earth mesh about +Z by GMST(epoch + replay
     time). Other bodies stay static. Safe when the mesh, epoch or helper is
     missing (renders exactly as before). */
  function spinBody(tSecs){
   try{
    if(S.body!=='Earth'||!S.bodyMesh||S.epochJD==null||!S.gmstFn)return;
    var gd=earthSpinDeg(S.epochJD+(+tSecs||0)/86400,S.gmstFn);
    if(gd==null)return;
    var rad=gd*Math.PI/180;
    try{
     var rt=S.bodyMesh.rotation;
     if(rt){if(rt.set)rt.set(rt.x||0,rt.y||0,rad);else rt.z=rad;}
    }catch(e){}
   }catch(e){}
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
    for(var r=0;r<S.runs.length;r++){
     (function(run){
      var c=0;
      if(t>=run.times[run.times.length-1])c=run.times.length;
      else if(t>run.times[0])c=countAtOrBefore(run.times,t);
      try{run.bright.geometry.setDrawRange(0,c);}catch(e){}
      try{run.faint.visible=!!S.showFull;}catch(ee){}
     })(S.runs[r]);
    }
   }
  }catch(e){p=null;}
  try{
   if(S.craft&&p){S.craft.position.set(p[0],p[1],p[2]);}
   if(S.craftLabel&&p){S.craftLabel.position.set(p[0]+S.maxR*0.02,p[1]+S.maxR*0.02,p[2]);}
   if(S.model&&p){
    if(S.model.position&&S.model.position.set)S.model.position.set(p[0],p[1],p[2]);
    else if(S.model.position){S.model.position.x=p[0];S.model.position.y=p[1];S.model.position.z=p[2];}
   }
   S.curPos=p||S.curPos||null;
  }catch(e){}
  try{spinBody(t);}catch(e){}
 }
 function render(){
  try{if(!S.renderer||!S.scene||!S.camera)return;
   try{if(S.stars&&S.stars.position&&S.stars.position.copy)S.stars.position.copy(S.camera.position);}catch(e){}
   try{
    var lbls=S.labels||[];
    if(lbls.length&&S.camera&&S.camera.position){
     var cxp=S.camera.position;
     var cd=Math.sqrt(cxp.x*cxp.x+cxp.y*cxp.y+cxp.z*cxp.z);
     if(isFinite(cd)&&cd>0){
      for(var li=0;li<lbls.length;li++){
       try{if(lbls[li]&&lbls[li].scale&&lbls[li].scale.set)lbls[li].scale.set(cd*LABEL_FRAC,cd*LABEL_FRAC/2,1);}catch(e2){}
      }
     }
    }
   }catch(e){}
   try{
    if(S.model&&S.modelBase>0&&S.camera&&S.camera.position){
     var cp=S.curPos||[0,0,0];
     var dx=S.camera.position.x-cp[0],dy=S.camera.position.y-cp[1],dz=S.camera.position.z-cp[2];
     var d=Math.sqrt(dx*dx+dy*dy+dz*dz);
     var s=(d>0&&isFinite(d))?(d*0.03)/S.modelBase:1;
     if(isFinite(s)&&s>0&&S.model.scale&&S.model.scale.set)S.model.scale.set(s,s,s);
    }
   }catch(e){}
   S.renderer.render(S.scene,S.camera);
  }catch(e){}
 }
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
     var e2=(telemetry[j]||{}).elapsed_secs;
     S.lineTimes.push(isFinite(+e2)?+e2:j);
    }
   }
   /* keep only samples that had finite positions, aligned with lineTimes */
   if(S.lineTimes.length!==S.tele.length){
    var lt=[];
    if(Array.isArray(telemetry)){
     for(var k=0;k<telemetry.length;k++){
      var r=telemetry[k];
      if(isFinite(+r.x_km)&&isFinite(+r.y_km)&&isFinite(+r.z_km)){
       var ee=r.elapsed_secs;lt.push(isFinite(+ee)?+ee:k);
      }
     }
    }
    S.lineTimes=lt;
   }
   S.body=(typeof centralBody==='string'&&centralBody)?centralBody:'';
   S.epochJD=null;S.gmstFn=null;
   try{
    var GT=null;
    try{GT=(deps&&deps.GroundTrack)||null;}catch(e){GT=null;}
    if(!GT){try{GT=(typeof GroundTrack!=='undefined')?GroundTrack:null;}catch(e){GT=null;}}
    var eraw=null;
    try{eraw=(container&&container.dataset&&container.dataset.epochValue)||null;}catch(e){eraw=null;}
    if(GT&&GT.gmstDeg)S.gmstFn=GT.gmstDeg;
    if(eraw&&GT&&GT.parseGmatEpoch){var ejd=GT.parseGmatEpoch(eraw);if(isFinite(ejd))S.epochJD=ejd;}
   }catch(e){S.epochJD=null;S.gmstFn=null;}
   try{
    var ds=null;
    try{ds=(container&&container.dataset)?container.dataset:null;}catch(e){ds=null;}
    S.spacecraftName=(ds&&typeof ds.spacecraftName==='string')?ds.spacecraftName:'';
    S.bodyName=(ds&&typeof ds.bodyName==='string'&&ds.bodyName)?ds.bodyName:S.body;
   }catch(e){S.spacecraftName='';S.bodyName=S.body;}
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
   try{clearRunObjects();}catch(e){}
   try{if(S.renderer&&S.renderer.dispose)S.renderer.dispose();}catch(e){}
   try{
    if(S.canvasEl&&S.canvasEl.parentNode===container){try{container.removeChild(S.canvasEl);}catch(e){}S.canvasEl=null;}
   }catch(e){}
   try{
    var box=null;
    try{box=(container&&container.querySelector)?container.querySelector('#view3dUI'):null;}catch(e){}
    if(box&&(box.parentNode===container||!box.parentNode)){try{if(box.parentNode===container)container.removeChild(box);else if(box.remove)box.remove();}catch(e){}}
   }catch(e){}
   S.renderer=null;S.scene=null;S.camera=null;S.controls=null;S.model=null;S.modelBase=0;
  }catch(e){}
 }
 return api;
}
try{if(typeof module!=='undefined'&&module.exports){module.exports={BODY_RADII_KM:BODY_RADII_KM,BODY_COLORS:BODY_COLORS,textureFileFor:textureFileFor,modelFileFor:modelFileFor,decimatePoints:decimatePoints,clamp01:clamp01,sampleAtTimes:sampleAtTimes,countAtOrBefore:countAtOrBefore,splitRuns:splitRuns,bodyRadiusKm:bodyRadiusKm,bodyColorHex:bodyColorHex,EARTH_TEX_OFFSET_DEG:EARTH_TEX_OFFSET_DEG,earthTexAngleDeg:earthTexAngleDeg,earthSpinDeg:earthSpinDeg,createView3D:createView3D};}}catch(e){}
try{if(typeof globalThis!=='undefined'){globalThis.createView3D=createView3D;}}catch(e){}
})();
