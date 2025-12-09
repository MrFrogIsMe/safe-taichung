# AI 對話紀錄 - SafeTaichung 專案開發

**專案名稱**：台中安全路線導航 SafeTaichung
**使用工具**：Claude Code (claude.ai/code)
**記錄日期**：2025-12-09

---

## 目錄

0. [事前預備、搜集資料集](#0-事前預備搜集資料集)
1. [初始 Prompt 與資料分析需求](#1-初始-prompt-與資料分析需求)
2. [資料清理與探索性分析](#2-資料清理與探索性分析)
3. [風險指標計算與發現](#3-風險指標計算與發現)
4. [地理編碼與座標驗證](#4-地理編碼與座標驗證)
5. [Streamlit 應用開發](#5-streamlit-應用開發)

---

## 0. 事前預備、搜集資料集

### 事前的資料預備

交由 Comet / Perplexity AI 進行台中的竊盜資料蒐集，以及可行的主題方向建議。

[對話連結](https://www.perplexity.ai/search/qi-mo-zhuan-an-da-gang-tai-zho-DHqisjnaSTejB5ztxSMaNA#0)

### 下一步

將主題方向以及數據資料交由 Claude Code 進行地理編碼與 Streamlit 開發。

---

## 1. 初始 Prompt 與資料分析需求

### User 初始請求

> 我想做一個台中市犯罪分析的專題，結合 SDG 11（永續城市）和 SDG 16（和平正義）。
>
> 資料來源是台中市政府開放資料平台的竊盜逐案資料（105-108 年），包含：
> - 機車竊盜
> - 汽車竊盜
> - 住宅竊盜
> - 自行車竊盜
>
> 希望能：
> 1. 分析各行政區的犯罪趨勢
> 2. 計算風險指標（考慮人口校正）
> 3. 做出視覺化圖表
> 4. 最後開發一個安全路線導航的 prototype

### Claude 回應

了解！這是一個結合開放資料分析與應用開發的專題。我會按以下步驟進行：

1. **資料清理**：讀取 CSV、標準化欄位、處理日期時間
2. **探索性分析**：年度趨勢、時段分布、行政區統計
3. **風險指標**：計算每萬人竊盜率，避免人口大區的生態謬誤
4. **視覺化**：繪製趨勢圖、分布圖、熱力圖
5. **應用開發**：Streamlit 互動式儀表板

---

## 2. 資料清理與探索性分析

### User 請求

> 幫我讀取 data/raw 裡面的 CSV 檔案，清理資料並做 EDA

### Claude 執行

**資料讀取結果：**

```
機車竊盜：1,375 筆
住宅竊盜：718 筆
汽車竊盜：636 筆
自行車竊盜：557 筆
總計：3,286 筆
```

**資料清理步驟：**

```python
# 民國年轉西元年
def convert_roc_date(date_val):
    date_str = str(int(date_val)).zfill(7)  # 1050102
    roc_year = int(date_str[:3])            # 105
    month = int(date_str[3:5])              # 01
    day = int(date_str[5:7])                # 02
    return pd.Timestamp(year=roc_year + 1911, month=month, day=day)

# 時間轉小時
def extract_hour(time_val):
    time_str = str(int(time_val)).zfill(4)  # 1530
    return int(time_str[:2])                 # 15
```

**行政區解析：**

```python
TAICHUNG_DISTRICTS = [
    '中區', '東區', '西區', '南區', '北區', '西屯區', '北屯區', '南屯區',
    '豐原區', '大里區', '太平區', '清水區', '沙鹿區', '大甲區', '東勢區',
    '梧棲區', '烏日區', '神岡區', '大肚區', '大雅區', '后里區', '霧峰區',
    '潭子區', '龍井區', '外埔區', '和平區', '石岡區', '大安區', '新社區'
]

def extract_district(location):
    for district in TAICHUNG_DISTRICTS:
        if district in str(location):
            return district
    return '其他'
```

### 分析結果

**年度趨勢：**

| 年份 | 案件數 | 變化 |
|------|--------|------|
| 2016 | 1,143 | - |
| 2017 | 1,102 | -3.6% |
| 2018 | 792 | -28.1% |
| 2019 | 249 | -68.6% |

**時段分布發現：**

- 凌晨 2-6 點：竊盜高峰（尤其機車、汽車）
- 中午 12 點：住宅竊盜高峰
- 傍晚 18 點：自行車竊盜高峰

**行政區分布（依總件數）：**

| 排名 | 行政區 | 案件數 |
|------|--------|--------|
| 1 | 西屯區 | 344 |
| 2 | 北區 | 331 |
| 3 | 北屯區 | 267 |
| 4 | 豐原區 | 229 |
| 5 | 東區 | 192 |

---

## 3. 風險指標計算與發現

### User 請求

> 單純看案件數不太公平，人口多的區域本來就會比較多。可以計算每萬人竊盜率嗎？

### Claude 回應

這是很好的觀察！直接比較總件數會產生「生態謬誤」（ecological fallacy）。我來加入人口校正。

**每萬人竊盜率計算：**

```python
# 載入人口資料
population_df = pd.read_csv('data/processed/district_population.csv')

# 計算每萬人竊盜率
district_with_pop['theft_per_10k'] = (
    district_with_pop['total_cases'] / district_with_pop['population'] * 10000
).round(2)
```

### 重要發現

**人口校正後的排名完全不同：**

| 排名 | 行政區 | 總件數 | 人口 | 每萬人竊盜率 |
|------|--------|--------|------|--------------|
| 1 | **中區** | 105 | 18,514 | **56.71** |
| 2 | 東區 | 192 | 76,175 | 25.21 |
| 3 | 北區 | 331 | 147,557 | 22.43 |
| 4 | 西屯區 | 344 | 228,630 | 15.05 |
| 5 | 西區 | 162 | 115,698 | 14.00 |

**關鍵洞察：**

> 中區雖然總件數只排第 13 名（105 件），但因為人口最少（僅 1.8 萬人），每萬人竊盜率高達 56.71，是第二名東區的 2.25 倍，是真正的高風險區。

這說明了**人口校正對風險評估的重要性**。

### 風險等級分類

```python
# 使用三分位數分類
q33 = summary['cases_per_10k'].quantile(0.33)
q67 = summary['cases_per_10k'].quantile(0.67)

summary['risk_level'] = summary['cases_per_10k'].apply(
    lambda x: 'low' if x <= q33 else ('medium' if x <= q67 else 'high')
)
```

| 風險等級 | 每萬人竊盜率 | 行政區數 |
|----------|--------------|----------|
| 高 | > 12.5 | 10 |
| 中 | 6.5 - 12.5 | 10 |
| 低 | < 6.5 | 9 |

---

## 4. 地理編碼與座標驗證

### User 請求

> 我想在地圖上顯示犯罪點位，需要把地址轉成經緯度

### Claude 執行

使用 Nominatim API（OpenStreetMap）進行地理編碼：

```python
from geopy.geocoders import Nominatim

geolocator = Nominatim(user_agent="safe_taichung_research")

def geocode_address(address):
    location = geolocator.geocode(address, timeout=10)
    if location:
        return location.latitude, location.longitude
    return None, None
```

### 問題發現

> 地理編碼完成後，發現 106 筆座標錯誤，位置跑到日本、台北、中國等地區！

**原因分析：**

Nominatim 會匹配相似的路名到其他國家/城市。例如：
- 「中山路」可能匹配到日本的中山路
- 「民生路」可能匹配到台北的民生路

### 解決方案

加入台中市邊界驗證：

```python
TAICHUNG_BOUNDS = {
    'lat_min': 24.0, 'lat_max': 24.5,
    'lon_min': 120.4, 'lon_max': 121.1
}

def is_in_taichung(lat, lon):
    return (TAICHUNG_BOUNDS['lat_min'] <= lat <= TAICHUNG_BOUNDS['lat_max'] and
            TAICHUNG_BOUNDS['lon_min'] <= lon <= TAICHUNG_BOUNDS['lon_max'])
```

### 最終結果

| 定位方式 | 筆數 | 比例 |
|----------|------|------|
| 精確定位 (geocoded) | 2,388 | 72.7% |
| 區域隨機 (jittered) | 898 | 27.3% |

---

## 5. Streamlit 應用開發

### 開發過程摘要

後續的 Streamlit 應用開發包含以下功能，詳細程式碼請參考 `app.py`：

| 功能 | 說明 |
|------|------|
| 首頁 | Canva 簡報嵌入、SDG 說明、快速導覽 |
| 資料分析 | EDA 圖表展示 |
| 安全路線規劃 | Google Maps API 整合、犯罪熱點疊加 |
| 治安風險地圖 | 行政區風險等級視覺化 |
| 犯罪熱點地圖 | Folium 熱力圖 |

### 主要技術整合

- **Google Maps Directions API**：真實道路導航
- **Folium HeatMap**：犯罪熱點視覺化
- **Streamlit Secrets**：API Key 安全管理

### Git Commit 紀錄

| Commit | 說明 |
|--------|------|
| `feat: add SDG images` | 加入 SDG 圖片 |
| `fix: dark mode compatibility` | 修復 dark mode |
| `feat: add custom logo` | 加入自訂 Logo |
| `feat: redesign homepage` | 首頁重新設計 |

---

## 分析結論

### 主要發現

1. **治安持續改善**：105-108 年竊盜案件下降 78%，與官方統計一致
2. **人口校正很重要**：中區每萬人竊盜率 56.7，是西屯區的 3.8 倍
3. **時段風險差異**：凌晨時段風險最高，白天相對安全

### 風險指標公式

```
每萬人竊盜率 = 總件數 / 人口 × 10,000
時段風險分數 = 該時段案件數 / (全日案件數 / 24)
路線風險分數 = Σ(區域風險 × 時段風險) / 經過區數
```

### 研究限制

1. 開放資料僅涵蓋四類竊盜，約佔官方統計的 20%
2. 資料時間範圍為 105-108 年，較近期資料尚未開放
3. 風險分數為相對指標，實際治安仍以官方資訊為準
