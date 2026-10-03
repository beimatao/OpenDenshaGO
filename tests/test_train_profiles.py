import copy,json,subprocess,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from engine import TRAINS,Route,Game,automatic_schedule
ROOT=Path(__file__).resolve().parents[1]
class TrainProfiles(unittest.TestCase):
    def test_selected_formations(self):
        self.assertEqual([t['cars'] for t in TRAINS.values()],[6,8,12,16])
        self.assertEqual([t['vmax'] for t in TRAINS.values()],[80,130,300,320])
    def test_tilt_changes_limit_but_obeys_caps(self):
        d=json.loads((ROOT/'routes/demo.json').read_text());d['segments']=[dict(length=2000,radius=1000,mode='ground',offset=0,limit=None)];d['stations']=[];d['global_limit']=320
        r=Route(d,editing=True);t=copy.deepcopy(TRAINS['shinkansen']);on=r.speed_limit(10,t)
        t['curve']['tilt_enabled']=False
        self.assertGreater(on,r.speed_limit(10,t))
        r.global_limit=87
        self.assertEqual(r.speed_limit(10,t),85)
    def test_frontend_backend_limits_agree(self):
        d=json.loads((ROOT/'routes/demo.json').read_text());d['stations']=[]
        cases=[];expected=[]
        for t in TRAINS.values():
            for radius in (0,15,300,-1000,4000,10000):
                for cap in (None,55):
                    seg=dict(length=10,radius=radius,mode='ground',offset=0,limit=cap)
                    route=dict(d,segments=[seg]);cases.append([route,seg,t]);expected.append(Route(route,editing=True).speed_limit(1,t))
        script="const G=require('./static/geometry.js');let s='';process.stdin.on('data',x=>s+=x);process.stdin.on('end',()=>console.log(JSON.stringify(JSON.parse(s).map(x=>G.limit(...x)))));"
        actual=json.loads(subprocess.check_output(['node','-e',script],input=json.dumps(cases).encode(),cwd=ROOT))
        self.assertEqual(actual,expected)
    def test_all_train_schedules_and_braking(self):
        d=json.loads((ROOT/'routes/demo.json').read_text())
        d['terrain']=[[0,0],[100000,0]]
        for seg in d['segments']:seg.update(mode='ground',offset=0)
        for st in d['stations']:st['arrival']=None
        for key,t in TRAINS.items():
            result=automatic_schedule(d,key)
            self.assertTrue(all(leg['minimum_seconds']>0 for leg in result['legs']))
            r=Route(result['route']);service=Game(r,key);emergency=Game(r,key)
            for g in (service,emergency):g.paused=False;g.v=10;g.notch=-8
            emergency.command('emergency');service.tick(.1);emergency.tick(.1)
            self.assertLess(emergency.v,service.v)
