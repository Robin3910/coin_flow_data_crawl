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
from selenium.webdriver.common.action_chains import ActionChains
import logging  # 添加导入


app = Flask(__name__)

# 配置日志记录
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[logging.FileHandler("coin_flow_monitor.log", encoding='utf-8'),  # 添加文件处理器
                              logging.StreamHandler()])  # 可选：同时输出到控制台
logger = logging.getLogger(__name__)  # 创建logger实例

# 配置文件路径
CONFIG_FILE = 'config.json'

# 默认配置
default_config = {
  "period_list": [
    {
      "threshold": 1000.0,
      "unit": "万",
      "period": "30分钟"
    },
    {
      "threshold": 1000.0,
      "unit": "万",
      "period": "1小时"
    },
    {
      "threshold": 1000.0,
      "unit": "万",
      "period": "4小时"
    },

  ],
  "wx_token": "SCT264877TGGj20niEYBVMMFU1aN6NQF6g"
}

# 全局变量
period_list = ["5分钟", "15分钟", "30分钟", "1小时", "4小时", "12小时", "1天", "1周"]
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
            if minutes == 0:
                minutes = 5
            next_time = now.replace(minute=minutes - 1, second=10, microsecond=0)
            if next_time <= now:
                next_time += timedelta(minutes=5)
        elif period == "15分钟":
            minutes = minutes // 15 * 15
            if minutes == 0:
                minutes = 15
            next_time = now.replace(minute=minutes - 1, second=10, microsecond=0)
            if next_time <= now:
                next_time += timedelta(minutes=15)
        else:  # 30分钟
            minutes = minutes // 30 * 30
            if minutes == 0:
                minutes = 30
            next_time = now.replace(minute=minutes - 1, second=10, microsecond=0)
            if next_time <= now:
                next_time += timedelta(minutes=30)
    if period == "1小时":
        hours = now.hour
        next_time = now.replace(minute=59, second=59, microsecond=10)
        if next_time <= now:
            next_time += timedelta(hours=1)
    elif period == "4小时":
        hours = now.hour // 4 * 4
        if hours == 0:
            hours = 4
        next_time = now.replace(hour=hours - 1, minute=59, second=59, microsecond=10)
        if next_time <= now:
            next_time += timedelta(hours=4)
    elif period == "12小时":
        hours = now.hour // 12 * 12
        if hours == 0:
            hours = 12
        next_time = now.replace(hour=hours - 1, minute=59, second=59, microsecond=10)
        if next_time <= now:
            next_time += timedelta(hours=12)
    elif period == "24小时" or period == "1天":
        next_time = now.replace(hour=23, minute=59, second=59, microsecond=10)
        if next_time <= now:
            next_time += timedelta(days=1)
    elif period == "1周":
        next_time = now.replace(hour=23, minute=59, second=59, microsecond=10)
        days_ahead = 7 - now.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        next_time += timedelta(days=days_ahead - 1)
    elif period == "15天":
        next_time = now.replace(hour=23, minute=59, second=59, microsecond=10)
        days_ahead = 15 - now.day
        if days_ahead <= 0:
            days_ahead += 15
        next_time += timedelta(days=days_ahead - 1)
    elif period == "30天":
        next_time = now.replace(hour=23, minute=59, second=59, microsecond=10)
        days_ahead = 30 - now.day
        if days_ahead <= 0:
            days_ahead += 30
        next_time += timedelta(days=days_ahead - 1)

    return next_time

# 定时任务
def scheduled_task(period_obj):
    # config = load_config()
    result = get_btc_flow_data(period_obj)
    if result:
        # 处理结果，后续添加告警逻辑
        logger.info(f"执行定时任务，获取到数据：{result}")

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
        for period in new_config['period_list']:

            next_run_time = get_next_run_time(period['period'])
            # 根据周期设置interval参数
            interval_params = {}
            if period['period'] == "5分钟":
                interval_params['minutes'] = 5
            elif period['period'] == "15分钟":
                interval_params['minutes'] = 15
            elif period['period'] == "30分钟":
                interval_params['minutes'] = 30
            elif period['period'] == "1小时":
                interval_params['hours'] = 1
            elif period['period'] == "4小时":
                interval_params['hours'] = 4
            elif period['period'] == "12小时":
                interval_params['hours'] = 12
            elif period['period'] == "24小时":
                interval_params['days'] = 1
            elif period['period'] == "1周":
                interval_params['weeks'] = 1
            elif period['period'] == "15天":
                interval_params['days'] = 15
            elif period['period'] == "1月":
                interval_params['days'] = 30

            # 添加定时任务
            scheduler.add_job(
                lambda: scheduled_task(period_obj=period),  # 使用 lambda 函数
                'interval',
                next_run_time=next_run_time,
                **interval_params,
                id=f'btc_flow_monitor_{period["period"]}_{period["threshold"]}_{period["unit"]}'
            )
        
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

def get_btc_flow_data(period_obj):
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

        time.sleep(2)

        # 修改鼠标移动逻辑
        chart_element = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "echarts-for-react")))
        
        time.sleep(2)

        # 根据当前配置的时间周期，点击对应的按钮
        period_list_btn = wait.until(EC.presence_of_element_located((By.XPATH, '//*[@aria-controls=":R7acdaeqm:"]')))
        period_list_btn.click()

        # 根据default_config['period']，点击对应的按钮
        # 等待并点击对应时间周期的选项
        period_options = wait.until(EC.presence_of_element_located((By.XPATH, f"//ul[@id=':R7acdaeqm:']")))
        period_option = period_options.find_element(By.XPATH, f"//li[text()='{period_obj['period']}']")
        period_option.click()

        time.sleep(2)

        # 获取图表的位置和大小
        size = chart_element.size
        
        # 使用相对元素的移动方式
        actions = ActionChains(driver)
        actions.move_to_element(chart_element).perform()  # 移动到图表中心
        time.sleep(0.5)

        # 平滑移动到最右边的数据
        half_offset = size['width'] // 4

        actions.move_by_offset(half_offset, 0).perform()

        right_offset = size['width'] // 4 - 30
        
        steps = 80
        
        for i in range(steps):
            # 前半段步子大，后半段步子小
            if i < steps / 2:
                progress = i / (steps / 2)  # 0到1的进度
                x_step = (right_offset / steps) * (2 - progress)  # 从2倍逐渐减小到1倍
            else:
                progress = (i - steps/2) / (steps/2)  # 0到1的进度
                x_step = (right_offset / steps) * (1 - progress * 0.5)  # 从1倍逐渐减小到0.5倍
            
            actions.move_by_offset(x_step, 0).perform()
            # time.sleep(0.02)  # 每步暂停一小段时间，使移动更平滑
        time.sleep(0.5)

        # 获取到整个页面的HTML内容
        html = driver.page_source
        # 从html里面匹配出pl20的文本。BTC净流入是class为pl20的div
        pl20_text = re.findall(r'<div class="pl20">(.*?)</div>', html)
        if len(pl20_text) > 0:
            logger.info(f"获取到的pl20文本: {pl20_text[0]}")
            value = pl20_text[0]
            match = re.match(r'^(-?\$[\d,.]+)(万|亿)$', value)
            if not match:
                raise ValueError(f"无法解析数值: {value}")
            value = match.group(1)  # 保留正负号和数值部分
            unit = match.group(2)  # 提取单位
            value_num = float(value.replace('$', ''))
            
            # 转换为万单位
            if unit == '亿':
                value_num = value_num * 10000  # 亿转万
            
            # 获取阈值并转换为万单位
            threshold = float(period_obj['threshold'])
            if period_obj['unit'] == '亿':
                threshold = threshold * 10000
                
            # 根据阈值正负判断是否需要告警
            should_alert = False
            if abs(value_num) > abs(threshold):
                should_alert = True
            # if threshold > 0 and value_num > threshold:
            #     should_alert = True
            # elif threshold < 0 and value_num < threshold:
            #     should_alert = True
                
            if should_alert:
                alert_msg = f"BTC{period_obj['period']}的净流入值{pl20_text[0]},超过阈值{period_obj['threshold']}{period_obj['unit']}"
                send_wx_notification(alert_msg, alert_msg)
            logger.info(f"{period_obj['period']}的值为: {pl20_text[0]}")
            return value
    except ValueError:
        logger.error(f"未找到目标周期 {period_obj['period']}")
        return None

        
    except Exception as e:
        logger.error(f"发生错误: {str(e)}")
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
        logger.error(f'发送微信消息失败: {str(e)}')

def init_scheduler():
       
    # 更新定时任务
    scheduler.remove_all_jobs()
    for period in default_config['period_list']:
        next_run_time = get_next_run_time(period['period'])
        # 根据周期设置interval参数
        interval_params = {}
        if period['period'] == "5分钟":
            interval_params['minutes'] = 5
        elif period['period'] == "15分钟":
            interval_params['minutes'] = 15
        elif period['period'] == "30分钟":
            interval_params['minutes'] = 30
        elif period['period'] == "1小时":
            interval_params['hours'] = 1
        elif period['period'] == "4小时":
            interval_params['hours'] = 4
        elif period['period'] == "12小时":
            interval_params['hours'] = 12
        elif period['period'] == "24小时":
            interval_params['days'] = 1
        elif period['period'] == "1周":
            interval_params['weeks'] = 1
        elif period['period'] == "15天":
            interval_params['days'] = 15
        elif period['period'] == "1月":
            interval_params['days'] = 30

        # 添加定时任务
        scheduler.add_job(
            lambda: scheduled_task(period_obj=period),  # 使用 lambda 函数
            'interval',
            next_run_time=next_run_time,
            **interval_params,
            id=f'btc_flow_monitor_{period["period"]}_{period["threshold"]}_{period["unit"]}'
        )
        logger.info(f"添加定时任务: {period['period']}")

if __name__ == '__main__':
    default_config = load_config()
    init_scheduler()
    
    app.run(debug=False, host='0.0.0.0', port=80)


    # test
    # while True:
    #     get_btc_flow_data()
    #     time.sleep(60)