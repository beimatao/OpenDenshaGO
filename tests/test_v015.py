import copy,json,tempfile,unittest
from pathlib import Path
from engine import Route
from terrain_processing import sample_geotiff,smooth_terrain
from route_simplify import simplify_route
try:
 import rasterio
 import numpy as np
 from rasterio.transform import from_origin
 from rasterio.warp import transform
except ImportError:rasterio=None

def fixture():
 return dict(name='試驗',lat=25.,lon=121.,heading=0,terrain=[[0,10],[1000,20]],segments=[dict(length=1000,radius=0,mode='ground',limit=None)],start_station=dict(name='S',center=200),stations=[dict(name='A',center=750,arrival=100,dwell=20)])

@unittest.skipUnless(rasterio,'DTM dependencies not installed')
class TIFFTests(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'test.tif'
 def tearDown(self):self.tmp.cleanup()
 def write(self,data=None,crs='EPSG:4326',affine=None,scale=None,offset=None,units=None):
  if data is None:data=np.full((20,20),123,dtype='float32')
  with rasterio.open(self.path,'w',driver='GTiff',width=data.shape[1],height=data.shape[0],count=1,dtype=data.dtype,crs=crs,transform=affine or from_origin(120.995,25.015,.001,.001),nodata=-9999) as dst:
   dst.write(data,1)
   if scale:dst.scales=(scale,)
   if offset:dst.offsets=(offset,)
   if units:dst.set_band_unit(1,units)
 def test_geographic_and_backup(self):
  self.write();d=fixture();r=sample_geotiff(self.path,d,25);self.assertTrue(all(abs(z-123)<1e-8 for s,z in r['route']['terrain']));self.assertEqual(r['route']['terrain'],r['route']['terrain_original']);self.assertEqual(d['terrain'],[[0,10],[1000,20]])
 def test_projected_crs(self):
  x,y=transform('EPSG:4326','EPSG:3826',[121],[25]);self.write(crs='EPSG:3826',affine=from_origin(x[0]-500,y[0]+1500,100,100));self.assertEqual(sample_geotiff(self.path,fixture())['metadata']['crs'],'EPSG:3826')
 def test_bilinear_scale_offset(self):
  self.write(np.tile(np.arange(20,dtype='float32'),(20,1)),scale=2,offset=10);r=sample_geotiff(self.path,fixture());self.assertAlmostEqual(r['route']['terrain'][0][1],19,places=6)
 def test_nodata(self):
  self.write(np.full((20,20),-9999,dtype='float32'))
  with self.assertRaisesRegex(ValueError,'NoData'):sample_geotiff(self.path,fixture())
 def test_outside(self):
  self.write();d=fixture();d['lon']=135
  with self.assertRaisesRegex(ValueError,'範圍外'):sample_geotiff(self.path,d)
 def test_unknown_crs(self):
  self.write(crs=None)
  with self.assertRaisesRegex(ValueError,'座標系統'):sample_geotiff(self.path,fixture())
  self.assertGreater(sample_geotiff(self.path,fixture(),crs_override='EPSG:4326')['count'],2)
 def test_feet(self):
  self.write(units='ft')
  with self.assertRaisesRegex(ValueError,'英尺'):sample_geotiff(self.path,fixture())
  self.assertAlmostEqual(sample_geotiff(self.path,fixture(),unit='ft')['route']['terrain'][0][1],123*.3048)
 def test_band_and_color(self):
  self.write()
  with self.assertRaises(ValueError):sample_geotiff(self.path,fixture(),band=2)
  with rasterio.open(self.path,'w',driver='GTiff',height=20,width=20,count=3,dtype='uint8',crs='EPSG:4326',transform=from_origin(120.995,25.015,.001,.001)) as dst:dst.write(np.zeros((3,20,20),dtype='uint8'))
  with self.assertRaisesRegex(ValueError,'彩色'):sample_geotiff(self.path,fixture())

class SmoothTests(unittest.TestCase):
 def test_spike_reduction_and_unchanged_route(self):
  d=fixture();d['terrain']=[[0,0],[490,0],[500,25],[510,0],[1000,0]];before=copy.deepcopy(d);r=smooth_terrain(d,100);self.assertEqual(d,before);self.assertLess(r['stats']['after']['max_grade_pct'],r['stats']['before']['max_grade_pct']/10);self.assertEqual(r['route']['stations'],d['stations']);self.assertEqual(r['route']['segments'],d['segments']);self.assertEqual(r['route']['terrain_original'],d['terrain']);self.assertEqual(r['route']['terrain'][0],[0,0]);self.assertEqual(r['route']['terrain'][-1],[1000,0])
 def test_linear_ramp_density_independent(self):
  d=fixture();a=smooth_terrain(d)['route']['terrain'];d['terrain']=[[0,10],[1,10.01],[10,10.1],[300,13],[999,19.99],[1000,20]];b=smooth_terrain(d)['route']['terrain']
  for (s,z),(_,q) in zip(a,b):self.assertAlmostEqual(z,10+s/100,places=7);self.assertAlmostEqual(z,q,places=7)
 def test_backup_and_absolute(self):
  d=fixture();d['segments'][0].update(mode='absolute',z_end=90);r=smooth_terrain(smooth_terrain(d)['route'],200)['route'];self.assertEqual(r['terrain_original'],d['terrain']);self.assertEqual(r['segments'],d['segments'])
 def test_invalid(self):
  for width in (0,float('nan'),10000):
   with self.assertRaises(ValueError):smooth_terrain(fixture(),width)

class SimplifyTests(unittest.TestCase):
 def fragmented(self):
  d=fixture();d['segments']=[dict(length=10,radius=0,mode='ground',offset=0,limit=None) for _ in range(100)];return d
 def test_station_and_terrain_mapping(self):
  d=self.fragmented();d['terrain_original']=copy.deepcopy(d['terrain']);before=copy.deepcopy(d);r=simplify_route(d);self.assertLess(r['stats']['after'],10);self.assertEqual(d,before);self.assertIsNone(r['route']['stations'][0]['arrival']);self.assertEqual(r['route']['terrain_original'],r['route']['terrain']);self.assertLess(r['stats']['station_shift'],.001)
 def test_settings_protected(self):
  d=self.fragmented();d['segments'][40].update(mode='absolute',z_end=30);d['segments'][41].update(mode='smooth',z_end=20,grade_start=.01,grade_end=.02);d['segments'][70]['limit']=40;r=simplify_route(d)['route'];self.assertTrue(any(s.get('limit')==40 for s in r['segments']));p=[s for s in r['segments'] if s['mode'] in ('absolute','smooth')];self.assertEqual(len(p),2);self.assertEqual(p[1]['grade_start'],.01);self.assertEqual(p[1]['length'],10)
 def test_arc(self):
  d=self.fragmented()
  for s in d['segments']:s['radius']=2000
  r=simplify_route(d,1);self.assertTrue(r['changed']);self.assertLess(r['stats']['station_shift'],.001);self.assertTrue(any(s['radius'] for s in r['route']['segments']))
 def test_osm_pack(self):
  for p in (Path(__file__).parents[1]/'routes/osm').glob('*.json'):
   with self.subTest(route=p.name):
    r=simplify_route(json.loads(p.read_text()),5);self.assertTrue(r['changed']);self.assertLess(r['stats']['after'],r['stats']['before']);self.assertLess(r['stats']['station_shift'],.001);self.assertLessEqual(r['stats']['max_deviation'],5)
if __name__=='__main__':unittest.main()
