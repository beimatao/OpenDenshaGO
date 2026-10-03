"""Stdlib geographic exchange and DEM sampled-CSV conversion. Does not invent elevations."""
import argparse,csv,io,json,math
from pathlib import Path
from xml.sax.saxutils import escape
from engine import Route,number,MAX_TERRAIN

def export_route(data,kind='geojson',spacing=25):
    route=Route(data,editing=True);spacing=number(spacing,1,1000)
    count=math.ceil(route.length/spacing)
    if count+len(route.ends)+1>MAX_TERRAIN:raise ValueError('採樣點過多，請增加採樣間距')
    distances=sorted(set([min(i*spacing,route.length) for i in range(count+1)]+route.ends))
    points=[route.point(s) for s in distances]
    if kind=='geojson':
        obj=dict(type='FeatureCollection',features=[dict(type='Feature',properties=dict(s=round(p['s'],6),sample_id=i),geometry=dict(type='Point',coordinates=[p['lon'],p['lat']])) for i,p in enumerate(points)])
        return dict(text=json.dumps(obj,ensure_ascii=False),extension='geojson',mime='application/geo+json',count=len(points))
    if kind=='kml':
        coords=' '.join(f"{p['lon']:.10f},{p['lat']:.10f},0" for p in points)
        xml=f'<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>{escape(route.name)}</name><Placemark><name>{escape(route.name)}</name><description>貼地路徑；座標中的 0 不是地形高程，請使用 DEM 另行採樣。</description><LineString><tessellate>1</tessellate><altitudeMode>clampToGround</altitudeMode><coordinates>{coords}</coordinates></LineString></Placemark></Document></kml>'
        return dict(text=xml,extension='kml',mime='application/vnd.google-earth.kml+xml',count=len(points))
    raise ValueError('僅支援 KML／GeoJSON')

def convert_csv(text,z_column='',s_column='s',route_length=None):
    reader=csv.DictReader(io.StringIO(text.lstrip('\ufeff')))
    if not reader.fieldnames:raise ValueError('CSV 沒有欄位名稱')
    fields={f.strip().lower():f for f in reader.fieldnames}
    skey=fields.get(s_column.strip().lower())
    candidates=[z_column.strip().lower()] if z_column.strip() else ['z','elevation','sample_1','rvalue_1','dem_1']
    zkey=next((fields[k] for k in candidates if k in fields),None)
    if not skey or not zkey:raise ValueError('CSV 需包含 s 與地面高程欄位（z／elevation／SAMPLE_1），或指定高程欄名')
    values=[]
    for index,row in enumerate(reader,2):
        if len(values)>=MAX_TERRAIN:raise ValueError('高程資料超過 200000 點')
        try:
            if row.get(skey,'').strip()=='' or row.get(zkey,'').strip()=='':raise ValueError()
            values.append([number(row[skey],0,1e7),number(row[zkey],-500,9000)])
        except (ValueError,TypeError,AttributeError):raise ValueError(f'第 {index} 列里程或高程缺失／無效，請檢查 DEM NoData 或欄位')
    values.sort(key=lambda p:p[0])
    if len(values)<2 or any(b[0]<=a[0] for a,b in zip(values,values[1:])):raise ValueError('需至少兩個不同里程；不可重複')
    if route_length is not None and (values[0][0]>.01 or values[-1][0]<route_length-.01):raise ValueError('高程採樣需涵蓋路線起點 0 m 至終點，請用同一路線重新採樣')
    out=io.StringIO();writer=csv.writer(out);writer.writerow(['s','z']);writer.writerows(values)
    return dict(terrain=values,csv=out.getvalue(),count=len(values),z_column=zkey)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description='將 QGIS DEM 採樣 CSV 轉成 OpenDenshaGO s,z CSV（高程單位須為公尺）')
    parser.add_argument('input');parser.add_argument('output');parser.add_argument('--z-column',default='');parser.add_argument('--s-column',default='s')
    args=parser.parse_args()
    result=convert_csv(Path(args.input).read_text(encoding='utf-8-sig'),args.z_column,args.s_column)
    Path(args.output).write_text(result['csv'],encoding='utf-8-sig');print(f"已轉換 {result['count']} 個高程點")
