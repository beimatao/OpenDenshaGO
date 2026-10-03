import unittest,tempfile,subprocess,sys,json,time,socket,urllib.request,urllib.error
from pathlib import Path
from test_v015 import fixture,rasterio
if rasterio:
 import numpy as np
 from rasterio.transform import from_origin
ROOT=Path(__file__).resolve().parents[1]
@unittest.skipUnless(rasterio,'DTM dependency not installed')
class ProcessingHTTPTests(unittest.TestCase):
 def test_binary_upload_and_preview_only(self):
  with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
  base=f'http://127.0.0.1:{port}'
  def post(path,data,binary=False):
   req=urllib.request.Request(base+'/api/'+path,data if binary else json.dumps(data).encode(),{'Content-Type':'image/tiff' if binary else 'application/json','Origin':base})
   with urllib.request.urlopen(req,timeout=15) as r:return json.load(r)
  proc=subprocess.Popen([sys.executable,str(ROOT/'app.py'),'--no-browser','--port',str(port)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
  try:
   for _ in range(60):
    try:
     with urllib.request.urlopen(base+'/api/init',timeout=1) as r:initial=json.load(r)
     break
    except OSError:time.sleep(.05)
   else:self.fail('server did not start')
   with tempfile.TemporaryDirectory() as td:
    p=Path(td)/'dem.tif'
    with rasterio.open(p,'w',driver='GTiff',height=20,width=20,count=1,dtype='float32',crs='EPSG:4326',transform=from_origin(120.995,25.015,.001,.001)) as dst:dst.write(np.full((20,20),100,dtype='float32'),1)
    d=fixture();token=post('dtm-start',dict(route=d,filename='dem.tif'))['token'];result=post('dtm-upload/'+token,p.read_bytes(),True)
    self.assertAlmostEqual(result['route']['terrain'][0][1],100)
    with self.assertRaises(urllib.error.HTTPError):post('dtm-upload/'+token,p.read_bytes(),True)
    token=post('dtm-start',dict(route=d))['token']
    with self.assertRaises(urllib.error.HTTPError):post('dtm-upload/'+token,b'<xml>bad file</xml>',True)
    sm=post('smooth-terrain',dict(route=result['route'],width=100));self.assertEqual(sm['route']['terrain_original'],result['route']['terrain'])
    d['segments']=[dict(length=10,radius=0,mode='ground') for _ in range(100)]
    simplified=post('simplify-route',dict(route=d,tolerance=5));self.assertTrue(simplified['changed'])
    with urllib.request.urlopen(base+'/api/init') as r:after=json.load(r)
    self.assertEqual(initial['route'],after['route'])
  finally:proc.terminate();proc.communicate(timeout=5)
