from typing import Union, List
import math
import re

from sqlalchemy.orm import Session

from app.service.user.core.models import Information
from app.common.path import QUERY_DB_ADMIN
from app.sql.db_pool import get_db_pool


def fetch_dialect_region(input_data: Union[str, List[str]], query_db=QUERY_DB_ADMIN, user=None,
                         db: Session = None, ) -> dict:
    if isinstance(input_data, list):
        query_str = input_data[0]  # 取數組的第一個元素
    else:
        query_str = input_data  # 如果是字符串，直接使用它

    def query_database(db_path: str, table_name: str) -> tuple:
        pool = get_db_pool(db_path)
        with pool.get_connection() as conn:
            cursor = conn.cursor()
            query = f"SELECT 音典分區 FROM {table_name} WHERE 簡稱 = ?"
            cursor.execute(query, (query_str,))
            result = cursor.fetchone()
        return result

    # 首先查詢主資料庫的表
    result = query_database(query_db, 'dialects')  # 假設主資料庫表名為 'dialects'

    # 如果在主資料庫中找不到結果，則查詢補充資料庫的表 informations，並根據 user_id 進行過濾
    if (not result) and db and user:
        # if db and user:
        result = db.query(Information.音典分區).filter(Information.簡稱 == query_str,
                                                       Information.user_id == user.id).first()

    # 如果找到結果，返回分區；否則返回錯誤消息
    if result:
        return {"音典分區": result[0]}
    else:
        return {"error": "未找到對應的音典分區"}


def get_coordinates_from_db(abbreviation_list, supplementary_abbreviation_list=None,
                            db_path=QUERY_DB_ADMIN, use_supplementary_db=False, user=None,
                            db: Session = None, region_mode='yindian'):
    def _quote_ident(name: str) -> str:
        return '"' + str(name).replace('"', '""') + '"'

    def _parse_lat_lon(value: str):
        if not value:
            return None, None
        parts = [p for p in re.split(r'[,，;；\\s]+', str(value).strip()) if p]
        if len(parts) < 2:
            raise ValueError(f'invalid lat/lon: {value}')
        return float(parts[0]), float(parts[1])

    def haversine(lat1, lon1, lat2, lon2):
        r = 6371
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)
        a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return r * c

    def get_optimal_zoom(lat_diff, lon_diff):
        max_diff = max(lat_diff, lon_diff)
        unit_distance = 1000 * max_diff / 6
        zoom_to_distance = {
            20: 10, 19: 10, 18: 25, 17: 50, 16: 100,
            15: 200, 14: 500, 13: 1000, 12: 2000, 11: 5000,
            10: 10000, 9: 20000, 8: 30000, 7: 50000, 6: 100000,
            5: 200000, 4: 500000, 3: 1000000, 2: 2000000
        }
        for zoom, distance_threshold in zoom_to_distance.items():
            if unit_distance <= distance_threshold:
                return zoom
        return 10

    abbreviation_list = [abbr for abbr in (abbreviation_list or []) if abbr]
    ordered_main_abbrs = list(dict.fromkeys(abbreviation_list))

    supplementary_abbreviation_list = [
        abbr for abbr in (supplementary_abbreviation_list or [])
        if abbr and abbr not in abbreviation_list
    ]

    result = []
    latitudes = []
    longitudes = []
    abbreviation_lat_lon_pairs = []
    abbreviation_region_pairs = {}

    pool = get_db_pool(db_path)
    with pool.get_connection() as conn:
        cursor = conn.cursor()

        partition_column = '地圖集二分區' if region_mode == 'map' else '音典分區'

        row_map = {}
        if ordered_main_abbrs:
            chunk_size = 500
            for i in range(0, len(ordered_main_abbrs), chunk_size):
                chunk = ordered_main_abbrs[i:i + chunk_size]
                placeholders = ','.join(['?'] * len(chunk))
                sql = (
                    f'SELECT {_quote_ident("簡稱")}, {_quote_ident("經緯度")}, {_quote_ident(partition_column)} '
                    f'FROM dialects WHERE {_quote_ident("簡稱")} IN ({placeholders})'
                )
                cursor.execute(sql, chunk)
                for row in cursor.fetchall():
                    if row[0] not in row_map:
                        row_map[row[0]] = (row[1], row[2])

        for abbreviation in ordered_main_abbrs:
            row = row_map.get(abbreviation)
            if not row:
                continue
            lat_lon_str, region = row
            try:
                latitude, longitude = _parse_lat_lon(lat_lon_str)
            except ValueError:
                continue
            result.append((latitude, longitude))
            latitudes.append(latitude)
            longitudes.append(longitude)
            abbreviation_lat_lon_pairs.append((abbreviation, (latitude, longitude)))
            abbreviation_region_pairs[abbreviation] = region

    if use_supplementary_db and supplementary_abbreviation_list and user and db:
        info_table = Information.__table__
        rows = (
            db.query(
                info_table.c['簡稱'],
                info_table.c['經緯度'],
                info_table.c['音典分區']
            )
            .filter(
                info_table.c['簡稱'].in_(supplementary_abbreviation_list),
                info_table.c['user_id'] == user.id
            )
            .all()
        )
        for abbreviation, lat_lon_str, region in rows:
            try:
                latitude, longitude = _parse_lat_lon(lat_lon_str)
            except ValueError:
                continue
            result.append((latitude, longitude))
            latitudes.append(latitude)
            longitudes.append(longitude)
            abbreviation_lat_lon_pairs.append((abbreviation, (latitude, longitude)))
            abbreviation_region_pairs[abbreviation] = region

    valid_latitudes = [lat for lat in latitudes if lat is not None]
    valid_longitudes = [lon for lon in longitudes if lon is not None]

    if valid_latitudes and valid_longitudes:
        center_latitude = (max(valid_latitudes) + min(valid_latitudes)) / 2
        center_longitude = (max(valid_longitudes) + min(valid_longitudes)) / 2
        center_coordinate = [round(center_latitude, 6), round(center_longitude, 6)]

        min_lat = min(valid_latitudes)
        max_lat = max(valid_latitudes)
        min_lon = min(valid_longitudes)
        max_lon = max(valid_longitudes)

        # O(1) bounding-box distance estimate to avoid O(n^2) pairwise loops.
        max_lat_distance = haversine(min_lat, center_longitude, max_lat, center_longitude)
        max_lon_distance = haversine(center_latitude, min_lon, center_latitude, max_lon)
        max_lat_distance = round(max_lat_distance, 2)
        max_lon_distance = round(max_lon_distance, 2)
        zoom_level = get_optimal_zoom(max_lat_distance, max_lon_distance)
    else:
        center_coordinate = None
        max_lat_distance = 0
        max_lon_distance = 0
        zoom_level = None

    coordinates = {
        'coordinates_locations': abbreviation_lat_lon_pairs,
        'region_mappings': abbreviation_region_pairs,
        'center_coordinate': center_coordinate,
        'max_distances': {
            'lat_km': max_lat_distance,
            'lon_km': max_lon_distance,
        },
        'zoom_level': zoom_level
    }

    return coordinates

