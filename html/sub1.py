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


def format_time(time_str):
    """
    根据微博常见的时间描述，转成标准 %Y-%m-%d %H:%M:%S。
    如果字符串中本身带了xxxx年，就用它的年份；
    否则，如果只有月日，则使用当前系统年份。
    如果出现非标准字符，就尝试用正则提取日期时间。
    """
    now = datetime.now()

    # 1) 若包含 '秒前'
    if '秒前' in time_str:
        seconds = int(re.search(r'(\d+)', time_str).group(1))
        time_obj = now - timedelta(seconds=seconds)
        return time_obj.strftime('%Y-%m-%d %H:%M:%S'), None

    # 2) 若包含 '分钟前'
    elif '分钟前' in time_str:
        minutes = int(re.search(r'(\d+)', time_str).group(1))
        time_obj = now - timedelta(minutes=minutes)
        return time_obj.strftime('%Y-%m-%d %H:%M:%S'), None

    # 3) 若包含 '今天'
    elif '今天' in time_str:
        # 形如: 今天 20:09
        time_part = time_str.split('今天')[1].strip()
        time_str_parsed = f"{now.strftime('%Y-%m-%d')} {time_part}:00"
        try:
            time_obj = datetime.strptime(time_str_parsed, '%Y-%m-%d %H:%M:%S')
            return time_obj.strftime('%Y-%m-%d %H:%M:%S'), None
        except ValueError as e:
            # 解析失败就直接返回
            return time_str, e

    # 4) 若包含 '昨天'
    elif '昨天' in time_str:
        yesterday = now - timedelta(days=1)
        time_part = time_str.split('昨天')[1].strip()
        time_str_parsed = f"{yesterday.strftime('%Y-%m-%d')} {time_part}:00"
        try:
            time_obj = datetime.strptime(time_str_parsed, '%Y-%m-%d %H:%M:%S')
            return time_obj.strftime('%Y-%m-%d %H:%M:%S'), None
        except ValueError as e:
            return time_str, e

    # 5) 若包含 '前天'
    elif '前天' in time_str:
        day_before_yesterday = now - timedelta(days=2)
        time_part = time_str.split('前天')[1].strip()
        time_str_parsed = f"{day_before_yesterday.strftime('%Y-%m-%d')} {time_part}:00"
        try:
            time_obj = datetime.strptime(time_str_parsed, '%Y-%m-%d %H:%M:%S')
            return time_obj.strftime('%Y-%m-%d %H:%M:%S'), None
        except ValueError as e:
            return time_str, e

    # 6) 若字符串里有 "xxxx年xx月xx日 xx:xx(:xx)?"
    match_full = re.match(
        r'^(\d{4})年(\d{1,2})月(\d{1,2})日\s*(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?$',
        time_str
    )
    if match_full:
        year, month, day, hour, minute, second = match_full.groups()
        if not second:
            second = '00'
        try:
            time_obj = datetime(int(year), int(month), int(day), int(hour), int(minute), int(second))
            return time_obj.strftime('%Y-%m-%d %H:%M:%S'), None
        except ValueError as e:
            return time_str, e

    # 7) 若只有 "xx月xx日 xx:xx(:xx)?"
    if '月' in time_str and '日' in time_str:
        md_match = re.match(r'(\d{1,2})月(\d{1,2})日\s*(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?', time_str)
        if md_match:
            month, day, hour, minute, second = md_match.groups()
            if not second:
                second = '00'
            time_str_parsed = f"{now.year}-{month}-{day} {hour}:{minute}:{second}"
            try:
                time_obj = datetime.strptime(time_str_parsed, '%Y-%m-%d %H:%M:%S')
                return time_obj.strftime('%Y-%m-%d %H:%M:%S'), None
            except ValueError as e:
                return time_str, e

    # 8) 兜底：尝试用正则单独提取 “2025-01-01 04:17:00” 这类标准格式
    #    这是为了解决比如：'2025-01-01 04:17 转赞人数超过20:00'
    #    我们找子串 [xxxx-xx-xx xx:xx(:xx)?]
    potential_times = re.findall(r'\d{4}-\d{1,2}-\d{1,2}\s+\d{1,2}:\d{1,2}(:\d{1,2})?', time_str)
    # re.findall 返回的是列表，里头每个元素可能只有最后一组。我们可以改用 finditer 或再加工。
    # 这里改一下写法，用 finditer 捕获完整子串:
    match_iter = list(re.finditer(r'(\d{4}-\d{1,2}-\d{1,2}\s+\d{1,2}:\d{1,2}(:\d{1,2})?)', time_str))
    if match_iter:
        # 取第一个就好
        sub_str = match_iter[0].group(1)
        # 分别尝试两种解析：带秒 和 不带秒
        for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M']:
            try:
                time_obj = datetime.strptime(sub_str, fmt)
                return time_obj.strftime('%Y-%m-%d %H:%M:%S'), None
            except ValueError:
                continue
        # 都不行再返回原文本
        return time_str, None

    # 都不匹配时返回原始字符串
    return time_str, None


# 解析列表
def parse_the_list(text):
    soup = BeautifulSoup(text, "html.parser")
    divs = soup.select('div[action-type="feed_list_item"]')
    lst = []
    for div in divs:
        mid = div.get('mid')
        # uid
        uid_ele = div.select('div.card-feed > div.avator > a')
        uid = uid_ele[0].get('href').replace('.com/', '?').split('?')[1] if uid_ele else None
        
        # 昵称
        p_last = div.select('div.card-feed > div.content > p:last-of-type')[-1]
        nick_name = p_last.get('nick-name') if p_last else None
        
        # 时间
        time_ele = div.select('div.card-feed > div.content > div.from > a:first-of-type')
        raw_time_str = time_ele[0].string.strip() if time_ele else None
        if raw_time_str:
            parsed_time, extra_info = format_time(raw_time_str)
        else:
            parsed_time, extra_info = None, None
        
        # 内容
        p_content = div.select('div.card-feed > div.content > p:last-of-type')
        if p_content:
            content = '\n'.join([para.replace('\u200b', '').strip() for para in list(p_content[0].strings)])
        else:
            content = None
        
        # 评论数 (一般在倒数第2个 li)
        li_acts = div.select('div.card > div.card-act > ul > li')
        if li_acts:
            comment_text = li_acts[-2].text.strip()
        else:
            comment_text = '0'
        
        lst.append((
            uid, 
            nick_name, 
            int(mid) if mid else None, 
            content, 
            parsed_time, 
            comment_text, 
            extra_info
        ))
    
    df = pd.DataFrame(lst, columns=['uid', 'nick_name', 'mid', 'content', 'time', 'comment', 'extra_info'])
    return df


# 获取列表
def get_the_list(q, p, cookies_pool, retries=20):
    df_list = []
    # 初始随机选择一个cookies
    cookies = random.choice(cookies_pool)
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

                elif response.status_code == 418:  # 碰到418状态码切换 cookies
                    logging.warning(f'第{i}页请求失败 (状态码: 418)。更换 cookies 后重试...')
                    print(f'第{i}页请求失败 (状态码: 418)。更换 cookies 后重试...')
                    
                    # 切换 cookies
                    old_cookies = cookies
                    cookies = random.choice(cookies_pool)
                    print(f"更换 cookies: {str(old_cookies)[:50]}... => {str(cookies)[:50]}...")
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
    
    # 已经爬过的目录列表
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
