"""Local GeoTIFF sampling and distance-based terrain filtering."""
import bisect,copy,math
from engine import Route,number,MAX_TERRAIN


def samples(route,spacing):
    spacing=number(spacing,1,1000)
    n=math.ceil(route.length/spacing)
    if n+len(route.ends)+2>MAX_TERRAIN:raise ValueError('採樣超過 200000 點，請增加間距')
    return sorted(set([min(i*spacing,route.length) for i in range(n+1)]+route.ends))


def raster_support():
    try:
        import rasterio
        return dict(available=True,version=rasterio.__version__)
    except ImportError:
        return dict(available=False,message='尚未安裝 DTM 支援；請關閉程式，執行 install_dtm_support.bat，再用 start_windows.bat 啟動。')


def sample_geotiff(path,data,spacing=25,band=1,method='bilinear',unit='m',crs_override=''):
    try:
        import rasterio
        from rasterio.warp import transform
        from rasterio.windows import Window
        from rasterio.enums import ColorInterp
    except ImportError:raise ValueError(raster_support()['message'])
    route=Route(data,editing=True);ss=samples(route,spacing)
    if method not in ('nearest','bilinear'):raise ValueError('不支援的取樣方法')
    if unit not in ('m','ft'):raise ValueError('高程單位只支援公尺或英尺')
    factor=1 if unit=='m' else .3048
    try:
        with rasterio.Env(GDAL_CACHEMAX=64*1024*1024):
            with rasterio.open(path) as src:
                if src.driver!='GTiff':raise ValueError('請選擇 GeoTIFF（.tif／.tiff）')
                band_value=number(band,1,src.count)
                if int(band_value)!=band_value:raise ValueError('高程波段需為整數')
                band=int(band_value)
                if src.colorinterp[band-1] in (ColorInterp.red,ColorInterp.green,ColorInterp.blue,ColorInterp.palette):
                    raise ValueError('選取的波段是彩色影像；請使用記錄高程數值的 DTM／DEM，不能使用彩色地形圖')
                crs=rasterio.crs.CRS.from_user_input(crs_override.strip()) if crs_override.strip() else src.crs
                if not crs:raise ValueError('TIFF 沒有座標系統；請依資料說明填寫正確 EPSG，不可猜測')
                if src.transform.is_identity:raise ValueError('TIFF 沒有可用的地理定位轉換，請先轉成有座標定位的 GeoTIFF')
                known_unit=(src.units[band-1] or '').lower()
                if known_unit in ('ft','foot','feet','international foot') and unit!='ft':raise ValueError('此 TIFF 標示高程單位為英尺，請將高程單位改為英尺')
                if known_unit in ('m','meter','metre','meters','metres') and unit!='m':raise ValueError('此 TIFF 標示高程單位為公尺，請將高程單位改為公尺')
                points=[route.point(s) for s in ss]
                xs,ys=transform('EPSG:4326',crs,[p['lon'] for p in points],[p['lat'] for p in points])
                inverse=~src.transform;scale=src.scales[band-1];offset=src.offsets[band-1]
                values=[];bad=[];cache={}
                # Small fixed-size windows avoid loading the whole national DEM into RAM.
                def pixel(row,col):
                    row=max(0,min(src.height-1,row));col=max(0,min(src.width-1,col))
                    key=(row//128,col//128)
                    if key not in cache:
                        if len(cache)>=128:cache.pop(next(iter(cache)))
                        cache[key]=src.read(band,window=Window(key[1]*128,key[0]*128,min(128,src.width-key[1]*128),min(128,src.height-key[0]*128)),masked=True)
                    v=cache[key][row-key[0]*128,col-key[1]*128]
                    return None if bool(getattr(v,'mask',False)) or not math.isfinite(float(v)) else float(v)
                for s,x,y in zip(ss,xs,ys):
                    col,row=inverse*(x,y)
                    if not math.isfinite(col+row) or not 0<=col<src.width or not 0<=row<src.height:
                        bad.append((s,'範圍外'));continue
                    if method=='nearest':z=pixel(math.floor(row),math.floor(col))
                    else:
                        c,r=col-.5,row-.5;c0,r0=math.floor(c),math.floor(r);tx,ty=c-c0,r-r0
                        weights=[((1-tx)*(1-ty),r0,c0),(tx*(1-ty),r0,c0+1),((1-tx)*ty,r0+1,c0),(tx*ty,r0+1,c0+1)]
                        weighted=[(w,pixel(r,c)) for w,r,c in weights if w>1e-12]
                        z=None if any(v is None for w,v in weighted) else sum(w*v for w,v in weighted)
                    if z is None:bad.append((s,'NoData'));continue
                    z=(z*scale+offset)*factor
                    if not math.isfinite(z) or not -500<=z<=9000:bad.append((s,'高程不在 -500～9000 m'));continue
                    values.append([s,z])
                if bad:
                    detail='、'.join(f'{s:.1f} m（{reason}）' for s,reason in bad[:8])
                    raise ValueError(f'{len(bad)} 個取樣點缺失：{detail}。未套用地形；請補齊全線與頭尾緩衝段資料，或改用最近像素取樣檢查邊界。')
                metadata=dict(crs=crs.to_string(),band=band,width=src.width,height=src.height,method=method,unit=unit,spacing=float(spacing),scale=scale,offset=offset)
                result=copy.deepcopy(data);result['terrain']=values;result['terrain_original']=copy.deepcopy(values);result['terrain_source']=dict(type='GeoTIFF',**metadata)
                return dict(route=result,count=len(values),metadata=metadata,stats=terrain_stats(values),warnings=Route(result,editing=True).warnings)
    except ValueError:raise
    except Exception as exc:raise ValueError('無法讀取 GeoTIFF：'+str(exc)) from exc


def terrain_stats(points):
    grades=[abs((b[1]-a[1])/(b[0]-a[0]))*100 for a,b in zip(points,points[1:])]
    return dict(min_z=min(p[1] for p in points),max_z=max(p[1] for p in points),max_grade_pct=max(grades,default=0))


class LinearProfile:
    def __init__(self,points,edge_span=None):
        self.edge_span=edge_span
        self.x=[p[0] for p in points];self.y=[p[1] for p in points];self.area=[0]
        for a,b in zip(points,points[1:]):self.area.append(self.area[-1]+(b[0]-a[0])*(a[1]+b[1])/2)
    def index(self,x):return max(0,min(len(self.x)-2,bisect.bisect_right(self.x,x)-1))
    def value(self,x):
        i=self.index(x);return self.y[i]+(self.y[i+1]-self.y[i])*(x-self.x[i])/(self.x[i+1]-self.x[i])
    def integral(self,x):
        if self.edge_span and (x<self.x[0] or x>self.x[-1]):
            width=min(self.edge_span,self.x[-1]-self.x[0])
            if x<self.x[0]:
                d=x-self.x[0];slope=(self.value(self.x[0]+width)-self.y[0])/width
                return d*self.y[0]+d*d*slope/2
            d=x-self.x[-1];slope=(self.y[-1]-self.value(self.x[-1]-width))/width
            return self.area[-1]+d*self.y[-1]+d*d*slope/2
        i=self.index(x);d=x-self.x[i];slope=(self.y[i+1]-self.y[i])/(self.x[i+1]-self.x[i])
        return self.area[i]+d*self.y[i]+d*d*slope/2


def smooth_terrain(data,width=100,strength=1):
    route=Route(data,editing=True);width=number(width,5,5000);strength=number(strength,0,1)
    # Uniform distance grid avoids density bias from extra samples at segment boundaries.
    step=max(1,min(10,width/10));n=math.ceil(route.length/step)
    if n+1>MAX_TERRAIN:raise ValueError('路線過長，請分段處理地形')
    original=[[route.length*i/n,route.terrain(route.length*i/n)] for i in range(n+1)]
    source=[[0,route.terrain(0)]]+[[s,z] for s,z in route.ground if 0<s<route.length]+[[route.length,route.terrain(route.length)]]
    current=source;half=width/2
    for _ in range(3):
        p=LinearProfile(current,edge_span=width)
        current=[[s,(p.integral(s+half)-p.integral(s-half))/width] for s,z in original]
    left=original[0][1]-current[0][1];right=original[-1][1]-current[-1][1]
    for i,((s,z),(_,old)) in enumerate(zip(current,original)):
        corrected=z+left*(1-s/route.length)+right*s/route.length
        current[i][1]=old+strength*(corrected-old)
        number(current[i][1],-500,9000)
    current[0][1]=original[0][1];current[-1][1]=original[-1][1]
    # Keep terrain outside the modeled route for future extensions.
    current += [[s,z] for s,z in route.ground if s>route.length]
    if len(current)>MAX_TERRAIN:raise ValueError('平滑後點數超過 200000')
    out=copy.deepcopy(data);out.setdefault('terrain_original',copy.deepcopy(data.get('terrain',[[0,0],[route.length,0]])))
    out['terrain']=current
    out['terrain_processing']=dict(method='three_box_distance',width=width,strength=strength)
    old=LinearProfile(source);filtered=LinearProfile(current);check=set([s for s,z in source]+[s for s,z in current if s<=route.length]);max_change=max(abs(filtered.value(s)-old.value(s)) for s in check)
    return dict(route=out,stats=dict(before=terrain_stats(source),after=terrain_stats(current[:n+1]),max_change=max_change,count=n+1),warnings=Route(out,editing=True).warnings)
