"""Conservative endpoint-anchored analytic line/arc simplification."""
import bisect,copy,math
from engine import Route,number,MAX_SEGMENTS,MAX_TERRAIN
from terrain_processing import LinearProfile


def angle(a):return (a+math.pi)%(2*math.pi)-math.pi

def heading(h):return math.degrees(angle(h))


def biarc(A,B,h0,h1):
    vx,vy=B[0]-A[0],B[1]-A[1];t0=(math.sin(h0),math.cos(h0));t1=(math.sin(h1),math.cos(h1))
    aa=2*(1-t0[0]*t1[0]-t0[1]*t1[1]);bb=2*(vx*(t0[0]+t1[0])+vy*(t0[1]+t1[1]));cc=-(vx*vx+vy*vy)
    if abs(aa)<1e-10:
        if abs(bb)<1e-10:return None
        d=-cc/bb
    else:d=(-bb+math.sqrt(max(0,bb*bb-4*aa*cc)))/(2*aa)
    if d<=0:return None
    M=((A[0]+B[0]+d*(t0[0]-t1[0]))/2,(A[1]+B[1]+d*(t0[1]-t1[1]))/2)
    def one(a,b,h):
        dx,dy=b[0]-a[0],b[1]-a[1];chord=math.hypot(dx,dy);right=dx*math.cos(h)-dy*math.sin(h);forward=dx*math.sin(h)+dy*math.cos(h)
        if abs(right)<1e-8:
            if forward<1:return None
            return dict(x=a[0],y=a[1],h=h,radius=0,length=chord)
        r=chord*chord/(2*right);turn=2*math.atan2(right,forward)
        if abs(r)<15 or abs(r)>1e12 or abs(turn)>math.pi or abs(r*turn)<1:return None
        return dict(x=a[0],y=a[1],h=h,radius=r,length=abs(r*turn))
    first=one(A,M,h0);rev=one(B,M,h1+math.pi)
    if not first or not rev:return None
    end=Route._xy(rev,rev['length']);second=dict(x=M[0],y=M[1],h=end[2]+math.pi,radius=-rev['radius'],length=rev['length'])
    if abs(angle(Route._xy(first,first['length'])[2]-second['h']))>1e-6:return None
    return [first,second]


def simplify_route(data,tolerance=5):
    old=Route(data,editing=True);tolerance=number(tolerance,1,500)
    relative={'ground','elevated','underground','absolute'}
    anchors=sorted(set([st['center'] for st in old.stations]+([old.origin['center']] if old.origin else [])))
    fragments=[]
    for i,seg in enumerate(old.segments):
        raw=copy.deepcopy(data['segments'][i]);cuts=[seg['s']]
        if seg['mode'] in relative:cuts += [s for s in anchors if seg['s']+1<s<seg['end']-1]
        cuts.append(seg['end'])
        for a,b in zip(cuts,cuts[1:]):
            h=old._xy(seg,a-seg['s'])[2]
            item=dict(raw,length=b-a,heading=heading(h))
            if seg['mode']=='absolute':
                item['z_start']=old._height(seg,a-seg['s']);item['z_end']=old._height(seg,b-seg['s'])
                if raw.get('height_points'):
                    knots=[a]+[seg['s']+t*seg['length'] for t,z in raw['height_points'] if a<seg['s']+t*seg['length']<b]+[b]
                    item['height_points']=[[0 if k==0 else 1 if k==len(knots)-1 else (v-a)/(b-a),old._height(seg,v-seg['s'])] for k,v in enumerate(knots)]
            # Only relative segments with identical operational settings are merged.
            attrs={k:v for k,v in raw.items() if k not in ('length','radius','heading','z_start','z_end','height_points','grade_start','grade_end')}
            attrs.update(mode=seg['mode'],offset=seg['offset'],limit=seg['limit'])
            fragments.append(dict(a=a,b=b,raw=item,key=attrs,protected=seg['mode'] not in relative or any(a<s<b for s in anchors),seg=seg))
    anchor_set=set(anchors)
    def point(s):
        p=old.point(s);return p['x'],p['y']
    def build(a,b):
        A=point(a);B=point(b);dx,dy=B[0]-A[0],B[1]-A[1];chord=math.hypot(dx,dy)
        if chord<1:return []
        line=dict(x=A[0],y=A[1],h=math.atan2(dx,dy),radius=0,length=chord)
        candidates=[line]
        M=point((a+b)/2);ux,uy=M[0]-A[0],M[1]-A[1];det=2*(ux*dy-uy*dx)
        if abs(det)>1e-8:
            u2=ux*ux+uy*uy;v2=dx*dx+dy*dy
            cx=(u2*dy-v2*uy)/det;cy=(ux*v2-dx*u2)/det;r=math.hypot(cx,cy)
            turn=angle(math.atan2(B[0]-A[0]-cx,B[1]-A[1]-cy)-math.atan2(-cx,-cy))
            if 15<=r<=1e12 and abs(turn)>1e-9:
                signed=math.copysign(r,turn);h=math.atan2(dx,dy)-turn/2
                candidates.append(dict(x=A[0],y=A[1],h=h,radius=signed,length=r*abs(turn)))
        return [[c] for c in candidates]
    def fit(i,j):
        a,b=fragments[i]['a'],fragments[j]['b'];span=b-a
        start_h=old._xy(fragments[i]['seg'],a-fragments[i]['seg']['s'])[2]
        end_h=old._xy(fragments[j]['seg'],b-fragments[j]['seg']['s'])[2]
        candidates=build(a,b)
        pair=biarc(point(a),point(b),start_h,end_h)
        if pair:candidates.append(pair)
        # Single arcs retain near-tangency; biarcs preserve exact end tangents.
        for pieces in candidates:
            if len(pieces)>=j-i+1:continue
            c=pieces[0];last=pieces[-1];length=sum(v['length'] for v in pieces)
            end_c=last['h']+(last['length']/last['radius'] if last['radius'] else 0)
            if abs(angle(c['h']-start_h))>math.radians(.5) or abs(angle(end_c-end_h))>math.radians(.5):continue
            if any(not 1<=v['length']<=100000 or (v['radius'] and v['length']/abs(v['radius'])>math.pi) for v in pieces):continue
            # Bound between-sample error using speed (arc-length parametrization) Lipschitz bound.
            step=min(10,tolerance/(2*(1+length/span)))
            count=math.ceil(span/step)
            if count>100000:continue
            positions={a+span*k/count for k in range(count+1)}
            positions.update(fragments[k]['b'] for k in range(i,j))
            max_error=0
            for s in sorted(positions):
                x,y=point(s);d=(s-a)/span*length
                piece=pieces[0]
                if len(pieces)==2 and d>piece['length']:d-=piece['length'];piece=pieces[1]
                xx,yy,_=Route._xy(piece,d)
                error=math.hypot(x-xx,y-yy);max_error=max(max_error,error)
                if error>tolerance*.74:break
            else:return pieces,max_error+tolerance*.25
        return None
    accepted=[];i=0;merged=0;max_bound=0
    while i<len(fragments):
        best=None;best_j=i;current=fragments[i]
        if not current['protected']:
            end=i
            while end+1<len(fragments) and end-i<511:
                if fragments[end]['b'] in anchor_set or fragments[end+1]['protected'] or fragments[end+1]['key']!=current['key']:break
                if abs(old._height(fragments[end]['seg'],fragments[end]['b']-fragments[end]['seg']['s'])-old._height(fragments[end+1]['seg'],fragments[end+1]['a']-fragments[end+1]['seg']['s']))>.05:break
                end+=1
            # Try the largest span first, then shorten. Avoid quadratic trials on very fragmented data.
            choices=[];n=end-i+1
            while n>=2:
                choices.append(i+n-1);n=n//2
            for j in choices:
                result=fit(i,j)
                if result:best=result;best_j=j;break
        if best:
            pieces,bound=best;a=current['a'];b=fragments[best_j]['b'];span=b-a;length=sum(c['length'] for c in pieces);done=0
            for ci,c in enumerate(pieces):
                aa=a+span*done/length;done+=c['length'];bb=b if ci==len(pieces)-1 else a+span*done/length
                raw=dict(current['raw'],length=c['length'],radius=c['radius'],heading=heading(c['h']))
                if raw.get('mode')=='absolute':
                    knots={aa,bb}
                    for k in range(i,best_j+1):
                        f=fragments[k];seg=f['seg']
                        for v in [f['a'],f['b']]+[seg['s']+t*seg['length'] for t,z in seg.get('height_points',[])]:
                            if aa<v<bb:knots.add(v)
                    knots=sorted(knots)
                    # Use the segment being merged for boundary values (not the following mode).
                    def z_at(v):
                        k=min(best_j,next((k for k in range(i,best_j+1) if v<=fragments[k]['b']),best_j))
                        seg=fragments[k]['seg'];return old._height(seg,v-seg['s'])
                    raw['height_points']=[[0 if k==0 else 1 if k==len(knots)-1 else (v-aa)/(bb-aa),z_at(v)] for k,v in enumerate(knots)]
                    raw['z_start']=raw['height_points'][0][1];raw['z_end']=raw['height_points'][-1][1]
                accepted.append((aa,bb,raw))
            merged+=best_j-i+1-len(pieces);max_bound=max(max_bound,bound);i=best_j+1
        else:accepted.append((current['a'],current['b'],current['raw']));i+=1
    # Do not replace the route with an output that only introduces station splits.
    if len(accepted)>=len(old.segments):
        return dict(route=copy.deepcopy(data),changed=False,stats=dict(before=len(old.segments),after=len(old.segments),old_length=old.length,new_length=old.length,max_deviation=0,station_shift=0),warnings=['此容許誤差下沒有可安全減少的路段；可提高誤差，或保留原線形。'])
    if len(accepted)>MAX_SEGMENTS:raise ValueError('簡化後路段數超出限制')
    starts=[];new_ends=[];total=0
    for a,b,raw in accepted:starts.append(total);total+=raw['length'];new_ends.append(total)
    ends=[b for a,b,raw in accepted]
    def remap(s):
        if s>old.length:return s+total-old.length
        i=min(len(ends)-1,bisect.bisect_right(ends,s));a,b,raw=accepted[i]
        return starts[i]+(s-a)/(b-a)*raw['length']
    out=copy.deepcopy(data);out['segments']=[raw for a,b,raw in accepted];out['heading']=out['segments'][0]['heading']
    for st in out['stations']:st['center']=remap(float(st['center']));st['arrival']=None
    if out.get('start_station'):out['start_station']['center']=remap(float(out['start_station']['center']))
    for field in ('terrain','terrain_original'):
        if field in out:
            profile=LinearProfile(out[field]);knots=sorted(set([float(s) for s,z in out[field]]+[a for a,b,raw in accepted]+[old.length]))
            if len(knots)>MAX_TERRAIN:raise ValueError('地形對應點超過 200000，請先減少地形採樣點')
            mapped=[]
            for s in knots:
                q=[remap(s),profile.value(max(profile.x[0],min(profile.x[-1],s)))]
                if mapped and q[0]-mapped[-1][0]<1e-8:mapped[-1]=q
                else:mapped.append(q)
            out[field]=mapped
    new=Route(out,editing=True)
    errors=[]
    for a,b in zip(old.stations,new.stations):
        p,q=old.point(a['center']),new.point(b['center']);errors.append(math.hypot(p['x']-q['x'],p['y']-q['y']))
    if old.origin:
        p,q=old.point(old.origin['center']),new.point(new.origin['center']);errors.append(math.hypot(p['x']-q['x'],p['y']-q['y']))
    if max(errors,default=0)>.001:raise ValueError('站點位置檢查未通過，未套用簡化；請降低容許誤差')
    # Reject newly introduced height discontinuities; existing draft warnings are allowed.
    if len(new.warnings)>len(old.warnings):raise ValueError('簡化造成新的高程斷點，未套用')
    return dict(route=out,changed=True,stats=dict(before=len(old.segments),after=len(new.segments),old_length=old.length,new_length=new.length,max_deviation=max_bound,station_shift=max(errors,default=0)),warnings=new.warnings)
