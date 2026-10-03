# 0.1.6 新路線來源與限制

五條新 JSON 位於 `routes/new_016/`。全部 `global_limit` 及區段 `limit` 為 null；時刻留白可依遊戲車型計算。山手線 `loop: true`，一圈包含重複的東京終點。

資料來源：© OpenStreetMap contributors，ODbL 1.0。原始 API JSON 存於 `routes/new_016/source_data/`，供查核及再利用。路線資料屬 OSM 衍生資料，遵循 ODbL 1.0；程式碼與資料授權分開。
- 著作標示：https://www.openstreetmap.org/copyright
- 授權：https://opendatacommons.org/licenses/odbl/1-0/
- 淡水信義線：https://www.openstreetmap.org/relation/5378981
- 高鐵：https://www.openstreetmap.org/relation/4500369 （2026-09-28 擷取的快照，按南港→左營建置）
- 山手線：https://www.openstreetmap.org/relation/5376382
- JR京都線：https://www.openstreetmap.org/relation/5329254
- 琵琶湖線：https://www.openstreetmap.org/relation/5331507
- 湖西線：https://www.openstreetmap.org/relation/1832686
- 御堂筋線：https://www.openstreetmap.org/relation/2411153
- 其他新來源於 2026-09-29 擷取；每份 JSON 內保留來源 metadata。

生成方式：以 OSM 軌道圖取得沿站序的連續路徑；一般折線簡化 2 m。山手線與京都／湖西走廊為處理多股軌道連通，以 10 m 範圍近鄰節點合併建立近似中心線，折線簡化 5 m，不代表實際道岔接線。再以直線與相切圓弧近似，並以 5 m 容許偏差作解析幾何簡化；JSON 的 analytic_simplification 記錄段數與站點位移。此 5 m 僅指最後一步相對前一步的偏差，不代表相對現地的總精度。兩端加 300 m 模擬緩衝，站點投影至近似中心線。

高程為 0 m 佔位、全站停靠、月台長度由車型自動决定；使用者可改為過站。尚未加入真實橋隧、坡度、道岔、號誌及營運限速。廣慈/奉天宮依擷取的 OSM 站點與軌道納入，本資料不作即時營運公告。

站序參考：
- JR東日本山手線：https://media.jreast.co.jp/articles/1214
- JR西日本路線圖：https://www.westjr.co.jp/travel-information/tc/plan-your-trip/routes-schedule/
- Osaka Metro：https://subway.osakametro.co.jp/
- 台灣高鐵：https://www.thsrc.com.tw/
- 臺北捷運工程局信義線東延段：https://www.dorts.gov.taipei/News_Content.aspx?n=E73B716AC6156318&s=B80AA837DB7D5D87

---

# OSM 路線包（0.1.4.2）

以下 7 個 JSON 位於 `routes/osm/`。每條路線的整體限速、區段限速、月台長度、抵達秒數都留白。

## 使用方法

1. 啟動新版，在駕駛室先選車型。
2. 在路線工坊匯入 `routes/osm/` 中的 JSON。
3. 選時刻難度，按「自動計算空白抵達秒數」，再按「套用／試駕」。
4. 日本通勤／地下鐵線可先用 C381 或 EMU3000 模擬；這不是實車車型重建。
5. 全部設為停站，可自行切換過站；月台長度交由車型與模式決定。
6. 已設定起始站 S，可直接切換反向班次。更換車型後若要重排既有時刻，請清空抵達秒數再計算。

| 檔名 | 範圍 | 站數（含起始站） | 遊戲軌道長度 | OSM 來源 |
|---|---|---:|---:|---|
| JR大阪環狀線_一圈.json | 大阪 → 大阪 | 20 | 22.34 km | [relation 1864758](https://www.openstreetmap.org/relation/1864758) |
| 台北捷運板南線.json | 頂埔 → 南港展覽館 | 23 | 27.24 km | [relation 9437776](https://www.openstreetmap.org/relation/9437776) |
| 台灣高鐵_台中至南港.json | 台中 → 南港 | 7 | 170.56 km | [relation 4500369](https://www.openstreetmap.org/relation/4500369) |
| 東京地下鐵丸之內線.json | 荻窪 → 池袋 | 25 | 24.82 km | [relation 443282](https://www.openstreetmap.org/relation/443282) |
| 東京地下鐵銀座線.json | 浅草 → 渋谷 | 19 | 14.78 km | [relation 443281](https://www.openstreetmap.org/relation/443281) |
| 都營淺草線.json | 西馬込 → 押上〈スカイツリー前〉 | 20 | 18.94 km | [relation 3302734](https://www.openstreetmap.org/relation/3302734) |
| 高雄捷運紅線.json | 小港 → 岡山車站 | 25 | 30.54 km | [relation 4174828](https://www.openstreetmap.org/relation/4174828) |

大阪環狀線為 19 個不同車站，起終點大阪重複列入，完成一圈即結束，沒有無限循環。

## 精度與地形

- 來源為 2026-09-28 取得的 OpenStreetMap 軌道節點與站點；先以約 2 m 容差簡化折線，再以相切直線／圓弧近似。不是鐵路工程線形或官方里程。
- 曲線半徑為幾何近似，系統算出的限速是遊戲值，不是實際營運限速；地圖節點誤差可能造成較急的局部曲線，可在工坊調整。
- 每條路線首尾各附加約 300 m 遊戲緩衝直線，供長編組及反向班次使用；不是實際止擋或真實延伸軌道。表內長度包含緩衝段。
- 軌道高程與地形暫設為 0 m，模式為貼地；未重建真實橋梁、隧道、坡度、號誌、道岔與月台長度。請依 TERRAIN_WORKFLOW.md 匯入 DEM，再編修轨道高程。
- 台灣高鐵僅台中至南港；本包未加入山手線，以避免來源轉轍区造成的錯誤折返。

## 來源及授權

© OpenStreetMap contributors。原始資料與衍生路線資料適用 Open Database License（ODbL）1.0。

- https://www.openstreetmap.org/copyright
- https://opendatacommons.org/licenses/odbl/1-0/
- 本包 `routes/osm/source_data/` 附用於製作的 OSM relation 原始快照。
- 每個路線 JSON 的 `source` 保留 relation 網址、取得日期、授權與簡化說明；站點的 `osm_node` 保留來源節點 ID。
- 遊戲程式與 OSM 資料分開；上述 ODbL 說明適用於地圖資料。
