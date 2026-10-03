"""End-to-end local server smoke test; no external services required."""
import json, os, socket, subprocess, sys, time, unittest, urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class HTTPTests(unittest.TestCase):
    def test_local_server_controls_and_editor(self):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]
        base=f'http://127.0.0.1:{port}/'
        def get(path):
            with urllib.request.urlopen(base+path,timeout=3) as r:return json.load(r)
        def post(path,body):
            request=urllib.request.Request(base+path,json.dumps(body).encode(),{'Content-Type':'application/json','Origin':base.rstrip('/')})
            with urllib.request.urlopen(request,timeout=3) as r:return json.load(r)
        proc=subprocess.Popen([sys.executable,str(ROOT/'app.py'),'--no-browser','--port',str(port)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            for _ in range(50):
                try: init=get('api/init');break
                except OSError:time.sleep(.05)
            else:self.fail('Local server did not start')
            self.assertGreater(len(init['profile']),100)
            blank=json.loads(json.dumps(init['route']))
            for st in blank['stations']:st['arrival']=None
            scheduled=post('api/schedule',{'route':blank,'train':'metro','difficulty':'normal'})
            self.assertTrue(all(st['arrival']>0 for st in scheduled['route']['stations']))
            post('api/command',{'command':'pause'})
            for _ in range(5):post('api/command',{'command':'power'})
            time.sleep(.6);self.assertGreater(get('api/state')['speed'],1)
            post('api/command',{'command':'emergency'})
            time.sleep(.7);self.assertEqual(get('api/state')['speed'],0)
            post('api/command',{'command':'release'})
            data=post('api/coordinates',{'coordinates':[[121.5,25],[121.5,25.02],[121.52,25.02]],'radius':300})
            loaded=post('api/load',{'route':data['route'],'train':'hsr'})
            self.assertEqual(loaded['state']['train']['length'],304)
            self.assertTrue(loaded['state']['paused'])
            service=data['route'];service['start_station']={'name':'起始站','center':300,'platform':None}
            service['stations'].insert(0,dict(name='過站測試',center=1000,platform=None,arrival=50,dwell=500,stop_enabled=False))
            service['stations'][-1]['platform']=None
            scheduled=post('api/schedule',{'route':service,'train':'hsr','recompute':True,'difficulty':'precise'})
            self.assertGreater(scheduled['legs'][0]['pass_speed_kmh'],0)
            reversed_game=post('api/load',{'route':scheduled['route'],'train':'hsr','direction':'backward','mode':'classic'})
            self.assertEqual(reversed_game['state']['service_direction'],'backward')
            self.assertEqual(reversed_game['state']['service_stations'][0]['platform'],324)
            self.assertEqual(reversed_game['state']['service_stations'][-1]['name'],'起始站')
            self.assertEqual(reversed_game['route']['start_station']['center'],300)
            middle=post('api/load',{'route':scheduled['route'],'train':'hsr','start_station':0})
            self.assertEqual(middle['state']['start_station_id'],0)
            self.assertEqual(middle['state']['service_stations'][0]['name'],'過站測試')
            self.assertEqual(middle['route']['stations'],scheduled['route']['stations'])
            reversed_game=post('api/load',{'route':scheduled['route'],'train':'hsr','direction':'backward','mode':'classic'})
            simple=post('api/mode',{'mode':'simple'})
            self.assertEqual(simple['service_stations'][0]['platform'],344)
            cut=post('api/split',{'route':scheduled['route'],'position':500})
            self.assertEqual(len(cut['route']['segments']),len(scheduled['route']['segments'])+1)
            exported=post('api/export-terrain',{'route':cut['route'],'format':'geojson','spacing':25})
            samples=json.loads(exported['text'])['features']
            end=samples[-1]['properties']['s']
            converted=post('api/convert-terrain',{'route':cut['route'],'text':f's,SAMPLE_1\n0,10\n{end},20\n'})
            self.assertEqual(converted['terrain'][0],[0,10])
            draft=json.loads(json.dumps(scheduled['route']))
            draft['segments'][0]['radius']=200001
            draft['segments'][0]['mode']='absolute';draft['segments'][0]['z_end']=5
            draft['segments'][1]['mode']='ground';draft['segments'][1]['offset']=0
            draft['terrain']=[[0,100],[100000,200]]
            preview=post('api/preview',{'route':draft})
            self.assertTrue(preview['warnings'])
            split_draft=post('api/split',{'route':draft,'position':500})
            reopened=post('api/preview',{'route':json.loads(json.dumps(split_draft['route']))})
            self.assertTrue(reopened['warnings'])
            with urllib.request.urlopen(base,timeout=3) as r:self.assertIn('OpenDenshaGO',r.read().decode())
            with urllib.request.urlopen(base+'api/results',timeout=3) as r:self.assertTrue(r.read().startswith(b'\xef\xbb\xbf'))
        finally:
            proc.terminate();proc.communicate(timeout=5)
if __name__=='__main__':unittest.main()
