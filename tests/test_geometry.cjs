const assert=require('node:assert/strict'),G=require('../static/geometry.js');
const near=(a,b)=>assert.ok(Math.abs(a-b)<1e-6,`${a} != ${b}`);
let count=0;function test(name,fn){fn();count++;console.log('PASS '+name)}
test('line endpoints',()=>{const a={x:50,y:-20},b={x:350,y:400},g=G.arc(a,b);const end=G.at(g,g.length);near(end.x,b.x);near(end.y,b.y)});
test('minor arc left/right exact endpoints and radius',()=>{for(const r of [-600,600,500,-500]){const a={x:0,y:0},b={x:1000,y:0},g=G.arc(a,b,r),end=G.at(g,g.length);near(end.x,b.x);near(end.y,b.y);const mid=G.at(g,g.length/2);near(Math.abs(G.radiusFromHandle(a,b,mid)),Math.abs(r));assert.equal(Math.sign(G.radiusFromHandle(a,b,mid)),Math.sign(r))}});
test('infeasible R rejected',()=>assert.throws(()=>G.arc({x:0,y:0},{x:1000,y:0},300)));
test('drag endpoint keeps shared nodes continuous',()=>{const d={lat:25,lon:121,heading:0,segments:[{length:1000,radius:0},{length:500,radius:600}]};const geo=G.geometry(d);geo.nodes[1]={x:100,y:800};const rebuilt=G.rebuild(d,geo.nodes,d.segments),after=G.geometry(rebuilt);after.nodes.forEach((p,i)=>{near(p.x,geo.nodes[i].x);near(p.y,geo.nodes[i].y)})});
test('drag origin preserves other geographic endpoints',()=>{const d={lat:25,lon:121,heading:0,segments:[{length:1000,radius:0}]};const nodes=[{x:20,y:10},{x:0,y:1000}],b=G.rebuild(d,nodes,d.segments),end=G.geometry(b).nodes[1];near(b.lat+end.y/111320,d.lat+1000/111320)});
test('undo/redo snapshots and branching',()=>{const h=new G.History(2),a={x:[1]},b={x:[2]},c={x:[3]};h.push(a,b);h.push(b,c);assert.deepEqual(h.undo(c),b);assert.deepEqual(h.undo(b),a);assert.deepEqual(h.redo(a),b);h.push(b,{x:[5]});assert.equal(h.redo({x:[5]}),null)});
test('auto speed 5 km/h conservative rounding',()=>{const train={vmax:300,lateral:.8};assert.equal(G.limit({global_limit:93},{radius:0,limit:null},train),90);assert.equal(G.limit({global_limit:320},{radius:800,limit:''},train),90);assert.equal(G.limit({global_limit:320},{radius:800,limit:62},train),60)});

test('tangent line projects pointer onto previous direction',()=>{const g=G.tangent({x:0,y:0},{x:400,y:600},0,0);near(G.at(g,g.length).x,0);near(G.at(g,g.length).y,600)});
test('tangent arc shares incoming heading',()=>{for(const r of [300,-300]){const g=G.tangent({x:0,y:0},{x:Math.sign(r)*300,y:300},0,r);near(g.h,0);near(g.length,300*Math.PI/2);const straight=G.tangent(G.at(g,g.length),{x:Math.sign(r)*800,y:350},G.at(g,g.length).h,0);near(straight.h,G.at(g,g.length).h)}});
test('nearest route station projection is exact on line',()=>{const g={...G.arc({x:0,y:0},{x:1000,y:0}),s:50};const hit=G.closest({x:333,y:20},[g]);near(hit.s,383);near(hit.y,0)});
test('smooth gradient has flat ends',()=>{const route={lat:0,lon:0,heading:0,terrain:[[0,0],[2000,0]],segments:[{length:1000,radius:0,mode:'smooth',z_end:-20}]};const p=G.profile(route);near(p[0].z,0);near(p.at(-1).z,-20);near(p[Math.floor(p.length/2)].z,-10)});

console.log(`${count} geometry/history tests passed`);

for(const r of [100000,-100001,1e6,-1e6,1e12,-1e12]){
 const g={x:123,y:456,h:.645771823,radius:r,length:2000,s:0};
 const p=G.at(g,723.45),near=G.closest(p,[g]);
 assert.ok(Math.abs(near.s-723.45)<1e-6,`large R nearest ${r}`);
 const tangent=G.tangent({x:g.x,y:g.y},p,g.h,r);
 assert.ok(Math.abs(tangent.length-723.45)<1e-6,`large R tangent ${r}`);
}
console.log('PASS large signed arc projection and tangent to 1e12 m');
const elevated={heading:0,lat:25,lon:121,terrain:[[0,10],[13,23],[25,15],[100,20]],segments:[{length:100,radius:0,mode:'elevated',offset:10}],stations:[]};
const eg=G.geometry(elevated),ep=G.profile(elevated,eg);
assert.ok(ep.some(p=>p.s===13&&p.ground===23&&p.z===33));
assert.equal(G.heightAt(elevated,eg.pieces[0],5).grade,1);
console.log('PASS DEM sample peaks retained and exact relative track grade');
