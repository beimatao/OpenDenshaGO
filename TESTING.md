# 0.1.6 驗證

`python -m unittest discover -s tests`：95 項全數通過，含 Rasterio DTM 測試，無跳過。
`npm test`：75 項模擬 DOM 操作，以及幾何、高程、起點延伸回歸測試通過。

新增驗證：同向彎道入口最低速、反向彎道分組、短暫提速實際限制、全車通過解限、中間站双向定位、站點順序與識別、終點折返的時間和成績、山手線雙向下一圈、五條新路線雙向載入、固定高程簡化與站點保持、500 m 上限、起點選單與續行按鈕請求。

Linux Python/Node 執行環境；尚未在實體 Windows 瀏覽器進行視覺與操作測試。

# OpenDenshaGO 0.1.5.1 驗證

已通過：73 項 Python unittest、13 組既有幾何檢查及起點延伸測試、63 項模擬 DOM 事件檢查。

執行方式：

```
python -m unittest discover -s tests
npm install
npm test
```

一般遊戲無須 npm。TIFF 測試需要 requirements-dtm.txt；本次使用 Rasterio 1.5.1，在 Linux 上產生合成 GeoTIFF 並驗證。沒有安裝 Rasterio 時，TIFF 相關測試會 skip，不能據此宣稱已驗證 TIFF 功能。

涵蓋：EPSG:4326 與 EPSG:3826 轉換、雙線性插值、波段 scale/offset、英尺轉公尺、NoData、覆蓋不足、缺 CRS、RGB 拒絕、HTTP 原始二進位上傳及一次性票據。平滑測試包含尖峰衰減、線性坡度保留、採樣密度獨立性、原始高程保留。簡化測試包含直線與圓弧合併、7 條 OSM 路線、站點位置、手動限速及高度模式保護。介面驗證包含預覽不改資料、套用、取消、復原和過期預覽拒絕。

限制：未做 Windows 實機瀏覽器、Windows 一鍵安裝器、多 GB 真實 TIFF 壓力測試，也未在使用者的 QGIS 安裝日本 DEM 插件。未核驗實際日本圖幅的垂直基準轉換；程式本身不執行垂直基準轉換。
