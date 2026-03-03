#!/usr/bin/env python3
"""
坐標系分析腳本 - TWD67 vs WGS84 比較分析
使用真實CWA API資料進行完整的坐標系比較分析
"""

import os
import requests
import json
import pandas as pd
import folium
import math
from datetime import datetime
import numpy as np

class CRSCoordinateAnalysis:
    def __init__(self):
        # 直接設置API Key
        self.api_key = "CWA-6310DF17-9FBC-4F67-B67B-F70BDEE7F379"
        self.base_url = "https://opendata.cwa.gov.tw/api/v1/rest/datastore"
        self.dataset_id = "O-A0003-001"
        
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
    
    def parse_coordinates(self, data):
        """解析不同坐標系的資料"""
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
                
                # 計算坐標間的距離
                if len(station_data['coordinates']) >= 2:
                    coord1 = station_data['coordinates'][0]
                    coord2 = station_data['coordinates'][1]
                    
                    # 使用 Haversine 公式計算距離（米）
                    distance = self.calculate_distance(
                        coord1['latitude'], coord1['longitude'],
                        coord2['latitude'], coord2['longitude']
                    )
                    
                    station_data['distance_meters'] = distance
                    station_data['distance_kilometers'] = distance / 1000
                
                stations.append(station_data)
                
                # 顯示進度
                if (i + 1) % 50 == 0:
                    print(f"已處理 {i + 1} 個測站...")
                
            except (KeyError, ValueError, TypeError) as e:
                print(f"解析站點資料時發生錯誤 {record.get('StationId', 'Unknown')}: {e}")
                continue
        
        print(f"坐標解析完成，成功處理 {len(stations)} 個測站")
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
    
    def generate_statistics(self, stations_data):
        """生成統計資料"""
        if not stations_data:
            return None
        
        stats = {
            'total_stations': len(stations_data),
            'stations_with_multiple_coords': 0,
            'distances': [],
            'coordinate_systems': set(),
            'coordinate_details': {}
        }
        
        for station in stations_data:
            if len(station['coordinates']) >= 2:
                stats['stations_with_multiple_coords'] += 1
                
                if 'distance_kilometers' in station:
                    stats['distances'].append(station['distance_kilometers'])
            
            for coord in station['coordinates']:
                stats['coordinate_systems'].add(coord['coordinate_name'])
                
                # 統計每種坐標系的使用次數
                if coord['coordinate_name'] not in stats['coordinate_details']:
                    stats['coordinate_details'][coord['coordinate_name']] = {
                        'count': 0,
                        'description': coord['description']
                    }
                stats['coordinate_details'][coord['coordinate_name']]['count'] += 1
        
        # 計算距離統計
        if stats['distances']:
            stats['distance_stats'] = {
                'min_distance_km': min(stats['distances']),
                'max_distance_km': max(stats['distances']),
                'avg_distance_km': sum(stats['distances']) / len(stats['distances']),
                'median_distance_km': sorted(stats['distances'])[len(stats['distances']) // 2]
            }
        
        stats['coordinate_systems'] = list(stats['coordinate_systems'])
        
        return stats
    
    def create_comparison_map(self, stations_data):
        """創建坐標系比較地圖"""
        if not stations_data:
            return None
        
        # 只顯示有距離資料的測站
        valid_stations = [s for s in stations_data if 'distance_kilometers' in s]
        print(f"地圖將顯示 {len(valid_stations)} 個有多個坐標的測站")
        
        # 計算地圖中心點
        all_lats = []
        all_lons = []
        
        for station in valid_stations:
            for coord in station['coordinates']:
                all_lats.append(coord['latitude'])
                all_lons.append(coord['longitude'])
        
        center_lat = sum(all_lats) / len(all_lats)
        center_lon = sum(all_lons) / len(all_lons)
        
        # 創建地圖
        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=8,
            tiles='OpenStreetMap'
        )
        
        # 添加坐標點
        for station in valid_stations:
            if len(station['coordinates']) >= 2:
                # 第一個坐標系 (TWD67) - 藍色
                coord1 = station['coordinates'][0]
                folium.CircleMarker(
                    location=[coord1['latitude'], coord1['longitude']],
                    radius=6,
                    popup=f"<b>{station['station_name']}測站</b><br>"
                          f"{coord1['coordinate_name']}<br>"
                          f"緯度: {coord1['latitude']:.6f}<br>"
                          f"經度: {coord1['longitude']:.6f}<br>"
                          f"描述: {coord1['description']}",
                    color='blue',
                    fill=True,
                    fillColor='blue',
                    fillOpacity=0.7
                ).add_to(m)
                
                # 第二個坐標系 (WGS84) - 紅色
                coord2 = station['coordinates'][1]
                folium.CircleMarker(
                    location=[coord2['latitude'], coord2['longitude']],
                    radius=6,
                    popup=f"<b>{station['station_name']}測站</b><br>"
                          f"{coord2['coordinate_name']}<br>"
                          f"緯度: {coord2['latitude']:.6f}<br>"
                          f"經度: {coord2['longitude']:.6f}<br>"
                          f"描述: {coord2['description']}",
                    color='red',
                    fill=True,
                    fillColor='red',
                    fillOpacity=0.7
                ).add_to(m)
                
                # 連接兩個坐標點的線
                folium.PolyLine(
                    locations=[
                        [coord1['latitude'], coord1['longitude']],
                        [coord2['latitude'], coord2['longitude']]
                    ],
                    color='green',
                    weight=2,
                    opacity=0.6,
                    popup=f"<b>{station['station_name']}</b><br>"
                          f"距離: {station.get('distance_kilometers', 0):.3f} km"
                ).add_to(m)
                
                # 添加距離標籤
                mid_lat = (coord1['latitude'] + coord2['latitude']) / 2
                mid_lon = (coord1['longitude'] + coord2['longitude']) / 2
                folium.Marker(
                    location=[mid_lat, mid_lon],
                    icon=folium.DivIcon(
                        html=f'<div style="font-size: 10px; color: green; font-weight: bold;">'
                             f'{station.get("distance_kilometers", 0):.1f}km</div>',
                        icon_size=(60, 20),
                        icon_anchor=(30, 10)
                    )
                ).add_to(m)
        
        # 添加圖例
        legend_html = '''
        <div style="position: fixed; 
                    top: 10px; right: 10px; width: 250px; height: 140px; 
                    background-color: white; border:2px solid grey; z-index:9999; 
                    font-size:14px; padding: 10px;
                    box-shadow: 3px 3px 3px rgba(0,0,0,0.3);">
        <h4 style="margin-top: 0;">坐標系比較圖例</h4>
        <p><i class="fa fa-circle" style="color:blue"></i> TWD67坐標系</p>
        <p><i class="fa fa-circle" style="color:red"></i> WGS84坐標系</p>
        <p><i class="fa fa-minus" style="color:green"></i> 坐標差距連線</p>
        <p style="font-size: 12px; color: #666;">基於CWA真實資料</p>
        </div>
        '''
        m.get_root().html.add_child(folium.Element(legend_html))
        
        return m
    
    def save_results(self, stations_data, stats, map_obj):
        """儲存分析結果"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 儲存詳細資料
        df = pd.DataFrame([
            {
                '測站ID': station['station_id'],
                '測站名稱': station['station_name'],
                '位置': station['location'],
                '坐標系1': station['coordinates'][0]['coordinate_name'] if len(station['coordinates']) > 0 else '',
                '坐標系1緯度': station['coordinates'][0]['latitude'] if len(station['coordinates']) > 0 else None,
                '坐標系1經度': station['coordinates'][0]['longitude'] if len(station['coordinates']) > 0 else None,
                '坐標系2': station['coordinates'][1]['coordinate_name'] if len(station['coordinates']) > 1 else '',
                '坐標系2緯度': station['coordinates'][1]['latitude'] if len(station['coordinates']) > 1 else None,
                '坐標系2經度': station['coordinates'][1]['longitude'] if len(station['coordinates']) > 1 else None,
                '坐標差距(km)': station.get('distance_kilometers', None)
            }
            for station in stations_data
        ])
        
        df.to_csv(f'outputs/crs_coordinate_analysis_{timestamp}.csv', index=False, encoding='utf-8-sig')
        
        # 儲存統計資料
        with open(f'outputs/crs_statistics_{timestamp}.json', 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
        
        # 儲存地圖
        if map_obj:
            map_obj.save(f'outputs/crs_comparison_map_{timestamp}.html')
        
        print(f"坐標系分析結果已儲存至 outputs/ 目錄")
        print(f"- 詳細資料: crs_coordinate_analysis_{timestamp}.csv")
        print(f"- 統計資料: crs_statistics_{timestamp}.json")
        print(f"- 比較地圖: crs_comparison_map_{timestamp}.html")
        
        return timestamp
    
    def run_analysis(self):
        """執行完整分析"""
        print("=== 坐標系比較分析開始 ===")
        print("開始獲取真實氣象站資料...")
        data = self.fetch_weather_data()
        
        if not data:
            print("無法獲取氣象站資料")
            return
        
        print("解析坐標資料...")
        stations_data = self.parse_coordinates(data)
        
        if not stations_data:
            print("無法解析坐標資料")
            return
        
        print("生成統計資料...")
        stats = self.generate_statistics(stations_data)
        
        print("創建比較地圖...")
        map_obj = self.create_comparison_map(stations_data)
        
        print("儲存分析結果...")
        timestamp = self.save_results(stations_data, stats, map_obj)
        
        # 顯示統計摘要
        print("\n=== 坐標系比較分析摘要 ===")
        print(f"總測站數量: {stats['total_stations']}")
        print(f"具有多個坐標的測站: {stats['stations_with_multiple_coords']}")
        print(f"發現的坐標系: {', '.join(stats['coordinate_systems'])}")
        
        # 顯示坐標系詳細資訊
        print(f"\n=== 坐標系詳細資訊 ===")
        for coord_name, details in stats['coordinate_details'].items():
            print(f"{coord_name}: {details['count']} 個測站使用")
            print(f"  描述: {details['description']}")
        
        if 'distance_stats' in stats:
            ds = stats['distance_stats']
            print(f"\n坐標距離統計:")
            print(f"最小距離: {ds['min_distance_km']:.6f} km ({ds['min_distance_km']*1000:.2f} 公尺)")
            print(f"最大距離: {ds['max_distance_km']:.6f} km ({ds['max_distance_km']*1000:.2f} 公尺)")
            print(f"平均距離: {ds['avg_distance_km']:.6f} km ({ds['avg_distance_km']*1000:.2f} 公尺)")
            print(f"中位數距離: {ds['median_distance_km']:.6f} km ({ds['median_distance_km']*1000:.2f} 公尺)")
        
        # 顯示距離最大的前10個測站
        stations_with_distance = [s for s in stations_data if 'distance_kilometers' in s]
        stations_with_distance.sort(key=lambda x: x['distance_kilometers'], reverse=True)
        
        print(f"\n=== 坐標差距最大的前10個測站 ===")
        for i, station in enumerate(stations_with_distance[:10]):
            print(f"{i+1:2d}. {station['station_name']:8s}: {station['distance_kilometers']:.6f} km "
                  f"({station['distance_meters']:.2f} 公尺)")
        
        print(f"\n=== 分析完成 ===")
        print(f"所有結果已儲存，時間戳: {timestamp}")
        
        return timestamp

if __name__ == "__main__":
    analyzer = CRSCoordinateAnalysis()
    analyzer.run_analysis()
