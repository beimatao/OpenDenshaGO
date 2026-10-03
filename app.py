"""Local-only stdlib server. Run: python app.py [--port 8765] [--no-browser]."""
import argparse, csv, io, json, mimetypes, threading, time, webbrowser, tempfile, secrets, os
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
from engine import Route, Game, TRAINS, from_coordinates, automatic_schedule, create_game, split_route, continue_service
from terrain_tools import export_route, convert_csv
from terrain_processing import sample_geotiff, smooth_terrain, raster_support
from route_simplify import simplify_route

ROOT=Path(__file__).resolve().parent
LOCK=threading.RLock()
GAME=None
DTM_JOBS={}
DTM_LOCK=threading.Lock()
MAX_TIFF=2*1024**3
LAST_CLIENT=time.monotonic()

def payload():
    return dict(route=GAME.route.data,profile=GAME.route.profile(),trains=TRAINS,state=GAME.state())

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def send(self,body,status=200,kind='application/json; charset=utf-8'):
        if not isinstance(body,bytes): body=json.dumps(body,ensure_ascii=False,allow_nan=False).encode('utf-8')
        self.send_response(status); self.send_header('Content-Type',kind)
        self.send_header('Content-Length',str(len(body))); self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff'); self.end_headers(); self.wfile.write(body)
    def do_GET(self):
        global LAST_CLIENT
        path=urlparse(self.path).path
        with LOCK:
            if path=='/api/dtm-support': self.send(raster_support()); return
            if path=='/api/state': LAST_CLIENT=time.monotonic(); self.send(GAME.state(False)); return
            if path=='/api/init': self.send(payload()); return
            if path=='/api/results':
                out=io.StringIO(); writer=csv.DictWriter(out,fieldnames=['station','error_cm','time_delta','arrival','ontime','missed','passed','score'])
                writer.writeheader(); writer.writerows(GAME.results)
                self.send(('\ufeff'+out.getvalue()).encode(),kind='text/csv; charset=utf-8'); return
        if path=='/': path='/index.html'
        file=(ROOT/'static'/path.lstrip('/')).resolve()
        if not file.is_relative_to(ROOT/'static') or not file.is_file(): self.send({'error':'找不到檔案'},404); return
        self.send(file.read_bytes(),kind=mimetypes.guess_type(str(file))[0] or 'application/octet-stream')
    def do_POST(self):
        global GAME,LAST_CLIENT
        # Reject cross-origin browser requests; bind exclusively to loopback.
        origin=self.headers.get('Origin')
        if origin and origin not in (f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}'):
            self.send({'error':'來源不允許'},403); return
        try:
            if self.path.startswith('/api/dtm-upload/'):
                self.receive_dtm();return
            size=int(self.headers.get('Content-Length',0))
            if not 0<size<=33554432: raise ValueError('請求大小錯誤，限制 32 MiB')
            data=json.loads(self.rfile.read(size))
            if self.path=='/api/dtm-start':
                support=raster_support()
                if not support['available']:raise ValueError(support['message'])
                Route(data['route'],editing=True)
                with DTM_LOCK:
                    for key in list(DTM_JOBS):
                        if time.monotonic()-DTM_JOBS[key][0]>600:del DTM_JOBS[key]
                    if len(DTM_JOBS)>=4:raise ValueError('已有待處理的 DTM 匯入，請稍後重試')
                    token=secrets.token_urlsafe(24);DTM_JOBS[token]=(time.monotonic(),data)
                self.send(dict(token=token));return
            if self.path=='/api/smooth-terrain':
                self.send(smooth_terrain(data['route'],data.get('width',100),data.get('strength',1)));return
            if self.path=='/api/simplify-route':
                self.send(simplify_route(data['route'],data.get('tolerance',5)));return
            with LOCK:
                LAST_CLIENT=time.monotonic()
                if self.path=='/api/command': GAME.command(data['command']); self.send(GAME.state())
                elif self.path=='/api/load':
                    new=create_game(data['route'],data.get('train','metro'),data.get('mode','simple'),data.get('direction','forward'),data.get('start_station')); GAME=new; self.send(payload())
                elif self.path=='/api/continue':
                    GAME=continue_service(GAME,data.get('action','turnback'));self.send(payload())
                elif self.path=='/api/split':
                    self.send(split_route(data['route'],data['position']))
                elif self.path=='/api/export-terrain':
                    self.send(export_route(data['route'],data.get('format','geojson'),data.get('spacing',25)))
                elif self.path=='/api/convert-terrain':
                    length=sum(float(s['length']) for s in data['route']['segments'])
                    self.send(convert_csv(data['text'],data.get('z_column',''),route_length=length))
                elif self.path=='/api/mode':
                    if data.get('mode') not in ('simple','classic'):raise ValueError('不支援的遊戲模式')
                    GAME.mode=data['mode'];self.send(GAME.state())
                elif self.path=='/api/schedule':
                    self.send(automatic_schedule(data['route'],data.get('train','metro'),data.get('difficulty','normal'),data.get('mode','simple'),data.get('recompute',False),data.get('direction','forward')))
                elif self.path=='/api/preview':
                    if not data['route'].get('segments'):
                        self.send(dict(profile=[],length=0)); return
                    route=Route(data['route'],editing=True)
                    train=TRAINS[data.get('train','metro')]
                    limits=[route.speed_limit(seg['s']+.001,train) for seg in route.segments]
                    self.send(dict(profile=route.profile(),length=route.length,limits=limits,warnings=route.warnings))
                elif self.path=='/api/coordinates':
                    route=from_coordinates(data['coordinates'],data.get('radius',300),data.get('name','地圖自訂路線'))
                    self.send(dict(route=route,profile=Route(route).profile()))
                elif self.path=='/api/demo':
                    GAME=create_game(json.loads((ROOT/'routes'/'demo.json').read_text(encoding='utf-8')),data.get('train','metro'),data.get('mode','simple'),data.get('direction','forward')); self.send(payload())
                else: self.send({'error':'不支援的操作'},404)
        except (ValueError,TypeError,KeyError,IndexError,OverflowError) as exc: self.send({'error':str(exc)},400)


    def receive_dtm(self):
        token=self.path.rsplit('/',1)[-1]
        with DTM_LOCK:job=DTM_JOBS.pop(token,None)
        if not job or time.monotonic()-job[0]>600:raise ValueError('DTM 匯入已逾時，請重新選取檔案')
        size=int(self.headers.get('Content-Length',0))
        if not 8<=size<=MAX_TIFF:raise ValueError('單一 GeoTIFF 需介於 8 bytes 與 2 GiB；更大資料請先裁切至路線範圍')
        data=job[1];path=None
        try:
            with tempfile.NamedTemporaryFile(suffix='.tif',delete=False) as f:
                path=f.name;remaining=size;first=True
                self.connection.settimeout(120)
                while remaining:
                    block=self.rfile.read(min(1024*1024,remaining))
                    if not block:raise ValueError('檔案傳輸中斷，未套用地形')
                    if first and block[:4] not in (b'II*\x00',b'MM\x00*',b'II+\x00',b'MM\x00+'):
                        raise ValueError('檔案不是 TIFF／BigTIFF；請選擇實際的高程 GeoTIFF')
                    first=False;f.write(block);remaining-=len(block)
            result=sample_geotiff(path,data['route'],data.get('spacing',25),data.get('band',1),data.get('method','bilinear'),data.get('unit','m'),data.get('crs_override',''))
            result['route']['terrain_source']['filename']=str(data.get('filename','DTM.tif'))[:200]
            self.send(result)
        except OSError as exc:raise ValueError('DTM 檔案讀取／暫存失敗：'+str(exc)) from exc
        finally:
            if path:
                try:os.unlink(path)
                except OSError:pass


def run():
    global GAME
    parser=argparse.ArgumentParser(); parser.add_argument('--port',type=int,default=8765); parser.add_argument('--no-browser',action='store_true')
    args=parser.parse_args()
    GAME=Game(Route(json.loads((ROOT/'routes'/'demo.json').read_text(encoding='utf-8'))))
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    running=threading.Event(); running.set()
    def physics():
        previous=time.monotonic(); accumulator=0
        while running.wait(0.01):
            now=time.monotonic(); elapsed=now-previous; previous=now
            with LOCK:
                if now-LAST_CLIENT>3 or elapsed>1:
                    GAME.paused=True
                accumulator+=min(elapsed,.1)
                while accumulator>=.01: GAME.tick(.01); accumulator-=.01
            time.sleep(.005)
    thread=threading.Thread(target=physics,daemon=True); thread.start()
    url=f'http://127.0.0.1:{args.port}'
    print(f'OpenDenshaGO — {url}\nCtrl+C to quit. Python simulation; browser cockpit.')
    if not args.no_browser: webbrowser.open(url)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: running.clear(); server.server_close()

if __name__=='__main__': run()
