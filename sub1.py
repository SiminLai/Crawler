import requests
import os
from bs4 import BeautifulSoup
import pandas as pd
import json
from datetime import datetime, timedelta
import re
import time
import random
import logging

from cookies_manager import cookies_pool

# 配置日志
now = datetime.now()
formatted_time = now.strftime("%Y-%m-%d-%H-%M-%S")
log_filename = f"error_{formatted_time}.log"
logging.basicConfig(filename=log_filename, level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

# 提取cookies
def extract_cookies(raw_cookie):
    cookies = re.split(r';\s*', raw_cookie)
    fields = ['SINAGLOBAL', 'SUB', 'SUBP', 'ALF', '_s_tentry', 'Apache', 'ULV']
    cookie_dict = {}
    for cookie in cookies:
        if '=' in cookie:
            key, value = cookie.split('=', 1)
            cookie_dict[key] = value
    extracted_cookies = {field: cookie_dict[field] for field in fields if field in cookie_dict}
    extracted_cookies['_s_tentry'] = 'passport.weibo.com'
    extracted_cookies['Apache'] = cookie_dict.get('SINAGLOBAL', '')
    return extracted_cookies

# 获取页面响应
def get_the_list_response(q, p, cookies):
    # 如果cookies是字符串，解析为字典
    if isinstance(cookies, str):
        cookies = extract_cookies(cookies)

    headers = {
        'authority': 'rm.api.weibo.com',
        'accept': '*/*',
        'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
        'Referer': 'https://weibo.com/',
        'sec-fetch-dest': 'script',
        'sec-fetch-mode': 'no-cors',
        'sec-fetch-site': 'same-site',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
    }
    refer = f'https://s.weibo.com/weibo?q=%23{q}%23&page={p}'
    r = requests.get(refer, cookies=cookies, timeout=10)
    return r


# 格式化时间
def format_time(time_str):
    now = datetime.now()
    if '秒前' in time_str:
        seconds = int(re.search(r'(\d+)', time_str).group(1))
        time = now - timedelta(seconds=seconds)
    elif '分钟前' in time_str:
        minutes = int(re.search(r'(\d+)', time_str).group(1))
        time = now - timedelta(minutes=minutes)
    elif '今天' in time_str:
        time = now.strftime('%Y-%m-%d') + ' ' + time_str.split('今天')[1] + ':00'
        time = datetime.strptime(time, '%Y-%m-%d %H:%M:%S')
    elif '月' in time_str and '日' in time_str:
        time = str(now.year) + ' ' + time_str.replace('月', '-').replace('日', '') + ':00'
        time = datetime.strptime(time, '%Y %m-%d %H:%M:%S')
    elif '昨天' in time_str:
        yesterday = now - timedelta(days=1)
        time = yesterday.strftime('%Y-%m-%d') + ' ' + time_str.split('昨天')[1] + ':00'
        time = datetime.strptime(time, '%Y-%m-%d %H:%M:%S')
    elif '前天' in time_str:
        day_before_yesterday = now - timedelta(days=2)
        time = day_before_yesterday.strftime('%Y-%m-%d') + ' ' + time_str.split('前天')[1] + ':00'
        time = datetime.strptime(time, '%Y-%m-%d %H:%M:%S')
    else:
        return time_str, None
    return time.strftime('%Y-%m-%d %H:%M:%S'), None

# 解析列表
def parse_the_list(text):
    soup = BeautifulSoup(text, "html.parser")
    divs = soup.select('div[action-type="feed_list_item"]')
    lst = []
    for div in divs:
        mid = div.get('mid')
        uid = div.select('div.card-feed > div.avator > a')
        uid = uid[0].get('href').replace('.com/', '?').split('?')[1] if uid else None
        p_last = div.select('div.card-feed > div.content > p:last-of-type')[-1]
        nick_name = p_last['nick-name'] if 'nick-name' in p_last.attrs else None
        time = div.select('div.card-feed > div.content > div.from > a:first-of-type')
        time = time[0].string.strip() if time else None
        time, extra_info = format_time(time) if time else (None, None)
        p = div.select('div.card-feed > div.content > p:last-of-type')
        content = '\n'.join([para.replace('\u200b', '').strip() for para in list(p[0].strings)]) if p else None
        comment = div.select('div.card > div.card-act > ul > li')[-2].text.strip() if div.select('div.card > div.card-act > ul > li') else '0'
        lst.append((uid, nick_name, int(mid), content, time, comment, extra_info))
    df = pd.DataFrame(lst, columns=['uid', 'nick_name', 'mid', 'content', 'time', 'comment', 'extra_info'])
    return df

# 获取列表
def get_the_list(q, p, cookies_pool, retries=3):
    df_list = []
    cookies = random.choice(cookies_pool)  # 初始随机选择一个cookies
    cookies = extract_cookies(cookies)  # 将字符串解析为字典

    for i in range(1, p + 1):
        for attempt in range(retries):
            try:
                response = get_the_list_response(q=q, p=i, cookies=cookies)

                if response.status_code == 200:
                    df = parse_the_list(response.text)
                    if df.empty:
                        logging.info(f'第{i}页解析完成，但没有内容。')
                    else:
                        df_list.append(df)
                        logging.info(f'第{i}页解析成功！')
                    break

                # elif response.status_code == 418:  # 遇到418状态码时切换cookies
                #     logging.warning(f'第{i}页请求失败 (状态码: 418)。更换cookies后重试...')
                #     cookies = random.choice(cookies_pool)
                #     cookies = extract_cookies(cookies)  # 切换新cookies并解析为字典
                #     time.sleep(random.uniform(3, 7))  # 等待后重试
                elif response.status_code == 418:  # 碰到418状态码切换 cookies
                    logging.warning(f'第{i}页请求失败 (状态码: 418)。更换 cookies 后重试...')
                    print(f'第{i}页请求失败 (状态码: 418)。更换 cookies 后重试...')
                    
                    # 切换 cookies
                    old_cookies = cookies
                    cookies = random.choice(cookies_pool)
                    print(f"更换 cookies: {old_cookies[:50]}... => {cookies[:50]}...")
                    cookies = extract_cookies(cookies)  # 解析新 cookies
                    
                    time.sleep(random.uniform(3, 7))  # 等待后重试
                else:
                    logging.warning(f'第{i}页请求失败，状态码：{response.status_code}')
                    time.sleep(random.uniform(1, 3))  # 常规延迟

            except Exception as e:
                logging.error(f'第{i}页解析失败，错误信息：{e}')
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)  # 指数退避
                else:
                    break
    return df_list


# 主处理函数
def get_sub1(raw_cookies, duplicated_name, sub1_foldername):
    cookies = extract_cookies(raw_cookies)
    if not os.path.exists(sub1_foldername):
        os.makedirs(sub1_foldername)
    df = pd.read_csv(duplicated_name)
    df_unique = df.drop_duplicates(subset=['word'])
    dir_list = [x[1:-5] for x in os.listdir(sub1_foldername)]
    for q in df_unique['word']:
        if q in dir_list:
            logging.info(f'{q}_已存在')
        else:
            try:
                df_list = get_the_list(q, 100, cookies_pool)
                if df_list:
                    pd.concat(df_list).to_csv(f'./{sub1_foldername}/#{q}#.csv', index=False, encoding='utf_8_sig')
            except Exception as e:
                logging.error(f'词条 "{q}" 处理失败，错误信息：{e}')
