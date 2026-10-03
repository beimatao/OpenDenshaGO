import copy,csv,io,json,math,sys,unittest,subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from engine import *
from terrain_tools import export_route,convert_csv

def simple():
 return dict(name='山線 & 試驗',lat=25,lon=121,segments=[dict(length=2000,radius=0,mode='ground')],stations=[dict(name='A',center=1000,arrival=120,platform=None,dwell=30),dict(name='B',center=1750,arrival=220,platform=None,dwell=20)])
class Version014(unittest.TestCase):
 def test_center_is_not_front(self):
  d=simple();g=create_game(d,'hsr');self.assertEqual(g.target()['stop'],1152)
  d['start_station']=dict(center=300,name='S');g=create_game(d,'hsr',direction='backward')
  self.assertAlmostEqual(g.route.length-g.target()['stop'],1000-152)
 def test_derail_limits_and_frozen_end(self):
  for key,t in TRAINS.items():
   g=create_game(simple(),key);g.paused=False;threshold=g.derailment_limit();g.v=(threshold-.1)/3.6;g.tick(.001);self.assertIsNone(g.failure)
   g.v=(threshold+1)/3.6;g.tick(.01);self.assertEqual(g.failure['kind'],'derailed');self.assertEqual(g.state()['score'],0)
   frozen=(g.s,g.t,g.notch);g.command('power');g.command('pause');g.tick(2);self.assertEqual(frozen,(g.s,g.t,g.notch))
 def test_buffer_both_directions(self):
  for micro_reverse in (False,True):
   g=create_game(simple());g.paused=False;g.reverse=micro_reverse;g.v=1;g.s=g.train['length']+.001 if micro_reverse else g.route.length-.001
   g.tick(.01);self.assertEqual(g.failure['kind'],'buffer_collision')
 def test_missed_final_can_reach_buffer(self):
  g=create_game(simple());g.index=1;g.paused=False;g.s=g.target()['stop']+51;g.v=1;g.tick(.01)
  self.assertFalse(g.done);g.s=g.route.length-.001;g.tick(.01);self.assertEqual(g.failure['kind'],'buffer_collision')
 def test_reverse_service_buffer(self):
  d=simple();d['start_station']=dict(center=300,name='S');g=create_game(d,direction='backward');g.paused=False;g.s=g.route.length-.001;g.v=1;g.tick(.01)
  self.assertEqual(g.failure['kind'],'buffer_collision')
 def test_skip_dwell_preserves_score_and_wait(self):
  g=create_game(simple());g.paused=False;g.s=g.target()['stop'];g.t=100;g.station_action();before=copy.deepcopy(g.results);position=g.s
  g.command('skip_dwell');self.assertEqual(g.release-g.t,5);self.assertTrue(g.skipped_dwell);self.assertEqual(before,g.results);self.assertEqual(position,g.s)
  g.command('skip_dwell');self.assertEqual(g.release-g.t,5)
  g.station_action();self.assertTrue(g.doors)
  for _ in range(501):g.tick(.01)
  g.station_action();self.assertFalse(g.doors);self.assertFalse(g.skipped_dwell)
 def test_skip_invalid_does_not_change_time(self):
  g=create_game(simple());g.command('skip_dwell');self.assertEqual(g.t,0)
 def test_split_preserves_geometry_height_and_stations(self):
  for mode in ('ground','elevated','underground','transition','absolute','smooth'):
   d=simple();d['segments']=[dict(length=2000,radius=-1200,mode=mode,z_end=30,offset={'elevated':10,'underground':-10}.get(mode,0))]
   a=Route(d);result=split_route(d,712.34);b=Route(result['route'])
   self.assertEqual(d['stations'],result['route']['stations']);self.assertEqual(len(b.segments),2)
   for x in range(0,2001,5):
    for k in ('x','y','h','z'):self.assertAlmostEqual(a.point(x)[k],b.point(x)[k],places=7,msg=(mode,x,k))
   # Multiple cuts of a smooth segment retain its derivatives.
   c=Route(split_route(result['route'],1300)['route'])
   self.assertAlmostEqual(a.point(1499)['z'],c.point(1499)['z'])
 def test_cut_near_endpoint_rejected(self):
  for x in (0,.5,1999.5,2000):
   with self.assertRaises(ValueError):split_route(simple(),x)
 def test_expanded_limits(self):
  d=simple();d['segments']=[dict(length=1,radius=0,mode='ground') for _ in range(MAX_SEGMENTS)];d['stations']=[dict(name=str(i),center=i*1.5+300,arrival=i+1) for i in range(MAX_STATIONS)]
  r=Route(d);self.assertEqual(len(r.segments),20000);self.assertEqual(len(r.stations),10000)
  d['segments'].append(dict(length=1,radius=0,mode='ground'))
  with self.assertRaises(ValueError):Route(d)
 def test_exchange_formats_and_real_z_required(self):
  d=simple();j=json.loads(export_route(d,'geojson',25)['text']);self.assertEqual(j['features'][0]['properties']['s'],0);self.assertEqual(j['features'][-1]['properties']['s'],2000)
  self.assertEqual(len(j['features'][0]['geometry']['coordinates']),2)
  kml=export_route(d,'kml')['text'];self.assertIn('clampToGround',kml);self.assertIn('山線 &amp; 試驗',kml)
  r=convert_csv('s,SAMPLE_1,name\n2000,40,end\n0,12,start\n',route_length=2000);self.assertEqual(r['terrain'],[[0,12],[2000,40]])
  self.assertTrue(r['csv'].startswith('s,z'))
  for text in ('s,z\n0,\n2000,40','s,z\n0,-9999\n2000,40','s,z\n0,1\n0,2','s,z\n1,2\n2000,5'):
   with self.assertRaises(ValueError):convert_csv(text,route_length=2000)

 def test_split_smooth_frontend_profile_matches_core(self):
  d=simple();d['segments']=[dict(length=2000,radius=1000,mode='smooth',z_end=40)]
  d=split_route(d,713)['route'];r=Route(d)
  script="const G=require('./static/geometry.js');let text='';process.stdin.on('data',x=>text+=x);process.stdin.on('end',()=>console.log(JSON.stringify(G.profile(JSON.parse(text)).map(p=>[p.s,p.z])))));".replace('])))));',']))));')
  points=json.loads(subprocess.check_output(['node','-e',script],cwd=Path(__file__).resolve().parents[1],input=json.dumps(d).encode()))
  for x,z in points:self.assertAlmostEqual(r.point(x)['z'],z,places=8)
