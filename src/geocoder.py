"""
台中安全路線導航 - 地址轉經緯度模組
SafeTaichung Geocoding Module

將犯罪案件地址轉換為經緯度座標
"""

import pandas as pd
import numpy as np
import json
import time
from pathlib import Path
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import random

# 路徑設定
DATA_DIR = Path(__file__).parent.parent / 'data'
PROCESSED_DIR = DATA_DIR / 'processed'
CACHE_FILE = PROCESSED_DIR / 'geocode_cache.json'

# 台中市整體邊界框（用於驗證座標）
TAICHUNG_BOUNDS = {
    'lat_min': 24.0,
    'lat_max': 24.5,
    'lon_min': 120.4,
    'lon_max': 121.1  # 和平區較東
}

# 台中市行政區中心座標與邊界（近似值）
DISTRICT_BOUNDS = {
    '中區': {'center': (24.1436, 120.6794), 'radius': 0.008},
    '東區': {'center': (24.1378, 120.7024), 'radius': 0.015},
    '西區': {'center': (24.1402, 120.6632), 'radius': 0.012},
    '南區': {'center': (24.1193, 120.6642), 'radius': 0.018},
    '北區': {'center': (24.1614, 120.6818), 'radius': 0.012},
    '西屯區': {'center': (24.1815, 120.6177), 'radius': 0.025},
    '北屯區': {'center': (24.1824, 120.6884), 'radius': 0.030},
    '南屯區': {'center': (24.1384, 120.6096), 'radius': 0.025},
    '豐原區': {'center': (24.2500, 120.7177), 'radius': 0.020},
    '大里區': {'center': (24.0990, 120.6778), 'radius': 0.025},
    '太平區': {'center': (24.1268, 120.7164), 'radius': 0.030},
    '清水區': {'center': (24.2639, 120.5594), 'radius': 0.025},
    '沙鹿區': {'center': (24.2333, 120.5667), 'radius': 0.020},
    '大甲區': {'center': (24.3489, 120.6222), 'radius': 0.025},
    '東勢區': {'center': (24.2581, 120.8272), 'radius': 0.025},
    '梧棲區': {'center': (24.2550, 120.5319), 'radius': 0.015},
    '烏日區': {'center': (24.1044, 120.6227), 'radius': 0.020},
    '神岡區': {'center': (24.2583, 120.6653), 'radius': 0.020},
    '大肚區': {'center': (24.1536, 120.5406), 'radius': 0.020},
    '大雅區': {'center': (24.2289, 120.6486), 'radius': 0.018},
    '后里區': {'center': (24.3047, 120.7114), 'radius': 0.025},
    '霧峰區': {'center': (24.0617, 120.7006), 'radius': 0.025},
    '潭子區': {'center': (24.2089, 120.7058), 'radius': 0.018},
    '龍井區': {'center': (24.1917, 120.5461), 'radius': 0.020},
    '外埔區': {'center': (24.3319, 120.6556), 'radius': 0.020},
    '和平區': {'center': (24.2500, 121.0000), 'radius': 0.080},
    '石岡區': {'center': (24.2747, 120.7806), 'radius': 0.015},
    '大安區': {'center': (24.3461, 120.5856), 'radius': 0.018},
    '新社區': {'center': (24.2333, 120.8167), 'radius': 0.030}
}


def load_cache() -> dict:
    """載入地理編碼快取"""
    if CACHE_FILE.exists():
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_cache(cache: dict):
    """儲存地理編碼快取"""
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def is_in_taichung(lat: float, lon: float) -> bool:
    """檢查座標是否在台中市範圍內"""
    return (TAICHUNG_BOUNDS['lat_min'] <= lat <= TAICHUNG_BOUNDS['lat_max'] and
            TAICHUNG_BOUNDS['lon_min'] <= lon <= TAICHUNG_BOUNDS['lon_max'])


def geocode_address(address: str, geolocator, cache: dict) -> tuple:
    """
    使用 Nominatim 對單一地址進行地理編碼

    回傳: (lat, lon, method) 或 (None, None, 'failed')
    """
    # 檢查快取（同時驗證座標是否在台中市範圍內）
    if address in cache:
        cached = cache[address]
        lat, lon = cached['lat'], cached['lon']
        if is_in_taichung(lat, lon):
            return lat, lon, 'cache'
        # 快取中的座標不在台中，需要重新編碼

    try:
        # 嘗試地理編碼
        location = geolocator.geocode(address, timeout=10)
        if location:
            lat, lon = location.latitude, location.longitude
            # 驗證座標是否在台中市範圍內
            if is_in_taichung(lat, lon):
                cache[address] = {'lat': lat, 'lon': lon}
                return lat, lon, 'nominatim'
            else:
                print(f"  ⚠ 座標超出台中範圍: {address[:25]} -> ({lat:.2f}, {lon:.2f})")
                return None, None, 'out_of_bounds'
    except (GeocoderTimedOut, GeocoderServiceError) as e:
        print(f"Geocoding error for {address}: {e}")
    except Exception as e:
        print(f"Unexpected error for {address}: {e}")

    return None, None, 'failed'


def jitter_within_district(district: str, seed: int = None) -> tuple:
    """
    在行政區範圍內產生隨機座標（用於無法精確定位的地址）

    使用高斯分布使點位更集中於中心
    """
    if district not in DISTRICT_BOUNDS:
        return None, None

    bounds = DISTRICT_BOUNDS[district]
    center_lat, center_lon = bounds['center']
    radius = bounds['radius']

    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)

    # 使用高斯分布產生偏移量（sigma = radius/2 使大部分點落在中心附近）
    lat_offset = np.random.normal(0, radius / 2)
    lon_offset = np.random.normal(0, radius / 2)

    # 限制在 2 倍 radius 內
    lat_offset = np.clip(lat_offset, -radius, radius)
    lon_offset = np.clip(lon_offset, -radius, radius)

    return center_lat + lat_offset, center_lon + lon_offset


def geocode_crime_data(
    use_nominatim: bool = False,
    sample_size: int = 100,
    save_interval: int = 50
) -> pd.DataFrame:
    """
    對犯罪資料進行地理編碼

    參數:
        use_nominatim: 是否使用 Nominatim API（較慢但較準確）
        sample_size: 使用 Nominatim 編碼的樣本數
        save_interval: 每幾筆儲存一次快取

    回傳:
        包含經緯度的 DataFrame
    """
    # 載入資料
    df = pd.read_csv(PROCESSED_DIR / 'taichung_theft_all.csv', encoding='utf-8-sig')
    df['date'] = pd.to_datetime(df['date'])

    print(f"載入 {len(df)} 筆犯罪資料")

    # 初始化結果欄位
    df['latitude'] = None
    df['longitude'] = None
    df['geocode_method'] = None

    # 載入快取
    cache = load_cache()
    print(f"快取中有 {len(cache)} 筆地址")

    # 初始化 geolocator
    geolocator = None
    if use_nominatim:
        geolocator = Nominatim(user_agent="safe_taichung_research")

    # 取得唯一地址列表
    unique_addresses = df['location'].unique()
    print(f"共 {len(unique_addresses)} 個唯一地址")

    # 對樣本地址使用 Nominatim
    if use_nominatim and sample_size > 0:
        # 優先選擇未在快取中的地址
        uncached = [addr for addr in unique_addresses if addr not in cache]
        sample_addresses = uncached[:sample_size] if len(uncached) >= sample_size else uncached

        print(f"對 {len(sample_addresses)} 個地址進行 Nominatim 編碼...")

        for i, address in enumerate(sample_addresses):
            if i % 10 == 0:
                print(f"  進度: {i}/{len(sample_addresses)}")

            lat, lon, method = geocode_address(address, geolocator, cache)

            if lat is not None:
                print(f"  ✓ {address[:20]}... -> ({lat:.4f}, {lon:.4f})")

            # 每 save_interval 筆儲存一次快取
            if (i + 1) % save_interval == 0:
                save_cache(cache)

            # Nominatim 有速率限制，需要間隔
            time.sleep(1.1)

        # 最後儲存快取
        save_cache(cache)

    # 對所有資料填入座標
    print("\n填入座標...")
    geocoded_count = 0
    jittered_count = 0

    for idx, row in df.iterrows():
        address = row['location']
        district = row['district']

        # 優先使用快取
        if address in cache:
            df.at[idx, 'latitude'] = cache[address]['lat']
            df.at[idx, 'longitude'] = cache[address]['lon']
            df.at[idx, 'geocode_method'] = 'geocoded'
            geocoded_count += 1
        else:
            # 使用行政區內隨機座標
            lat, lon = jitter_within_district(district, seed=idx)
            if lat is not None:
                df.at[idx, 'latitude'] = lat
                df.at[idx, 'longitude'] = lon
                df.at[idx, 'geocode_method'] = 'jittered'
                jittered_count += 1

    print(f"\n完成！")
    print(f"  - 精確定位: {geocoded_count} 筆")
    print(f"  - 區域隨機: {jittered_count} 筆")
    print(f"  - 無法定位: {len(df) - geocoded_count - jittered_count} 筆")

    return df


def save_geocoded_data(df: pd.DataFrame):
    """儲存地理編碼後的資料"""
    output_path = PROCESSED_DIR / 'taichung_theft_geocoded.csv'
    df.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"已儲存至 {output_path}")
    return output_path


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='對犯罪資料進行地理編碼')
    parser.add_argument('--nominatim', action='store_true', help='使用 Nominatim API')
    parser.add_argument('--sample', type=int, default=50, help='Nominatim 樣本數')

    args = parser.parse_args()

    # 執行地理編碼
    df = geocode_crime_data(
        use_nominatim=args.nominatim,
        sample_size=args.sample
    )

    # 儲存結果
    save_geocoded_data(df)

    # 顯示範例
    print("\n=== 地理編碼結果範例 ===")
    print(df[['district', 'location', 'latitude', 'longitude', 'geocode_method']].head(10))
