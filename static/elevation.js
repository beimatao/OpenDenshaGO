'use strict';
// Viewport state is deliberately separate from route data and undo history.
let elevationView=null,elevationCursor=null,elevationDrag=null,elevationScale=null;
function elevationRange(){
 const total=Math.max(1,editGeom.length);
 if(!elevationView)elevationView={start:0,span:total,zScale:1};
 elevationView.span=Math.max(Math.min(20,total),Math.min(total,elevationView.span));
 elevationView.start=Math.max(0,Math.min(total-elevationView.span,elevationView.start));
 return elevationView;
}
function elevationSample(s){
 let lo=0,hi=editGeom.pieces.length;
 while(lo<hi){const m=(lo+hi)>>1;if(editGeom.pieces[m].s+editGeom.pieces[m].length<=s)lo=m+1;else hi=m;}
 const g=editGeom.pieces[Math.min(lo,editGeom.pieces.length-1)];
 return g?RailGeometry.heightAt(draft,g,s):null;
}
function drawElevation(){
 const [c,w,h]=fitCanvas($('elevation'));c.fillStyle='#0d1821';c.fillRect(0,0,w,h);
 if(!preview.length){$('elevationReadout').textContent='尚無軌道，請先繪製路線';return;}
 const v=elevationRange(),end=v.start+v.span,left=62,right=w-16,top=35,bottom=h-32;
 const points=[elevationSample(v.start),...preview.filter(p=>p.s>v.start&&p.s<end),elevationSample(end)];
 let lo=Infinity,hi=-Infinity;for(const p of points){lo=Math.min(lo,p.z,p.ground);hi=Math.max(hi,p.z,p.ground);}
 const pending=activeProcessing();if(pending&&pending.kind!=='simplify'){for(const p of pending.profile){if(p.s>=v.start&&p.s<=end){lo=Math.min(lo,p.ground);hi=Math.max(hi,p.ground)}}}
 const mid=(hi+lo)/2,range=Math.max(10,hi-lo+10)/v.zScale;lo=mid-range/2;hi=mid+range/2;
 const x=s=>left+(s-v.start)/v.span*(right-left),y=z=>bottom-(z-lo)/range*(bottom-top);
 elevationScale={left,right,top,bottom,w,h};
 c.font='11px monospace';c.lineWidth=1;
 for(let i=0;i<=4;i++){const z=lo+range*i/4,py=y(z);c.strokeStyle='#263747';c.beginPath();c.moveTo(left,py);c.lineTo(right,py);c.stroke();c.fillStyle='#9aafbc';c.fillText(z.toFixed(1),2,py+4);const s=v.start+v.span*i/4;c.fillText((s/1000).toFixed(2)+' km',Math.max(left,Math.min(right-65,x(s)-25)),h-9);}
 c.save();c.beginPath();c.rect(left,top,right-left,bottom-top);c.clip();
 // Draw ground first; a dark outline keeps the rail visible even when coincident.
 for(const [key,color,width] of [['ground','#88a977',2],['z','#071017',6],['z','#55dfd0',2.5]]){c.strokeStyle=color;c.lineWidth=width;c.beginPath();points.forEach((p,i)=>i?c.lineTo(x(p.s),y(p[key])):c.moveTo(x(p.s),y(p[key])));c.stroke();}
 if(selectedSegment>=0){const g=editGeom.pieces[selectedSegment];if(g){c.strokeStyle='#ffa44d';c.lineWidth=4;c.beginPath();let first=true;for(const p of points){if(p.segment===selectedSegment){first?c.moveTo(x(p.s),y(p.z)):c.lineTo(x(p.s),y(p.z));first=false;}}c.stroke();}}
 const stations=[...(draft.start_station?[{...draft.start_station,isOrigin:true}]:[]),...draft.stations];let lastLabel=-Infinity,row=0;
 for(const st of stations){if(st.center<v.start||st.center>end)continue;const px=x(st.center);c.strokeStyle=st.stop_enabled===false?'#73db88':'#ffca72';c.lineWidth=1;c.setLineDash([5,4]);c.beginPath();c.moveTo(px,top);c.lineTo(px,bottom);c.stroke();c.setLineDash([]);if(px-lastLabel>85){c.fillStyle=c.strokeStyle;c.fillText((st.isOrigin?'起 ':st.stop_enabled===false?'過 ':'停 ')+st.name,px+3,top+12+(row++%2)*14);lastLabel=px;}}
 // Grade labels become visible once zoomed; values use analytic rail derivatives.
 if(v.span<editGeom.length*.95){for(let px=left+60;px<right-40;px+=135){const p=elevationSample(v.start+(px-left)/(right-left)*v.span);const py=Math.max(top+45,Math.min(bottom-6,y(p.z)-9));c.fillStyle='#071017';c.fillRect(px-35,py-12,85,17);c.fillStyle='#55dfd0';c.fillText((p.grade>=0?'+':'')+(p.grade*100).toFixed(2)+'%',px-30,py);}}
 if(elevationCursor!=null&&elevationCursor>=v.start&&elevationCursor<=end){const p=elevationSample(elevationCursor),px=x(p.s);c.strokeStyle='#fff';c.lineWidth=1;c.setLineDash([3,3]);c.beginPath();c.moveTo(px,top);c.lineTo(px,bottom);c.stroke();c.setLineDash([]);c.fillStyle='#fff';c.beginPath();c.arc(px,y(p.z),4,0,2*Math.PI);c.fill();$('elevationReadout').textContent=`里程 ${p.s.toFixed(1)} m｜第 ${p.segment+1} 段｜軌道 ${p.z.toFixed(2)} m｜地面 ${p.ground.toFixed(2)} m｜軌道－地面 ${(p.z-p.ground).toFixed(2)} m｜坡度 ${(p.grade*100).toFixed(2)}%（順向）`;}
 else $('elevationReadout').textContent=`顯示 ${(v.start/1000).toFixed(2)}–${(end/1000).toFixed(2)} km｜移動游標查看軌道高程與坡度；點擊選取線段`;
 drawProcessingElevation(c,x,y,v.start,end);c.restore();c.fillStyle='#9aafbc';c.fillText('高程 m  ·  青色軌道 / 綠色地面 / 橘色選取段',left,18);
}
function resetElevation(){elevationView=null;elevationCursor=null;drawMap();}
const elevationCanvas=$('elevation');
$('elevationReset').onclick=resetElevation;elevationCanvas.ondblclick=resetElevation;
function elevationPointer(e){return e.clientX-elevationCanvas.getBoundingClientRect().left;}
function elevationS(px){const q=elevationScale,v=elevationRange();return Math.max(v.start,Math.min(v.start+v.span,v.start+(px-q.left)/(q.right-q.left)*v.span));}
elevationCanvas.addEventListener('wheel',e=>{
 e.preventDefault();if(!preview.length||!elevationScale)return;const v=elevationRange(),factor=Math.exp(Math.max(-1,Math.min(1,e.deltaY*.002)));
 if(e.shiftKey)v.zScale=Math.max(.25,Math.min(20,v.zScale/factor));
 else{const s=elevationS(elevationPointer(e)),ratio=(s-v.start)/v.span;v.span=Math.max(Math.min(20,editGeom.length),Math.min(editGeom.length,v.span*factor));v.start=s-ratio*v.span;elevationRange();}
 drawElevation();
},{passive:false});
elevationCanvas.addEventListener('pointerdown',e=>{if(e.button!==0||!preview.length)return;const v=elevationRange();elevationDrag={x:elevationPointer(e),start:v.start,span:v.span,moved:false};elevationCanvas.setPointerCapture(e.pointerId);});
elevationCanvas.addEventListener('pointermove',e=>{if(!preview.length||!elevationScale)return;const px=elevationPointer(e);if(elevationDrag){const d=elevationDrag;d.moved ||=Math.abs(px-d.x)>3;elevationView.start=d.start-(px-d.x)/(elevationScale.right-elevationScale.left)*d.span;elevationRange();}elevationCursor=elevationS(px);drawMap();});
elevationCanvas.addEventListener('pointerup',e=>{if(!elevationDrag)return;const moved=elevationDrag.moved;elevationDrag=null;if(elevationCanvas.hasPointerCapture(e.pointerId))elevationCanvas.releasePointerCapture(e.pointerId);if(!moved&&preview.length){elevationCursor=elevationS(elevationPointer(e));selectedSegment=elevationSample(elevationCursor).segment;selectedNode=-1;segmentPage=Math.floor(selectedSegment/PAGE_SIZE);renderTables();selectionUI();}drawMap();});
elevationCanvas.addEventListener('pointercancel',()=>{elevationDrag=null;});
