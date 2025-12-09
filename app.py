"""
台中安全路線導航 SafeTaichung
Streamlit 應用程式

啟動方式: streamlit run app.py
"""

import os
from pathlib import Path

import folium
import pandas as pd
import streamlit as st
from folium.plugins import HeatMap, MarkerCluster
from streamlit_folium import st_folium


# Google Maps API（如果有設定 API Key）
def _check_google_maps_available():
    """檢查 Google Maps API 是否可用"""
    # 檢查環境變數
    if os.getenv('GOOGLE_MAPS_API_KEY'):
        return True
    # 檢查 Streamlit Secrets
    try:
        if hasattr(st, 'secrets') and 'GOOGLE_MAPS_API_KEY' in st.secrets:
            return True
    except Exception:
        pass
    return False

try:
    from src.google_maps import decode_polyline, get_directions
    GOOGLE_MAPS_AVAILABLE = _check_google_maps_available()
except ImportError:
    GOOGLE_MAPS_AVAILABLE = False

# 設定頁面配置
st.set_page_config(
    page_title="台中安全路線導航 SafeTaichung",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 路徑設定
DATA_DIR = Path(__file__).parent / 'data' / 'processed'

# 台中市行政區中心座標（近似值）
DISTRICT_COORDS = {
    '中區': (24.1436, 120.6794),
    '東區': (24.1378, 120.7024),
    '西區': (24.1402, 120.6632),
    '南區': (24.1193, 120.6642),
    '北區': (24.1614, 120.6818),
    '西屯區': (24.1815, 120.6177),
    '北屯區': (24.1824, 120.6884),
    '南屯區': (24.1384, 120.6096),
    '豐原區': (24.2500, 120.7177),
    '大里區': (24.0990, 120.6778),
    '太平區': (24.1268, 120.7164),
    '清水區': (24.2639, 120.5594),
    '沙鹿區': (24.2333, 120.5667),
    '大甲區': (24.3489, 120.6222),
    '東勢區': (24.2581, 120.8272),
    '梧棲區': (24.2550, 120.5319),
    '烏日區': (24.1044, 120.6227),
    '神岡區': (24.2583, 120.6653),
    '大肚區': (24.1536, 120.5406),
    '大雅區': (24.2289, 120.6486),
    '后里區': (24.3047, 120.7114),
    '霧峰區': (24.0617, 120.7006),
    '潭子區': (24.2089, 120.7058),
    '龍井區': (24.1917, 120.5461),
    '外埔區': (24.3319, 120.6556),
    '和平區': (24.2500, 121.0000),
    '石岡區': (24.2747, 120.7806),
    '大安區': (24.3461, 120.5856),
    '新社區': (24.2333, 120.8167)
}

# 常見地標座標
LANDMARKS = {
    '台中車站': {'coords': (24.1369, 120.6869), 'district': '中區'},
    '逢甲夜市': {'coords': (24.1789, 120.6456), 'district': '西屯區'},
    '勤美誠品綠園道': {'coords': (24.1509, 120.6622), 'district': '西區'},
    '一中街商圈': {'coords': (24.1504, 120.6849), 'district': '北區'},
    '台中高鐵站': {'coords': (24.1119, 120.6156), 'district': '烏日區'},
    '東海大學': {'coords': (24.1818, 120.6004), 'district': '西屯區'},
    '中興大學': {'coords': (24.1211, 120.6753), 'district': '南區'},
    '台中科技大學': {'coords': (24.1533, 120.6817), 'district': '北區'},
    '朝馬轉運站': {'coords': (24.1633, 120.6378), 'district': '西屯區'},
    '豐原車站': {'coords': (24.2536, 120.7231), 'district': '豐原區'},
}


@st.cache_data
def load_district_risk():
    """載入行政區風險資料"""
    return pd.read_csv(DATA_DIR / 'district_risk_summary.csv', encoding='utf-8-sig')


@st.cache_data
def load_hourly_risk():
    """載入時段風險資料"""
    return pd.read_csv(DATA_DIR / 'hourly_risk_summary.csv', encoding='utf-8-sig')


@st.cache_data
def load_geocoded_crimes():
    """載入地理編碼後的犯罪資料"""
    geocoded_path = DATA_DIR / 'taichung_theft_geocoded.csv'
    if geocoded_path.exists():
        df = pd.read_csv(geocoded_path, encoding='utf-8-sig')
        df['date'] = pd.to_datetime(df['date'])
        return df
    return None


def get_risk_color(risk_level):
    """根據風險等級返回顏色"""
    colors = {
        '低': '#2ecc71',  # 綠色
        '中': '#f39c12',  # 橘色
        '高': '#e74c3c',  # 紅色
        '未知': '#95a5a6'  # 灰色
    }
    return colors.get(risk_level, '#95a5a6')


def compute_route_risk(origin_district, dest_district, hour):
    """計算路線風險（簡化版：只考慮起點和終點）"""
    district_risk = load_district_risk()
    hourly_risk = load_hourly_risk()

    districts = [origin_district, dest_district]
    if origin_district == dest_district:
        districts = [origin_district]

    results = []
    total_score = 0

    for district in districts:
        dist_row = district_risk[district_risk['district'] == district]
        if not dist_row.empty:
            cases_per_10k = dist_row.iloc[0]['cases_per_10k_pop']
            risk_level = dist_row.iloc[0]['risk_level']
        else:
            cases_per_10k = 0
            risk_level = '未知'

        hour_row = hourly_risk[
            (hourly_risk['district'] == district) &
            (hourly_risk['hour'] == hour)
        ]
        hour_score = hour_row.iloc[0]['hour_risk_score'] if not hour_row.empty else 1.0

        segment_risk = cases_per_10k * hour_score
        total_score += segment_risk

        results.append({
            'district': district,
            'cases_per_10k_pop': cases_per_10k,
            'risk_level': risk_level,
            'hour_risk_score': hour_score,
            'segment_risk': round(segment_risk, 2)
        })

    avg_score = total_score / len(districts)

    if avg_score < 15:
        route_label = '低'
    elif avg_score < 40:
        route_label = '中'
    else:
        route_label = '高'

    return {
        'route_risk_score': round(avg_score, 2),
        'route_risk_label': route_label,
        'district_risks': results
    }


def create_risk_map(district_risk_df, show_rate=True):
    """建立風險地圖"""
    m = folium.Map(
        location=[24.1477, 120.6736],
        zoom_start=11,
        tiles='cartodbpositron'
    )

    for _, row in district_risk_df.iterrows():
        district = row['district']
        if district not in DISTRICT_COORDS:
            continue

        lat, lon = DISTRICT_COORDS[district]
        risk_level = row['risk_level']
        color = get_risk_color(risk_level)

        if show_rate:
            value = row['cases_per_10k_pop']
            label = f"每萬人竊盜率: {value}"
        else:
            value = row['total_cases']
            label = f"總件數: {value}"

        # 圓圈大小根據數值調整
        radius = max(500, min(value * 50 if show_rate else value * 5, 3000))

        folium.CircleMarker(
            location=[lat, lon],
            radius=radius / 100,
            popup=f"<b>{district}</b><br>{label}<br>風險等級: {risk_level}",
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.6
        ).add_to(m)

        # 添加標籤
        folium.Marker(
            location=[lat, lon],
            icon=folium.DivIcon(
                html=f'<div style="font-size: 9px; font-weight: bold; text-align: center;">{district}</div>'
            )
        ).add_to(m)

    return m


def create_route_map(origin_name, dest_name, route_result, google_route=None, show_crimes=True):
    """建立路線地圖（支援 Google Maps 真實路線 + 犯罪熱點）"""
    origin_info = LANDMARKS.get(origin_name)
    dest_info = LANDMARKS.get(dest_name)

    if not origin_info or not dest_info:
        return None

    # 計算地圖中心與邊界
    center_lat = (origin_info['coords'][0] + dest_info['coords'][0]) / 2
    center_lon = (origin_info['coords'][1] + dest_info['coords'][1]) / 2

    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=14,
        tiles='cartodbpositron'
    )

    # 計算路線邊界框（用於篩選附近犯罪點）
    route_coords = []
    if google_route and 'polyline' in google_route:
        coords = decode_polyline(google_route['polyline'])
        route_coords = [(p['lat'], p['lng']) for p in coords]
    else:
        route_coords = [origin_info['coords'], dest_info['coords']]

    # 顯示路線附近的犯罪熱點
    if show_crimes and route_coords:
        crime_data = load_geocoded_crimes()
        if crime_data is not None:
            # 計算路線邊界框
            lats = [c[0] for c in route_coords]
            lons = [c[1] for c in route_coords]
            lat_min, lat_max = min(lats) - 0.008, max(lats) + 0.008  # 約 800m 緩衝
            lon_min, lon_max = min(lons) - 0.01, max(lons) + 0.01

            # 篩選路線附近的犯罪點
            nearby_crimes = crime_data[
                (crime_data['latitude'] >= lat_min) &
                (crime_data['latitude'] <= lat_max) &
                (crime_data['longitude'] >= lon_min) &
                (crime_data['longitude'] <= lon_max)
            ].dropna(subset=['latitude', 'longitude'])

            if len(nearby_crimes) > 0:
                # 添加熱力圖層
                heat_data = nearby_crimes[['latitude', 'longitude']].values.tolist()
                HeatMap(
                    heat_data,
                    radius=20,
                    blur=15,
                    max_zoom=15,
                    gradient={0.2: 'blue', 0.4: 'lime', 0.6: 'yellow', 0.8: 'orange', 1: 'red'}
                ).add_to(m)

    # 添加起點標記
    folium.Marker(
        location=origin_info['coords'],
        popup=f"<b>起點</b><br>{origin_name}",
        icon=folium.Icon(color='green', icon='play')
    ).add_to(m)

    # 添加終點標記
    folium.Marker(
        location=dest_info['coords'],
        popup=f"<b>終點</b><br>{dest_name}",
        icon=folium.Icon(color='red', icon='stop')
    ).add_to(m)

    # 繪製路線（在熱力圖上方）
    route_color = get_risk_color(route_result['route_risk_label'])

    if google_route and 'polyline' in google_route:
        folium.PolyLine(
            locations=route_coords,
            weight=6,
            color=route_color,
            opacity=0.9,
            popup=f"距離: {google_route['distance']['text']}<br>時間: {google_route['duration']['text']}"
        ).add_to(m)
    else:
        folium.PolyLine(
            locations=[origin_info['coords'], dest_info['coords']],
            weight=5,
            color=route_color,
            opacity=0.8,
            dash_array='10, 10',
            popup="簡化路線（非實際道路）"
        ).add_to(m)

    return m


# ===== 主程式 =====

def main():
    # 側邊欄
    with st.sidebar:
        # Logo
        st.image("assets/images/logo.png", use_container_width=True)

        st.markdown("---")
        page = st.radio(
            "選擇功能",
            ["🏠 首頁", "📈 資料分析", "🗺️ 安全路線規劃", "📊 治安風險地圖", "🔥 犯罪熱點地圖"],
            index=0
        )

        st.markdown("---")
        st.markdown("""
        **SDG 永續發展目標**
        - 🏙️ SDG 11 永續城市
        - ⚖️ SDG 16 和平正義
        """)

    # 主頁面內容
    if page == "🏠 首頁":
        show_home()
    elif page == "📈 資料分析":
        show_data_analysis()
    elif page == "🗺️ 安全路線規劃":
        show_route_planning()
    elif page == "📊 治安風險地圖":
        show_risk_map()
    elif page == "🔥 犯罪熱點地圖":
        show_crime_heatmap()


def show_home():
    """首頁 - 專題介紹與簡報"""
    # 首頁 Logo 置中顯示
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image("assets/images/logo.png", use_container_width=True)

    st.markdown("""
    <div style="text-align: center; margin-bottom: 20px;">
        <h2 style="margin: 0;">計算思維與人工智慧 期末專題</h2>
        <p style="font-size: 1.1em; color: #666;">台中市都市犯罪分析：以 AI 輔助打造安全永續城市</p>
    </div>
    """, unsafe_allow_html=True)

    # 專題簡報（Canva 嵌入）
    st.markdown("---")
    st.subheader("📊 專題簡報")

    st.markdown("""
    <div style="position: relative; width: 100%; height: 0; padding-top: 56.25%;
         padding-bottom: 0; box-shadow: 0 2px 8px 0 rgba(63,69,81,0.16); margin-top: 1.6em; margin-bottom: 0.9em; overflow: hidden;
         border-radius: 8px; will-change: transform;">
        <iframe loading="lazy" style="position: absolute; width: 100%; height: 100%; top: 0; left: 0; border: none; padding: 0; margin: 0;"
            src="https://www.canva.com/design/DAG6VHyKleU/FkzpZ_51nfX0rtUcZ_63vw/view?embed" allowfullscreen="allowfullscreen" allow="fullscreen">
        </iframe>
    </div>
    """, unsafe_allow_html=True)

    # 系統目的
    st.markdown("---")
    st.subheader("📌 系統目的")

    st.markdown("""
    本系統結合臺中市竊盜逐案開放資料與人口統計，透過行政區風險指標與時段分析，
    設計出「台中安全路線導航」原型系統，協助市民與遊客在規劃移動路線時兼顧距離與治安風險。
    """)

    # 快速導覽
    st.markdown("---")
    st.subheader("🚀 快速導覽")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("""
        <div style="background: #e8f5e9; padding: 20px; border-radius: 10px; text-align: center; color: #1a1a1a;">
            <h3 style="color: #2e7d32; margin: 0 0 8px 0;">📈 資料分析</h3>
            <p style="color: #333; margin: 0;">查看完整的 EDA 圖表與統計結果</p>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div style="background: #e3f2fd; padding: 20px; border-radius: 10px; text-align: center; color: #1a1a1a;">
            <h3 style="color: #1565c0; margin: 0 0 8px 0;">🗺️ 安全路線</h3>
            <p style="color: #333; margin: 0;">規劃路線並評估治安風險</p>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown("""
        <div style="background: #fff3e0; padding: 20px; border-radius: 10px; text-align: center; color: #1a1a1a;">
            <h3 style="color: #e65100; margin: 0 0 8px 0;">🔥 熱點地圖</h3>
            <p style="color: #333; margin: 0;">探索犯罪案件的空間分布</p>
        </div>
        """, unsafe_allow_html=True)

    # SDG 永續發展目標
    st.markdown("---")
    st.subheader("🌍 SDG 永續發展目標連結")

    col1, col2 = st.columns(2)
    with col1:
        st.image("assets/images/sdg11.png", use_container_width=True)
    with col2:
        st.image("assets/images/sdg16.png", use_container_width=True)

    with st.expander("📖 SDG 11：永續城市與社區", expanded=False):
        st.markdown("""
        **建構具包容、安全、韌性及永續特質的城市與鄉村**

        - **本研究將台中市竊盜逐案資料轉換為「行政區風險指標」與「安全路線建議」**
          透過將原本零散的逐案竊盜紀錄進行統計分析，本研究將犯罪點位聚合為各行政區的「相對風險指標」，並進一步結合生活／旅遊動線，產出具體的安全路線與時段建議。

        - **提供市民與遊客在規劃移動路徑時參考，降低治安疑慮，提升都市居住與旅遊安全感**
          研究成果可應用在學生上下課、旅客前往夜市或商圈等情境，協助使用者在規劃行走路線時，能避開相對高風險區域。

        - **透過互動式治安風險地圖，讓公眾能更直觀地理解空間風險差異**
          以視覺化與互動式地圖呈現不同行政區犯罪的分布，讓沒有數據分析背景的一般民眾，也能一眼看出「哪裡相對安全、哪裡需要多注意」。
        """)

    with st.expander("📖 SDG 16：和平、正義與健全制度", expanded=False):
        st.markdown("""
        **促進和平多元的社會，確保司法平等，建立具公信力且廣納民意的體系**

        - **本系統以政府開放資料與警政統計為基礎，提升治安資訊透明度與公民參與度**
          本系統完全建立在政府開放資料與警政統計等公開資料之上，透過清楚標示資料來源與分析流程，讓民眾可以追溯與檢驗分析結果。

        - **透過數據驅動方式澄清「台中治安很差」等刻板印象**
          本系統以客觀政府數據呈現台中各行政區的實際風險狀況，避免單一事件被過度放大的情況。

        - **促進民眾對治安政策與警政資源配置的理性討論**
          當犯罪熱點被明確可視化後，民眾在討論是否需要增加警力、調整巡邏路線或改善公共空間設計時，可以有更具體的依據。
        """)

    # 資料來源
    st.markdown("---")
    st.subheader("📊 資料來源")

    st.markdown("""
    | 資料集 | 來源 | 時間範圍 |
    |--------|------|----------|
    | 竊盜逐案資料 | 台中市政府開放資料平台 | 105-108年 |
    | 人口統計 | 台中市政府民政局 | 107年12月 |
    | 官方治安統計 | 台中市政府警察局 | 2016-2022年 |
    """)

    # 使用說明與限制
    with st.expander("⚠️ 使用說明與限制"):
        st.markdown("""
        1. **本系統為學術/教學用途**，風險分數為相對指標，實際治安仍以官方資訊為準
        2. 開放資料僅涵蓋四類竊盜（機車、汽車、住宅、自行車），非完整竊盜統計
        3. 資料時間範圍為 105-108 年，較近期資料尚未開放
        4. 路線規劃已串接 Google Maps API，提供真實道路導航
        """)

    # 技術架構
    with st.expander("🛠️ 技術架構"):
        st.markdown("""
        ```
        資料處理流程：
        竊盜逐案點位 → 行政區與時段統計 → 人口校正 → 風險指標 → 路線風險評估
        ```

        - **後端**：Python + Pandas
        - **前端**：Streamlit + Folium
        - **地圖 API**：Google Maps Directions API
        - **資料分析**：Jupyter Notebook
        """)


def show_data_analysis():
    """資料分析頁面 - 展示所有圖表"""
    st.header("📈 資料分析結果")

    st.markdown("""
    本頁面展示台中市 105-108 年（2016-2019）竊盜案件的探索性資料分析結果。
    資料來源：[台中市政府開放資料平台](https://opendata.taichung.gov.tw/)
    """)

    # 資料概覽
    st.markdown("---")
    st.subheader("📊 資料概覽")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("總案件數", "3,286 件")
    with col2:
        st.metric("資料年份", "105-108 年")
    with col3:
        st.metric("涵蓋行政區", "29 區")
    with col4:
        st.metric("犯罪類型", "4 種")

    # 圖表區域
    st.markdown("---")
    st.subheader("📉 年度趨勢分析")

    st.markdown("""
    **發現**：105-108 年間，台中市竊盜案件呈現明顯的下降趨勢，與官方統計數據一致。
    """)

    # 顯示年度趨勢圖
    trend_img = Path("outputs/figures/theft_trend_by_year.png")
    if trend_img.exists():
        st.image(str(trend_img), caption="台中市竊盜案件年度趨勢", use_container_width=True)
    else:
        st.warning("圖表檔案不存在，請先執行 Notebook 產生圖表")

    # 時段分析
    st.markdown("---")
    st.subheader("🕐 時段分布分析")

    st.markdown("""
    **發現**：
    - 凌晨 2-6 點、中午 12 點、傍晚 17-18 點為竊盜高峰時段
    - 不同類型竊盜的時段分布有明顯差異
    """)

    hour_img = Path("outputs/figures/theft_by_hour.png")
    if hour_img.exists():
        st.image(str(hour_img), caption="竊盜案件 24 小時分布", use_container_width=True)

    # 月份分析
    st.markdown("---")
    st.subheader("📅 月份分布分析")

    month_img = Path("outputs/figures/theft_by_month.png")
    if month_img.exists():
        st.image(str(month_img), caption="竊盜案件月份分布", use_container_width=True)

    # 行政區分析
    st.markdown("---")
    st.subheader("🏘️ 行政區分析")

    st.markdown("""
    **重要發現 - 生態謬誤**：
    - 以「總件數」排名：西屯區(344件)、北區(331件)、北屯區(267件) 居前三
    - 以「每萬人竊盜率」排名：**中區(56.7)** 遠高於其他區域

    這說明人口校正的重要性！人口僅 1.8 萬的中區，其每萬人竊盜率是第二名的 2 倍以上。
    """)

    comparison_img = Path("outputs/figures/district_theft_comparison.png")
    if comparison_img.exists():
        st.image(str(comparison_img), caption="總件數 vs 每萬人竊盜率比較", use_container_width=True)

    # 犯罪類型分布
    st.markdown("---")
    st.subheader("🔍 犯罪類型分布")

    type_img = Path("outputs/figures/district_theft_by_type.png")
    if type_img.exists():
        st.image(str(type_img), caption="各行政區竊盜類型分布", use_container_width=True)

    # 官方統計對照
    st.markdown("---")
    st.subheader("📋 官方統計對照")

    st.markdown("""
    **驗證分析可信度**：將開放資料分析結果與台中市警察局官方統計進行對照。
    - 開放資料（四類竊盜）約佔官方全部竊盜統計的 18-25%
    - 兩者的年度趨勢一致，皆呈現逐年下降
    """)

    official_img = Path("outputs/figures/official_stats_comparison.png")
    if official_img.exists():
        st.image(str(official_img), caption="開放資料 vs 官方統計對照", use_container_width=True)

    # 風險指標說明
    st.markdown("---")
    st.subheader("📐 風險指標計算方法")

    st.markdown("""
    | 指標 | 計算公式 | 用途 |
    |------|----------|------|
    | 每萬人竊盜率 | 總件數 / 人口 × 10,000 | 行政區間公平比較 |
    | 時段風險分數 | 該時段案件數 / 全日平均 | 辨識高風險時段 |
    | 路線風險分數 | Σ(區域風險 × 時段風險) / 經過區數 | 路線安全評估 |
    """)

    # 資料表格
    st.markdown("---")
    st.subheader("📋 行政區風險指標表")

    district_risk = load_district_risk()
    st.dataframe(
        district_risk.style.background_gradient(subset=['cases_per_10k_pop'], cmap='Reds'),
        use_container_width=True,
        hide_index=True
    )


def show_route_planning():
    """安全路線規劃頁面"""
    st.header("🗺️ 安全路線規劃")

    # 顯示 API 狀態
    if GOOGLE_MAPS_AVAILABLE:
        st.success("✅ Google Maps API 已啟用 - 使用真實道路導航")
    else:
        st.warning("⚠️ Google Maps API 未設定 - 使用簡化直線路線")

    st.markdown("""
    輸入您的出發地與目的地，系統將評估路線的治安風險等級，
    並提供安全建議。
    """)

    # 情境範例按鈕
    col_demo1, col_demo2, col_demo3 = st.columns(3)
    with col_demo1:
        if st.button("📌 情境A: 台中車站→逢甲夜市(晚上)"):
            st.session_state['origin'] = '台中車站'
            st.session_state['dest'] = '逢甲夜市'
            st.session_state['hour'] = 22
    with col_demo2:
        if st.button("📌 情境B: 勤美→一中街(下午)"):
            st.session_state['origin'] = '勤美誠品綠園道'
            st.session_state['dest'] = '一中街商圈'
            st.session_state['hour'] = 15
    with col_demo3:
        if st.button("📌 情境C: 高鐵站→東海大學"):
            st.session_state['origin'] = '台中高鐵站'
            st.session_state['dest'] = '東海大學'
            st.session_state['hour'] = 18

    st.markdown("---")

    # 輸入區域
    col1, col2, col3 = st.columns(3)

    with col1:
        origin = st.selectbox(
            "🚩 出發地",
            list(LANDMARKS.keys()),
            index=list(LANDMARKS.keys()).index(st.session_state.get('origin', '台中車站'))
        )

    with col2:
        dest = st.selectbox(
            "🎯 目的地",
            list(LANDMARKS.keys()),
            index=list(LANDMARKS.keys()).index(st.session_state.get('dest', '逢甲夜市'))
        )

    with col3:
        hour = st.slider(
            "🕐 出發時間",
            0, 23,
            st.session_state.get('hour', 20),
            format="%d:00"
        )

    # 交通方式選擇（只在 API 可用時顯示）
    if GOOGLE_MAPS_AVAILABLE:
        travel_mode = st.radio(
            "🚶 交通方式",
            ["walking", "driving", "bicycling"],
            format_func=lambda x: {"walking": "🚶 步行", "driving": "🚗 開車", "bicycling": "🚴 騎車"}[x],
            horizontal=True
        )
    else:
        travel_mode = "walking"

    # 分析按鈕
    if st.button("🔍 分析路線風險", type="primary", use_container_width=True):
        origin_district = LANDMARKS[origin]['district']
        dest_district = LANDMARKS[dest]['district']

        result = compute_route_risk(origin_district, dest_district, hour)

        # 呼叫 Google Maps API 取得真實路線
        google_route = None
        if GOOGLE_MAPS_AVAILABLE:
            with st.spinner("正在規劃路線..."):
                origin_coords = LANDMARKS[origin]['coords']
                dest_coords = LANDMARKS[dest]['coords']
                routes = get_directions(
                    origin=origin_coords,
                    destination=dest_coords,
                    mode=travel_mode,
                    alternatives=False  # 只取一條路線，節省資源
                )
                if routes:
                    google_route = routes[0]

        # 將結果存入 session_state
        st.session_state['route_result'] = result
        st.session_state['route_origin'] = origin
        st.session_state['route_dest'] = dest
        st.session_state['route_hour'] = hour
        st.session_state['google_route'] = google_route
        st.session_state['travel_mode'] = travel_mode

    # 顯示分析結果（從 session_state 讀取）
    if 'route_result' in st.session_state:
        result = st.session_state['route_result']
        origin = st.session_state.get('route_origin', origin)
        dest = st.session_state.get('route_dest', dest)
        hour = st.session_state.get('route_hour', hour)
        google_route = st.session_state.get('google_route')
        travel_mode = st.session_state.get('travel_mode', 'walking')

        st.markdown("---")
        st.subheader("📋 路線風險分析結果")

        # 風險分數卡片
        if google_route:
            # 有 Google Maps 路線資訊
            col_dist, col_time, col_score, col_level = st.columns(4)

            with col_dist:
                st.metric("📏 距離", google_route['distance']['text'])

            with col_time:
                st.metric("⏱️ 預估時間", google_route['duration']['text'])

            with col_score:
                st.metric("⚠️ 風險分數", f"{result['route_risk_score']}")

            with col_level:
                level_emoji = {'低': '🟢', '中': '🟡', '高': '🔴'}
                st.metric("🎯 風險等級", f"{level_emoji.get(result['route_risk_label'], '⚪')} {result['route_risk_label']}")
        else:
            # 沒有 Google Maps 路線
            col_score, col_level, col_time = st.columns(3)

            with col_score:
                st.metric("風險分數", f"{result['route_risk_score']}")

            with col_level:
                level_emoji = {'低': '🟢', '中': '🟡', '高': '🔴'}
                st.metric("風險等級", f"{level_emoji.get(result['route_risk_label'], '⚪')} {result['route_risk_label']}")

            with col_time:
                time_period = "深夜" if hour >= 22 or hour < 6 else "晚間" if hour >= 18 else "白天" if hour >= 6 else "深夜"
                st.metric("出發時段", f"{hour}:00 ({time_period})")

        # 地圖
        st.subheader("🗺️ 路線地圖")

        # 犯罪熱點開關
        show_crimes = st.checkbox("🔥 顯示路線附近犯罪熱點", value=True)

        route_map = create_route_map(origin, dest, result, google_route, show_crimes=show_crimes)
        if route_map:
            st_folium(route_map, width=700, height=450)

        # 路線附近犯罪統計
        if show_crimes:
            crime_data = load_geocoded_crimes()
            if crime_data is not None and google_route:
                coords = decode_polyline(google_route['polyline'])
                route_coords = [(p['lat'], p['lng']) for p in coords]
                lats = [c[0] for c in route_coords]
                lons = [c[1] for c in route_coords]
                lat_min, lat_max = min(lats) - 0.008, max(lats) + 0.008
                lon_min, lon_max = min(lons) - 0.01, max(lons) + 0.01

                nearby_crimes = crime_data[
                    (crime_data['latitude'] >= lat_min) &
                    (crime_data['latitude'] <= lat_max) &
                    (crime_data['longitude'] >= lon_min) &
                    (crime_data['longitude'] <= lon_max)
                ]

                if len(nearby_crimes) > 0:
                    st.markdown("**📊 路線附近犯罪統計** (約 800m 範圍內)")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("附近案件數", f"{len(nearby_crimes)} 件")
                    with col2:
                        top_crime = nearby_crimes['crime_category'].value_counts().idxmax()
                        st.metric("最常見類型", top_crime)

        # 導航步驟（如果有 Google Maps 路線）
        if google_route and google_route.get('steps'):
            with st.expander("📝 導航步驟", expanded=False):
                for i, step in enumerate(google_route['steps'], 1):
                    # 清理 HTML 標籤
                    instruction = step['instruction']
                    instruction = instruction.replace('<b>', '**').replace('</b>', '**')
                    instruction = instruction.replace('<div style="font-size:0.9em">', ' (').replace('</div>', ')')
                    instruction = instruction.replace('<wbr/>', '')  # 移除換行提示標籤
                    instruction = instruction.replace('<wbr>', '')
                    st.markdown(f"{i}. {instruction} - {step['distance']}")

        # 詳細分析
        st.subheader("📊 詳細分析")

        for dr in result['district_risks']:
            level_color = get_risk_color(dr['risk_level'])
            st.markdown(f"""
            **{dr['district']}**
            - 每萬人竊盜率: {dr['cases_per_10k_pop']}
            - 風險等級: <span style="color:{level_color}; font-weight:bold;">{dr['risk_level']}</span>
            - 時段風險係數: {dr['hour_risk_score']}x
            """, unsafe_allow_html=True)

        # 安全建議
        st.subheader("💡 安全建議")
        if result['route_risk_label'] == '高':
            st.warning(f"""
            ⚠️ **此路線在 {hour}:00 時段的風險偏高**

            建議措施：
            - 結伴同行，避免單獨行動
            - 機車/自行車請停放在有監視器的區域
            - 貴重物品隨身攜帶，勿置於車上
            - 可考慮選擇其他時段出發
            """)
        elif result['route_risk_label'] == '中':
            st.info("""
            ℹ️ **此路線風險中等**

            建議措施：
            - 保持警覺，注意周遭環境
            - 避免在偏僻巷弄逗留
            """)
        else:
            st.success("""
            ✅ **此路線相對安全**

            仍建議保持基本警覺，注意個人財物安全。
            """)

        # 清除結果按鈕
        if st.button("🔄 重新查詢", key="clear_route"):
            for key in ['route_result', 'route_origin', 'route_dest', 'route_hour', 'google_route', 'travel_mode']:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()


def show_risk_map():
    """治安風險地圖頁面"""
    st.header("📊 治安風險地圖")

    st.markdown("""
    此地圖顯示台中市各行政區的竊盜風險指標。
    可切換檢視「每萬人竊盜率」與「總件數」兩種呈現方式。
    """)

    # 切換按鈕
    show_rate = st.toggle("顯示每萬人竊盜率（建議）", value=True)

    if not show_rate:
        st.info("💡 提示：「總件數」會受人口多寡影響，人口大區件數自然較多。建議使用「每萬人竊盜率」做公平比較。")

    # 載入資料
    district_risk = load_district_risk()

    # 顯示地圖
    risk_map = create_risk_map(district_risk, show_rate=show_rate)
    st_folium(risk_map, width=700, height=500)

    # 圖例
    st.markdown("""
    **圖例說明**
    - 🟢 綠色：低風險
    - 🟡 橘色：中風險
    - 🔴 紅色：高風險
    """)

    # 排行榜
    st.subheader("📈 行政區風險排行")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**⬆️ 風險最高 Top 5**")
        top5 = district_risk.nlargest(5, 'cases_per_10k_pop')[['district', 'cases_per_10k_pop', 'risk_level']]
        st.dataframe(top5, hide_index=True)

    with col2:
        st.markdown("**⬇️ 風險最低 Top 5**")
        bottom5 = district_risk.nsmallest(5, 'cases_per_10k_pop')[['district', 'cases_per_10k_pop', 'risk_level']]
        st.dataframe(bottom5, hide_index=True)


def show_crime_heatmap():
    """犯罪熱點地圖頁面"""
    st.header("🔥 犯罪熱點地圖")

    st.markdown("""
    此地圖顯示 105-108 年台中市竊盜案件的實際分布位置。
    可選擇不同的視覺化方式與篩選條件。
    """)

    # 載入地理編碼資料
    crime_data = load_geocoded_crimes()

    if crime_data is None:
        st.error("找不到地理編碼資料，請先執行 `python src/geocoder.py`")
        return

    # 篩選控制項
    col1, col2, col3 = st.columns(3)

    with col1:
        crime_types = ['全部'] + list(crime_data['crime_category'].unique())
        selected_crime = st.selectbox("犯罪類型", crime_types)

    with col2:
        districts = ['全部'] + sorted(crime_data['district'].unique().tolist())
        selected_district = st.selectbox("行政區", districts)

    with col3:
        view_mode = st.radio("顯示模式", ["熱力圖", "點位圖", "聚合標記"], horizontal=True)

    # 時段篩選
    hour_range = st.slider("時段範圍", 0, 23, (0, 23), format="%d:00")

    # 篩選資料
    filtered_data = crime_data.copy()

    if selected_crime != '全部':
        filtered_data = filtered_data[filtered_data['crime_category'] == selected_crime]

    if selected_district != '全部':
        filtered_data = filtered_data[filtered_data['district'] == selected_district]

    filtered_data = filtered_data[
        (filtered_data['hour'] >= hour_range[0]) &
        (filtered_data['hour'] <= hour_range[1])
    ]

    st.info(f"顯示 {len(filtered_data)} 筆案件")

    # 建立地圖
    m = folium.Map(
        location=[24.1477, 120.6736],
        zoom_start=11,
        tiles='cartodbpositron'
    )

    # 確保有有效座標
    valid_data = filtered_data.dropna(subset=['latitude', 'longitude'])

    if len(valid_data) == 0:
        st.warning("沒有符合條件的資料")
        return

    # 根據模式繪製
    if view_mode == "熱力圖":
        heat_data = valid_data[['latitude', 'longitude']].values.tolist()
        HeatMap(
            heat_data,
            radius=15,
            blur=10,
            max_zoom=13,
            gradient={0.2: 'blue', 0.4: 'lime', 0.6: 'yellow', 0.8: 'orange', 1: 'red'}
        ).add_to(m)

    elif view_mode == "點位圖":
        # 顏色對應犯罪類型
        crime_colors = {
            '機車竊盜': '#2ecc71',
            '汽車竊盜': '#3498db',
            '住宅竊盜': '#e74c3c',
            '自行車竊盜': '#f39c12'
        }

        for _, row in valid_data.iterrows():
            color = crime_colors.get(row['crime_category'], '#95a5a6')
            folium.CircleMarker(
                location=[row['latitude'], row['longitude']],
                radius=4,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.7,
                popup=f"{row['crime_category']}<br>{row['district']}<br>{row['hour']}:00"
            ).add_to(m)

    else:  # 聚合標記
        marker_cluster = MarkerCluster().add_to(m)
        for _, row in valid_data.iterrows():
            folium.Marker(
                location=[row['latitude'], row['longitude']],
                popup=f"{row['crime_category']}<br>{row['district']}<br>{row['hour']}:00",
                icon=folium.Icon(color='red', icon='exclamation-sign')
            ).add_to(marker_cluster)

    # 顯示地圖
    st_folium(m, width=700, height=500)

    # 統計資訊
    st.subheader("📊 篩選結果統計")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**依犯罪類型**")
        crime_stats = filtered_data['crime_category'].value_counts()
        st.dataframe(crime_stats, use_container_width=True)

    with col2:
        st.markdown("**依行政區**")
        district_stats = filtered_data['district'].value_counts().head(10)
        st.dataframe(district_stats, use_container_width=True)

    # 圖例（點位圖模式）
    if view_mode == "點位圖":
        st.markdown("""
        **圖例說明**
        - 🟢 綠色：機車竊盜
        - 🔵 藍色：汽車竊盜
        - 🔴 紅色：住宅竊盜
        - 🟡 橘色：自行車竊盜
        """)




# 初始化 session state
if 'origin' not in st.session_state:
    st.session_state['origin'] = '台中車站'
if 'dest' not in st.session_state:
    st.session_state['dest'] = '逢甲夜市'
if 'hour' not in st.session_state:
    st.session_state['hour'] = 20


if __name__ == '__main__':
    main()
