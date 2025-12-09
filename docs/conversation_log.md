# AI 對話紀錄 - SafeTaichung 專案開發

**專案名稱**：台中安全路線導航 SafeTaichung
**使用工具**：Claude Code (claude.ai/code)
**記錄日期**：2025-12-09

---

## 目錄

1. [地理編碼與資料驗證](#1-地理編碼與資料驗證)
2. [Google Maps API 研究與整合](#2-google-maps-api-研究與整合)
3. [Streamlit 路線導航功能](#3-streamlit-路線導航功能)
4. [犯罪熱點疊加與 HTML 修復](#4-犯罪熱點疊加與-html-修復)
5. [Streamlit Cloud 部署設定](#5-streamlit-cloud-部署設定)
6. [SDG 圖片整合](#6-sdg-圖片整合)
7. [Dark Mode 相容性修復](#7-dark-mode-相容性修復)
8. [Logo 設計與整合](#8-logo-設計與整合)
9. [首頁重新設計與 Canva 嵌入](#9-首頁重新設計與-canva-嵌入)

---

## 1. 地理編碼與資料驗證

### 背景
專案需要將竊盜案件的地址轉換為經緯度座標，以便在地圖上顯示。使用 Nominatim API 進行地理編碼。

### 問題發現
地理編碼完成後，發現 **106 筆座標錯誤**，位置跑到日本、台北、中國等地區。原因是 Nominatim 會匹配相似的路名到其他國家/城市。

### 解決方案

**User**: （發現座標問題後）

**Claude**: 在 `src/geocoder.py` 中加入台中市邊界驗證：

```python
# 台中市邊界範圍
TAICHUNG_BOUNDS = {
    'lat_min': 24.0, 'lat_max': 24.5,
    'lon_min': 120.4, 'lon_max': 121.1
}

def is_in_taichung(lat: float, lon: float) -> bool:
    """檢查座標是否在台中市範圍內"""
    return (TAICHUNG_BOUNDS['lat_min'] <= lat <= TAICHUNG_BOUNDS['lat_max'] and
            TAICHUNG_BOUNDS['lon_min'] <= lon <= TAICHUNG_BOUNDS['lon_max'])
```

### 結果
- 清理無效快取後重新編碼
- 最終結果：2,388 筆精確定位 (72.7%)，898 筆使用 jittered 座標 (27.3%)

---

## 2. Google Maps API 研究與整合

### User 請求
> 完成了嗎？那就請你研究使用 google map api

### Claude 研究結果

**Google Maps API 定價與免費額度：**
- 每月 $200 美元免費額度
- Geocoding API：$5/1000 次 → 約 40,000 次免費
- Directions API：$5/1000 次 → 約 40,000 次免費
- 新帳號有 $300 試用額度（90 天）

**建立整合模組 `src/google_maps.py`：**

```python
import googlemaps
import os
from dotenv import load_dotenv

load_dotenv()

def _get_api_key() -> str | None:
    """取得 API Key（支援 .env 和 Streamlit Secrets）"""
    api_key = os.getenv('GOOGLE_MAPS_API_KEY')
    if api_key:
        return api_key
    try:
        import streamlit as st
        if hasattr(st, 'secrets') and 'GOOGLE_MAPS_API_KEY' in st.secrets:
            return st.secrets['GOOGLE_MAPS_API_KEY']
    except Exception:
        pass
    return None

def geocode(address: str) -> dict | None:
    """地理編碼：地址 → 經緯度"""
    api_key = _get_api_key()
    if not api_key:
        return None
    gmaps = googlemaps.Client(key=api_key)
    result = gmaps.geocode(address, language='zh-TW')
    if result:
        location = result[0]['geometry']['location']
        return {
            'lat': location['lat'],
            'lng': location['lng'],
            'formatted_address': result[0]['formatted_address']
        }
    return None

def get_directions(origin: str, destination: str, mode: str = 'walking') -> dict | None:
    """取得路線規劃"""
    api_key = _get_api_key()
    if not api_key:
        return None
    gmaps = googlemaps.Client(key=api_key)
    result = gmaps.directions(origin, destination, mode=mode, language='zh-TW')
    if result:
        route = result[0]
        leg = route['legs'][0]
        return {
            'distance': leg['distance']['text'],
            'duration': leg['duration']['text'],
            'steps': leg['steps'],
            'polyline': route['overview_polyline']['points']
        }
    return None

def decode_polyline(polyline_str: str) -> list[tuple[float, float]]:
    """解碼 Google Maps polyline 為座標列表"""
    # ... polyline 解碼邏輯
```

**新增檔案：**
- `src/google_maps.py` - Google Maps API 模組
- `.env.example` - API Key 設定範本
- 更新 `.gitignore` 加入 `.env`

---

## 3. Streamlit 路線導航功能

### User 請求
> ok（表示要整合真實導航）

### 問題
原本的路線規劃只是在地圖上畫直線，不是真正的道路導航。

### Claude 實作

**在 `app.py` 中整合 Google Maps Directions API：**

```python
def create_route_map(origin_name, dest_name, route_result, google_route=None, show_crimes=True):
    """建立路線地圖，支援真實道路導航"""

    # 如果有 Google 路線，使用真實道路
    if google_route and 'polyline' in google_route:
        from src.google_maps import decode_polyline
        route_coords = decode_polyline(google_route['polyline'])
        folium.PolyLine(
            route_coords,
            color='#4285F4',  # Google Maps 藍色
            weight=5,
            opacity=0.8
        ).add_to(m)
```

**導航步驟顯示：**
```python
if google_route:
    st.success(f"📍 路線規劃成功！")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("總距離", google_route['distance'])
    with col2:
        st.metric("預估時間", google_route['duration'])
    with col3:
        st.metric("移動方式", travel_mode_display)

    # 顯示導航步驟
    with st.expander("📝 詳細導航步驟"):
        for i, step in enumerate(google_route['steps'], 1):
            instruction = step['html_instructions']
            # 清理 HTML 標籤
            instruction = instruction.replace('<wbr/>', '').replace('<wbr>', '')
            st.markdown(f"{i}. {instruction}")
```

---

## 4. 犯罪熱點疊加與 HTML 修復

### User 請求
> 我想要再安全路線上顯示附近的風險或犯罪熱度

同時回報問題：
> 然後這個<wbr/>是什麼 = =

### Claude 分析

**`<wbr/>` 問題：**
這是 HTML 的「可選換行點」(Word Break Opportunity) 標籤，Google Maps API 回傳的導航指示中包含此標籤，用於提示瀏覽器可以在此處換行。

**修復：**
```python
instruction = step['html_instructions']
instruction = instruction.replace('<wbr/>', '').replace('<wbr>', '')
```

**犯罪熱點疊加實作：**
```python
def create_route_map(origin_name, dest_name, route_result, google_route=None, show_crimes=True):
    # ... 建立地圖

    # 計算路線緩衝區（800m）
    if show_crimes and route_coords:
        lats = [c[0] for c in route_coords]
        lons = [c[1] for c in route_coords]
        buffer = 0.008  # 約 800 公尺

        lat_min, lat_max = min(lats) - buffer, max(lats) + buffer
        lon_min, lon_max = min(lons) - buffer, max(lons) + buffer

        # 篩選路線附近的犯罪點位
        nearby_crimes = crime_data[
            (crime_data['latitude'] >= lat_min) &
            (crime_data['latitude'] <= lat_max) &
            (crime_data['longitude'] >= lon_min) &
            (crime_data['longitude'] <= lon_max)
        ]

        # 加入熱力圖
        if len(nearby_crimes) > 0:
            heat_data = nearby_crimes[['latitude', 'longitude']].values.tolist()
            HeatMap(
                heat_data,
                radius=20,
                blur=15,
                gradient={'0.4': 'yellow', '0.65': 'orange', '1': 'red'}
            ).add_to(m)
```

---

## 5. Streamlit Cloud 部署設定

### User 請求
> 移除標記！！要怎麼在部署 stramlit 加上.env?

### Claude 說明

**Git Commit 簽名移除：**
已從 commit message 中移除：
```
🤖 Generated with [Claude Code](https://claude.com/claude-code)
Co-Authored-By: Claude <noreply@anthropic.com>
```

**Streamlit Cloud Secrets 設定：**

1. 進入 Streamlit Cloud 專案設定
2. 點擊 "Secrets" 區塊
3. 加入以下內容：
```toml
GOOGLE_MAPS_API_KEY = "你的_API_KEY"
```

**修改 `src/google_maps.py` 支援兩種來源：**
```python
def _get_api_key() -> str | None:
    """取得 API Key（支援 .env 和 Streamlit Secrets）"""
    # 優先使用環境變數 (.env)
    api_key = os.getenv('GOOGLE_MAPS_API_KEY')
    if api_key:
        return api_key

    # 其次使用 Streamlit Secrets
    try:
        import streamlit as st
        if hasattr(st, 'secrets') and 'GOOGLE_MAPS_API_KEY' in st.secrets:
            return st.secrets['GOOGLE_MAPS_API_KEY']
    except Exception:
        pass

    return None
```

---

## 6. SDG 圖片整合

### User 請求
> 幫我在介紹頁面加上 sdg 的圖片
> 也幫我整理到一個資料夾中

**User 上傳了兩張圖片：**
- SDG 11（永續城市與社區）
- SDG 16（和平、正義與健全制度）

### Claude 實作

**檔案整理：**
```bash
# 建立資料夾並移動圖片
mkdir -p assets/images/
mv sdg11_screenshot.png assets/images/sdg11.png
mv sdg16_screenshot.png assets/images/sdg16.png
```

**在 `show_about()` 中加入圖片：**
```python
# SDG 圖片並排顯示
col1, col2 = st.columns(2)
with col1:
    st.image("assets/images/sdg11.png", use_container_width=True)
with col2:
    st.image("assets/images/sdg16.png", use_container_width=True)
```

**Git Commit：**
```
feat: add SDG 11 and 16 images to about page
```

---

## 7. Dark Mode 相容性修復

### User 回報問題
> 修復 dark mode，快速導覽的選項背景顏色與字體顏色重疊，看不到字

（附上截圖顯示卡片文字被吃掉）

### Claude 分析

**問題原因：**
- 卡片使用硬編碼的淺色背景（`#e8f5e9`、`#e3f2fd`、`#fff3e0`）
- 但沒有指定文字顏色，導致繼承 Streamlit 主題色
- Dark mode 下主題文字是白色 → 淺色背景 + 白色文字 = 看不見

### 修復

**修改前：**
```html
<div style="background: #e8f5e9; padding: 20px; border-radius: 10px; text-align: center;">
    <h3>📈 資料分析</h3>
    <p>查看完整的 EDA 圖表與統計結果</p>
</div>
```

**修改後：**
```html
<div style="background: #e8f5e9; padding: 20px; border-radius: 10px; text-align: center; color: #1a1a1a;">
    <h3 style="color: #2e7d32; margin: 0 0 8px 0;">📈 資料分析</h3>
    <p style="color: #333; margin: 0;">查看完整的 EDA 圖表與統計結果</p>
</div>
```

**Git Commit：**
```
fix: add explicit text colors for dark mode compatibility
```

---

## 8. Logo 設計與整合

### User 請求
> 幫我生一個 prompt，我丟給 gemini banana pro 生成一個專屬於網頁的 logo，請你寫出詳盡的描述，契合這個專案，簡易卡通風格，用英文生成 prompt，若圖中要有文字，請寫繁體中文

### Claude 生成的 Prompt

```
A simple flat cartoon-style logo for a web application called "SafeTaichung".

The design features a stylized shield shape in gradient purple-blue colors
(from #667eea to #764ba2), symbolizing safety and protection. Inside the
shield, there is a minimalist white map pin icon combined with a walking
person silhouette, representing safe route navigation.

Around or behind the shield, subtle dotted lines suggest a route path or
navigation trail. A small sparkle or checkmark near the shield indicates
safety verification.

Below or integrated with the shield, include the text "台中安全導航" in clean,
rounded Traditional Chinese font.

The overall style is modern, friendly, and minimal - similar to app icons
like Google Maps or city safety apps. Use soft shadows and clean edges.
The color palette should be calming yet trustworthy: purple (#764ba2),
blue (#667eea), white, and a touch of green (#2ecc71) for the safety checkmark.

Background should be transparent or pure white. The logo should work well
at small sizes (favicon) and large sizes (header). No complex gradients or
3D effects - keep it flat design with subtle depth.
```

### User 提供生成的 Logo
> @"assets/images/Gemini_Generated_Image_5dfjhf5dfjhf5dfj (1).png" 用這張圖

### Claude 整合

```bash
# 重新命名檔案
mv "assets/images/Gemini_Generated_Image_5dfjhf5dfjhf5dfj (1).png" assets/images/logo.png
```

**修改側邊欄（移除 emoji + 漸層方塊）：**
```python
# 原本
st.markdown("""
<div style="text-align: center; padding: 10px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 10px; margin-bottom: 10px;">
    <h1 style="color: white; margin: 0; font-size: 2em;">🛡️</h1>
    <h3 style="color: white; margin: 5px 0;">SafeTaichung</h3>
</div>
""", unsafe_allow_html=True)

# 改為
st.image("assets/images/logo.png", use_container_width=True)
```

**首頁 Logo 置中顯示：**
```python
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    st.image("assets/images/logo.png", use_container_width=True)
```

**Git Commit：**
```
feat: add custom logo to sidebar and homepage
```

---

## 9. 首頁重新設計與 Canva 嵌入

### User 請求
> https://www.canva.com/design/DAG6VHyKleU/FkzpZ_51nfX0rtUcZ_63vw/view
> （提供 Canva embed code）
> 幫我完成 canva 嵌入
>
> 我想把關於此系統放到首頁上，原因是想要讓使用者更容易看到我們的目的、sdg, 研究相關的資料

### Claude 實作

**1. Canva 簡報直接嵌入（移除手動輸入框）：**
```python
st.markdown("""
<div style="position: relative; width: 100%; height: 0; padding-top: 56.25%;
     padding-bottom: 0; box-shadow: 0 2px 8px 0 rgba(63,69,81,0.16);
     margin-top: 1.6em; margin-bottom: 0.9em; overflow: hidden;
     border-radius: 8px; will-change: transform;">
    <iframe loading="lazy"
        style="position: absolute; width: 100%; height: 100%; top: 0; left: 0; border: none; padding: 0; margin: 0;"
        src="https://www.canva.com/design/DAG6VHyKleU/FkzpZ_51nfX0rtUcZ_63vw/view?embed"
        allowfullscreen="allowfullscreen" allow="fullscreen">
    </iframe>
</div>
""", unsafe_allow_html=True)
```

**2. 整合「關於本系統」內容到首頁：**

新的首頁結構：
```
📊 首頁
├── Logo（置中）
├── 標題：計算思維與人工智慧 期末專題
├── ──────────────────
├── 📊 專題簡報（Canva 嵌入）
├── ──────────────────
├── 📌 系統目的
├── ──────────────────
├── 🚀 快速導覽（三張功能卡片）
├── ──────────────────
├── 🌍 SDG 永續發展目標連結
│   ├── SDG 11/16 圖片
│   ├── [expander] SDG 11 詳細說明
│   └── [expander] SDG 16 詳細說明
├── ──────────────────
├── 📊 資料來源（表格）
├── [expander] ⚠️ 使用說明與限制
└── [expander] 🛠️ 技術架構
```

**3. 使用 `st.expander()` 摺疊長內容：**
```python
with st.expander("📖 SDG 11：永續城市與社區", expanded=False):
    st.markdown("""
    **建構具包容、安全、韌性及永續特質的城市與鄉村**

    - **本研究將台中市竊盜逐案資料轉換為「行政區風險指標」與「安全路線建議」**
      透過將原本零散的逐案竊盜紀錄進行統計分析...
    """)
```

**4. 移除獨立的「關於本系統」頁面：**
```python
# 側邊欄選單從 6 個減為 5 個
page = st.radio(
    "選擇功能",
    ["🏠 首頁", "📈 資料分析", "🗺️ 安全路線規劃", "📊 治安風險地圖", "🔥 犯罪熱點地圖"],
    index=0
)

# 刪除 show_about() 函數
```

**Git Commit：**
```
feat: redesign homepage with Canva embed and SDG content
```

---

## 技術重點整理

### 1. Nominatim 地理編碼驗證
- 免費但可能匹配到錯誤位置
- 必須加入邊界驗證（bounding box）

### 2. Google Maps API
- 支援 Geocoding、Directions、Distance Matrix
- 每月 $200 免費額度（約 40,000 次呼叫）
- Polyline 需要解碼才能在 Folium 顯示

### 3. Streamlit 部署
- 本地用 `.env`，雲端用 `st.secrets`
- 程式碼需同時支援兩種來源

### 4. Dark Mode 相容性
- 自訂 HTML 必須明確指定 `color` 屬性
- 不要依賴主題繼承

### 5. Streamlit 排版技巧
- `st.columns([1, 2, 1])` 實現置中
- `st.expander()` 摺疊長內容
- `use_container_width=True` 讓圖片響應式

---

## Git Commit 紀錄

| Commit | 說明 |
|--------|------|
| `feat: add SDG 11 and 16 images to about page` | 加入 SDG 圖片 |
| `fix: add explicit text colors for dark mode compatibility` | 修復 dark mode 文字顏色 |
| `feat: add custom logo to sidebar and homepage` | 加入自訂 Logo |
| `feat: redesign homepage with Canva embed and SDG content` | 首頁重新設計 |

---

## 檔案變更總覽

### 新增檔案
- `src/google_maps.py` - Google Maps API 整合模組
- `.env.example` - API Key 設定範本
- `assets/images/logo.png` - 專案 Logo
- `assets/images/sdg11.png` - SDG 11 圖示
- `assets/images/sdg16.png` - SDG 16 圖示
- `docs/AI_conversation_log.md` - 本對話紀錄

### 修改檔案
- `app.py` - Streamlit 主應用程式（多處修改）
- `src/geocoder.py` - 加入台中邊界驗證
- `.gitignore` - 加入 `.env`

---

*此文件由 Claude Code 自動生成，記錄 2025-12-09 的開發對話過程。*
