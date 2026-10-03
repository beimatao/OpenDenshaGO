# 路線地面高程取得與 CSV 回匯（0.1.4）

遊戲需要的是沿路線的「地面高程縱斷面」：s 是路線水平累計里程（m），z 是該處地面高程（m）。等高線則是同高地點連成的平面曲線。僅有你畫的路線經緯度不能推算真實地面高度，必須另外有 DEM／DTM 高程資料。

## Google Earth Pro：查看路線與高程剖面

1. 在工坊展開「地形高程交換」，按「匯出路線 KML」。
2. 在 Google Earth Pro 電腦版開啟 KML，在地點清單中選取路徑，使用「顯示高程剖面」。
3. 本版 KML 使用 clampToGround 貼地显示；檔案裡的 0 是佔位值，不是實際地面海拔。
4. 顯示高程剖面不代表另存 KML 就會附上整條路徑的真實高程。本版不把這種 KML 的零值當成 DEM，也不提供 Google Earth 地形擷取器。

Google 官方說明：
https://support.google.com/earth/answer/148134?hl=zh-Hant
https://support.google.com/earth/answer/148150?hl=zh-Hant

## QGIS + DEM：取得數值再回匯

1. 準備涵蓋整條路線的 DEM／DTM，例如你有使用權的地形 GeoTIFF。請確認高程單位是公尺，且垂直基準與路線絕對高程一致。DSM 可能包含建築或樹木高度，地面路線通常應使用地形高程。
2. 工坊輸入採樣間距，預設 25 m，按「匯出 DEM 採樣點 GeoJSON」。檔案包含 Point 幾何、sample_id 與 s 欄，沒有假造 z。座標為 WGS84 經緯度。
3. 在 QGIS 加入 GeoJSON 和 DEM。需要時將點圖層重投影至 DEM 的座標系統，保留 s 欄。
4. 開啟處理工具箱，搜尋 **Sample raster values（取樣網格值）**。Input layer 選採樣點，Raster layer 選 DEM；輸出欄名前綴保留 SAMPLE_。這項工具會依採樣位置取出網格數值；單波段高程通常會得到 SAMPLE_1。
5. 將採樣結果圖層匯出成 UTF-8 CSV，保留 **s** 與 **SAMPLE_1**。不用自己重算里程，也不要改用外部工具沿折線重新累計的距離，以免與遊戲圓弧里程不同。
6. 回到工坊按「轉換 DEM 採樣 CSV」。若欄名不同，先填「CSV 高程欄名」，例如 dem_height。轉換器也能自動辨識 z、elevation、SAMPLE_1、rvalue_1、dem_1。
7. 程式下載「路線名稱_地形.csv」並套用地形；可使用復原。它會依 s 排序，拒絕缺值、NoData、重複里程或未涵蓋全線的資料，不會以 0 偷補缺值。
8. 檢查工坊高程圖：綠色是地面，青色是軌道。貼地／地下／高架的相對模式會隨新地形改變；絕對高程與坡道保留原設定，可能需要剪段與緩坡銜接。最後重算時刻。

QGIS 官方參考：
https://docs.qgis.org/3.44/en/docs/user_manual/processing_algs/qgis/rasteranalysis.html#sample-raster-values

採樣間距比 DEM 格網細，不會增加來源資料的真實精度。路線長、點數過多時可改用 50 或 100 m。若線形位置或里程已變更，請重新匯出採樣點，不要套回舊路線的 CSV。

## 不開遊戲也能轉換 CSV

在專案目錄執行（只需 Python 標準函式庫）：

```powershell
py terrain_tools.py "QGIS採樣結果.csv" "地形.csv" --z-column SAMPLE_1
```

輸出格式：

```csv
s,z
0,12.4
25,12.8
50,13.1
```

命令列只轉換欄位，不檢查特定路線長度；遊戲匯入時會檢查全線覆蓋。

若手中只有等高線向量資料，需先在 GIS 依已知高程建立地形表面，再沿路線採樣。不能把等高線的頂點任意排列成 s,z。這個版本提供資料交換與 CSV 轉換，沒有內建等高線插值或自動下載 DEM。

## 0.1.4.1：DEM 匯入後修整與保存

可先保存 JSON 草稿，下次直接匯入繼續編輯，無須再次取樣 DEM。高度斷點會提示段號和高差；完成坡道銜接後再重算時刻與試駕。斷面圖滾輪縮放、滑鼠拖曳橫移、Shift＋滾輪改變高程比例；放大會顯示坡度百分比，游標顯示軌道與地面高度，點擊可選取對應路段。雙擊或「全線範圍」還原。
