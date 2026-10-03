/* Shared pure geometry for the interactive editor. Coordinates: east x, north y. */
(function(root){
'use strict';
const rad=Math.PI/180, deg=180/Math.PI, MAX_RADIUS=1e12;
function arc(a,b,r=0){
 const dx=b.x-a.x,dy=b.y-a.y,c=Math.hypot(dx,dy);
 if(!Number.isFinite(c)||c<1)throw Error('起終點至少相距 1 m');
 let h=Math.atan2(dx,dy),length=c;
 if(r){if(!Number.isFinite(r)||Math.abs(r)<15||Math.abs(r)>MAX_RADIUS||Math.abs(r)+1e-7<c/2)throw Error(`R 至少需 ${Math.max(15,c/2).toFixed(1)} m（弦長的一半）`);const angle=2*Math.asin(Math.min(1,c/(2*Math.abs(r))));h-=Math.sign(r)*angle/2;length=Math.abs(r)*angle;}
 return {x:a.x,y:a.y,h,radius:r,length};
}
function at(g,d){if(g.radius){const h=g.h+d/g.radius,mid=g.h+d/(2*g.radius),chord=2*g.radius*Math.sin(d/(2*g.radius));return{x:g.x+chord*Math.sin(mid),y:g.y+chord*Math.cos(mid),h}}return{x:g.x+Math.sin(g.h)*d,y:g.y+Math.cos(g.h)*d,h:g.h};}
function radiusFromHandle(a,b,p){const dx=b.x-a.x,dy=b.y-a.y,c=Math.hypot(dx,dy);if(c<1)throw Error('起終點太近');let sag=((p.x-(a.x+b.x)/2)*dy-(p.y-(a.y+b.y)/2)*dx)/c;const sign=Math.sign(sag)||1;sag=sign*Math.min(c/2,Math.max(c*c/(8*MAX_RADIUS),Math.abs(sag)));return -sign*Math.max(15,Math.min(MAX_RADIUS,c*c/(8*Math.abs(sag))+Math.abs(sag)/2));}
function geometry(route){let x=0,y=0,h=(+route.heading||0)*rad,s=0;const pieces=[],nodes=[{x:0,y:0}];for(const raw of route.segments){if(raw.heading!=null)h=raw.heading*rad;const g={x,y,h,s,length:+raw.length,radius:+raw.radius||0};pieces.push(g);const end=at(g,g.length);x=end.x;y=end.y;h=end.h;s+=g.length;nodes.push({x,y});}return{pieces,nodes,length:s};}
function tangent(a,p,h,r=0){
 if(r&&(!Number.isFinite(r)||Math.abs(r)<15||Math.abs(r)>MAX_RADIUS))throw Error('圓弧 R 必須介於 15 與 1000000000000 m');
 const dx=p.x-a.x,dy=p.y-a.y;
 if(!r){const length=dx*Math.sin(h)+dy*Math.cos(h);if(length<1)throw Error('請沿前段切線向前拉出至少 1 m');return{x:a.x,y:a.y,h,radius:0,length};}
 const forward=dx*Math.sin(h)+dy*Math.cos(h),right=dx*Math.cos(h)-dy*Math.sin(h);
 let angle=Math.atan2(forward/r,1-right/r)*Math.sign(r);if(angle<0)angle+=2*Math.PI;
 if(angle>Math.PI)throw Error('相切圓弧僅支援向前 180° 內，請調整左／右彎');
 const length=Math.abs(r)*angle;if(length<1)throw Error('圓弧長度至少 1 m');
 return{x:a.x,y:a.y,h,radius:r,length};
}
function align(route,start=1){const out=JSON.parse(JSON.stringify(route));let h=(+out.heading||0)*rad;out.segments.forEach((seg,i)=>{if(i<start&&seg.heading!=null)h=seg.heading*rad;else seg.heading=((h*deg+180)%360+360)%360-180;h+=seg.radius?seg.length/seg.radius:0;});return out;}
function closest(p,pieces){let best=null;for(const g of pieces){let d;if(!g.radius){d=(p.x-g.x)*Math.sin(g.h)+(p.y-g.y)*Math.cos(g.h)}else{const dx=p.x-g.x,dy=p.y-g.y,forward=dx*Math.sin(g.h)+dy*Math.cos(g.h),right=dx*Math.cos(g.h)-dy*Math.sin(g.h);let angle=Math.atan2(forward/g.radius,1-right/g.radius)*Math.sign(g.radius);if(angle<0)angle+=2*Math.PI;d=angle*Math.abs(g.radius);if(d>g.length){const a=at(g,0),b=at(g,g.length);d=Math.hypot(p.x-a.x,p.y-a.y)<Math.hypot(p.x-b.x,p.y-b.y)?0:g.length;}}d=Math.max(0,Math.min(g.length,d));const q=at(g,d),distance=Math.hypot(p.x-q.x,p.y-q.y);if(!best||distance<best.distance)best={...q,s:g.s+d,distance};}return best;}
function ground(route,s){const pts=route.terrain||[[0,0],[1e7,0]];if(s<=pts[0][0])return pts[0][1];let lo=0,hi=pts.length-1;while(lo+1<hi){const m=(lo+hi)>>1;if(pts[m][0]<s)lo=m;else hi=m}const a=pts[lo],b=pts[hi];return a[1]+(b[1]-a[1])*Math.max(0,Math.min(1,(s-a[0])/(b[0]-a[0])));}
function groundSlope(route,s){const pts=route.terrain||[[0,0],[1e7,0]];if(s<pts[0][0]||s>pts.at(-1)[0])return 0;let lo=0,hi=pts.length-1;while(lo+1<hi){const m=(lo+hi)>>1;if(pts[m][0]<=s)lo=m;else hi=m}return (pts[hi][1]-pts[lo][1])/(pts[hi][0]-pts[lo][0]);}
function heightAt(route,g,s){
 const raw=route.segments[g.index],t=Math.max(0,Math.min(1,(s-g.s)/g.length)),terrain=ground(route,s);
 let z,grade;
 if(['absolute','transition','smooth'].includes(raw.mode)){
  const a=g.z0,b=g.z1,u=+raw.grade_start||0,v=+raw.grade_end||0;
  if(raw.mode==='absolute'&&raw.height_points){const pts=raw.height_points;let lo=0,hi=pts.length-1;while(lo+1<hi){const m=(lo+hi)>>1;if(pts[m][0]<=t)lo=m;else hi=m}const [x,y]=pts[lo],[xx,yy]=pts[hi];z=y+(yy-y)*(t-x)/(xx-x);grade=(yy-y)/((xx-x)*g.length);}
  else if(raw.mode==='smooth'){z=(2*t**3-3*t*t+1)*a+(t**3-2*t*t+t)*g.length*u+(-2*t**3+3*t*t)*b+(t**3-t*t)*g.length*v;grade=((6*t*t-6*t)*a+(-6*t*t+6*t)*b)/g.length+(3*t*t-4*t+1)*u+(3*t*t-2*t)*v;}
  else{z=a+(b-a)*t;grade=(b-a)/g.length;}
 }else{z=terrain+(+raw.offset||0);grade=groundSlope(route,s);}
 return {s,z,ground:terrain,grade,segment:g.index};
}
function profile(route,geom=geometry(route)){
 const result=[];let last=ground(route,0),terrainIndex=0;const terrain=route.terrain||[];
 for(let i=0;i<geom.pieces.length;i++){
  const g=geom.pieces[i],raw=route.segments[i];g.index=i;g.z0=raw.z_start??last;g.z1=raw.z_end??last;
  const count=Math.min(1000,Math.max(1,Math.ceil(g.length/Math.max(10,geom.length/20000))));
  const samples=new Set(Array.from({length:count+1},(_,j)=>g.s+g.length*j/count));
  for(const [t] of raw.height_points||[])samples.add(g.s+t*g.length);
  while(terrainIndex<terrain.length&&terrain[terrainIndex][0]<g.s)terrainIndex++;
  while(terrainIndex<terrain.length&&terrain[terrainIndex][0]<=g.s+g.length){samples.add(terrain[terrainIndex++][0]);}
  for(const s of [...samples].sort((a,b)=>a-b)){const p=at(g,s-g.s),v=heightAt(route,g,s);result.push({...p,...v,tunnel:v.z<v.ground-2||raw.mode==='underground',radius:g.radius,mode:raw.mode,lat:+route.lat+p.y/111320,lon:+route.lon+p.x/(111320*Math.cos((route.projection_lat??route.lat)*rad))});last=v.z;}
 }return result;
}
function rebuild(route,nodes,templates){if(nodes.length!==templates.length+1)throw Error('節點數與區段不符');const origin=nodes[0];const segments=templates.map((t,i)=>{let r=+t.radius||0;if(r)r=Math.sign(r)*Math.max(Math.abs(r),Math.hypot(nodes[i+1].x-nodes[i].x,nodes[i+1].y-nodes[i].y)/2,15);const g=arc(nodes[i],nodes[i+1],r);return{...t,length:g.length,radius:r,heading:((g.h*deg+180)%360+360)%360-180};});return{...route,lat:+route.lat+origin.y/111320,lon:+route.lon+origin.x/(111320*Math.cos((route.projection_lat??route.lat)*rad)),heading:segments[0]?.heading||0,segments};}
// Prepend a tangent segment without moving existing geometry or its chainage data.
function prepend(route,length,radius=0){
 length=+length;radius=+radius;
 if(!route.segments.length)throw Error('請先建立路線');
 if(route.segments.length>=20000)throw Error('路段已達 20000 段');
 if(!Number.isFinite(length)||length<1||length>100000)throw Error('延伸長度需介於 1–100000 m');
 if(!Number.isFinite(radius)||(radius&&(Math.abs(radius)<15||Math.abs(radius)>MAX_RADIUS||length/Math.abs(radius)>Math.PI)))throw Error('圓弧 R 至少 15 m，每段不得超過 180°');
 const out=JSON.parse(JSON.stringify(route)),first=route.segments[0],h=(first.heading??route.heading??0)*rad;
 const startH=h-(radius?length/radius:0),delta=at({x:0,y:0,h:startH,radius},length);
 out.projection_lat=route.projection_lat??+route.lat;
 out.lat=+route.lat-delta.y/111320;out.lon=+route.lon-delta.x/(111320*Math.cos(out.projection_lat*rad));
 if(Math.abs(out.lat)>85||Math.abs(out.lon)>180)throw Error('延伸超出支援的經緯度範圍');
 const degrees=((startH*deg+180)%360+360)%360-180;
 const relative=['ground','underground','elevated'].includes(first.mode||'ground');
 out.segments.unshift({length,radius,heading:degrees,mode:relative?(first.mode||'ground'):'absolute',offset:relative?(first.offset||0):0,z_start:first.z_start??ground(route,0),z_end:first.z_start??ground(route,0),limit:null});
 out.segments[1].heading=h*deg;out.heading=degrees;
 out.stations.forEach(st=>st.center=+st.center+length);
 if(out.start_station)out.start_station.center=+out.start_station.center+length;
 const terrain=route.terrain||[[0,0],[Math.max(1,geometry(route).length),0]];
 out.terrain=[[0,ground(route,0)],...terrain.map(([s,z])=>[+s+length,z])];
 if(out.terrain_original){const z=out.terrain_original[0][1];out.terrain_original=[[0,z],...out.terrain_original.map(([s,z])=>[+s+length,z])];}
 if(terrain[0][0]>0)out.terrain.splice(1,0,[length,ground(route,0)]);
 return out;
}
function limit(route,seg,train){const spec=train.curve;const lateral=spec?Math.min(spec.max_unbalanced_mps2,spec.comfort_lateral_mps2+9.81*Math.tan((spec.tilt_enabled?spec.max_tilt_deg:0)*Math.PI/180)):train.lateral;const curve=seg.radius?3.6*Math.sqrt(lateral*Math.abs(seg.radius)):Infinity;return Math.floor((Math.min(train.vmax,route.global_limit==null||route.global_limit===''?400:+route.global_limit,seg.limit==null||seg.limit===''?400:+seg.limit,curve)+1e-9)/5)*5;}
class History{constructor(max=100){this.max=max;this.undoStack=[];this.redoStack=[];}push(before,after){if(JSON.stringify(before)===JSON.stringify(after))return;this.undoStack.push(JSON.parse(JSON.stringify(before)));if(this.undoStack.length>this.max)this.undoStack.shift();this.redoStack=[];}undo(current){if(!this.undoStack.length)return null;this.redoStack.push(JSON.parse(JSON.stringify(current)));return this.undoStack.pop();}redo(current){if(!this.redoStack.length)return null;this.undoStack.push(JSON.parse(JSON.stringify(current)));return this.redoStack.pop();}}

// Capture relative terrain knots without adding horizontal geometry segments.
function freezeHeights(route){const out=JSON.parse(JSON.stringify(route)),geo=geometry(route);profile(route,geo);let terrainIndex=0;const terrain=route.terrain||[];
 geo.pieces.forEach((g,i)=>{const raw=route.segments[i],seg=out.segments[i];seg.z_start=heightAt(route,g,g.s).z;
 if(!['absolute','transition','smooth'].includes(raw.mode)){const ss=[g.s];while(terrainIndex<terrain.length&&terrain[terrainIndex][0]<=g.s)terrainIndex++;while(terrainIndex<terrain.length&&terrain[terrainIndex][0]<g.s+g.length)ss.push(terrain[terrainIndex++][0]);ss.push(g.s+g.length);seg.height_points=ss.map((s,j)=>[j===0?0:j===ss.length-1?1:(s-g.s)/g.length,heightAt(route,g,s).z]);seg.mode='absolute';seg.offset=0;seg.z_end=seg.height_points.at(-1)[1];}
 });return out;}
function changeModes(route,indices,mode){const out=JSON.parse(JSON.stringify(route)),geo=geometry(route);profile(route,geo);
 if(!['ground','underground','elevated','absolute','transition','smooth'].includes(mode))throw Error('請選擇高度模式');
 for(const i of indices){const seg=out.segments[i],g=geo.pieces[i];if(seg.mode===mode)continue;delete seg.height_points;seg.mode=mode;seg.offset=mode==='underground'?-20:mode==='elevated'?10:0;seg.z_start=heightAt(route,g,g.s).z;seg.z_end=heightAt(route,g,g.s+g.length).z;if(mode==='smooth'){seg.grade_start=0;seg.grade_end=0;}}
 return out;}
function uniformGrade(route,indices,start,end){const ids=[...new Set(indices)].sort((a,b)=>a-b);if(ids.length<2||ids.some((v,i)=>!route.segments[v]||(i&&v!==ids[i-1]+1)))throw Error('請選取至少兩個相鄰區段');
 if(start===''||end===''||![+start,+end].every(z=>Number.isFinite(z)&&z>=-500&&z<=9000))throw Error('請輸入 -500 至 9000 m 的起點及末端絕對高程');
 const out=JSON.parse(JSON.stringify(route)),total=ids.reduce((a,i)=>a+(+route.segments[i].length),0);let s=0;start=Math.round(+start*100)/100;end=Math.round(+end*100)/100;
 for(const i of ids){const seg=out.segments[i];seg.mode='absolute';seg.offset=0;delete seg.height_points;seg.z_start=+(start+(end-start)*s/total).toFixed(2);s+=+seg.length;seg.z_end=+(start+(end-start)*s/total).toFixed(2);}return out;}

const api={freezeHeights,changeModes,uniformGrade,prepend,arc,at,tangent,closest,align,radiusFromHandle,geometry,profile,heightAt,rebuild,limit,History};if(typeof module!=='undefined')module.exports=api;root.RailGeometry=api;
})(typeof window==='undefined'?globalThis:window);
