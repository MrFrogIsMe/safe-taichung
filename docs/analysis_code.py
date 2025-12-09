"""
SafeTaichung - 台中市竊盜案件資料分析程式碼
Data Analysis Code for Taichung Theft Cases

課程：計算思維與人工智慧
專題：台中市都市犯罪分析
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'Microsoft JhengHei', 'Heiti TC']
plt.rcParams['axes.unicode_minus'] = False

RAW_DIR = Path('data/raw')
PROCESSED_DIR = Path('data/processed')
FIGURES_DIR = Path('outputs/figures')


# =============================================================================
# 1. 資料讀取
# =============================================================================

crime_types = {
    'scooter_theft': '機車竊盜',
    'car_theft': '汽車竊盜',
    'residential_burglary': '住宅竊盜',
    'bike_theft': '自行車竊盜'
}
years = ['105', '106', '107', '108']

datasets = {}
for crime_key, crime_name in crime_types.items():
    dfs = []
    for year in years:
        file_path = RAW_DIR / f'{crime_key}_{year}.csv'
        if file_path.exists():
            df = pd.read_csv(file_path, encoding='utf-8-sig')
            df['year_file'] = year
            dfs.append(df)
    if dfs:
        datasets[crime_key] = pd.concat(dfs, ignore_index=True)


# =============================================================================
# 2. 資料清理
# =============================================================================

def clean_crime_data(df, crime_category):
    df_clean = df.copy()
    df_clean = df_clean.rename(columns={
        '發生日期': 'date_raw',
        '發生時間': 'time_raw',
        '發生地點': 'location'
    })

    def convert_roc_date(date_val):
        try:
            date_str = str(int(date_val)).zfill(7)
            roc_year = int(date_str[:3])
            month = int(date_str[3:5])
            day = int(date_str[5:7])
            return pd.Timestamp(year=roc_year + 1911, month=month, day=day)
        except:
            return pd.NaT

    def extract_hour(time_val):
        try:
            time_str = str(int(time_val)).zfill(4)
            return int(time_str[:2])
        except:
            return -1

    df_clean['date'] = df_clean['date_raw'].apply(convert_roc_date)
    df_clean['hour'] = df_clean['time_raw'].apply(extract_hour)
    df_clean['crime_category'] = crime_category
    df_clean['is_valid'] = 1
    df_clean.loc[df_clean['date'].isna(), 'is_valid'] = 0
    df_clean.loc[df_clean['location'].isna(), 'is_valid'] = 0
    df_clean.loc[df_clean['hour'] < 0, 'is_valid'] = 0

    return df_clean

cleaned_datasets = {k: clean_crime_data(v, crime_types[k]) for k, v in datasets.items()}


# =============================================================================
# 3. 行政區解析
# =============================================================================

TAICHUNG_DISTRICTS = [
    '中區', '東區', '西區', '南區', '北區', '西屯區', '北屯區', '南屯區',
    '豐原區', '大里區', '太平區', '清水區', '沙鹿區', '大甲區', '東勢區',
    '梧棲區', '烏日區', '神岡區', '大肚區', '大雅區', '后里區', '霧峰區',
    '潭子區', '龍井區', '外埔區', '和平區', '石岡區', '大安區', '新社區'
]

def extract_district(location):
    if pd.isna(location):
        return '未知'
    for district in TAICHUNG_DISTRICTS:
        if district in str(location):
            return district
    return '其他'

for key in cleaned_datasets:
    cleaned_datasets[key]['district'] = cleaned_datasets[key]['location'].apply(extract_district)


# =============================================================================
# 4. 合併資料
# =============================================================================

columns_to_keep = ['date', 'hour', 'location', 'district', 'crime_category', 'is_valid']
all_theft_data = pd.concat(
    [cleaned_datasets[key][columns_to_keep] for key in cleaned_datasets],
    ignore_index=True
)
valid_data = all_theft_data[all_theft_data['is_valid'] == 1].copy()
valid_data['year'] = valid_data['date'].dt.year
valid_data['month'] = valid_data['date'].dt.month


# =============================================================================
# 5. 年度趨勢分析
# =============================================================================

yearly_total = valid_data.groupby('year').size()
yearly_by_type = valid_data.groupby(['year', 'crime_category']).size().unstack(fill_value=0)


# =============================================================================
# 6. 時段分析
# =============================================================================

hourly = valid_data[valid_data['hour'] >= 0].groupby('hour').size()
hourly_by_type = valid_data[valid_data['hour'] >= 0].groupby(
    ['crime_category', 'hour']
).size().unstack(fill_value=0)


# =============================================================================
# 7. 行政區分析
# =============================================================================

district_stats = valid_data.groupby('district').agg(
    total_cases=('district', 'size')
).reset_index()

district_by_type = valid_data.groupby(['district', 'crime_category']).size().unstack(fill_value=0)
district_stats = district_stats.merge(district_by_type, on='district')
district_stats = district_stats[~district_stats['district'].isin(['其他', '未知'])]
district_stats = district_stats.sort_values('total_cases', ascending=False)


# =============================================================================
# 8. 每萬人竊盜率計算
# =============================================================================

population_df = pd.read_csv(PROCESSED_DIR / 'district_population.csv', encoding='utf-8-sig')
district_with_pop = district_stats.merge(
    population_df[['district', 'population']], on='district', how='left'
)
district_with_pop['theft_per_10k'] = (
    district_with_pop['total_cases'] / district_with_pop['population'] * 10000
).round(2)


# =============================================================================
# 9. 風險模型
# =============================================================================

def compute_district_risk():
    theft_df = valid_data.copy()
    pop_df = population_df.copy()

    district_cases = theft_df.groupby('district').size().reset_index(name='total_cases')
    theft_df['is_daytime'] = theft_df['hour'].apply(lambda h: 1 if 6 <= h < 18 else 0)
    daytime_cases = theft_df.groupby('district')['is_daytime'].sum().reset_index(name='daytime_cases')

    summary = district_cases.merge(daytime_cases, on='district')
    summary = summary.merge(pop_df[['district', 'population']], on='district', how='left')
    summary['cases_per_10k'] = (summary['total_cases'] / summary['population'] * 10000).round(2)
    summary['daytime_ratio'] = (summary['daytime_cases'] / summary['total_cases'] * 100).round(1)
    summary['night_ratio'] = 100 - summary['daytime_ratio']

    q33 = summary['cases_per_10k'].quantile(0.33)
    q67 = summary['cases_per_10k'].quantile(0.67)
    summary['risk_level'] = summary['cases_per_10k'].apply(
        lambda x: 'low' if x <= q33 else ('medium' if x <= q67 else 'high')
    )
    return summary.sort_values('cases_per_10k', ascending=False)


def compute_hourly_risk():
    theft_df = valid_data.copy()
    hourly = theft_df.groupby(['district', 'hour']).size().reset_index(name='hour_cases')
    district_total = theft_df.groupby('district').size().reset_index(name='district_total')
    hourly = hourly.merge(district_total, on='district')
    hourly['hour_risk_score'] = (hourly['hour_cases'] / (hourly['district_total'] / 24)).round(2)
    return hourly[['district', 'hour', 'hour_cases', 'hour_risk_score']]


def compute_route_risk(districts, hour):
    district_risk = compute_district_risk()
    hourly_risk = compute_hourly_risk()

    total_score = 0
    details = []

    for d in districts:
        dist_row = district_risk[district_risk['district'] == d]
        cases_per_10k = dist_row['cases_per_10k'].values[0] if len(dist_row) > 0 else 0

        hour_row = hourly_risk[(hourly_risk['district'] == d) & (hourly_risk['hour'] == hour)]
        hour_score = hour_row['hour_risk_score'].values[0] if len(hour_row) > 0 else 1.0

        segment_risk = cases_per_10k * hour_score
        total_score += segment_risk
        details.append({'district': d, 'risk': round(segment_risk, 2)})

    avg_score = total_score / len(districts) if districts else 0
    label = 'low' if avg_score < 15 else ('medium' if avg_score < 40 else 'high')

    return {'score': round(avg_score, 2), 'label': label, 'details': details}


# =============================================================================
# 10. 地理編碼
# =============================================================================

TAICHUNG_BOUNDS = {
    'lat_min': 24.0, 'lat_max': 24.5,
    'lon_min': 120.4, 'lon_max': 121.1
}

def is_in_taichung(lat, lon):
    return (TAICHUNG_BOUNDS['lat_min'] <= lat <= TAICHUNG_BOUNDS['lat_max'] and
            TAICHUNG_BOUNDS['lon_min'] <= lon <= TAICHUNG_BOUNDS['lon_max'])

DISTRICT_CENTERS = {
    '中區': (24.1436, 120.6794), '東區': (24.1378, 120.7024),
    '西區': (24.1402, 120.6632), '南區': (24.1193, 120.6642),
    '北區': (24.1614, 120.6818), '西屯區': (24.1815, 120.6177),
    '北屯區': (24.1824, 120.6884), '南屯區': (24.1384, 120.6096),
    '豐原區': (24.2500, 120.7177), '大里區': (24.0990, 120.6778),
    '太平區': (24.1268, 120.7164), '清水區': (24.2639, 120.5594),
    '沙鹿區': (24.2333, 120.5667), '大甲區': (24.3489, 120.6222),
    '東勢區': (24.2581, 120.8272), '梧棲區': (24.2550, 120.5319),
    '烏日區': (24.1044, 120.6227), '神岡區': (24.2583, 120.6653),
    '大肚區': (24.1536, 120.5406), '大雅區': (24.2289, 120.6486),
    '后里區': (24.3047, 120.7114), '霧峰區': (24.0617, 120.7006),
    '潭子區': (24.2089, 120.7058), '龍井區': (24.1917, 120.5461),
    '外埔區': (24.3319, 120.6556), '和平區': (24.2500, 121.0000),
    '石岡區': (24.2747, 120.7806), '大安區': (24.3461, 120.5856),
    '新社區': (24.2333, 120.8167)
}


# =============================================================================
# 主程式
# =============================================================================

if __name__ == '__main__':
    print(f'總資料筆數: {len(all_theft_data)}')
    print(f'有效資料筆數: {len(valid_data)}')
    print(f'\n各類型案件數:')
    print(valid_data['crime_category'].value_counts())
    print(f'\n年度趨勢:')
    print(yearly_total)
    print(f'\n行政區風險指標 (前10):')
    print(compute_district_risk().head(10).to_string(index=False))
