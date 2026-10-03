import copy,json,math,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from engine import Route,split_route,automatic_schedule

class WorkshopRegression(unittest.TestCase):
 def route(self,radius=0):
  return dict(heading=37,segments=[dict(length=2000,radius=radius,mode='ground')],stations=[dict(center=1800,arrival=200)])
 def test_large_signed_arcs_split_preserves_geometry(self):
  for r in [100000,-100000,100001,-100001,1e6,-1e6,1e12,-1e12]:
   with self.subTest(radius=r):
    d=self.route(r);before=Route(d);cut=split_route(d,723.45)['route'];after=Route(cut)
    self.assertEqual([s['radius'] for s in cut['segments']],[r,r])
    for s in [0,723.45,1000,1999,2000]:
     a,b=before.point(s),after.point(s)
     for k in ['x','y','z','h']:self.assertAlmostEqual(a[k],b[k],places=7)
 def test_dem_draft_roundtrip_and_cut_with_height_discontinuity(self):
  d=self.route(200000);d['segments']=[dict(length=1000,radius=200000,mode='absolute',z_end=10),dict(length=1000,radius=-200000,mode='ground')];d['terrain']=[[0,100],[500,140],[1000,200],[2000,220]]
  original=copy.deepcopy(d);r=Route(json.loads(json.dumps(d)),editing=True)
  self.assertEqual(len(r.warnings),1);self.assertEqual(d,original)
  cut=split_route(d,1400)['route'];self.assertEqual(cut['terrain'],d['terrain']);self.assertEqual(len(Route(cut,editing=True).warnings),1)
  with self.assertRaisesRegex(ValueError,'高度不連續'):Route(cut)
  with self.assertRaisesRegex(ValueError,'高度不連續'):automatic_schedule(cut)
 def test_editing_still_rejects_invalid_numbers(self):
  for radius in [float('nan'),float('inf'),1e13,3]:
   with self.assertRaises(ValueError):Route(self.route(radius),editing=True)
