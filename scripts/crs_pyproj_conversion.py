#!/usr/bin/env python3
"""
使用 pyproj 進行坐標系轉換分析
將 TWD67 正確轉換為 WGS84，並與 API 提供的 WGS84 數值比對
"""

import os
import requests
import json
import pandas as pd
import folium
import math
from datetime import datetime
import numpy as np
from pyproj import CRS, Transformer

class CRSConversionAnalysis:
    def __init__(self):
        # 直接設置API Key
        self.api_key = "CWA-6310DF17-9FBC-4F67-B67B-F70BDEE7F379"
        self.base_url = "https://opendata.cwa.gov.tw/api/v1/rest/datastore"
        self.dataset_id = "O-A0003-001"
        
        # 定義坐標系
        self.twd67_crs = CRS.from_epsg(3828)  # TWD67 / TM2 zone 121 (正確的TWD67)
        self.wgs84_crs = CRS.from_epsg(4326)  # WGS84
        
        # 創建轉換器
        self.twd67_to_wgs84 = Transformer.from_crs(self.twd67_crs, self.wgs84_crs, always_xy=True)
        
        print("坐標系轉換器初始化完成")
        print(f"TWD67: {self.twd67_crs.name} (EPSG:3828)")
        print(f"WGS84: {self.wgs84_crs.name} (EPSG:4326)")
        
        # 測試轉換
        test_lon, test_lat = self.twd67_to_wgs84.transform(121.0, 23.5)
        print(f"測試轉換: TWD67(121.0, 23.5) -> WGS84({test_lon:.6f}, {test_lat:.6f})")
        
    def fetch_weather_data(self):
        """獲取氣象站資料"""
        url = f"{self.base_url}/{self.dataset_id}"
        headers = {
            'Authorization': self.api_key,
            'Accept': 'application/json'
        }
        params = {
            'format': 'JSON'
        }
        
        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"API 請求失敗: {e}")
            return None
    
    def parse_and_convert_coordinates(self, data):
        """解析坐標並進行轉換"""
        if not data or 'records' not in data:
            return None
        
        stations = []
        records = data['records']['Station']
        
        print(f"開始解析 {len(records)} 個測站的坐標資料...")
        
        for i, record in enumerate(records):
            try:
                # 獲取所有坐標
                coordinates = record['GeoInfo']['Coordinates']
                
                station_data = {
                    'station_id': record['StationId'],
                    'station_name': record['StationName'],
                    'location': record['GeoInfo']['CountyName'] + record['GeoInfo']['TownName'],
                    'coordinates': []
                }
                
                # 解析每個坐標系
                for j, coord in enumerate(coordinates):
                    coord_info = {
                        'index': j,
                        'coordinate_name': coord.get('CoordinateName', f'Coordinate_{j}'),
                        'latitude': float(coord['StationLatitude']),
                        'longitude': float(coord['StationLongitude']),
                        'description': coord.get('Description', '')
                    }
                    station_data['coordinates'].append(coord_info)
                
                # 如果有兩個坐標系，進行轉換分析
                if len(station_data['coordinates']) >= 2:
                    coord1 = station_data['coordinates'][0]  # 假設第一個是 TWD67
                    coord2 = station_data['coordinates'][1]  # 假設第二個是 WGS84
                    
                    # 計算原始差距
                    original_distance = self.calculate_distance(
                        coord1['latitude'], coord1['longitude'],
                        coord2['latitude'], coord2['longitude']
                    )
                    
                    # 使用 pyproj 將 TWD67 轉換為 WGS84
                    try:
                        # 只處理前5個測站進行調試
                        if i >= 5:
                            break
                        
                        # 注意：pyproj 需要 (longitude, latitude) 順序
                        print(f"正在轉換 {station_data['station_name']}:")
                        print(f"  TWD67: ({coord1['longitude']:.6f}, {coord1['latitude']:.6f})")
                        
                        converted_lon, converted_lat = self.twd67_to_wgs84.transform(
                            coord1['longitude'], coord1['latitude']
                        )
                        
                        print(f"  轉換後: ({converted_lon:.6f}, {converted_lat:.6f})")
                        print(f"  API WGS84: ({coord2['longitude']:.6f}, {coord2['latitude']:.6f})")
                        
                        # 計算轉換後的差距
                        converted_distance = self.calculate_distance(
                            converted_lat, converted_lon,
                            coord2['latitude'], coord2['longitude']
                        )
                        
                        print(f"  轉換後差距: {converted_distance:.2f} 公尺")
                        
                        station_data['original_distance_m'] = original_distance
                        station_data['original_distance_km'] = original_distance / 1000
                        station_data['converted_distance_m'] = converted_distance
                        station_data['converted_distance_km'] = converted_distance / 1000
                        station_data['improvement_m'] = original_distance - converted_distance
                        station_data['improvement_km'] = (original_distance - converted_distance) / 1000
                        station_data['improvement_percentage'] = ((original_distance - converted_distance) / original_distance) * 100
                        
                        # 保存轉換後的坐標
                        station_data['twd67_lat'] = coord1['latitude']
                        station_data['twd67_lon'] = coord1['longitude']
                        station_data['twd67_to_wgs84_lat'] = converted_lat
                        station_data['twd67_to_wgs84_lon'] = converted_lon
                        station_data['api_wgs84_lat'] = coord2['latitude']
                        station_data['api_wgs84_lon'] = coord2['longitude']
                        
                    except Exception as e:
                        print(f"坐標轉換失敗 {station_data['station_name']}: {e}")
                        station_data['conversion_error'] = str(e)
                
                stations.append(station_data)
                
                # 顯示進度
                if (i + 1) % 50 == 0:
                    print(f"已處理 {i + 1} 個測站...")
                
            except (KeyError, ValueError, TypeError) as e:
                print(f"解析站點資料時發生錯誤 {record.get('StationId', 'Unknown')}: {e}")
                continue
        
        print(f"坐標解析和轉換完成，成功處理 {len(stations)} 個測站")
        return stations
    
    def calculate_distance(self, lat1, lon1, lat2, lon2):
        """使用 Haversine 公式計算兩點間的距離"""
        R = 6371000  # 地球半徑（米）
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        
        a = (math.sin(delta_lat/2)**2 + 
             math.cos(lat1_rad) * math.cos(lat2_rad) * 
             math.sin(delta_lon/2)**2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c
    
    def generate_conversion_statistics(self, stations_data):
        """生成轉換統計資料"""
        if not stations_data:
            return None
        
        # 過濾成功轉換的測站
        successful_conversions = [s for s in stations_data 
                                if 'original_distance_m' in s and 'conversion_error' not in s]
        
        if not successful_conversions:
            return None
        
        original_distances = [s['original_distance_m'] for s in successful_conversions]
        converted_distances = [s['converted_distance_m'] for s in successful_conversions]
        improvements = [s['improvement_m'] for s in successful_conversions]
        improvement_percentages = [s['improvement_percentage'] for s in successful_conversions]
        
        stats = {
            'total_stations': len(stations_data),
            'successful_conversions': len(successful_conversions),
            'failed_conversions': len(stations_data) - len(successful_conversions),
            'original_stats': {
                'min_distance_m': min(original_distances),
                'max_distance_m': max(original_distances),
                'avg_distance_m': sum(original_distances) / len(original_distances),
                'median_distance_m': sorted(original_distances)[len(original_distances) // 2]
            },
            'converted_stats': {
                'min_distance_m': min(converted_distances),
                'max_distance_m': max(converted_distances),
                'avg_distance_m': sum(converted_distances) / len(converted_distances),
                'median_distance_m': sorted(converted_distances)[len(converted_distances) // 2]
            },
            'improvement_stats': {
                'min_improvement_m': min(improvements),
                'max_improvement_m': max(improvements),
                'avg_improvement_m': sum(improvements) / len(improvements),
                'median_improvement_m': sorted(improvements)[len(improvements) // 2],
                'min_improvement_percentage': min(improvement_percentages),
                'max_improvement_percentage': max(improvement_percentages),
                'avg_improvement_percentage': sum(improvement_percentages) / len(improvement_percentages),
                'median_improvement_percentage': sorted(improvement_percentages)[len(improvement_percentages) // 2]
            }
        }
        
        # 找出改善最大和最小的測站
        stats['best_improvements'] = sorted(successful_conversions, 
                                          key=lambda x: x['improvement_percentage'], 
                                          reverse=True)[:10]
        stats['worst_improvements'] = sorted(successful_conversions, 
                                           key=lambda x: x['improvement_percentage'])[:10]
        
        return stats
    
    def create_comparison_map(self, stations_data):
        """創建轉換比較地圖"""
        successful_conversions = [s for s in stations_data 
                                if 'original_distance_m' in s and 'conversion_error' not in s]
        
        if not successful_conversions:
            return None
        
        print(f"地圖將顯示 {len(successful_conversions)} 個成功轉換的測站")
        
        # 計算地圖中心點
        all_lats = []
        all_lons = []
        
        for station in successful_conversions:
            all_lats.extend([
                station['api_wgs84_lat'], 
                station['twd67_to_wgs84_lat']
            ])
            all_lons.extend([
                station['api_wgs84_lon'], 
                station['twd67_to_wgs84_lon']
            ])
        
        center_lat = sum(all_lats) / len(all_lats)
        center_lon = sum(all_lons) / len(all_lons)
        
        # 創建地圖
        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=8,
            tiles='OpenStreetMap'
        )
        
        # 添加坐標點和連線
        for station in successful_conversions:
            # API WGS84 坐標 - 藍色
            folium.CircleMarker(
                location=[station['api_wgs84_lat'], station['api_wgs84_lon']],
                radius=6,
                popup=f"<b>{station['station_name']}</b><br>"
                      f"API WGS84<br>"
                      f"緯度: {station['api_wgs84_lat']:.6f}<br>"
                      f"經度: {station['api_wgs84_lon']:.6f}",
                color='blue',
                fill=True,
                fillColor='blue',
                fillOpacity=0.7
            ).add_to(m)
            
            # 轉換後的 WGS84 坐標 - 紅色
            folium.CircleMarker(
                location=[station['twd67_to_wgs84_lat'], station['twd67_to_wgs84_lon']],
                radius=6,
                popup=f"<b>{station['station_name']}</b><br>"
                      f"TWD67→WGS84<br>"
                      f"緯度: {station['twd67_to_wgs84_lat']:.6f}<br>"
                      f"經度: {station['twd67_to_wgs84_lon']:.6f}<br>"
                      f"改善: {station['improvement_percentage']:.1f}%",
                color='red',
                fill=True,
                fillColor='red',
                fillOpacity=0.7
            ).add_to(m)
            
            # 連接兩個坐標點的線
            folium.PolyLine(
                locations=[
                    [station['api_wgs84_lat'], station['api_wgs84_lon']],
                    [station['twd67_to_wgs84_lat'], station['twd67_to_wgs84_lon']]
                ],
                color='green',
                weight=2,
                opacity=0.6,
                popup=f"<b>{station['station_name']}</b><br>"
                      f"轉換後差距: {station['converted_distance_km']:.3f} km<br>"
                      f"改善程度: {station['improvement_percentage']:.1f}%"
            ).add_to(m)
        
        # 添加圖例
        legend_html = '''
        <div style="position: fixed; 
                    top: 10px; right: 10px; width: 280px; height: 160px; 
                    background-color: white; border:2px solid grey; z-index:9999; 
                    font-size:14px; padding: 10px;
                    box-shadow: 3px 3px 3px rgba(0,0,0,0.3);">
        <h4 style="margin-top: 0;">坐標轉換比較圖例</h4>
        <p><i class="fa fa-circle" style="color:blue"></i> API WGS84坐標</p>
        <p><i class="fa fa-circle" style="color:red"></i> TWD67→WGS84轉換</p>
        <p><i class="fa fa-minus" style="color:green"></i> 轉換後差距</p>
        <p style="font-size: 12px; color: #666;">使用pyproj進行坐標轉換</p>
        </div>
        '''
        m.get_root().html.add_child(folium.Element(legend_html))
        
        return m
    
    def save_results(self, stations_data, stats, map_obj):
        """儲存分析結果"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 儲存詳細資料
        successful_conversions = [s for s in stations_data 
                                if 'original_distance_m' in s and 'conversion_error' not in s]
        
        df = pd.DataFrame([
            {
                '測站ID': station['station_id'],
                '測站名稱': station['station_name'],
                '位置': station['location'],
                '原始差距(km)': station.get('original_distance_km', None),
                '轉換後差距(km)': station.get('converted_distance_km', None),
                '改善程度(公尺)': station.get('improvement_m', None),
                '改善百分比': station.get('improvement_percentage', None),
                'TWD67緯度': station.get('twd67_lat', None),
                'TWD67經度': station.get('twd67_lon', None),
                '轉換WGS84緯度': station.get('twd67_to_wgs84_lat', None),
                '轉換WGS84經度': station.get('twd67_to_wgs84_lon', None),
                'API_WGS84緯度': station.get('api_wgs84_lat', None),
                'API_WGS84經度': station.get('api_wgs84_lon', None),
                '轉換錯誤': station.get('conversion_error', None)
            }
            for station in stations_data
        ])
        
        df.to_csv(f'outputs/crs_pyproj_conversion_{timestamp}.csv', index=False, encoding='utf-8-sig')
        
        # 儲存統計資料
        with open(f'outputs/crs_pyproj_statistics_{timestamp}.json', 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
        
        # 儲存地圖
        if map_obj:
            map_obj.save(f'outputs/crs_pyproj_map_{timestamp}.html')
        
        print(f"坐標轉換分析結果已儲存至 outputs/ 目錄")
        print(f"- 詳細資料: crs_pyproj_conversion_{timestamp}.csv")
        print(f"- 統計資料: crs_pyproj_statistics_{timestamp}.json")
        print(f"- 轉換地圖: crs_pyproj_map_{timestamp}.html")
        
        return timestamp
    
    def run_analysis(self):
        """執行完整的坐標轉換分析"""
        print("=== PyProj 坐標轉換分析開始 ===")
        print("開始獲取真實氣象站資料...")
        data = self.fetch_weather_data()
        
        if not data:
            print("無法獲取氣象站資料")
            return
        
        print("解析坐標並進行轉換...")
        stations_data = self.parse_and_convert_coordinates(data)
        
        if not stations_data:
            print("無法解析坐標資料")
            return
        
        print("生成轉換統計資料...")
        stats = self.generate_conversion_statistics(stations_data)
        
        if not stats:
            print("無法生成統計資料")
            return
        
        print("創建轉換比較地圖...")
        map_obj = self.create_comparison_map(stations_data)
        
        print("儲存分析結果...")
        timestamp = self.save_results(stations_data, stats, map_obj)
        
        # 顯示統計摘要
        print("\n=== PyProj 坐標轉換分析摘要 ===")
        print(f"總測站數量: {stats['total_stations']}")
        print(f"成功轉換: {stats['successful_conversions']}")
        print(f"轉換失敗: {stats['failed_conversions']}")
        
        print(f"\n=== 原始差距統計 ===")
        orig = stats['original_stats']
        print(f"最小差距: {orig['min_distance_m']:.2f} 公尺")
        print(f"最大差距: {orig['max_distance_m']:.2f} 公尺")
        print(f"平均差距: {orig['avg_distance_m']:.2f} 公尺")
        print(f"中位數差距: {orig['median_distance_m']:.2f} 公尺")
        
        print(f"\n=== 轉換後差距統計 ===")
        conv = stats['converted_stats']
        print(f"最小差距: {conv['min_distance_m']:.2f} 公尺")
        print(f"最大差距: {conv['max_distance_m']:.2f} 公尺")
        print(f"平均差距: {conv['avg_distance_m']:.2f} 公尺")
        print(f"中位數差距: {conv['median_distance_m']:.2f} 公尺")
        
        print(f"\n=== 改善程度統計 ===")
        imp = stats['improvement_stats']
        print(f"最小改善: {imp['min_improvement_m']:.2f} 公尺 ({imp['min_improvement_percentage']:.1f}%)")
        print(f"最大改善: {imp['max_improvement_m']:.2f} 公尺 ({imp['max_improvement_percentage']:.1f}%)")
        print(f"平均改善: {imp['avg_improvement_m']:.2f} 公尺 ({imp['avg_improvement_percentage']:.1f}%)")
        print(f"中位數改善: {imp['median_improvement_m']:.2f} 公尺 ({imp['median_improvement_percentage']:.1f}%)")
        
        print(f"\n=== 改善最大的前10個測站 ===")
        for i, station in enumerate(stats['best_improvements'], 1):
            print(f"{i:2d}. {station['station_name']:8s}: 改善 {station['improvement_percentage']:.1f}% "
                  f"({station['improvement_m']:.2f} 公尺)")
        
        print(f"\n=== 改善最小的前10個測站 ===")
        for i, station in enumerate(stats['worst_improvements'], 1):
            print(f"{i:2d}. {station['station_name']:8s}: 改善 {station['improvement_percentage']:.1f}% "
                  f"({station['improvement_m']:.2f} 公尺)")
        
        print(f"\n=== 結論 ===")
        if imp['avg_improvement_percentage'] > 50:
            print("✅ 坐標轉換顯著改善了差距！")
        elif imp['avg_improvement_percentage'] > 10:
            print("⚠️ 坐標轉換有改善，但差距仍然存在")
        else:
            print("❌ 坐標轉換改善有限，差距可能來自其他因素")
        
        print(f"\n=== 分析完成 ===")
        print(f"所有結果已儲存，時間戳: {timestamp}")
        
        return timestamp

if __name__ == "__main__":
    analyzer = CRSConversionAnalysis()
    analyzer.run_analysis()
