import unittest,json,subprocess
from pathlib import Path
from engine import Route,automatic_schedule,create_game,TRAINS
ROOT=Path(__file__).resolve().parents[1]
class UpdateTests(unittest.TestCase):
 def test_pack(self):
  files=list((ROOT/'routes/osm').glob('*.json'));self.assertEqual(len(files),7)
  for path in files:
   with self.subTest(route=path.name):
    d=json.loads(path.read_text());self.assertIsNone(d['global_limit']);self.assertTrue(all(s['limit'] is None for s in d['segments']))
    r=Route(d,editing=True);self.assertFalse(r.warnings);self.assertGreater(d['start_station']['center'],220)
    self.assertLess(d['stations'][-1]['center'],r.length-220)
    scheduled=automatic_schedule(d,d['recommended_train'])['route']
    for direction in ('forward','backward'):
     g=create_game(scheduled,d['recommended_train'],direction=direction);self.assertGreater(g.limit(),0)
 def test_blank_global(self):
  d=json.loads((ROOT/'routes/demo.json').read_text())
  for limit in (None,''):
   d['global_limit']=limit;r=Route(d);self.assertEqual(r.global_limit,400)
 def test_prepend_python_geography_and_height(self):
  d=json.loads((ROOT/'routes/bidirectional_demo.json').read_text());d['projection_lat']=23
  script="const G=require('./static/geometry.js');let s='';process.stdin.on('data',d=>s+=d);process.stdin.on('end',()=>process.stdout.write(JSON.stringify(G.prepend(JSON.parse(s),1200,-3000))));"
  out=json.loads(subprocess.check_output(['node','-e',script],input=json.dumps(d).encode(),cwd=ROOT));a,b=Route(d),Route(out)
  for st in [d['start_station'],*d['stations']]:
   p,q=a.point(st['center']),b.point(st['center']+1200)
   for key in ('lat','lon','z','ground'):self.assertAlmostEqual(p[key],q[key],places=9)
if __name__=='__main__':unittest.main()
