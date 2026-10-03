import copy,json,math,unittest
from pathlib import Path
from engine import Route,Game,TRAINS,ReverseRoute,create_game,continue_service,automatic_schedule
from route_simplify import simplify_route
ROOT=Path(__file__).resolve().parents[1]
def fixture():
 return dict(lat=25,lon=121,terrain=[[0,0],[5000,0]],start_station=dict(name='S',center=300),stations=[dict(name='A',center=1000,arrival=100),dict(name='B',center=2000,arrival=200),dict(name='C',center=3500,arrival=350)],segments=[dict(length=4000,mode='ground')])
class V016(unittest.TestCase):
 def test_curve_group_entry_and_release(self):
  d=fixture();d['segments']=[dict(length=1000,mode='ground'),dict(length=29,radius=150,mode='ground'),dict(length=20,radius=90,mode='ground'),dict(length=2951,mode='ground')]
  r=Route(d);t=TRAINS['metro'];self.assertGreater(r.raw_speed_limit(1001,t),r.raw_speed_limit(1030,t));self.assertEqual(r.speed_limit(1000,t),r.raw_speed_limit(1030,t))
  g=Game(r);g.s=900;events=g.state()['restrictions'];self.assertEqual(events[0]['distance'],100);self.assertFalse(events[0]['release']);self.assertEqual(len(events),2)
  g.s=1049+t['length']-.001;self.assertEqual(g.limit(),r.speed_limit(1000,t));g.s+=.002;self.assertEqual(g.limit(),80)
 def test_opposite_curves_separate(self):
  d=fixture();d['segments']=[dict(length=1000,mode='ground'),dict(length=40,radius=150,mode='ground'),dict(length=40,radius=-90,mode='ground'),dict(length=2920,mode='ground')]
  r=Route(d);t=TRAINS['metro'];self.assertGreater(r.speed_limit(1000,t),r.speed_limit(1040,t))
 def test_short_rise_previous_low_for_real_limit(self):
  d=fixture();d['segments']=[dict(length=1000,mode='ground',limit=30),dict(length=100,mode='ground',limit=65),dict(length=2900,mode='ground',limit=25)]
  r=Route(d);t=TRAINS['metro'];self.assertEqual(r.speed_limit(1050,t),30);self.assertEqual(r.speed_limit(1100,t),25)
 def test_start_middle_both_directions_and_clock(self):
  d=fixture()
  for direction,target in [('forward','C'),('backward','A')]:
   g=create_game(d,direction=direction,start_station=1);self.assertEqual(g.route.origin['name'],'B');self.assertEqual(g.target()['name'],target);self.assertEqual(g.t,0);self.assertGreater(g.target()['arrival'],0)
   p=g.route.point(g.s-g.train['length']/2);q=Route(d).point(2000)
   self.assertAlmostEqual(p['x'],q['x']);self.assertAlmostEqual(p['y'],q['y']);self.assertEqual(g.state()['start_station_id'],1)
  self.assertEqual(d,fixture())
 def test_start_terminal_rejected(self):
  with self.assertRaises(ValueError):create_game(fixture(),start_station=2)
  with self.assertRaises(ValueError):create_game(fixture(),start_station=100)
 def test_turnback_preserves_center_time_and_results(self):
  g=create_game(fixture());g.index=2;g.s=g.target()['stop'];g.paused=False;g.t=350;g.station_action();self.assertTrue(g.done)
  n=continue_service(g);self.assertEqual(n.route.direction,'backward');self.assertEqual(n.target()['name'],'B');self.assertEqual(n.results,g.results);self.assertEqual(n.route.start_time,g.route.start_time+g.release)
  p=g.route.point(g.s-g.train['length']/2);q=n.route.point(n.s-n.train['length']/2);self.assertAlmostEqual(p['y'],q['y']);self.assertTrue(n.paused)
 def test_continue_guard(self):
  with self.assertRaises(ValueError):continue_service(create_game(fixture()))
 def test_biarc_simplification_station_and_absolute_height(self):
  d=json.loads(next((ROOT/'routes/osm').glob('*板南*')).read_text());d['terrain']=[[0,10],[10000,100],[40000,20]]
  r=Route(d,editing=True)
  for seg,raw in zip(r.segments,d['segments']):raw.update(mode='absolute',z_start=r._height(seg,0),z_end=r._height(seg,seg['length']))
  out=simplify_route(d,20);self.assertTrue(out['changed']);self.assertLess(out['stats']['after'],out['stats']['before']/2);self.assertLess(out['stats']['station_shift'],.001)
  new=Route(out['route'],editing=True);self.assertFalse(new.warnings)
  for a,b in zip(Route(d,editing=True).stations,new.stations):self.assertAlmostEqual(Route(d,editing=True).point(a['center'])['z'],new.point(b['center'])['z'],places=6)
 def test_tolerance_500(self):
  out=simplify_route(fixture(),500);self.assertFalse(out['changed'])

 def test_new_route_pack_and_loop_continuation(self):
  files=list((ROOT/'routes/new_016').glob('*.json'));self.assertEqual(len(files),5)
  for f in files:
   d=json.loads(f.read_text());self.assertIsNone(d['global_limit']);self.assertTrue(all(s.get('limit') is None for s in d['segments']))
   for direction in ['forward','backward']:
    g=create_game(d,d['recommended_train'],direction=direction);self.assertGreater(g.limit(),0);self.assertTrue(g.target())
   if d.get('loop'):
    self.assertEqual(len(d['stations']),30)
    for direction in ['forward','backward']:
     g=create_game(d,d['recommended_train'],direction=direction);g.index=len(g.route.stations)-1;g.s=g.target()['stop'];g.t=g.target()['arrival'];g.paused=False;g.station_action()
     n=continue_service(g,'lap');self.assertEqual(n.route.direction,direction);self.assertEqual(n.state()['run_number'],2);self.assertEqual(n.route.origin['name'],'東京')
     back=continue_service(g,'turnback');self.assertNotEqual(back.route.direction,direction)
 def test_start_id_stable_for_unsorted_editor(self):
  d=fixture();d['stations'].reverse();g=create_game(d,start_station=1);self.assertEqual(g.route.origin['name'],'B');self.assertEqual(g.target()['name'],'C')
