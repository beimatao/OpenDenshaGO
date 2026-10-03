"""OpenDenshaGO prototype: all geometry, train dynamics and scoring in Python/SI units."""
from __future__ import annotations
import bisect, copy, math

# Editable source of truth; compatibility aliases keep older UI/API consumers working.
import json
from pathlib import Path

def load_trains():
    trains=json.loads((Path(__file__).with_name('trains.json')).read_text(encoding='utf-8'))
    for train in trains.values():
        for key in ('length','operating_max_kmh','acceleration_mps2','service_brake_mps2','emergency_brake_mps2'):
            if not isinstance(train[key],(int,float)) or not math.isfinite(train[key]) or train[key]<=0:
                raise ValueError(f'車型參數 {key} 必須為正有限數')
        if train['emergency_brake_mps2']<train['service_brake_mps2']:
            raise ValueError('緊急煞車不得弱於常用全煞車')
        curve=train['curve']
        for key in ('comfort_lateral_mps2','max_unbalanced_mps2','max_tilt_deg'):
            if not math.isfinite(curve[key]) or curve[key]<0: raise ValueError('曲線參數必須非負且有限')
        if not 0<=curve['max_tilt_deg']<=10: raise ValueError('傾斜角必須介於 0–10 度')
        if min(curve['comfort_lateral_mps2'],curve['max_unbalanced_mps2'])<=0: raise ValueError('曲線加速度必須大於零')
        train.update(name=f"{train['model']}・{train['cars']} 節編組",vmax=train['operating_max_kmh'],
                     accel=train['acceleration_mps2'],brake=train['service_brake_mps2'],emergency=train['emergency_brake_mps2'],
                     lateral=curve['comfort_lateral_mps2'])
    return trains

TRAINS = load_trains()

def curve_acceleration(train):
    """Simplified comfort + tilt allowance, capped independently for track forces.
    No cant, transition-curve dynamics or actual railway authorization is implied.
    """
    curve=train.get('curve')
    if not curve: return train['lateral']
    angle=curve['max_tilt_deg'] if curve['tilt_enabled'] else 0
    return min(curve['max_unbalanced_mps2'],curve['comfort_lateral_mps2']+9.81*math.tan(math.radians(angle)))

def traction_acceleration(train, speed):
    """Game traction curve, speed in m/s; listed acceleration is starting performance."""
    return train['accel']*max(.2,1-(speed*3.6/train['vmax'])**2)

MAX_SEGMENTS=20000
MAX_STATIONS=10000
MAX_TERRAIN=200000

MODES = {'ground', 'underground', 'elevated', 'transition', 'absolute', 'smooth'}

def number(value, lo=-1e7, hi=1e7):
    value = float(value)
    if not math.isfinite(value) or not lo <= value <= hi:
        raise ValueError(f'數值必須介於 {lo:g} 和 {hi:g}')
    return value

class Route:
    """Analytic tangent lines/circular arcs; s is horizontal engineering chainage."""
    def __init__(self, data, editing=False):
        self.data = copy.deepcopy(data)
        self.global_limit = 400 if data.get('global_limit') in (None,'') else number(data['global_limit'],5,400)
        self.name = str(data.get('name', '自訂路線'))[:80]
        self.lat = number(data.get('lat', 25.03), -85, 85)
        self.projection_lat = number(data.get('projection_lat',self.lat), -85, 85)
        self.lon = number(data.get('lon', 121.56), -180, 180)
        self.heading = math.radians(number(data.get('heading', 0), -360, 360))
        self.start_time = number(data.get('start_time', 28800), 0, 86399)
        self.early = number(data.get('early', 30), 0, 600)
        self.late = number(data.get('late', 30), 0, 600)
        raw_ground = data.get('terrain', [[0, 0], [100000, 0]])
        if not 2 <= len(raw_ground) <= MAX_TERRAIN:
            raise ValueError('地形資料需至少兩點，最多 200000 點')
        self.ground = [(number(s,0,1e7),number(z,-500,9000)) for s,z in raw_ground]
        if any(b[0] <= a[0] for a,b in zip(self.ground,self.ground[1:])):
            raise ValueError('地形里程必須遞增')
        self.ground_s = [p[0] for p in self.ground]
        self.segments, self.ends = [], []
        self.warnings = []
        x=y=s=0.0; heading=self.heading; last_z=self.terrain(0)
        raw = data.get('segments', [])
        if not 1 <= len(raw) <= MAX_SEGMENTS:
            raise ValueError('路線需 1–20000 個區段')
        for seg in raw:
            if seg.get('heading') is not None:
                heading=math.radians(number(seg['heading'],-360,360))
            length=number(seg.get('length',500),1,100000)
            radius=number(seg.get('radius',0),-1e12,1e12)
            if radius and abs(radius)<15: raise ValueError('彎道半徑至少 15 m，0 代表直線')
            if radius and length/abs(radius)>math.pi+1e-9: raise ValueError('每段圓弧不得超過 180 度')
            mode=seg.get('mode','ground')
            if mode not in MODES: raise ValueError('不支援的高度模式')
            offset=number(seg.get('offset',0),-300,300)
            if mode=='ground' and offset!=0: raise ValueError('貼地模式偏移必須為 0')
            if mode=='underground' and offset>=0: raise ValueError('地下模式偏移必須為負值')
            if mode=='elevated' and offset<=0: raise ValueError('高架模式偏移必須為正值')
            z_end=number(seg.get('z_end',last_z),-500,9000)
            # A transition is an absolute linear grade. Relative modes follow supplied terrain.
            item=dict(s=s,end=s+length,length=length,x=x,y=y,h=heading,radius=radius,
                      mode=mode,offset=offset,z0=number(seg.get('z_start',last_z),-500,9000),z1=z_end,
                      grade_start=number(seg.get('grade_start',0),-10,10),grade_end=number(seg.get('grade_end',0),-10,10),
                      limit=None if seg.get('limit') in (None,'') else number(seg['limit'],5,400))
            if mode=='absolute' and seg.get('height_points') is not None:
                pts=seg['height_points']
                if not isinstance(pts,list) or not 2<=len(pts)<=MAX_TERRAIN: raise ValueError('固定高程點數無效')
                # Accept endpoint roundoff from 0.1.5.1 exports, without hiding malformed profiles.
                tolerance=1e-9
                pts=[(number(a,-tolerance,1+tolerance),number(b,-500,9000)) for a,b in pts]
                if abs(pts[0][0])<=tolerance: pts[0]=(0.0,pts[0][1])
                if abs(pts[-1][0]-1)<=tolerance: pts[-1]=(1.0,pts[-1][1])
                if pts[0][0]!=0 or pts[-1][0]!=1 or any(b[0]<=a[0] for a,b in zip(pts,pts[1:])): raise ValueError('固定高程點必須由 0 遞增至 1')
                if abs(pts[0][1]-item['z0'])>1e-7 or abs(pts[-1][1]-item['z1'])>1e-7: raise ValueError('固定高程端點不符')
                item['height_points']=pts
                item['height_t']=[a for a,b in pts]
            start_z=self._height(item,0)
            if self.segments and abs(start_z-last_z)>0.05:
                message=f'第 {len(self.segments)+1} 段起點高度不連續（差 {start_z-last_z:+.2f} m）：請插入切換坡道或緩坡銜接'
                if not editing: raise ValueError(message)
                self.warnings.append(message)
            self.segments.append(item); self.ends.append(s+length)
            x,y,heading=self._xy(item,length)
            last_z=self._height(item,length); s+=length
        self.length=s
        self.door_margins={key:number(data.get('door_margins',{}).get(key,default),0,100)
                           for key,default in (('simple',20),('classic',10))}
        def station(st, origin=False):
            arrival=st.get('arrival')
            if not editing and not origin and arrival in (None,''):
                raise ValueError('抵達秒數尚有空白，請先自動計算或手動填寫')
            return dict(name=str(st.get('name','起始站' if origin else '車站'))[:50],
                center=number(st.get('center',0),0,s),
                platform=None if st.get('platform') in (None,'') else number(st['platform'],10,1000),
                arrival=None if origin or arrival in (None,'') else number(arrival,1,86400),
                dwell=number(st.get('dwell',20),0,600),stop_enabled=st.get('stop_enabled',True) is not False)
        if len(data.get('stations',[]))>MAX_STATIONS:raise ValueError('停靠站最多 10000 站')
        self.stations=[station(st) for st in data.get('stations',[])]
        self.origin=station(data['start_station'],True) if data.get('start_station') else None
        self.direction='forward'
        if not self.stations and not editing: raise ValueError('請至少加入一個停靠站')
        self.stations.sort(key=lambda v:v['center'])
        for a,b in zip(self.stations,self.stations[1:]):
            if b['center']<=a['center'] or (not editing and b['arrival']<=a['arrival']):
                raise ValueError('站點里程與到站時間都必須遞增')
        if self.origin and self.stations and self.origin['center']>=self.stations[0]['center']:
            raise ValueError('起始站中心必須在第一站之前')

    def terrain(self,s):
        i=max(0,min(len(self.ground)-2,bisect.bisect_right(self.ground_s,s)-1))
        a,b=self.ground[i],self.ground[i+1]
        t=max(0,min(1,(s-a[0])/(b[0]-a[0])))
        return a[1]+(b[1]-a[1])*t

    def _height(self,seg,d):
        if seg.get('height_points'):
            t=max(0,min(1,d/seg['length']));pts=seg['height_points']
            i=max(0,min(len(pts)-2,bisect.bisect_right(seg['height_t'],t)-1))
            a,b=pts[i],pts[i+1]
            return a[1]+(b[1]-a[1])*(t-a[0])/(b[0]-a[0])
        if seg['mode']=='smooth':
            t=d/seg['length']
            return (2*t**3-3*t*t+1)*seg['z0']+(t**3-2*t*t+t)*seg['length']*seg['grade_start']+(-2*t**3+3*t*t)*seg['z1']+(t**3-t*t)*seg['length']*seg['grade_end']
        if seg['mode'] in ('absolute','transition'):
            return seg['z0']+(seg['z1']-seg['z0'])*d/seg['length']
        return self.terrain(seg['s']+d)+seg['offset']

    @staticmethod
    def _xy(seg,d):
        h=seg['h']; r=seg['radius']
        if r:
            h1=h+d/r
            chord=2*r*math.sin(d/(2*r)); mid=h+d/(2*r)
            return seg['x']+chord*math.sin(mid),seg['y']+chord*math.cos(mid),h1
        return seg['x']+math.sin(h)*d,seg['y']+math.cos(h)*d,h

    def point(self,s):
        s=max(0,min(self.length,s)); i=min(len(self.segments)-1,bisect.bisect_right(self.ends,s))
        seg=self.segments[i]; d=s-seg['s']; x,y,h=self._xy(seg,d)
        z=self._height(seg,d); ground=self.terrain(s)
        # Rail below DEM ground by >2 m is automatically classified as tunnel.
        tunnel=(z<ground-2) or seg['mode']=='underground'
        return dict(s=s,x=x,y=y,z=z,ground=ground,h=h,radius=seg['radius'],limit=seg['limit'],
                    tunnel=tunnel,mode=seg['mode'],lat=self.lat+y/111320,
                    lon=self.lon+x/(111320*math.cos(math.radians(self.projection_lat))))

    def profile(self,step=10):
        count=min(20000,math.ceil(self.length/step))
        return [self.point(self.length*i/count) for i in range(count+1)]

    def raw_speed_limit(self,s,train):
        p=self.point(s)
        curve=math.sqrt(curve_acceleration(train)*abs(p['radius']))*3.6 if p['radius'] else 999
        return math.floor((min(train['vmax'], self.global_limit, p['limit'] or 400, curve)+1e-9)/5)*5

    def effective_limits(self,train):
        key=(self.global_limit,train['length'],train['vmax'],curve_acceleration(train))
        cache=getattr(self,'_speed_cache',None)
        if cache is None:self._speed_cache={};cache=self._speed_cache
        if key in cache:return cache[key]
        segs=self.segments;values=[self.raw_speed_limit((v['s']+v['end'])/2,train) for v in segs]
        # OSM fillets often alternate arcs with short tangent connectors.
        # Join same-sign curves across a connector shorter than this train.
        i=0
        while i<len(segs):
            r=segs[i]['radius']
            if not r:i+=1;continue
            end=i;j=i+1
            while j<len(segs):
                if segs[j]['radius']:
                    if segs[j]['radius']*r<=0:break
                    end=j;j+=1;continue
                k=j
                while k<len(segs) and not segs[k]['radius']:k+=1
                gap=(segs[k]['s'] if k<len(segs) else self.length)-segs[j]['s']
                if k<len(segs) and gap<train['length'] and segs[k]['radius']*r>0:end=k;j=k+1
                else:break
            low=min(values[i:end+1]);values[i:end+1]=[low]*(end-i+1);i=end+1
        # A brief rise is held at the preceding lower limit until the next
        # reduction boundary; never raise any underlying lower restriction.
        drops=[i for i in range(1,len(values)) if values[i]<values[i-1]]
        base=values[:]
        for i in range(1,len(values)):
            if base[i]>base[i-1]:
                k=bisect.bisect_right(drops,i)
                if k<len(drops):
                    j=drops[k]
                    if segs[j]['s']-segs[i]['s']<train['length']:
                        held=values[i-1]
                        for n in range(i,j):values[n]=min(values[n],held)
        cache[key]=values
        return values

    def speed_limit(self,s,train):
        index=min(len(self.segments)-1,bisect.bisect_right(self.ends,max(0,min(self.length,s))))
        return self.effective_limits(train)[index]

def platform_length(station,train,route,mode='simple'):
    explicit=station.get('platform')
    return train['length']+2*route.door_margins[mode] if explicit in (None,'') else float(explicit)

class ReverseRoute(Route):
    """Exact reversed view of geometry. Canonical editor data remains forward-oriented."""
    def __init__(self,source):
        if not source.origin: raise ValueError('請先在工坊設定「起始站／逆向終點」')
        if not source.stations: raise ValueError('請先新增順向終點站')
        self.__dict__.update(source.__dict__)
        self.source=source;self.direction='backward';self._speed_cache={}
        self.origin=dict(source.stations[-1],center=self.length-source.stations[-1]['center'])
        ordered=list(reversed(source.stations[:-1]))+[dict(source.origin,stop_enabled=True)]
        self.stations=[dict(st,center=self.length-st['center'],arrival=None) for st in ordered]
        self.segments=[dict(seg,s=self.length-seg['end'],end=self.length-seg['s'],radius=-seg['radius']) for seg in reversed(source.segments)]
        self.ends=[seg['end'] for seg in self.segments]
    def point(self,s):
        s=max(0,min(self.length,s))
        p=self.source.point(self.length-s)
        # Select the entering segment at a boundary, not the segment just left.
        index=min(len(self.segments)-1,bisect.bisect_right(self.ends,s))
        seg=self.segments[index]
        return dict(p,s=s,h=p['h']+math.pi,radius=seg['radius'],limit=seg['limit'])


def departure_position(route,train):
    half=train['length']/2
    if route.origin:
        c=route.origin['center']
        if c<half or c+half>route.length: raise ValueError('起始月台中心太靠近路線邊界，列車無法完整放入路線')
        return c+half
    return train['length']


def service_route(data,direction='forward',start_station=None):
    if direction not in ('forward','backward'):raise ValueError('不支援的行車方向')
    source=Route(data,editing=True)
    if source.warnings:raise ValueError(source.warnings[0])
    station_ids={float(st['center']):i for i,st in enumerate(data.get('stations',[]))}
    for st in source.stations:st['station_id']=station_ids[st['center']]
    if source.origin:source.origin['station_id']=-1
    route=ReverseRoute(source) if direction=='backward' else source
    if start_station is not None:
        if isinstance(start_station,bool) or not isinstance(start_station,int):raise ValueError('起始站選擇無效')
        ordered=([route.origin] if route.origin else [])+route.stations
        index=next((i for i,st in enumerate(ordered) if st.get('station_id')==start_station),None)
        if index is None:raise ValueError('找不到指定起始站')
        if index==len(ordered)-1:raise ValueError('此方向已無下一站，請改選反方向')
        route.origin=dict(ordered[index],arrival=None,stop_enabled=True)
        route.stations=ordered[index+1:]
    route.start_station_id=route.origin.get('station_id') if route.origin else None
    return route


def create_game(data,train='metro',mode='simple',direction='forward',start_station=None):
    route=service_route(data,direction,start_station)
    needs_schedule=direction=='backward' or start_station is not None or any(st['arrival'] is None for st in route.stations)
    if not needs_schedule:Route(data)  # Preserve strict validation of supplied timetables.
    if needs_schedule:
        schedule=automatic_schedule(data,train,data.get('schedule_difficulty','normal'),mode,True,direction,_route=route)
        for st,leg in zip(route.stations,schedule['legs']):st['arrival']=leg['arrival']
    return Game(route,train,mode)


def continue_service(game,action='turnback'):
    if action not in ('turnback','lap'):raise ValueError('不支援的續行方式')
    if not game.done or game.failure or not game.results or game.results[-1].get('missed') or game.results[-1].get('passed'):
        raise ValueError('請先在終點停妥並開門完成班次')
    if game.v>.001:raise ValueError('請先停妥')
    data=game.route.data;direction=game.route.direction
    if action=='lap':
        if not data.get('loop'):raise ValueError('此路線未設定為環線')
        canonical=Route(data,editing=True)
        if not canonical.origin:raise ValueError('環線需要起始站')
        a,b=canonical.point(canonical.origin['center']),canonical.point(canonical.stations[-1]['center'])
        if math.hypot(a['x']-b['x'],a['y']-b['y'])>30:raise ValueError('環線首尾站位置不相接')
        start=None
    else:
        direction='backward' if direction=='forward' else 'forward'
        start=game.route.stations[-1].get('station_id')
    new=create_game(data,game.train_id,game.mode,direction,start)
    new.route.start_time=game.route.start_time+max(game.t,game.release)
    new.results=copy.deepcopy(game.results);new.overspeed=game.overspeed;new.emergencies=game.emergencies
    new.run_number=getattr(game,'run_number',1)+1
    new.message='已準備'+('下一圈' if action=='lap' else '折返班次')+'；停站時間已計入，按 P 發車'
    return new

class Game:
    def __init__(self,route,train='metro',mode='simple'):
        self.route=route; self.train=TRAINS[train]; self.train_id=train
        if mode not in ('simple','classic'):raise ValueError('不支援的遊戲模式')
        self.mode=mode
        if any(st['center']+self.train['length']/2>route.length for st in route.stations):
            raise ValueError('末站停車線超出路線，請延長末段')
        if route.stations[0]['center']+self.train['length']/2<=departure_position(route,self.train):
            raise ValueError('第一個停靠站太靠近起點')
        self.s=departure_position(route,self.train); self.v=0.; self.t=0.; self.notch=0
        self.emergency=False; self.paused=True; self.reverse=False; self.index=0
        self.results=[]; self.overspeed=0.; self.emergencies=0; self.stop_arrival=None
        self.doors=False; self.release=0.; self.done=False; self.failure=None; self.skipped_dwell=False; self.message='按 P 開始；W 加速、S 減速。'

    def target(self):
        if self.index>=len(self.route.stations): return None
        st=self.route.stations[self.index]
        return dict(st,platform=platform_length(st,self.train,self.route,self.mode),stop=st['center']+self.train['length']/2)

    def limit(self):
        rear=max(0,self.s-self.train['length'])
        lo=bisect.bisect_right(self.route.ends,rear);hi=bisect.bisect_right(self.route.ends,self.s)
        samples=[rear,self.s]+[self.route.ends[i]+.000001 for i in range(lo,hi) if self.route.ends[i]<self.s]
        return min(self.route.speed_limit(s,self.train) for s in samples)

    def command(self,cmd):
        if self.done:return
        if cmd=='skip_dwell':
            if not self.doors or self.v>0.001:self.message='請先停妥並開門後再跳過停站時間';return
            if self.release-self.t<=5:self.message='距發車已不足或等於 5 秒，無須跳過';return
            self.t=self.release-5;self.skipped_dwell=True
            self.message='已跳過停站時間｜將於5秒後發車';return
        if cmd=='pause': self.paused=not self.paused
        elif cmd=='power' and not self.emergency and not self.doors: self.notch=min(5,self.notch+1)
        elif cmd=='brake' and not self.emergency: self.notch=max(-8,self.notch-1)
        elif cmd=='coast' and not self.emergency: self.notch=0
        elif cmd=='emergency':
            if not self.emergency: self.emergencies+=1
            self.emergency=True; self.notch=-8; self.message='緊急剎車鎖定；停妥後按 X 解除'
        elif cmd=='release':
            if self.v<0.001: self.emergency=False; self.notch=-1; self.message='緊急剎車已解除'
        elif cmd=='reverse':
            if self.v<0.001 and not self.doors:
                self.reverse=not self.reverse; self.message='倒車微調（限 5 km/h）' if self.reverse else '前進'
        elif cmd=='horn': self.message='鳴笛！'
        elif cmd=='doors': self.station_action()

    def station_action(self):
        if self.paused: self.message='請先按 P 恢復模擬'; return
        if self.v>0.001: self.message='列車仍在移動，不能開門'; return
        if self.doors:
            if self.t<self.release: self.message=f'待發車：還需 {math.ceil(self.release-self.t)} 秒'; return
            self.doors=False; self.skipped_dwell=False; self.message='車門關閉，可以發車'; return
        st=self.target()
        if not st: return
        if not st['stop_enabled']:self.message='本站設定為過站，無須開門';return
        error=self.s-st['stop']
        if abs(error)>self.route.door_margins[self.mode]+0.01: self.message=f'超出開門容許範圍 ±{self.route.door_margins[self.mode]:g} m'; return
        platform_ok=(self.s<=st['center']+st['platform']/2+0.01 and
                     self.s-self.train['length']>=st['center']-st['platform']/2-0.01)
        if not platform_ok: self.message='列車未完整進入月台，無法開門；請調整位置或月台長度'; return
        arrival_time=self.stop_arrival if self.stop_arrival is not None else self.t
        delta=arrival_time-st['arrival']; ontime=-self.route.early<=delta<=self.route.late
        position_score=max(0,100-abs(error)*20)
        timing_score=max(0,100-max(0,abs(delta)- (self.route.early if delta<0 else self.route.late))*2)
        result=dict(station=st['name'],error_cm=round(error*100,2),time_delta=round(delta,2),
                    arrival=round(arrival_time,2),ontime=ontime,missed=False,
                    score=round((position_score+timing_score)/2,1))
        self.results.append(result); self.index+=1; self.doors=True; self.notch=-2; self.reverse=False
        self.release=max(self.t,st['arrival'])+st['dwell'];self.skipped_dwell=False
        self.message=f"{st['name']}：{'超過' if error>=0 else '未達'} {abs(error)*100:.1f} cm，{'準點' if ontime else '早到' if delta<0 else '晚點'}"
        if self.index>=len(self.route.stations): self.done=True; self.message+='；本次行程完成'

    def tick(self,dt):
        if self.paused or self.done: return
        # Fixed/small-step integration is essential for centimetre-scale stop reporting.
        self.t+=dt
        direction=-1 if self.reverse else 1
        if self.v*3.6>self.derailment_limit():
            self.fail('derailed','嚴重超速，列車脫軌');return
        a=self.route.point(max(0,self.s-0.5)); b=self.route.point(min(self.route.length,self.s+0.5))
        grade=(b['z']-a['z'])/max(0.001,b['s']-a['s'])
        brake=self.train['emergency'] if self.emergency else self.train['brake']*max(0,-self.notch)/8
        traction=traction_acceleration(self.train,self.v)*max(0,self.notch)/5
        acceleration=traction-brake-0.012-0.000012*self.v*self.v-9.81*grade*direction
        if self.doors: self.v=0.; return
        if self.v==0 and (self.notch<=0 or self.emergency): return # holding brake
        old=self.v; new=max(0,self.v+acceleration*dt)
        cap=(5 if self.reverse else 1000)/3.6
        new=min(cap,new)
        moving_dt=min(dt,old/-acceleration) if acceleration<0 and new==0 and old>0 else dt
        distance=(old+new)*0.5*moving_dt
        # s is horizontal chainage; v is speed along the 3D grade.
        self.s+=direction*distance/math.sqrt(1+grade*grade); self.v=new
        if new>0: self.stop_arrival=None
        elif old>0: self.stop_arrival=self.t-dt+moving_dt
        if distance>0 and (self.s<=self.train['length'] or self.s>=self.route.length):
            self.s=max(self.train['length'],min(self.route.length,self.s))
            self.fail('buffer_collision','撞到路線端點止擋');return
        if self.v*3.6>self.derailment_limit():
            self.fail('derailed','嚴重超速，列車脫軌');return
        if self.v*3.6>self.limit()+1: self.overspeed+=dt
        st=self.target()
        while st and not st['stop_enabled'] and self.s>=st['stop']:
            crossed=self.t-min(dt,max(0,self.s-st['stop'])/max(.001,self.v))
            delta=crossed-st['arrival'];ontime=-self.route.early<=delta<=self.route.late
            self.results.append(dict(station=st['name'],passed=True,missed=False,error_cm=None,
                time_delta=round(delta,2),arrival=round(crossed,2),ontime=ontime,
                score=max(0,100-max(0,abs(delta)-(self.route.early if delta<0 else self.route.late))*2)))
            self.index+=1;self.message=f"通過 {st['name']}（過站）"
            if self.index>=len(self.route.stations):self.done=True;self.paused=True;self.v=0;self.message+='；本次行程完成'
            st=self.target()
        if st and self.s>st['stop']+max(50,self.route.door_margins[self.mode]+20):
            self.results.append(dict(station=st['name'],missed=True,score=0,error_cm=None,time_delta=None,ontime=False))
            self.index+=1; self.message=f"通過 {st['name']}，漏停扣分"
            if self.index>=len(self.route.stations): self.message+='；前方為路線止擋，請停車'

    def fail(self,kind,message):
        self.failure=dict(kind=kind,speed=round(self.v*3.6,2),position=self.s)
        self.done=True;self.paused=True;self.v=0;self.notch=-8;self.doors=False
        self.message=message+'，遊戲結束；請重新開始'

    def derailment_limit(self):
        rule=self.train['derailment'];limit=self.limit()
        return min(self.train['vmax']*rule['absolute_speed_ratio'],max(limit*rule['limit_ratio'],limit+rule['minimum_excess_kmh']))

    def platform_warnings(self):
        return [f"{st['name']}：月台 {platform_length(st,self.train,self.route,self.mode):g} m 短於列車 {self.train['length']:g} m，無法完整停靠"
                for st in ([self.route.origin] if self.route.origin else [])+self.route.stations
                if platform_length(st,self.train,self.route,self.mode)<self.train['length']]

    def state(self,include_stations=True):
        p=self.route.point(self.s); st=self.target(); limit=self.limit()
        ahead=[]
        previous=self.route.speed_limit(self.s,self.train)
        lo=bisect.bisect_right(self.route.ends,self.s)
        horizon=self.s+5000+self.train['length']
        hi=bisect.bisect_right(self.route.ends,horizon)
        for seg in self.route.segments[lo:hi+1]:
            if self.s<seg['s']<=horizon:
                v=self.route.speed_limit(seg['s']+.001,self.train)
                if v!=previous:
                    ahead.append(dict(distance=seg['s']-self.s,limit=v,kind='speed',release=v>previous))
                previous=v
        ahead=[event for event in ahead if event['distance']<=5000]
        distance=st['stop']-self.s if st else None
        return dict(start_station_id=getattr(self.route,'start_station_id',None),service_start_time=self.route.start_time,run_number=getattr(self,'run_number',1),can_continue=self.done and not self.failure and bool(self.results) and not self.results[-1].get('missed') and not self.results[-1].get('passed'),is_loop=bool(self.route.data.get('loop')),s=self.s,speed=self.v*3.6,clock=self.route.start_time+self.t,elapsed=self.t,
            notch=self.notch,emergency=self.emergency,paused=self.paused,reverse=self.reverse,
            game_mode=self.mode,service_direction=self.route.direction,
            door_margin=self.route.door_margins[self.mode],platform_warnings=self.platform_warnings(),
            service_stations=[dict(st,platform=platform_length(st,self.train,self.route,self.mode)) for st in (([self.route.origin] if self.route.origin else [])+self.route.stations if include_stations else [])],
            point=p,target=st,distance=distance,limit=limit,restrictions=ahead[:20],global_limit=self.route.global_limit,
            eta=(self.route.start_time+self.t+max(0,distance)/self.v) if st and self.v>.2 else None,
            schedule=self.route.start_time+st['arrival'] if st else None,
            brake_distance=self.v*self.v/(2*self.train['brake']),
            doors=self.doors,wait=max(0,self.release-self.t) if self.doors else 0,
            results=self.results,overspeed=self.overspeed,emergencies=self.emergencies,
            score=0 if self.failure else max(0,round(sum(r['score'] for r in self.results)/max(1,len(self.results))-self.overspeed*.2-self.emergencies*5,1)),
            done=self.done,failure=self.failure,derailment_limit=self.derailment_limit(),
            skipped_dwell=self.skipped_dwell,message=self.message,train=self.train)

def from_coordinates(coords, radius=300, name='匯入路線'):
    """[lon,lat] polyline -> tangent straight/circular arc alignment (local projection)."""
    if not 2<=len(coords)<=10000: raise ValueError('需 2–10000 個路線點')
    radius=number(radius,15,50000)
    lon,lat=coords[0][:2]; lon=number(lon,-180,180); lat=number(lat,-85,85)
    points=[((number(p[0],-180,180)-lon)*111320*math.cos(math.radians(lat)),
             (number(p[1],-85,85)-lat)*111320) for p in coords]
    lengths=[]; headings=[]
    for a,b in zip(points,points[1:]):
        length=math.hypot(b[0]-a[0],b[1]-a[1])
        if length<2: raise ValueError('路線點相距至少 2 m；請先簡化密集 GPS 點')
        lengths.append(length); headings.append(math.atan2(b[0]-a[0],b[1]-a[1]))
    trims=[0.]*len(points); turns=[0.]*len(points)
    for i in range(1,len(points)-1):
        turn=(headings[i]-headings[i-1]+math.pi)%(2*math.pi)-math.pi
        if abs(turn)>math.radians(170): raise ValueError('轉角過大，請修改控制點')
        turns[i]=turn; trims[i]=radius*math.tan(abs(turn)/2)
    segments=[]
    for i,length in enumerate(lengths):
        line=length-trims[i]-trims[i+1]
        if line<1: raise ValueError('指定 R 太大，圓弧無法放入控制點之間；請減小 R 或移動控制點')
        segments.append(dict(length=line,radius=0,mode='ground',offset=0,limit=None))
        turn=turns[i+1]
        if abs(turn)*radius>=1:
            segments.append(dict(length=abs(turn)*radius,radius=math.copysign(radius,turn),mode='ground',offset=0,limit=None))
        elif abs(turn)>1e-8:
            raise ValueError('小轉角產生不足 1 m 的圓弧，請簡化控制點')
    total=sum(s['length'] for s in segments)
    if total<700: raise ValueError('原型路線至少需 700 m，供長編組起步與停靠')
    return dict(name=name,lat=lat,lon=lon,heading=math.degrees(headings[0]),start_time=28800,early=30,late=30,
                terrain=[[0,0],[total,0]],segments=segments,
                stations=[dict(name='終點站',center=total-250,platform=450,arrival=max(120,round(total/12)),dwell=20)])

def automatic_schedule(data, train_id='metro', difficulty='normal', mode='simple', recompute=False, direction='forward',_route=None):
    """One speed envelope across all stations; passing stations never reset speed or dwell."""
    margins={'normal':(.25,20),'hard':(.12,8),'precise':(.03,2)}
    if difficulty not in margins:raise ValueError('不支援的難度')
    if mode not in ('simple','classic'):raise ValueError('不支援的遊戲模式')
    if direction not in ('forward','backward'):raise ValueError('不支援的行車方向')
    route=_route if _route is not None else Route(data,editing=True)
    if route.warnings: raise ValueError(route.warnings[0])
    if direction=='backward' and _route is None:route=ReverseRoute(route)
    train=TRAINS[train_id];result=copy.deepcopy(data)
    result['schedule_difficulty']=difficulty
    result['stations'].sort(key=lambda st:float(st['center']))
    stations=route.stations
    if not stations:raise ValueError('請先新增停靠站')
    start=departure_position(route,train)
    targets=[st['center']+train['length']/2 for st in stations]
    if targets[0]<=start or targets[-1]>route.length:raise ValueError('站點停車線必須在起始月台之後且不超出路線')
    n=math.ceil((targets[-1]-start)/5)
    if n>200000:raise ValueError('路線過長，請分段建立班次')
    xs={start+(targets[-1]-start)*i/n for i in range(n+1)};xs.update(targets)
    for seg in route.segments:
        for x in (seg['s'],seg['s']+train['length']):
            if start<x<targets[-1]:xs.add(x)
    xs=sorted(xs);indices={x:i for i,x in enumerate(xs)}
    def occupied_limit(s):
        rear=max(0,s-train['length'])
        lo=bisect.bisect_right(route.ends,rear);hi=bisect.bisect_right(route.ends,s)
        positions=[rear,s]+[route.ends[i]+.000001 for i in range(lo,hi) if route.ends[i]<s]
        return min(route.speed_limit(x,train) for x in positions)/3.6
    speeds=[occupied_limit(x) for x in xs]
    for st,target in zip(stations,targets):
        if st['stop_enabled']:speeds[indices[target]]=0
    grades=[];distances=[]
    for a,b in zip(xs,xs[1:]):
        grade=(route.point(b)['z']-route.point(a)['z'])/(b-a)
        grades.append(grade);distances.append((b-a)*math.sqrt(1+grade*grade))
    for i in range(len(xs)-2,-1,-1):
        decel=train['brake']+9.81*grades[i]+.012
        if decel<=0:raise ValueError('下坡超過常用制動能力，請加長緩坡')
        speeds[i]=min(speeds[i],math.sqrt(speeds[i+1]**2+2*decel*distances[i]))
    speeds[0]=0;elapsed=[0.]
    for i,ds in enumerate(distances):
        v=speeds[i];accel=traction_acceleration(train,v)-.012-.000012*v*v-9.81*grades[i]
        reachable=v*v+2*accel*ds
        if reachable<=0 and v<.01:raise ValueError('上坡超過起步牽引能力，請加長緩坡')
        speeds[i+1]=min(speeds[i+1],math.sqrt(max(0,reachable)))
        if v+speeds[i+1]<=1e-8:raise ValueError('站點過近或限速過低，無法估算行車時間')
        elapsed.append(elapsed[-1]+2*ds/(v+speeds[i+1]))
    departure=0.;last_elapsed=0.;legs=[];warnings=[];ratio,extra=margins[difficulty]
    for index,(st,target) in enumerate(zip(stations,targets)):
        if platform_length(st,train,route,mode)<train['length']:
            warnings.append(f"{st['name']}：月台短於列車，停站時無法開門")
        duration=elapsed[indices[target]]-last_elapsed
        recommended=max(math.floor(departure)+1,math.ceil(departure+duration*(1+ratio)+(extra if st['stop_enabled'] else 0)))
        manual=not recompute and direction=='forward' and st['arrival'] is not None
        arrival=st['arrival'] if manual else recommended
        if arrival<departure+duration:warnings.append(f"{st['name']}：手動時刻早於理論可達時間，已保留")
        if legs and arrival<=legs[-1]['arrival']:raise ValueError('手動抵達時間與前站衝突；請修改或清空後重算')
        if direction=='forward' and _route is None:result['stations'][index]['arrival']=arrival
        legs.append(dict(station=st['name'],minimum_seconds=round(duration,1),arrival=arrival,manual=manual,
                         stop_enabled=st['stop_enabled'],pass_speed_kmh=round(speeds[indices[target]]*3.6,2)))
        departure=arrival+(st['dwell'] if st['stop_enabled'] else 0);last_elapsed=elapsed[indices[target]]
    return dict(route=result,legs=legs,warnings=warnings,direction=direction)

def split_route(data,position):
    route=Route(data,editing=True);s=number(position,0,route.length)
    if len(route.segments)>=MAX_SEGMENTS:raise ValueError('線段已達 20000 段上限')
    index=min(len(route.segments)-1,bisect.bisect_right(route.ends,s));seg=route.segments[index];d=s-seg['s']
    if d<1 or seg['length']-d<1:raise ValueError('剪切後兩段長度均須至少 1 m，請避開端點')
    result=copy.deepcopy(data);left=copy.deepcopy(data['segments'][index]);right=copy.deepcopy(left)
    left['length']=d;right['length']=seg['length']-d
    right['heading']=(math.degrees(route._xy(seg,d)[2])+180)%360-180
    if seg['mode'] in ('absolute','transition','smooth'):
        left['z_start']=seg['z0'];left['z_end']=route._height(seg,d)
        right['z_start']=left['z_end'];right['z_end']=seg['z1']
        if seg.get('height_points'):
            t=d/seg['length'];z=left['z_end'];pts=seg['height_points']
            left['height_points']=[[u/t,h] for u,h in pts if u<t]+[[1,z]]
            right['height_points']=[[0,z]]+[[(u-t)/(1-t),h] for u,h in pts if u>t]
        if seg['mode']=='smooth':
            t=d/seg['length'];L=seg['length']
            slope=((6*t*t-6*t)*seg['z0']+(-6*t*t+6*t)*seg['z1'])/L+(3*t*t-4*t+1)*seg['grade_start']+(3*t*t-2*t)*seg['grade_end']
            left.update(grade_start=seg['grade_start'],grade_end=slope)
            right.update(grade_start=slope,grade_end=seg['grade_end'])
    result['segments'][index:index+1]=[left,right]
    Route(result,editing=True)
    return dict(route=result,index=index,position=s)
