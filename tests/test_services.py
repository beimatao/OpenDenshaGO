import copy,math,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from engine import *

def data():
 return dict(name='雙向測試',lat=25,lon=121,heading=0,terrain=[[0,0],[6000,0]],
  segments=[dict(length=2000,radius=0,mode='ground',limit=120),dict(length=1000,radius=1500,mode='smooth',z_end=10,limit=65),dict(length=3000,radius=0,mode='absolute',z_end=0,limit=120)],
  start_station=dict(name='起始站',center=300,platform=None),
  stations=[dict(name=name,center=center,platform=None,arrival=arrival,dwell=20,stop_enabled=True) for name,center,arrival in [('A',1500,150),('B',3500,300),('C',5600,480)]])

class Services(unittest.TestCase):
 def test_reverse_geometry_and_departure(self):
  d=data();g=create_game(d,'shinkansen','classic','backward');r=g.route;source=Route(d)
  self.assertEqual([st['name'] for st in r.stations],['B','A','起始站'])
  self.assertAlmostEqual(source.length-r.origin['center'],5600)
  self.assertAlmostEqual(g.s,r.origin['center']+405/2)
  for x in (0,999,3500,4000,5999):
   a=r.point(x);b=source.point(6000-x)
   for key in ('x','y','z','lat','lon'):self.assertAlmostEqual(a[key],b[key])
   self.assertAlmostEqual(math.cos(a['h']-b['h']),-1)
  self.assertEqual(r.speed_limit(3500,g.train),65)
  self.assertEqual(d,data())
  self.assertGreater(r.stations[-1]['arrival'],r.stations[0]['arrival'])
 def test_reverse_requires_origin_and_valid_edges(self):
  d=data();del d['start_station']
  with self.assertRaisesRegex(ValueError,'起始站'):create_game(d,direction='backward')
  d=data();d['start_station']['center']=50
  with self.assertRaises(ValueError):create_game(d)
  with self.assertRaises(ValueError):create_game(d,direction='backward')
 def test_reverse_can_stop_at_original_origin(self):
  g=create_game(data(),direction='backward');g.index=len(g.route.stations)-1;g.paused=False;g.s=g.target()['stop'];g.t=g.target()['arrival'];g.station_action()
  self.assertTrue(g.done);self.assertEqual(g.results[-1]['station'],'起始站');self.assertEqual(g.results[-1]['error_cm'],0)
 def test_blank_platform_mode_and_train(self):
  for key,t in TRAINS.items():
   for mode,margin in [('simple',20),('classic',10)]:
    for error,allowed in [(margin,True),(-margin,True),(margin+.1,False),(-margin-.1,False)]:
     g=create_game(data(),key,mode);g.paused=False;g.s=g.target()['stop']+error;g.station_action()
     self.assertEqual(g.doors,allowed,(key,mode,error))
     self.assertEqual(g.target()['platform'] if not allowed else g.state()['service_stations'][1]['platform'],t['length']+2*margin)
 def test_explicit_short_platform_warns_and_blocks(self):
  d=data();d['stations'][0]['platform']=100;g=create_game(d);self.assertTrue(g.platform_warnings())
  g.paused=False;g.s=g.target()['stop'];g.station_action();self.assertFalse(g.doors)
  self.assertTrue(automatic_schedule(d,recompute=True)['warnings'])
 def test_custom_margins_do_not_override_explicit_platform(self):
  d=data();d['door_margins']={'simple':40,'classic':5};d['stations'][0]['platform']=TRAINS['metro']['length']+10
  g=create_game(d);g.paused=False;g.s=g.target()['stop']+6;g.station_action();self.assertFalse(g.doors)
  d['stations'][0]['platform']=None;g=create_game(d);g.paused=False;g.s=g.target()['stop']+35;g.station_action();self.assertTrue(g.doors)
 def test_pass_schedule_has_no_brake_or_dwell(self):
  d=data();stopped=automatic_schedule(d,recompute=True)
  d['stations'][0]['stop_enabled']=False
  passed=automatic_schedule(d,recompute=True)
  self.assertGreater(passed['legs'][0]['pass_speed_kmh'],0)
  self.assertEqual(stopped['legs'][0]['pass_speed_kmh'],0)
  self.assertLess(passed['legs'][-1]['arrival'],stopped['legs'][-1]['arrival'])
  d['stations'][0]['dwell']=500
  self.assertEqual(passed['legs'],automatic_schedule(d,recompute=True)['legs'])
  for mode in ('normal','hard','precise'):
   result=automatic_schedule(d,difficulty=mode,recompute=True)
   self.assertEqual(result['route']['schedule_difficulty'],mode)
 def test_pass_game_no_missed_penalty_or_doors(self):
  d=data();d['stations'][0]['stop_enabled']=False;g=create_game(d);g.paused=False;g.s=g.target()['stop']-.05;g.station_action();self.assertFalse(g.doors)
  g.v=10;g.tick(.1);self.assertTrue(g.results[0]['passed']);self.assertFalse(g.results[0]['missed']);self.assertEqual(g.index,1)
  g.tick(.1);self.assertEqual(len(g.results),1)
 def test_last_station_pass_completes(self):
  d=data();d['stations'][-1]['stop_enabled']=False;g=create_game(d);g.index=2;g.paused=False;g.s=g.target()['stop']-.05;g.v=10;g.tick(.1)
  self.assertTrue(g.done);self.assertTrue(g.results[-1]['passed'])
 def test_reverse_pass_flags_and_endpoint(self):
  d=data();d['stations'][0]['stop_enabled']=False;g=create_game(d,direction='backward')
  self.assertFalse(g.route.stations[1]['stop_enabled']);self.assertTrue(g.route.stations[-1]['stop_enabled'])
 def test_full_recompute_overwrites_manual_only_when_requested(self):
  d=data();self.assertEqual(automatic_schedule(d)['route']['stations'][0]['arrival'],150)
  self.assertNotEqual(automatic_schedule(d,recompute=True)['route']['stations'][0]['arrival'],150)
