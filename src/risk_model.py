"""
台中安全路線導航 - 風險模型模組
SafeTaichung Risk Model Module

計算行政區風險指標與時段風險分數
"""

import pandas as pd
import numpy as np
from pathlib import Path

# 路徑設定
DATA_DIR = Path(__file__).parent.parent / 'data'
PROCESSED_DIR = DATA_DIR / 'processed'


def load_theft_data() -> pd.DataFrame:
    """載入竊盜資料"""
    df = pd.read_csv(PROCESSED_DIR / 'taichung_theft_all.csv', encoding='utf-8-sig')
    df['date'] = pd.to_datetime(df['date'])
    return df[df['is_valid'] == 1]


def load_population_data() -> pd.DataFrame:
    """載入人口資料"""
    return pd.read_csv(PROCESSED_DIR / 'district_population.csv', encoding='utf-8-sig')


def compute_district_risk_summary() -> pd.DataFrame:
    """
    計算行政區風險指標表

    欄位：
    - district: 行政區名稱
    - total_cases: 總竊盜件數
    - cases_per_10k_pop: 每萬人竊盜件數
    - daytime_cases_ratio: 白天(06-18時)案件占比
    - night_cases_ratio: 夜間(18-06時)案件占比
    - risk_level: 風險等級 (低/中/高)
    """
    theft_df = load_theft_data()
    pop_df = load_population_data()

    # 計算各行政區總件數
    district_cases = theft_df.groupby('district').size().reset_index(name='total_cases')

    # 計算白天/夜間案件數
    theft_df['is_daytime'] = theft_df['hour'].apply(lambda h: 1 if 6 <= h < 18 else 0)

    daytime_cases = theft_df.groupby('district')['is_daytime'].sum().reset_index(name='daytime_cases')

    # 合併資料
    summary = district_cases.merge(daytime_cases, on='district')
    summary = summary.merge(pop_df[['district', 'population']], on='district', how='left')

    # 計算指標
    summary['night_cases'] = summary['total_cases'] - summary['daytime_cases']
    summary['daytime_cases_ratio'] = (summary['daytime_cases'] / summary['total_cases'] * 100).round(1)
    summary['night_cases_ratio'] = (summary['night_cases'] / summary['total_cases'] * 100).round(1)
    summary['cases_per_10k_pop'] = (summary['total_cases'] / summary['population'] * 10000).round(2)

    # 計算風險等級（使用三分位數）
    q33 = summary['cases_per_10k_pop'].quantile(0.33)
    q67 = summary['cases_per_10k_pop'].quantile(0.67)

    def assign_risk_level(rate):
        if pd.isna(rate):
            return '未知'
        elif rate <= q33:
            return '低'
        elif rate <= q67:
            return '中'
        else:
            return '高'

    summary['risk_level'] = summary['cases_per_10k_pop'].apply(assign_risk_level)

    # 選擇輸出欄位
    output_cols = [
        'district', 'total_cases', 'population', 'cases_per_10k_pop',
        'daytime_cases_ratio', 'night_cases_ratio', 'risk_level'
    ]

    return summary[output_cols].sort_values('cases_per_10k_pop', ascending=False)


def compute_hourly_risk_summary() -> pd.DataFrame:
    """
    計算時段風險表

    欄位：
    - district: 行政區
    - hour: 時段 (0-23)
    - hour_cases: 該時段案件數
    - hour_ratio: 該時段案件占比
    - hour_risk_score: 時段風險分數
    """
    theft_df = load_theft_data()

    # 計算每個行政區每小時案件數
    hourly = theft_df.groupby(['district', 'hour']).size().reset_index(name='hour_cases')

    # 計算全市每小時案件分布（作為基準）
    city_hourly = theft_df.groupby('hour').size()
    city_hourly_mean = city_hourly.mean()

    # 計算各區各時段占比
    district_total = theft_df.groupby('district').size().reset_index(name='district_total')
    hourly = hourly.merge(district_total, on='district')
    hourly['hour_ratio'] = (hourly['hour_cases'] / hourly['district_total'] * 100).round(2)

    # 計算時段風險分數（相對於全日平均）
    # 分數 > 1 表示該時段風險高於平均
    hourly['hour_risk_score'] = (hourly['hour_cases'] / (hourly['district_total'] / 24)).round(2)

    # 選擇輸出欄位
    output_cols = ['district', 'hour', 'hour_cases', 'hour_ratio', 'hour_risk_score']

    return hourly[output_cols].sort_values(['district', 'hour'])


def get_district_risk(district: str) -> dict:
    """取得特定行政區的風險資訊"""
    summary = compute_district_risk_summary()
    row = summary[summary['district'] == district]

    if row.empty:
        return {'district': district, 'risk_level': '未知', 'cases_per_10k_pop': None}

    return row.iloc[0].to_dict()


def get_hour_risk(district: str, hour: int) -> dict:
    """取得特定行政區特定時段的風險資訊"""
    hourly = compute_hourly_risk_summary()
    row = hourly[(hourly['district'] == district) & (hourly['hour'] == hour)]

    if row.empty:
        return {'district': district, 'hour': hour, 'hour_risk_score': 1.0}

    return row.iloc[0].to_dict()


def compute_route_risk(districts: list, departure_hour: int) -> dict:
    """
    計算路線風險分數

    參數:
        districts: 路線經過的行政區列表
        departure_hour: 出發時間 (0-23)

    回傳:
        route_risk_score: 綜合風險分數
        route_risk_label: 風險標籤 (低/中/高)
        district_risks: 各行政區風險詳情
    """
    district_summary = compute_district_risk_summary()
    hourly_summary = compute_hourly_risk_summary()

    district_risks = []
    total_risk_score = 0

    for district in districts:
        # 取得行政區風險
        dist_row = district_summary[district_summary['district'] == district]
        if not dist_row.empty:
            cases_per_10k = dist_row.iloc[0]['cases_per_10k_pop']
            risk_level = dist_row.iloc[0]['risk_level']
        else:
            cases_per_10k = 0
            risk_level = '未知'

        # 取得時段風險
        hour_row = hourly_summary[
            (hourly_summary['district'] == district) &
            (hourly_summary['hour'] == departure_hour)
        ]
        if not hour_row.empty:
            hour_risk_score = hour_row.iloc[0]['hour_risk_score']
        else:
            hour_risk_score = 1.0

        # 計算該區段綜合風險
        segment_risk = cases_per_10k * hour_risk_score
        total_risk_score += segment_risk

        district_risks.append({
            'district': district,
            'cases_per_10k_pop': cases_per_10k,
            'risk_level': risk_level,
            'hour_risk_score': hour_risk_score,
            'segment_risk': round(segment_risk, 2)
        })

    # 計算平均風險分數
    avg_risk_score = total_risk_score / len(districts) if districts else 0

    # 分配風險標籤
    if avg_risk_score < 15:
        route_risk_label = '低'
    elif avg_risk_score < 40:
        route_risk_label = '中'
    else:
        route_risk_label = '高'

    return {
        'route_risk_score': round(avg_risk_score, 2),
        'route_risk_label': route_risk_label,
        'district_risks': district_risks,
        'departure_hour': departure_hour
    }


def save_risk_summaries():
    """儲存風險指標表"""
    district_summary = compute_district_risk_summary()
    hourly_summary = compute_hourly_risk_summary()

    district_summary.to_csv(
        PROCESSED_DIR / 'district_risk_summary.csv',
        index=False,
        encoding='utf-8-sig'
    )

    hourly_summary.to_csv(
        PROCESSED_DIR / 'hourly_risk_summary.csv',
        index=False,
        encoding='utf-8-sig'
    )

    print(f'已儲存：{PROCESSED_DIR / "district_risk_summary.csv"}')
    print(f'已儲存：{PROCESSED_DIR / "hourly_risk_summary.csv"}')

    return district_summary, hourly_summary


if __name__ == '__main__':
    # 執行時產生風險指標表
    district_summary, hourly_summary = save_risk_summaries()

    print('\n=== 行政區風險指標（前10名）===')
    print(district_summary.head(10).to_string(index=False))

    print('\n=== 時段風險範例（中區）===')
    print(hourly_summary[hourly_summary['district'] == '中區'].to_string(index=False))
