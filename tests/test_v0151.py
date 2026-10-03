import copy,unittest
from engine import Route,split_route
class HeightTests(unittest.TestCase):
 def fixture(self):
  return dict(lat=25,lon=121,terrain=[[0,-30],[200,300]],stations=[],segments=[dict(length=100,mode='absolute',z_start=110,z_end=110,height_points=[[0,110],[.2,120],[.8,100],[1,110]]),dict(length=100,mode='smooth',z_start=110,z_end=150,grade_start=.1,grade_end=.2)])
 def test_reimport(self):
  a=self.fixture();b=copy.deepcopy(a);b['terrain']=[[0,1000],[200,0]]
  x,y=Route(a,editing=True),Route(b,editing=True)
  for d in range(201):self.assertAlmostEqual(x.point(d)['z'],y.point(d)['z'])
 def test_split_frozen_and_smooth(self):
  a=self.fixture();original=Route(a,editing=True)
  for cut in (20,45,150):
   b=Route(split_route(a,cut)['route'],editing=True)
   for d in range(201):self.assertAlmostEqual(original.point(d)['z'],b.point(d)['z'])
 def test_reject_bad_profile(self):
  a=self.fixture();a['segments'][0]['height_points'][0][1]=0
  with self.assertRaises(ValueError):Route(a,editing=True)

 def test_endpoint_roundoff_legacy(self):
  for end in (1-1e-15,1+1e-15):
   a=self.fixture();a['segments'][0]['height_points'][0][0]=-1e-15;a['segments'][0]['height_points'][-1][0]=end
   r=Route(a,editing=True)
   self.assertEqual(r.segments[0]['height_t'][0],0)
   self.assertEqual(r.segments[0]['height_t'][-1],1)
   split=Route(split_route(a,45.67)['route'],editing=True)
   for d in range(201):self.assertAlmostEqual(r.point(d)['z'],split.point(d)['z'])
 def test_real_errors_still_rejected(self):
  for pts in ([[0,110],[.5,105],[.4,108],[1,110]],[[0,110],[.5,105],[.5,108],[1,110]],[[0,110],[.999,110]],[[0,110],[1.001,110]]):
   a=self.fixture();a['segments'][0]['height_points']=pts
   with self.assertRaises(ValueError):Route(a,editing=True)
