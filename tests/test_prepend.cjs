const assert=require('node:assert/strict'),G=require('../static/geometry.js');
const source={lat:25,lon:121,heading:40,terrain:[[0,100],[600,130],[4000,160]],segments:[{length:1500,radius:2000,mode:'smooth',z_end:150,grade_start:.02,grade_end:0},{length:1500,radius:0,mode:'absolute',z_end:180}],start_station:{center:300,name:'S'},stations:[{center:1600,name:'A',arrival:200},{center:2600,name:'B',arrival:300}]};
function ll(route,p){return [route.lat+p.y/111320,route.lon+p.x/(111320*Math.cos((route.projection_lat??route.lat)*Math.PI/180))]}
for(const radius of [0,1500,-1500,1e8,-1e8]){
 const before=JSON.stringify(source),out=G.prepend(source,700,radius),a=G.geometry(source),b=G.geometry(out);G.profile(source,a);G.profile(out,b);
 assert.equal(JSON.stringify(source),before);assert.equal(out.start_station.center,1000);assert.equal(out.stations[1].center,3300);assert.equal(out.stations[1].arrival,300);
 for(let i=0;i<a.pieces.length;i++)for(const d of [0,100,a.pieces[i].length]){
  const old=ll(source,G.at(a.pieces[i],d)),now=ll(out,G.at(b.pieces[i+1],d));for(let k=0;k<2;k++)assert.ok(Math.abs(old[k]-now[k])<1e-10);
  const v=G.heightAt(source,a.pieces[i],a.pieces[i].s+d),w=G.heightAt(out,b.pieces[i+1],b.pieces[i+1].s+d);assert.ok(Math.abs(v.z-w.z)<1e-9);assert.ok(Math.abs(v.ground-w.ground)<1e-9);
 }
 assert.ok(Math.abs(G.at(b.pieces[0],700).h-a.pieces[0].h)<1e-9);
 const again=G.prepend(out,400,-800);assert.equal(again.stations[0].center,2700);
}
assert.throws(()=>G.prepend(source,0));assert.throws(()=>G.prepend(source,100,10));assert.throws(()=>G.prepend(source,1000,100));
console.log('PASS prepend signed arcs, repeated extension, geographic and vertical invariance, validation');
