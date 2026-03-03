#!/usr/bin/env python3
"""
中央氣象署自動氣象站觀測 API 串接腳本
API: O-A0003-001 (自動氣象站觀測資料)
獲取全台即時氣溫數據
"""

import os
import requests
import json
import math
from datetime import datetime
import pandas as pd
from dotenv import load_dotenv

# 載入環境變數
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
print(f"正在載入 .env 檔案: {dotenv_path}")
load_dotenv(dotenv_path)

# 檢查是否成功載入
api_key = os.getenv('CWA_API_KEY')
print(f"API Key 載入結果: {api_key[:10]}..." if api_key else "API Key 載入失敗")

class CWAWeatherAPI:
    def __init__(self):
        # 直接設置API Key
        self.api_key = "CWA-6310DF17-9FBC-4F67-B67B-F70BDEE7F379"
        print(f"CWAWeatherAPI 初始化，API Key: {self.api_key[:10]}...")
        
        self.base_url = "https://opendata.cwa.gov.tw/api/v1/rest/datastore"
        self.dataset_id = "O-A0003-001"  # 自動氣象站觀測資料
        
        if not self.api_key:
            raise ValueError("CWA_API_KEY not found in environment variables")
    
    def fetch_weather_data(self):
        """獲取全台自動氣象站觀測資料"""
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
    
    def parse_temperature_data(self, data):
        """解析氣溫數據"""
        if not data or 'records' not in data:
            return None
        
        stations = []
        records = data['records']['Station']
        
        for record in records:
            try:
                station_info = {
                    'station_id': record['StationId'],
                    'station_name': record['StationName'],
                    'latitude': float(record['GeoInfo']['Coordinates'][1]['StationLatitude']),  # 使用 WGS84 座標
                    'longitude': float(record['GeoInfo']['Coordinates'][1]['StationLongitude']),
                    'temperature': float(record['WeatherElement']['AirTemperature']) if record['WeatherElement']['AirTemperature'] else None,
                    'humidity': float(record['WeatherElement']['RelativeHumidity']) if record['WeatherElement']['RelativeHumidity'] else None,
                    'observation_time': record['ObsTime']['DateTime'],
                    'location': record['GeoInfo']['CountyName'] + record['GeoInfo']['TownName'],
                    'weather': record['WeatherElement'].get('Weather', ''),
                    'wind_speed': float(record['WeatherElement']['WindSpeed']) if record['WeatherElement']['WindSpeed'] else None,
                    'wind_direction': float(record['WeatherElement']['WindDirection']) if record['WeatherElement']['WindDirection'] else None,
                    'air_pressure': float(record['WeatherElement']['AirPressure']) if record['WeatherElement']['AirPressure'] else None
                }
                stations.append(station_info)
            except (KeyError, ValueError, TypeError) as e:
                print(f"解析站點資料時發生錯誤 {record.get('StationId', 'Unknown')}: {e}")
                continue
        
        return stations
    
    def save_to_csv(self, stations_data, filename=None):
        """將資料儲存為 CSV 檔案"""
        if not stations_data:
            print("沒有資料可儲存")
            return
        
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"outputs/weather_stations_{timestamp}.csv"
        
        df = pd.DataFrame(stations_data)
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        print(f"資料已儲存至: {filename}")
        return filename
    
    def get_temperature_summary(self, stations_data):
        """獲取氣溫統計摘要"""
        if not stations_data:
            return None
        
        temperatures = [s['temperature'] for s in stations_data if s['temperature'] is not None]
        
        if not temperatures:
            return None
        
        summary = {
            'total_stations': len(stations_data),
            'valid_temperature_readings': len(temperatures),
            'max_temp': max(temperatures),
            'min_temp': min(temperatures),
            'avg_temp': sum(temperatures) / len(temperatures),
            'max_temp_station': next(s['station_name'] for s in stations_data if s['temperature'] == max(temperatures)),
            'min_temp_station': next(s['station_name'] for s in stations_data if s['temperature'] == min(temperatures))
        }
        
        return summary
    
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
    
    def calculate_station_distances(self, stations_data):
        """計算所有測站之間的距離"""
        if not stations_data:
            return None
        
        print("開始計算測站間距離...")
        distances = []
        
        for i in range(len(stations_data)):
            for j in range(i + 1, len(stations_data)):
                station1 = stations_data[i]
                station2 = stations_data[j]
                
                distance_m = self.calculate_distance(
                    station1['latitude'], station1['longitude'],
                    station2['latitude'], station2['longitude']
                )
                
                distances.append({
                    'station1_name': station1['station_name'],
                    'station1_location': station1['location'],
                    'station2_name': station2['station_name'],
                    'station2_location': station2['location'],
                    'distance_km': distance_m / 1000,
                    'distance_m': distance_m
                })
        
        # 按距離排序
        distances.sort(key=lambda x: x['distance_km'])
        
        print(f"完成計算，共 {len(distances)} 個測站對")
        return distances
    
    def analyze_station_distances(self, distances):
        """分析測站距離統計"""
        if not distances:
            return None
        
        all_distances = [d['distance_km'] for d in distances]
        
        analysis = {
            'total_pairs': len(distances),
            'min_distance_km': min(all_distances),
            'max_distance_km': max(all_distances),
            'avg_distance_km': sum(all_distances) / len(all_distances),
            'median_distance_km': sorted(all_distances)[len(all_distances) // 2],
            'nearest_pairs': distances[:10],
            'farthest_pairs': distances[-10:]
        }
        
        return analysis

def main():
    """主程式"""
    print("開始獲取中央氣象署自動氣象站資料...")
    
    try:
        # 初始化 API 客戶端
        cwa_api = CWAWeatherAPI()
        
        # 獲取資料
        print("正在從 CWA API 獲取資料...")
        raw_data = cwa_api.fetch_weather_data()
        
        if raw_data:
            print("成功獲取資料，正在解析...")
            
            # 解析氣溫資料
            stations_data = cwa_api.parse_temperature_data(raw_data)
            
            if stations_data:
                print(f"成功解析 {len(stations_data)} 個測站資料")
                
                # 顯示統計摘要
                summary = cwa_api.get_temperature_summary(stations_data)
                if summary:
                    print("\n=== 氣溫統計摘要 ===")
                    print(f"總測站數: {summary['total_stations']}")
                    print(f"有效氣溫讀數: {summary['valid_temperature_readings']}")
                    print(f"最高溫: {summary['max_temp']:.1f}°C ({summary['max_temp_station']})")
                    print(f"最低溫: {summary['min_temp']:.1f}°C ({summary['min_temp_station']})")
                    print(f"平均溫度: {summary['avg_temp']:.1f}°C")
                
                # 儲存資料
                csv_file = cwa_api.save_to_csv(stations_data)
                
                # 顯示前5筆資料範例
                print("\n=== 前5筆測站資料 ===")
                for i, station in enumerate(stations_data[:5]):
                    print(f"{i+1}. {station['station_name']} ({station['location']})")
                    print(f"   溫度: {station['temperature']}°C, 濕度: {station['humidity']}%")
                    print(f"   天氣: {station['weather']}")
                    print(f"   風速: {station['wind_speed']} m/s, 風向: {station['wind_direction']}°")
                    print(f"   氣壓: {station['air_pressure']} hPa")
                    print(f"   座標: ({station['latitude']}, {station['longitude']})")
                    print(f"   觀測時間: {station['observation_time']}")
                    print()
                
                # 新增：測站距離分析
                print("\n=== 開始測站距離分析 ===")
                distances = cwa_api.calculate_station_distances(stations_data)
                
                if distances:
                    distance_analysis = cwa_api.analyze_station_distances(distances)
                    
                    if distance_analysis:
                        print(f"\n=== 測站距離統計摘要 ===")
                        print(f"總測站對數: {distance_analysis['total_pairs']:,}")
                        print(f"平均距離: {distance_analysis['avg_distance_km']:.2f} km")
                        print(f"最短距離: {distance_analysis['min_distance_km']:.3f} km")
                        print(f"最長距離: {distance_analysis['max_distance_km']:.2f} km")
                        print(f"中位數距離: {distance_analysis['median_distance_km']:.2f} km")
                        
                        print(f"\n=== 距離最近的10個測站對 ===")
                        for i, pair in enumerate(distance_analysis['nearest_pairs'], 1):
                            print(f"{i:2d}. {pair['station1_name']:8s} - {pair['station2_name']:8s}: {pair['distance_km']:.3f} km")
                        
                        print(f"\n=== 距離最遠的10個測站對 ===")
                        for i, pair in enumerate(distance_analysis['farthest_pairs'], 1):
                            print(f"{i:2d}. {pair['station1_name']:8s} - {pair['station2_name']:8s}: {pair['distance_km']:.2f} km")
                        
                        # 儲存距離分析結果
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        distance_df = pd.DataFrame(distances)
                        distance_file = f"outputs/station_distances_{timestamp}.csv"
                        distance_df.to_csv(distance_file, index=False, encoding='utf-8-sig')
                        print(f"\n測站距離資料已儲存至: {distance_file}")
                
            else:
                print("解析資料失敗")
        else:
            print("獲取資料失敗")
            
    except Exception as e:
        print(f"程式執行發生錯誤: {e}")

if __name__ == "__main__":
    main()
