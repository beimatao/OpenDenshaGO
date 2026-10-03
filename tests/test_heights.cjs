const assert=require('node:assert/strict'),G=require('../static/geometry.js');
const r={lat:25,lon:121,terrain:[[0,100],[20,110],[80,90],[100,100],[200,130]],segments:[{length:100,mode:'elevated',offset:10},{length:100,mode:'smooth',z_end:150,grade_start:.1,grade_end:.2}],stations:[]};
const frozen=G.freezeHeights(r),changed=JSON.parse(JSON.stringify(frozen));changed.terrain=[[0,-30],[200,200]];
const a=G.geometry(r),b=G.geometry(changed);G.profile(r,a);G.profile(changed,b);
for(let i=0;i<2;i++)for(let d=0;d<=100;d++)assert.ok(Math.abs(G.heightAt(r,a.pieces[i],i*100+d).z-G.heightAt(changed,b.pieces[i],i*100+d).z)<1e-8);
assert.equal(frozen.segments.length,2);assert.equal(frozen.segments[0].height_points.length,4);
const uniform=G.uniformGrade(frozen,[1,0],100,120);assert.deepEqual(uniform.segments.map(s=>[s.z_start,s.z_end]),[[100,110],[110,120]]);assert.equal(uniform.segments[0].height_points,undefined);
assert.throws(()=>G.uniformGrade(r,[0],0,1));assert.throws(()=>G.uniformGrade(r,[0,1],'',1));
const mode=G.changeModes(r,[0,1],'absolute');assert.equal(mode.segments[0].z_start,110);assert.equal(mode.segments[1].z_start,110);
console.log('Height freeze, terrain replacement, mixed curves, uniform grade and modes passed');

const decimal={lat:25,lon:121,terrain:[[0,10],[100000,20]],stations:[],segments:Array.from({length:308},(_,i)=>({length:i?78.9:1234.56,mode:'ground'}))};
const fixed=G.freezeHeights(decimal);
for(const seg of fixed.segments){assert.equal(seg.height_points[0][0],0);assert.equal(seg.height_points.at(-1)[0],1);}
console.log('PASS 308 decimal-length segments have exact frozen endpoints');
