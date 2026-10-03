# 日本公開地面高程資料（查核：2026-09-28）

## 首選：國土地理院「基盤地圖情報・數值標高模型」

- 官方入口：https://service.gsi.go.jp/kiban/
- 地圖下載：https://service.gsi.go.jp/kiban/app/map/?search=dem
- 資料說明：https://www.gsi.go.jp/kiban/faq.html
- 規格與範圍：https://service.gsi.go.jp/kiban/app/help/

免費註冊帳號後可下載。官方稱為 DEM；說明指出已排除建物、橋、樹木等，表示地面高程，符合此處尋找裸地 DTM 的目的。橋梁軌面與地下隧道仍要另行設計。

| 資料 | 水平網格約大小 | 來源與使用方式 |
|---|---:|---|
| DEM1A | 1 m | 航空雷射，提供區域有限；需要細部地形時選用 |
| DEM5A | 5 m | 航空雷射；可先檢查東京、大阪路線沿途是否完整覆蓋 |
| DEM5B／DEM5C | 5 m | 航空照片測量；沒有 5A 時可作候選 |
| DEM10B | 10 m | 日本全域整備，以地形圖等高線等建立；適合補足未有高解析資料的區域 |

網格大小不是高程誤差。請查看各圖幅的測量年度、精度與缺值；不同來源邊界可能不一致。

## 下載後怎麼得到 TIFF

官方基盤 DEM 主要是 JPGIS（GML）／XML，以 ZIP 包裝。OpenDenshaGO 0.1.5.1 不直接解析日本 XML，也不接受把副檔名改成 .tif。

你已使用 QGIS，可透過以下由開發者維護、刊登在 QGIS 插件庫的插件：

**QuickDEM4JP**

https://plugins.qgis.org/plugins/QuickDEM4JP/

插件可將國土地理院的 XML 或含 XML 的 ZIP 轉成 DEM GeoTIFF 或 Terrain RGB。操作路徑：QGIS「插件 → 管理與安裝插件」搜尋 QuickDEM4JP；載入下載資料，選擇 **DEM GeoTIFF** 輸出。不要選 Terrain RGB。

多個圖幅可在 QGIS 使用 GDAL 的 Merge／合併網格工具合成一幅數值高程 GeoTIFF，或裁切成涵蓋路線的區域。不要用「儲存為影像」把顏色渲染結果當成 DEM。轉出後檢查圖層 CRS、NoData 與實際像素高程，再匯入遊戲。

另一個可查看的插件是 **ElevationTile4JP**：

https://plugins.qgis.org/plugins/ElevationTile4JP/

其頁面說明可依指定範圍取得國土地理院標高圖磚並轉換、合併成 DEM GeoTIFF。來源及解析度應依所選圖磚確認。本次未在你的 Windows QGIS 安裝或驗證這些插件。

## 高程基準

國土地理院下載入口標示 JGD2011→JGD2024 的變更，並說明新版已反映高程成果改定；也可能提供較舊成果。依各檔案標示及資料規格判斷，不要把所有日本資料一律指定成同一 CRS。插件轉出後尤其要核對座標系統與原資料一致。

程式僅進行水平座標轉換，不進行新舊高程成果或垂直基準的校正。請使用與路線軌面設定一致的高程基準。

## 來源註記

使用及分享衍生資料時，依國土地理院來源頁面的利用條款標示出處；「免費下載」不表示可以省略來源。範例：地形來源：國土地理院・基盤地圖情報 數值標高模型（圖幅與取得日期）。
