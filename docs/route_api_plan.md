# Google Maps 路線規劃 API 整合計畫

## 一、架構設計

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  使用者輸入      │────▶│  Google Maps API  │────▶│  風險評估模組    │
│  起點/終點/時間  │     │  取得多條路線      │     │  計算各路線分數  │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                                          │
                                                          ▼
                                                 ┌─────────────────┐
                                                 │  推薦最安全路線  │
                                                 │  + 風險比較表   │
                                                 └─────────────────┘
```

## 二、API 選擇比較

| API | 費用 | 優點 | 缺點 |
|-----|------|------|------|
| Google Maps Directions | $5/1000 req | 準確、即時路況 | 需付費、無法自訂權重 |
| OSRM (自架) | 免費 | 可自訂權重、離線 | 需自己架設、無路況 |
| OpenRouteService | 免費額度 | 有避障功能 | 速度較慢 |
| Mapbox Directions | $0.5/1000 req | 便宜、品質好 | 需註冊 |

## 三、路線風險計算邏輯

### 3.1 解碼路線座標

Google Maps 回傳的路線是 encoded polyline，需要解碼：

```python
import polyline

# Google Maps API 回傳的 encoded polyline
encoded = "mz~aGcf_fV..."

# 解碼為座標列表
coords = polyline.decode(encoded)
# [(24.1436, 120.6794), (24.1440, 120.6798), ...]
```

### 3.2 座標對應行政區

```python
from shapely.geometry import Point, Polygon

def get_district_for_point(lat, lon, district_polygons):
    """判斷座標落在哪個行政區"""
    point = Point(lon, lat)
    for district, polygon in district_polygons.items():
        if polygon.contains(point):
            return district
    return find_nearest_district(lat, lon)  # fallback
```

### 3.3 計算路線風險分數

```python
def calculate_route_risk(route_coords, departure_hour):
    """
    計算整條路線的風險分數

    方法：將路線切成小段，計算每段經過的行政區風險，
    以距離加權平均
    """
    segment_risks = []

    for i in range(len(route_coords) - 1):
        start = route_coords[i]
        end = route_coords[i + 1]

        # 計算這段的距離（公尺）
        distance = haversine(start, end)

        # 判斷這段在哪個行政區
        mid_point = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
        district = get_district_for_point(*mid_point)

        # 取得該區域 + 時段的風險分數
        risk = get_risk_score(district, departure_hour)

        segment_risks.append({
            'distance': distance,
            'risk': risk,
            'district': district
        })

    # 以距離加權平均
    total_distance = sum(s['distance'] for s in segment_risks)
    weighted_risk = sum(s['distance'] * s['risk'] for s in segment_risks)

    return weighted_risk / total_distance if total_distance > 0 else 0
```

## 四、實作步驟

### Phase 1: 基礎版（使用 Google Maps API）

1. **申請 API Key**
   - 到 Google Cloud Console 建立專案
   - 啟用 Directions API
   - 設定 API 金鑰限制

2. **實作路線請求**
   ```python
   import googlemaps

   gmaps = googlemaps.Client(key='YOUR_API_KEY')

   result = gmaps.directions(
       origin="台中車站",
       destination="逢甲夜市",
       mode="driving",
       alternatives=True,  # 取得替代路線
       departure_time=datetime.now()
   )
   ```

3. **解析並評分路線**
   - 解碼每條路線的 polyline
   - 計算風險分數
   - 排序推薦

### Phase 2: 進階版（避開高風險區）

1. **使用 waypoints 引導路線**
   ```python
   # 如果直接路線經過高風險區，加入中繼點引導繞行
   safe_waypoints = find_safe_waypoints(origin, destination, avoid_districts=['中區'])

   result = gmaps.directions(
       origin=origin,
       destination=destination,
       waypoints=safe_waypoints,
       optimize_waypoints=True
   )
   ```

2. **或使用 OSRM 自訂權重**
   ```lua
   -- OSRM profile 設定
   -- 對高風險區域增加通行成本
   function process_way(profile, way, result)
       local district = get_district(way)
       local risk_factor = get_risk_factor(district)

       -- 風險越高，成本越高（速度越慢）
       result.forward_speed = base_speed / risk_factor
   end
   ```

## 五、免費替代方案

如果不想付費使用 Google Maps：

### 選項 A: OpenRouteService API

```python
import openrouteservice

client = openrouteservice.Client(key='YOUR_ORS_KEY')

routes = client.directions(
    coordinates=[[120.6869, 24.1369], [120.6456, 24.1789]],
    profile='driving-car',
    format='geojson',
    alternative_routes={'target_count': 3}
)
```

### 選項 B: 簡化版（不需要 API）

```python
# 使用預先定義的路線模板
ROUTE_TEMPLATES = {
    ('台中車站', '逢甲夜市'): {
        'route_a': ['中區', '北區', '西屯區'],  # 最短
        'route_b': ['東區', '北屯區', '西屯區'],  # 繞行
    }
}
```

## 六、成本估算

### Google Maps Directions API

| 用量 | 費用 |
|------|------|
| 0-100,000 次/月 | 每 1000 次 $5 |
| 100,000-500,000 次/月 | 每 1000 次 $4 |

免費額度：每月 $200 credit ≈ 40,000 次請求

### 預估專題需求

- Demo 展示：~100 次
- 測試開發：~500 次
- **結論：免費額度絕對夠用**

## 七、限制與注意事項

1. **無法強制禁止通過某區**
   - Google Maps 會優先考慮時間/距離
   - 只能透過 waypoints 間接引導

2. **替代路線不一定存在**
   - 某些起終點只有一條合理路線
   - 繞行可能大幅增加時間

3. **即時路況 vs 犯罪風險**
   - API 考慮的是交通，不是治安
   - 需要我們自己加上風險評估層

4. **API 請求限制**
   - 有 QPS 限制（每秒請求數）
   - 需要做 client-side caching
