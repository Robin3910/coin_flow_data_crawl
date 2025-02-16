from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import pandas as pd
from flask import Flask, render_template, request, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
import json
import os
import requests
import re


app = Flask(__name__)

# 配置文件路径
CONFIG_FILE = 'config.json'

# 默认配置
default_config = {
    'threshold': 1000.0,
    'unit': '万',
    'period': '5分钟',
    'wx_token': 'SCT264877TGGj20niEYBVMMFU1aN6NQF6g'
}

# 全局变量
period_list = ["5分钟", "15分钟", "30分钟", "1小时", "4小时", "12小时", "24小时", "1周", "15天", "1月"]
unit_list = ["万", "亿"]

def load_config():
    global default_config
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            default_config = json.load(f)
            return default_config
    return default_config

def save_config(config):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

# 获取下一个执行时间点
def get_next_run_time(period):
    now = datetime.now()
    if period in ["5分钟", "15分钟", "30分钟"]:
        minutes = now.minute
        if period == "5分钟":
            minutes = minutes // 5 * 5
            next_time = now.replace(minute=minutes, second=0, microsecond=0)
            if next_time <= now:
                next_time += timedelta(minutes=5)
        elif period == "15分钟":
            minutes = minutes // 15 * 15
            next_time = now.replace(minute=minutes, second=0, microsecond=0)
            if next_time <= now:
                next_time += timedelta(minutes=15)
        else:  # 30分钟
            minutes = minutes // 30 * 30
            next_time = now.replace(minute=minutes, second=0, microsecond=0)
            if next_time <= now:
                next_time += timedelta(minutes=30)
    if period == "1小时":
        hours = now.hour
        next_time = now.replace(minute=0, second=0, microsecond=0)
        if next_time <= now:
            next_time += timedelta(hours=1)
    elif period == "4小时":
        hours = now.hour // 4 * 4
        next_time = now.replace(hour=hours, minute=0, second=0, microsecond=0)
        if next_time <= now:
            next_time += timedelta(hours=4)
    elif period == "12小时":
        hours = now.hour // 12 * 12
        next_time = now.replace(hour=hours, minute=0, second=0, microsecond=0)
        if next_time <= now:
            next_time += timedelta(hours=12)
    elif period == "24小时" or period == "1天":
        next_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if next_time <= now:
            next_time += timedelta(days=1)
    elif period == "1周":
        next_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
        days_ahead = 7 - now.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        next_time += timedelta(days=days_ahead)
    elif period == "15天":
        next_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
        days_ahead = 15 - now.day
        if days_ahead <= 0:
            days_ahead += 15
        next_time += timedelta(days=days_ahead)
    elif period == "30天":
        next_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
        days_ahead = 30 - now.day
        if days_ahead <= 0:
            days_ahead += 30
        next_time += timedelta(days=days_ahead)

    return next_time

# 定时任务
def scheduled_task():
    # config = load_config()
    result = get_btc_flow_data()
    if result:
        # 处理结果，后续添加告警逻辑
        print(f"执行定时任务，获取到数据：{result}")

# 初始化调度器
scheduler = BackgroundScheduler()
scheduler.start()

@app.route('/')
def index():
    config = load_config()
    return render_template('index.html', 
                         config=config,
                         period_list=period_list,
                         unit_list=unit_list)

@app.route('/api/config', methods=['POST'])
def update_config():
    try:
        new_config = request.json
        global default_config
        default_config = new_config
        save_config(new_config)
        
        # 更新定时任务
        scheduler.remove_all_jobs()
        next_run_time = get_next_run_time(new_config['period'])
        # 根据周期设置interval参数
        interval_params = {}
        if new_config['period'] == "5分钟":
            interval_params['minutes'] = 5
        elif new_config['period'] == "15分钟":
            interval_params['minutes'] = 15
        elif new_config['period'] == "30分钟":
            interval_params['minutes'] = 30
        elif new_config['period'] == "1小时":
            interval_params['hours'] = 1
        elif new_config['period'] == "4小时":
            interval_params['hours'] = 4
        elif new_config['period'] == "12小时":
            interval_params['hours'] = 12
        elif new_config['period'] == "24小时":
            interval_params['days'] = 1
        elif new_config['period'] == "1周":
            interval_params['weeks'] = 1
        elif new_config['period'] == "15天":
            interval_params['days'] = 15
        elif new_config['period'] == "1月":
            interval_params['days'] = 30

        # 添加定时任务
        scheduler.add_job(
            scheduled_task,
            'interval',
            next_run_time=next_run_time,
            **interval_params,
            id='btc_flow_monitor'
        )
        
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

def get_btc_flow_data():
    # 设置Chrome选项
    options = webdriver.ChromeOptions()
    # 添加无头模式（可选）
    # options.add_argument('--headless')
    
    # 初始化浏览器
    driver = webdriver.Chrome(options=options)
    
    try:
        # 访问网页
        url = "https://www.coinglass.com/zh/spot-inflow-outflow"
        driver.get(url)
        
        # 等待页面加载（等待表格出现）
        wait = WebDriverWait(driver, 20)

        time.sleep(5)

        # 获取BTC行数据
        btc_row_xpath = "//tr[@data-row-key='BTC']"
        btc_row = wait.until(EC.presence_of_element_located((By.XPATH, btc_row_xpath)))
        time.sleep(1)
        
        # 获取所有td元素
        td_elements = btc_row.find_elements(By.TAG_NAME, "td")
        
        # 找到目标周期在period_list中的索引
        try:
            period_index = period_list.index(default_config['period'])
            
            target_td = None
            count = 0
            for td in td_elements:
                if td.text == "":
                    continue
                text = td.text.strip()
                if '$' in text:
                    count += 1
                if count - 1 == period_index:
                    target_td = td
                    break

            value = target_td.text.strip()
            # 提取数值并统一转换为万单位
            # 提取数值和单位
            match = re.match(r'^(-?\$[\d,.]+)(万|亿)$', value)
            if not match:
                raise ValueError(f"无法解析数值: {value}")
            value = match.group(1)  # 保留正负号和数值部分
            unit = match.group(2)  # 提取单位
            value_num = float(value.replace('$', ''))
            # unit = default_config['unit']
            
            # 转换为万单位
            if unit == '亿':
                value_num = value_num * 10000  # 亿转万
            
            # 获取阈值并转换为万单位
            threshold = float(default_config['threshold'])
            if default_config['unit'] == '亿':
                threshold = threshold * 10000
                
            # 根据阈值正负判断是否需要告警
            should_alert = False
            if threshold > 0 and value_num > threshold:
                should_alert = True
            elif threshold < 0 and value_num < threshold:
                should_alert = True
                
            if should_alert:
                alert_msg = f"BTC{default_config['period']}的净流入值{target_td.text.strip()},超过阈值{default_config['threshold']}{default_config['unit']}"
                send_wx_notification(alert_msg, alert_msg)
            print(f"{default_config['period']}的值为: {target_td.text.strip()}")
            # send_wx_notification(f"BTC{default_config['period']}的净流入值为: {value}", f"BTC{default_config['period']}的净流入值为: {value}")
            return value
        except ValueError:
            print(f"未找到目标周期 {default_config['period']}")
            return None
        except IndexError:
            print("获取数据失败，td元素数量不足")
            return None
        
    except Exception as e:
        print(f"发生错误: {str(e)}")
        return None
        
    finally:
        driver.quit()


def send_wx_notification(title, message):
    """
    发送微信通知
    
    Args:
        title: 通知标题
        message: 通知内容
    """
    try:
        mydata = {
            'title': title,
            'desp': message
        }
        # https://sctapi.ftqq.com/SCT264877TGGj20niEYBVMMFU1aN6NQF6g.send?title=五粮液
        requests.post(f"https://sctapi.ftqq.com/{default_config['wx_token']}.send", data=mydata)
        # logger.info('发送微信消息成功')
    except Exception as e:
        # logger.error(f'发送微信消息失败: {str(e)}')
        print(f'发送微信消息失败: {str(e)}')

def init_scheduler():
       
    # 更新定时任务
    scheduler.remove_all_jobs()
    next_run_time = get_next_run_time(default_config['period'])
    # 根据周期设置interval参数
    interval_params = {}
    if default_config['period'] == "5分钟":
        interval_params['minutes'] = 5
    elif default_config['period'] == "15分钟":
        interval_params['minutes'] = 15
    elif default_config['period'] == "30分钟":
        interval_params['minutes'] = 30
    elif default_config['period'] == "1小时":
        interval_params['hours'] = 1
    elif default_config['period'] == "4小时":
        interval_params['hours'] = 4
    elif default_config['period'] == "12小时":
        interval_params['hours'] = 12
    elif default_config['period'] == "24小时":
        interval_params['days'] = 1
    elif default_config['period'] == "1周":
        interval_params['weeks'] = 1
    elif default_config['period'] == "15天":
        interval_params['days'] = 15
    elif default_config['period'] == "1月":
        interval_params['days'] = 30

    # 添加定时任务
    scheduler.add_job(
        scheduled_task,
        'interval',
        next_run_time=next_run_time,
        **interval_params,
        id='btc_flow_monitor'
    )

if __name__ == '__main__':
    default_config = load_config()
    init_scheduler()
    
    app.run(debug=False, host='0.0.0.0', port=80)


    # test
    # while True:
    #     get_btc_flow_data()
    #     time.sleep(60)