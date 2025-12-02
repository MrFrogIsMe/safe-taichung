"""
SafeTaichung - Google Maps API 整合模組

提供地理編碼與路線規劃功能
"""

import os
from typing import Optional
from datetime import datetime
from dotenv import load_dotenv

# 載入環境變數
load_dotenv()

# 延遲載入 googlemaps，避免在沒有 API key 時出錯
_gmaps_client = None


def get_client():
    """取得 Google Maps Client（單例模式）"""
    global _gmaps_client

    if _gmaps_client is None:
        import googlemaps

        api_key = os.getenv('GOOGLE_MAPS_API_KEY')
        if not api_key:
            raise ValueError(
                "請設定 GOOGLE_MAPS_API_KEY 環境變數\n"
                "1. 建立 .env 檔案\n"
                "2. 加入: GOOGLE_MAPS_API_KEY=your_api_key_here\n"
                "取得 API Key: https://console.cloud.google.com/apis/credentials"
            )
        _gmaps_client = googlemaps.Client(key=api_key)

    return _gmaps_client


# ============================================================
# 地理編碼功能
# ============================================================

def geocode(address: str, region: str = 'tw') -> Optional[dict]:
    """
    將地址轉換為經緯度座標

    Args:
        address: 地址字串（例如：台中市西屯區台灣大道三段）
        region: 區域偏好（預設台灣）

    Returns:
        {'lat': float, 'lng': float, 'formatted_address': str} 或 None
    """
    try:
        client = get_client()
        results = client.geocode(address, region=region, language='zh-TW')

        if results:
            location = results[0]['geometry']['location']
            return {
                'lat': location['lat'],
                'lng': location['lng'],
                'formatted_address': results[0]['formatted_address']
            }
    except Exception as e:
        print(f"Geocoding error: {e}")

    return None


def reverse_geocode(lat: float, lng: float) -> Optional[str]:
    """
    將經緯度座標轉換為地址

    Args:
        lat: 緯度
        lng: 經度

    Returns:
        格式化的地址字串或 None
    """
    try:
        client = get_client()
        results = client.reverse_geocode((lat, lng), language='zh-TW')

        if results:
            return results[0]['formatted_address']
    except Exception as e:
        print(f"Reverse geocoding error: {e}")

    return None


# ============================================================
# 路線規劃功能
# ============================================================

def get_directions(
    origin: str | tuple,
    destination: str | tuple,
    mode: str = 'walking',
    departure_time: datetime = None,
    alternatives: bool = True,
    avoid: list = None
) -> Optional[list]:
    """
    取得兩點之間的路線

    Args:
        origin: 起點（地址字串或 (lat, lng) tuple）
        destination: 終點（地址字串或 (lat, lng) tuple）
        mode: 交通方式 ('driving', 'walking', 'bicycling', 'transit')
        departure_time: 出發時間（用於即時交通資訊）
        alternatives: 是否回傳多條替代路線
        avoid: 避開項目列表 (['tolls', 'highways', 'ferries'])

    Returns:
        路線列表，每條路線包含距離、時間、步驟等資訊
    """
    try:
        client = get_client()

        results = client.directions(
            origin=origin,
            destination=destination,
            mode=mode,
            departure_time=departure_time or datetime.now(),
            alternatives=alternatives,
            avoid=avoid,
            language='zh-TW',
            region='tw'
        )

        if not results:
            return None

        routes = []
        for route in results:
            leg = route['legs'][0]  # 單一起終點只有一個 leg

            route_info = {
                'summary': route.get('summary', ''),
                'distance': {
                    'text': leg['distance']['text'],
                    'meters': leg['distance']['value']
                },
                'duration': {
                    'text': leg['duration']['text'],
                    'seconds': leg['duration']['value']
                },
                'start_address': leg['start_address'],
                'end_address': leg['end_address'],
                'start_location': leg['start_location'],
                'end_location': leg['end_location'],
                'steps': [],
                'polyline': route['overview_polyline']['points'],
                'warnings': route.get('warnings', [])
            }

            # 解析每個步驟
            for step in leg['steps']:
                step_info = {
                    'instruction': step.get('html_instructions', ''),
                    'distance': step['distance']['text'],
                    'duration': step['duration']['text'],
                    'start_location': step['start_location'],
                    'end_location': step['end_location'],
                    'travel_mode': step['travel_mode']
                }
                route_info['steps'].append(step_info)

            routes.append(route_info)

        return routes

    except Exception as e:
        print(f"Directions error: {e}")
        return None


def get_distance_matrix(
    origins: list,
    destinations: list,
    mode: str = 'walking'
) -> Optional[dict]:
    """
    計算多個起點到多個終點的距離矩陣

    Args:
        origins: 起點列表（地址或座標）
        destinations: 終點列表（地址或座標）
        mode: 交通方式

    Returns:
        距離矩陣資訊
    """
    try:
        client = get_client()

        result = client.distance_matrix(
            origins=origins,
            destinations=destinations,
            mode=mode,
            language='zh-TW',
            region='tw'
        )

        return result

    except Exception as e:
        print(f"Distance matrix error: {e}")
        return None


# ============================================================
# 輔助函數
# ============================================================

def decode_polyline(polyline: str) -> list:
    """
    解碼 Google Maps polyline 字串為座標列表

    Args:
        polyline: 編碼的 polyline 字串

    Returns:
        [(lat, lng), ...] 座標列表
    """
    import googlemaps
    return googlemaps.convert.decode_polyline(polyline)


def format_route_summary(route: dict) -> str:
    """
    格式化路線摘要為可讀字串

    Args:
        route: get_directions 回傳的單一路線

    Returns:
        格式化的路線摘要
    """
    lines = [
        f"路線: {route['summary']}",
        f"距離: {route['distance']['text']}",
        f"時間: {route['duration']['text']}",
        f"起點: {route['start_address']}",
        f"終點: {route['end_address']}",
        "",
        "步驟:"
    ]

    for i, step in enumerate(route['steps'], 1):
        # 移除 HTML 標籤
        instruction = step['instruction'].replace('<b>', '').replace('</b>', '')
        instruction = instruction.replace('<div style="font-size:0.9em">', ' (')
        instruction = instruction.replace('</div>', ')')
        lines.append(f"  {i}. {instruction} ({step['distance']})")

    return '\n'.join(lines)


# ============================================================
# 測試函數
# ============================================================

def test_api():
    """測試 API 連線"""
    print("=== Google Maps API 測試 ===\n")

    # 測試地理編碼
    print("1. 測試地理編碼...")
    result = geocode("台中火車站")
    if result:
        print(f"   ✓ 台中火車站: ({result['lat']:.4f}, {result['lng']:.4f})")
        print(f"   地址: {result['formatted_address']}")
    else:
        print("   ✗ 地理編碼失敗")
        return False

    # 測試路線規劃
    print("\n2. 測試路線規劃...")
    routes = get_directions("台中火車站", "逢甲夜市", mode="walking")
    if routes:
        print(f"   ✓ 找到 {len(routes)} 條路線")
        route = routes[0]
        print(f"   最短路線: {route['distance']['text']}, {route['duration']['text']}")
    else:
        print("   ✗ 路線規劃失敗")
        return False

    print("\n=== API 測試通過 ===")
    return True


if __name__ == '__main__':
    test_api()
