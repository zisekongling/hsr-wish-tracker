# starrial.py
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta
from flask import Flask, jsonify
import json
import os
import subprocess

app = Flask(__name__)

# 设置数据保存路径
DATA_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data.json')

def adjust_to_target_weekday(date, target_weekday):
    """
    将日期调整到最近的指定星期（0=周一, 6=周日）
    返回调整后的日期
    """
    current_weekday = date.weekday()
    # 计算最近的两个候选日期（上一个和下一个目标星期）
    prev_candidate = date - timedelta(days=(current_weekday - target_weekday) % 7)
    next_candidate = date + timedelta(days=(target_weekday - current_weekday) % 7)
    
    # 选择距离原日期更近的那个
    if abs((date - prev_candidate).days) <= abs((next_candidate - date).days):
        return prev_candidate
    return next_candidate

def scrape_hsr_wish_data():
    """
    从biligame维基爬取崩坏：星穹铁道卡池信息
    """
    url = "https://wiki.biligame.com/sr/%E8%B7%83%E8%BF%81"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 定位包含卡池信息的容器
        wish_container = soup.find('div', class_='row', style='margin:0 -5px;')
        
        if not wish_container:
            print("未找到卡池信息容器")
            return []
            
        # 找到所有卡池表格
        wish_tables = wish_container.find_all('table', class_='wikitable')
        
        wish_data = []
        
        for table in wish_tables:
            wish_info = {}
            
            # 提取时间
            time_th = table.find('th', string='时间')
            if not time_th:
                time_th = table.find('th', string=re.compile(r'时间'))
            if time_th:
                time_td = time_th.find_next('td')
                if time_td:
                    # 直接获取文本内容，保留原始格式
                    wish_info['时间'] = time_td.get_text(strip=False).replace('\t', '')
            
            # 提取版本
            version_th = table.find('th', string='版本')
            if not version_th:
                version_th = table.find('th', string=re.compile(r'版本'))
            if version_th:
                version_td = version_th.find_next('td')
                if version_td:
                    version_text = version_td.get_text(strip=True)
                    # 提取主版本号 (如 "1.0")
                    version_match = re.search(r'(\d+\.\d+)', version_text)
                    if version_match:
                        wish_info['版本'] = version_match.group(1)
                    else:
                        wish_info['版本'] = version_text
            
            # 提取5星角色/光锥 - 保留完整文本
            star5_row = table.find('th', string=re.compile(r'5星(角色|光锥)'))
            if star5_row:
                star5_type = "角色" if "角色" in star5_row.get_text() else "光锥"
                star5_td = star5_row.find_next('td')
                if star5_td:
                    # 获取完整的文本内容，包括括号内的属性信息
                    star5_text = star5_td.get_text(strip=True)
                    # 只去除多余空格，保留所有内容
                    star5_text = re.sub(r'\s+', ' ', star5_text)
                    wish_info['5星类型'] = star5_type
                    wish_info['5星内容'] = star5_text
            
            # 提取4星角色/光锥
            star4_row = table.find('th', string=re.compile(r'4星(角色|光锥)'))
            if star4_row:
                star4_type = "角色" if "角色" in star4_row.get_text() else "光锥"
                star4_td = star4_row.find_next('td')
                if star4_td:
                    star4_items = []
                    for item in star4_td.children:
                        if item.name == 'br':
                            continue
                        if item.name == 'a':
                            item_text = item.get_text(strip=True)
                            if item_text:
                                star4_items.append(item_text)
                        elif isinstance(item, str) and item.strip():
                            star4_items.append(item.strip())
                    
                    if not star4_items:
                        star4_text = star4_td.get_text(strip=True)
                        star4_items = [s.strip() for s in star4_text.split('\n') if s.strip()]
                    
                    wish_info['4星类型'] = star4_type
                    wish_info['4星内容'] = ", ".join(star4_items)
            
            # 确定卡池类型
            if '5星类型' in wish_info:
                wish_info['卡池类型'] = "角色池" if wish_info['5星类型'] == "角色" else "光锥池"
                wish_data.append(wish_info)
        
        return wish_data
    
    except Exception as e:
        print(f"爬取卡池数据时出错: {str(e)}")
        return []

def scrape_version_info():
    """
    从Fandom维基爬取崩坏：星穹铁道版本信息
    返回最新版本号、标题、更新时间，并计算下一个版本更新时间和前瞻时间
    """
    url = "https://honkai-star-rail.fandom.com/zh/wiki/%E7%89%88%E6%9C%AC"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 定位版本表格 - 根据提供的HTML片段
        version_table = soup.find('table', class_='article-table')
        if not version_table:
            version_table = soup.find('table', class_='wikitable')
            if not version_table:
                print("未找到版本信息表格")
                return None
        
        # 提取表头行
        header_row = version_table.find('thead').find('tr') if version_table.find('thead') else None
        if not header_row:
            # 如果没有thead，尝试直接找tr
            rows = version_table.find_all('tr')
            if len(rows) > 0:
                header_row = rows[0]
        
        if not header_row:
            print("未找到表头行")
            return None
        
        # 确定列索引
        headers = [th.get_text(strip=True) for th in header_row.find_all(['th', 'td'])]
        version_index = headers.index('版本') if '版本' in headers else 0
        title_index = headers.index('标题') if '标题' in headers else 1
        date_index = headers.index('发布日期') if '发布日期' in headers else 2
        
        # 提取数据行 - 跳过表头行
        rows = version_table.find_all('tr')[1:]  # 跳过表头行
        
        if not rows:
            print("未找到数据行")
            return None
        
        # 获取第一行数据（最新版本）
        latest_row = rows[0]
        columns = latest_row.find_all('td')
        
        if len(columns) < max(version_index, title_index, date_index) + 1:
            print("列数不足")
            return None
        
        # 提取版本号
        version_number = columns[version_index].get_text(strip=True)
        
        # 提取标题 - 检查是否有链接
        title_cell = columns[title_index]
        title_link = title_cell.find('a')
        version_title = title_link.get_text(strip=True) if title_link else title_cell.get_text(strip=True)
        
        # 提取发布日期
        update_date_str = columns[date_index].get_text(strip=True)
        
        # 解析发布日期（格式：YYYY-MM-DD）
        try:
            update_date = datetime.strptime(update_date_str, '%Y-%m-%d')
        except ValueError:
            print(f"无法解析发布日期: {update_date_str}")
            return None
        
        # 计算下一个版本更新时间（+42天）
        next_version_date = update_date + timedelta(days=42)
        
        # 计算下一个版本前瞻时间（更新前11天）
        livestream_date = next_version_date - timedelta(days=11)
        
        # 调整日期到正确的星期
        next_version_date_adjusted = adjust_to_target_weekday(next_version_date, 2)  # 2=周三
        livestream_date_adjusted = adjust_to_target_weekday(livestream_date, 4)      # 4=周五
        
        # 确保前瞻日期在更新日期之前
        if livestream_date_adjusted >= next_version_date_adjusted:
            livestream_date_adjusted -= timedelta(days=7)
            # 重新调整到星期五
            livestream_date_adjusted = adjust_to_target_weekday(livestream_date_adjusted, 4)
        
        # 确保调整后前瞻日期仍在更新日期之前
        if livestream_date_adjusted >= next_version_date_adjusted:
            livestream_date_adjusted = next_version_date_adjusted - timedelta(days=7)
            livestream_date_adjusted = adjust_to_target_weekday(livestream_date_adjusted, 4)
        
        return {
            "current_version": version_number,
            "current_version_title": version_title,
            "current_version_update_date": update_date.strftime("%Y-%m-%d"),
            "next_version_update_date": next_version_date_adjusted.strftime("%Y-%m-%d"),
            "next_version_livestream_date": livestream_date_adjusted.strftime("%Y-%m-%d")
        }
    
    except Exception as e:
        print(f"爬取版本信息时出错: {str(e)}")
        return None

def parse_time_range(time_str):
    """
    解析时间范围字符串，返回开始时间和结束时间
    支持多种格式：
    - "3.4版本更新后 ~ 2025/07/23 11:59"
    - "2025/04/23 11:59 ~ 2025/07/23 11:59"
    """
    # 清理字符串：去除多余空格和换行
    time_str = re.sub(r'\s+', ' ', time_str).strip()
    
    # 尝试匹配日期格式：YYYY/MM/DD HH:MM
    date_pattern = r'\d{4}/\d{1,2}/\d{1,2} \d{1,2}:\d{2}'
    
    # 查找所有匹配的日期
    dates = re.findall(date_pattern, time_str)
    
    # 如果有两个日期，则第一个是开始时间，第二个是结束时间
    if len(dates) == 2:
        return dates[0], dates[1]
    
    # 如果只有一个日期，则作为结束时间
    elif len(dates) == 1:
        # 检查是否有版本更新后的描述
        if '版本更新后' in time_str:
            version_match = re.search(r'(\d+\.\d+)', time_str)
            version = version_match.group(1) if version_match else "未知版本"
            return f"{version}版本更新后", dates[0]
        else:
            return "", dates[0]
    
    # 如果没有日期，尝试其他格式
    else:
        # 尝试按分隔符分割
        separators = ['~', '-', '至']
        for sep in separators:
            if sep in time_str:
                parts = time_str.split(sep, 1)
                if len(parts) == 2:
                    return parts[0].strip(), parts[1].strip()
        
        # 如果都没有匹配，返回原始字符串
        return time_str, ""

def format_wish_data(wish_data):
    """
    格式化卡池数据用于API输出
    """
    formatted_data = []
    
    for wish in wish_data:
        # 提取卡池版本
        version = wish.get('版本', '未知版本')
        
        # 解析时间范围
        time_str = wish.get('时间', '时间未知')
        start_time, end_time = parse_time_range(time_str)
        
        # 保留完整的5星内容（包括属性信息）
        star5_content = wish.get('5星内容', '未知')
        
        formatted_data.append({
            "version": version,
            "pool_type": wish.get('卡池类型', '未知'),
            "start_time": start_time,
            "end_time": end_time,
            "five_star": star5_content,
            "four_star": wish.get('4星内容', '')
        })
    
    return formatted_data

def fetch_and_save_data():
    """
    获取数据并保存到文件
    """
    # 爬取卡池数据
    raw_data = scrape_hsr_wish_data()
    if not raw_data:
        print("未获取到卡池数据")
        return False
        
    formatted_data = format_wish_data(raw_data)
    
    if not formatted_data:
        print("格式化卡池数据失败")
        return False
        
    # 爬取版本信息
    version_info = scrape_version_info()
    
    # 添加更新时间戳
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data = {
        "last_updated": current_time,
        "wish_data": formatted_data
    }
    
    # 如果成功获取版本信息，添加到响应中
    if version_info:
        data["version_info"] = version_info
    
    # 保存到文件
    try:
        with open(DATA_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"数据已保存到 {DATA_FILE_PATH}")
        return True
    except Exception as e:
        print(f"保存数据失败: {str(e)}")
        return False

@app.route('/api/hsr_wish', methods=['GET'])
def get_wish_data():
    """
    API端点：返回卡池数据和版本信息的JSON格式
    """
    # 尝试从文件加载数据
    if os.path.exists(DATA_FILE_PATH):
        try:
            with open(DATA_FILE_PATH, 'r', encoding='utf-8') as f:
                return jsonify(json.load(f))
        except:
            pass
    
    # 如果文件不存在或加载失败，则实时爬取
    return jsonify(fetch_wish_data())

def fetch_wish_data():
    raw_data = scrape_hsr_wish_data()
    if not raw_data:
        return {"error": "Failed to fetch wish data"}
        
    formatted_data = format_wish_data(raw_data)
    
    if not formatted_data:
        return {"error": "No valid wish data found"}
        
    version_info = scrape_version_info()
    
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    response = {
        "last_updated": current_time,
        "wish_data": formatted_data
    }
    
    if version_info:
        response["version_info"] = version_info
    
    return response

if __name__ == '__main__':
    # 支持命令行参数
    import argparse
    parser = argparse.ArgumentParser(description='崩坏：星穹铁道卡池追踪服务')
    parser.add_argument('--save', action='store_true', help='仅获取数据并保存到文件，不启动服务器')
    args = parser.parse_args()
    
    if args.save:
        print("正在获取数据并保存...")
        fetch_and_save_data()
    else:
        app.run(host='0.0.0.0', port=5000)
