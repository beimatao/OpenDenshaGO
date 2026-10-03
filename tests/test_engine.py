import copy, json, math, sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from engine import Route,Game,TRAINS,from_coordinates,automatic_schedule
BASE=Path(__file__).resolve().parents[1]

def route(): return Route(json.loads((BASE/'routes/demo.json').read_text(encoding='utf-8')))
class RailTests(unittest.TestCase):
    def test_demo_continuity_and_tunnel(self):
        r=route()
        for end in r.ends[:-1]:
            a,b=r.point(end-1e-5),r.point(end+1e-5)
            self.assertLess(math.hypot(a['x']-b['x'],a['y']-b['y']),.001)
            self.assertLess(abs(a['z']-b['z']),.001)
            self.assertLess(abs(a['h']-b['h']),.001)
        self.assertTrue(r.point(2900)['tunnel'])
        self.assertTrue(r.point(4000)['tunnel'])
        self.assertFalse(r.point(2200)['tunnel'])
    def test_circle_exact_radius(self):
        d=route().data;d['heading']=0;d['segments']=[dict(length=1000,radius=1000,mode='ground',offset=0,limit=120)];d['stations']=[dict(name='A',center=700,platform=450,arrival=120)]
        r=Route(d); p=r.point(500)
        self.assertAlmostEqual(math.hypot(p['x']-1000,p['y']),1000)
        self.assertAlmostEqual(r.speed_limit(500,TRAINS['tra']),90)
    def test_curve_fillet_end_and_tangency(self):
        d=from_coordinates([[0,0],[0,.02],[.02,.02]],300)
        r=Route(d);end=r.point(r.length)
        self.assertAlmostEqual(end['x'],.02*111320,places=6)
        self.assertAlmostEqual(end['y'],.02*111320,places=6)
        self.assertAlmostEqual(r.segments[1]['radius'],300)
        for s in r.ends[:-1]: self.assertLess(abs(r.point(s-1e-6)['h']-r.point(s+1e-6)['h']),1e-6)
    def test_fillet_reject_infeasible(self):
        with self.assertRaises(ValueError):from_coordinates([[0,0],[0,.001],[.001,.001]],1000)
    def test_bad_height_rejected(self):
        d=route().data;d['segments'][1]['offset']=-20
        with self.assertRaises(ValueError):Route(d)
    def test_nonfinite_rejected(self):
        d=route().data;d['segments'][0]['length']=float('nan')
        with self.assertRaises(ValueError):Route(d)
    def test_throttle_brake_pause_emergency(self):
        g=Game(route());g.command('power');g.tick(1);self.assertEqual(g.v,0)
        g.paused=False
        for _ in range(4):g.command('power')
        for _ in range(1000):g.tick(.01)
        self.assertGreater(g.v,8)
        g.command('emergency');g.command('power');self.assertEqual(g.notch,-8)
        for _ in range(2000):g.tick(.01)
        self.assertEqual(g.v,0);g.command('release');self.assertFalse(g.emergency)
    def test_stop_cm_and_schedule(self):
        g=Game(route());g.paused=False;g.s=g.target()['stop']-.1234;g.t=120
        g.command('doors');r=g.results[0]
        self.assertAlmostEqual(r['error_cm'],-12.34);self.assertTrue(r['ontime']);self.assertTrue(g.doors)
        g.command('power');self.assertEqual(g.notch,-2)
        g.command('doors');self.assertTrue(g.doors)
        for _ in range(2001):g.tick(.01)
        g.command('doors');self.assertFalse(g.doors)
    def test_early_120_seconds_penalty(self):
        g=Game(route());g.paused=False;g.s=g.target()['stop'];g.t=0;g.command('doors')
        self.assertFalse(g.results[0]['ontime']);self.assertLess(g.results[0]['score'],100)
        self.assertEqual(g.release,140)
    def test_platform_too_short(self):
        d=route().data;d['stations'][0]['platform']=100
        g=Game(Route(d));g.paused=False;g.s=g.target()['stop'];g.command('doors');self.assertFalse(g.doors);self.assertFalse(g.results)
    def test_cannot_open_moving(self):
        g=Game(route());g.paused=False;g.s=g.target()['stop'];g.v=.5;g.command('doors');self.assertFalse(g.results)
    def test_reverse_adjustment(self):
        g=Game(route());g.paused=False;g.s=1200;g.command('reverse');g.notch=5
        for _ in range(1000):g.tick(.01)
        self.assertLess(g.s,1200);self.assertLessEqual(g.v,5/3.6)
    def test_body_limit_not_just_front(self):
        g=Game(route());g.s=1870
        self.assertLess(g.limit(),g.route.speed_limit(g.s,g.train))
    def test_missed_stop(self):
        g=Game(route());g.paused=False;g.s=g.target()['stop']+51;g.v=1;g.tick(.01)
        self.assertTrue(g.results[0]['missed'])
    def test_stop_time_is_not_door_time(self):
        g=Game(route());g.paused=False;g.s=g.target()['stop'];g.t=120
        g.v=.005;g.notch=-8;g.tick(.01)
        for _ in range(6000):g.tick(.01)
        g.command('doors')
        self.assertTrue(g.results[0]['ontime'])
        self.assertLess(abs(g.results[0]['time_delta']),.01)

    def test_global_auto_limit_five_kmh(self):
        d=route().data;d['global_limit']=93
        for seg in d['segments']:seg['limit']=None
        r=Route(d)
        self.assertEqual(r.speed_limit(100,TRAINS['hsr']),90)
        self.assertEqual(r.speed_limit(1500,TRAINS['hsr']),90)
        self.assertEqual(r.speed_limit(1500,TRAINS['metro']),80)
        d['global_limit']=320;r=Route(d)
        self.assertEqual(r.speed_limit(1500,TRAINS['hsr']),90)
        d['segments'][1]['limit']=62;r=Route(d)
        self.assertEqual(r.speed_limit(1500,TRAINS['hsr']),60)
    def test_blank_limit_and_preview_without_stations(self):
        d=route().data;d['global_limit']=320;d['stations']=[];d['segments'][0]['limit']=''
        r=Route(d,editing=True)
        self.assertEqual(r.speed_limit(100,TRAINS['tra']),130)
        with self.assertRaises(ValueError):Route(d)
    def test_explicit_heading_endpoint(self):
        d=route().data;d['segments'][0]['heading']=0;d['segments'][1]['heading']=90
        r=Route(d)
        self.assertAlmostEqual(r.point(100)['x'],0)
        a=r.point(1400);self.assertAlmostEqual(a['h'],math.pi/2)
        self.assertAlmostEqual(a['y'],1400)

    def test_smooth_grade_flat_endpoints(self):
        d=route().data;d['segments']=[dict(length=2000,radius=0,mode='smooth',z_end=-8)];d['stations']=[dict(name='B',center=1500,platform=450,arrival=200)]
        r=Route(d)
        self.assertAlmostEqual(r.point(0)['z'],12)
        self.assertAlmostEqual(r.point(1000)['z'],2)
        self.assertAlmostEqual(r.point(2000)['z'],-8)
        self.assertLess(abs(r.point(.01)['z']-12),1e-6)
    def test_schedule_difficulties_and_manual_preservation(self):
        d=route().data
        for station in d['stations']:station['arrival']=None
        outputs=[automatic_schedule(d,'metro',level) for level in ('normal','hard','precise')]
        for i in range(3):
            self.assertGreater(outputs[0]['route']['stations'][i]['arrival'],outputs[1]['route']['stations'][i]['arrival'])
            self.assertGreater(outputs[1]['route']['stations'][i]['arrival'],outputs[2]['route']['stations'][i]['arrival'])
        d['stations'][0]['arrival']=300
        out=automatic_schedule(d,'metro','normal')['route']
        self.assertEqual(out['stations'][0]['arrival'],300)
        self.assertGreater(out['stations'][1]['arrival'],320)
        Route(out)

    def test_all_trains(self):
        for train in TRAINS: self.assertGreater(Game(route(),train).target()['stop'],1150)
    def test_stopping_substep_distance(self):
        g=Game(route());g.paused=False;g.s=500;g.v=.005;g.notch=-8;g.tick(.01)
        self.assertEqual(g.v,0);self.assertGreater(g.s,500);self.assertLess(g.s-500,.00005)
if __name__=='__main__':unittest.main()
