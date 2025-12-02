"""
台中安全路線導航 SafeTaichung
Streamlit 應用程式

啟動方式: streamlit run app.py
"""

import streamlit as st
import pandas as pd
import folium
from folium.plugins import HeatMap, MarkerCluster
from streamlit_folium import st_folium
from pathlib import Path
import json

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


def create_route_map(origin_name, dest_name, route_result):
    """建立路線地圖"""
    origin_info = LANDMARKS.get(origin_name)
    dest_info = LANDMARKS.get(dest_name)

    if not origin_info or not dest_info:
        return None

    # 計算地圖中心
    center_lat = (origin_info['coords'][0] + dest_info['coords'][0]) / 2
    center_lon = (origin_info['coords'][1] + dest_info['coords'][1]) / 2

    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=13,
        tiles='cartodbpositron'
    )

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

    # 繪製連線（簡化路線）
    route_color = get_risk_color(route_result['route_risk_label'])
    folium.PolyLine(
        locations=[origin_info['coords'], dest_info['coords']],
        weight=5,
        color=route_color,
        opacity=0.8
    ).add_to(m)

    return m


# ===== 主程式 =====

def main():
    # 側邊欄
    with st.sidebar:
        st.markdown("""
        <div style="text-align: center; padding: 10px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 10px; margin-bottom: 10px;">
            <h1 style="color: white; margin: 0; font-size: 2em;">🛡️</h1>
            <h3 style="color: white; margin: 5px 0;">SafeTaichung</h3>
        </div>
        """, unsafe_allow_html=True)
        st.title("🛡️ 台中安全路線導航")

        st.markdown("---")
        page = st.radio(
            "選擇功能",
            ["🗺️ 安全路線規劃", "📊 治安風險地圖", "🔥 犯罪熱點地圖", "ℹ️ 關於本系統"],
            index=0
        )

        st.markdown("---")
        st.markdown("""
        **SDG 永續發展目標**
        - 🏙️ SDG 11 永續城市
        - ⚖️ SDG 16 和平正義
        """)

    # 主頁面內容
    if page == "🗺️ 安全路線規劃":
        show_route_planning()
    elif page == "📊 治安風險地圖":
        show_risk_map()
    elif page == "🔥 犯罪熱點地圖":
        show_crime_heatmap()
    else:
        show_about()


def show_route_planning():
    """安全路線規劃頁面"""
    st.header("🗺️ 安全路線規劃")

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

    # 分析按鈕
    if st.button("🔍 分析路線風險", type="primary", use_container_width=True):
        origin_district = LANDMARKS[origin]['district']
        dest_district = LANDMARKS[dest]['district']

        result = compute_route_risk(origin_district, dest_district, hour)

        # 將結果存入 session_state
        st.session_state['route_result'] = result
        st.session_state['route_origin'] = origin
        st.session_state['route_dest'] = dest
        st.session_state['route_hour'] = hour

    # 顯示分析結果（從 session_state 讀取）
    if 'route_result' in st.session_state:
        result = st.session_state['route_result']
        origin = st.session_state.get('route_origin', origin)
        dest = st.session_state.get('route_dest', dest)
        hour = st.session_state.get('route_hour', hour)

        st.markdown("---")
        st.subheader("📋 路線風險分析結果")

        # 風險分數卡片
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
        route_map = create_route_map(origin, dest, result)
        if route_map:
            st_folium(route_map, width=700, height=400)

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
            st.info(f"""
            ℹ️ **此路線風險中等**

            建議措施：
            - 保持警覺，注意周遭環境
            - 避免在偏僻巷弄逗留
            """)
        else:
            st.success(f"""
            ✅ **此路線相對安全**

            仍建議保持基本警覺，注意個人財物安全。
            """)

        # 清除結果按鈕
        if st.button("🔄 重新查詢", key="clear_route"):
            for key in ['route_result', 'route_origin', 'route_dest', 'route_hour']:
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


def show_about():
    """關於本系統頁面"""
    st.header("ℹ️ 關於本系統")

    st.markdown("""
    ## 台中安全路線導航 SafeTaichung（Prototype）

    ### 📌 系統目的

    本系統結合臺中市竊盜逐案開放資料與人口統計，透過行政區風險指標與時段分析，
    設計出「台中安全路線導航」原型系統，協助市民與遊客在規劃移動路線時兼顧距離與治安風險。

    ---

    ### 🌍 SDG 永續發展目標連結

    #### SDG 11：永續城市與社區
    - 本研究將台中市竊盜逐案資料轉換為「行政區風險指標」與「安全路線建議」
    - 提供市民與遊客在規劃移動路徑時參考，降低治安疑慮，提升都市居住與旅遊安全感
    - 透過互動式治安風險地圖，讓公眾能更直觀地理解空間風險差異

    #### SDG 16：和平、正義及健全制度
    - 本系統以政府開放資料與警政統計為基礎，提升治安資訊透明度與公民參與度
    - 透過數據驅動方式澄清「台中治安很差」等刻板印象
    - 促進民眾對治安政策與警政資源配置的理性討論

    ---

    ### 📊 資料來源

    | 資料集 | 來源 | 時間範圍 |
    |--------|------|----------|
    | 竊盜逐案資料 | 台中市政府開放資料平台 | 105-108年 |
    | 人口統計 | 台中市政府民政局 | 107年12月 |
    | 官方治安統計 | 台中市政府警察局 | 2016-2022年 |

    ---

    ### ⚠️ 使用說明與限制

    1. **本系統為學術/教學用途**，風險分數為相對指標，實際治安仍以官方資訊為準
    2. 開放資料僅涵蓋四類竊盜（機車、汽車、住宅、自行車），非完整竊盜統計
    3. 資料時間範圍為105-108年，較近期資料尚未開放
    4. 路線規劃為簡化版本，未實際串接導航 API

    ---

    ### 🛠️ 技術架構

    ```
    資料處理流程：
    竊盜逐案點位 → 行政區與時段統計 → 人口校正 → 風險指標 → 路線風險評估
    ```

    - **後端**：Python + Pandas
    - **前端**：Streamlit + Folium
    - **資料分析**：Jupyter Notebook

    ---

    ### 👥 開發團隊

    計算思維與人工智慧課程專題

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
