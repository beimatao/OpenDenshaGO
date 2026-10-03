import unittest
from engine import Route,Game,TRAINS
class RadarReleaseTests(unittest.TestCase):
 def game(self,gap,first=500):
  r=Route(dict(lat=25,lon=121,segments=[dict(length=first,mode='ground',limit=30),dict(length=gap,mode='ground',limit=80),dict(length=2000,mode='ground',limit=45)],stations=[dict(name='A',center=first+gap+1500,arrival=500)],terrain=[[0,0],[100000,0]]))
  g=Game(r);g.s=0;return g
 def test_short_release_hidden(self):
  g=self.game(12);self.assertEqual([(e['limit'],e['release']) for e in g.state()['restrictions']],[(45,True)])
 def test_exact_length_retained(self):
  g=self.game(TRAINS['metro']['length']);self.assertTrue(g.state()['restrictions'][0]['release'])
 def test_long_gap_retained(self):
  g=self.game(TRAINS['metro']['length']+1);self.assertTrue(g.state()['restrictions'][0]['release'])
 def test_horizon_lookahead(self):
  g=self.game(20,4990);self.assertEqual(g.state()['restrictions'],[])
 def test_actual_limit_unchanged(self):
  g=self.game(12);g.s=505;before=g.limit();g.state();self.assertEqual(g.limit(),before);self.assertEqual(before,30)
 def test_last_release_retained(self):
  g=self.game(12);g.s=600;self.assertEqual(g.state()['restrictions'],[])
  g.route.segments[-1]['limit']=80;g.s=0
  self.assertTrue(g.state()['restrictions'][0]['release'])
