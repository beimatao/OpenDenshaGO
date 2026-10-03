'use strict';
let processingPreview=null,processingBusy=false;
const processingButtons=['previewSmooth','restoreTerrain','previewSimplify','dtmFile'];
function processingMessage(text){$('processingStatus').textContent=text;}
function processingLock(busy){processingBusy=busy;processingButtons.forEach(id=>$(id).disabled=busy);$('applyProcessing').disabled=busy;}
function clearProcessing(){processingPreview=null;$('processingReview').hidden=true;drawMap();}
function showProcessing(result,before,kind,summary){
 if(JSON.stringify(draft)!==JSON.stringify(before)){processingMessage('處理期間路線已變更，結果未套用；請重新預覽。');return;}
 if(kind==='simplify'&&result.changed===false){processingMessage(result.warnings?.join('；')||'沒有可簡化的路段');return;}
 const geometry=G.geometry(result.route),profile=G.profile(result.route,geometry);
 processingPreview={route:result.route,signature:JSON.stringify(before),kind,geometry,profile};
 $('processingSummary').textContent=summary+(result.warnings?.length?'\n需檢查：'+result.warnings.slice(0,4).join('；'):'');$('processingReview').hidden=false;
 processingMessage('預覽完成，檢查橘色虛線後再套用。');drawMap();
}
async function processingRequest(kind,endpoint,options,format){
 if(processingBusy)return;clearProcessing();const before=clone(draft);processingLock(true);processingMessage('正在計算預覽…');
 try{const result=await api(endpoint,{route:before,...options});showProcessing(result,before,kind,format(result));}
 catch(e){processingMessage(e.message);toast(e.message)}finally{processingLock(false)}
}
$('previewSmooth').onclick=()=>processingRequest('smooth','smooth-terrain',{width:+$('smoothWidth').value,strength:+$('smoothStrength').value},r=>`高程平滑：最大坡度 ${r.stats.before.max_grade_pct.toFixed(2)}% → ${r.stats.after.max_grade_pct.toFixed(2)}%；最大高程改動 ${r.stats.max_change.toFixed(2)} m；${r.stats.count} 點。這是地形平滑，不是自動鐵路坡度設計。`);
$('previewSimplify').onclick=()=>processingRequest('simplify','simplify-route',{tolerance:+$('simplifyTolerance').value},r=>`線段 ${r.stats.before} → ${r.stats.after}；全長改變 ${(r.stats.new_length-r.stats.old_length).toFixed(2)} m；線形偏差上界 ${r.stats.max_deviation.toFixed(2)} m；站點位置誤差 ${(r.stats.station_shift*1000).toFixed(3)} mm。套用後需重新計算時刻。`);
$('restoreTerrain').onclick=async()=>{
 if(processingBusy)return;if(!draft.terrain_original){toast('尚無保留的原始高程，請先匯入地形或執行一次平滑');return}
 clearProcessing();const before=clone(draft),candidate=clone(draft);candidate.terrain=clone(candidate.terrain_original);delete candidate.terrain_processing;processingLock(true);
 try{const result=await api('preview',{route:candidate});showProcessing({route:candidate,warnings:result.warnings},before,'restore','還原匯入／首次平滑前的原始高程；不改動線形與站點。');}
 catch(e){processingMessage(e.message)}finally{processingLock(false)}
};
$('dtmFile').onchange=async e=>{
 const file=e.target.files[0];if(!file||processingBusy)return;clearProcessing();const before=clone(draft);processingLock(true);processingMessage('正在傳送及取樣 GeoTIFF，檔案只送到本機 Python 程式…');
 try{
  if(file.size>2*1024**3)throw Error('GeoTIFF 超過 2 GiB，請先在 QGIS 裁切至路線範圍');
  const start=await api('dtm-start',{route:before,filename:file.name,spacing:+$('dtmSpacing').value,band:+$('dtmBand').value,method:$('dtmMethod').value,unit:$('dtmUnit').value,crs_override:$('dtmCrs').value});
  const response=await fetch('/api/dtm-upload/'+encodeURIComponent(start.token),{method:'POST',headers:{'Content-Type':'image/tiff'},body:file});const r=await response.json();if(!response.ok)throw Error(r.error||'DTM 匯入失敗');
  showProcessing(r,before,'dtm',`GeoTIFF：${file.name}；${r.metadata.crs}；${r.count} 個高程點；${r.stats.min_z.toFixed(2)}～${r.stats.max_z.toFixed(2)} m；最大地形坡度 ${r.stats.max_grade_pct.toFixed(2)}%。請確認高程單位及垂直基準正確。`);
 }catch(err){processingMessage(err.message);toast(err.message)}finally{processingLock(false);e.target.value=''}
};
$('applyProcessing').onclick=()=>{
 if(!processingPreview||processingBusy)return;
 if(JSON.stringify(draft)!==processingPreview.signature){clearProcessing();processingMessage('原路線已變更，預覽失效；請重新處理。');return;}
 const before=clone(draft),kind=processingPreview.kind;draft=clone(processingPreview.route);processingPreview=null;$('processingReview').hidden=true;
 selectedNode=selectedSegment=-1;elevationView=null;elevationCursor=null;transaction(before);fillEditor();
 processingMessage(kind==='simplify'?'已簡化；抵達秒數已清空，請自動重算時刻。':'已套用高程；請檢查軌道坡度與高度銜接，可復原或預覽還原原始高程。');
};
$('cancelProcessing').onclick=()=>{clearProcessing();processingMessage('已取消預覽，原資料未變更。')};
$('exportTerrainCsv').onclick=()=>download(routeFilename()+'_地形.csv','\ufeffs,z\r\n'+(draft.terrain||[]).map(p=>p.join(',')).join('\r\n'),'text/csv;charset=utf-8');
function activeProcessing(){return processingPreview&&processingPreview.signature===JSON.stringify(draft)?processingPreview:null;}
function drawProcessingMap(c,drawPiece){const p=activeProcessing();if(!p||p.kind!=='simplify')return;c.save();c.setLineDash([8,5]);p.geometry.pieces.forEach(g=>drawPiece(g,'#ffad55',3,p.route));c.restore();}
function drawProcessingElevation(c,x,y,start,end){const p=activeProcessing();if(!p||p.kind==='simplify')return;c.save();c.strokeStyle='#ffad55';c.lineWidth=2.5;c.setLineDash([7,4]);c.beginPath();let first=true;for(const v of p.profile){if(v.s<start||v.s>end)continue;first?c.moveTo(x(v.s),y(v.ground)):c.lineTo(x(v.s),y(v.ground));first=false;}c.stroke();c.restore();}
