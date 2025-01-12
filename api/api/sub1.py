import os 
import requests
import pandas as pd
import json
from datetime import datetime
import re
import time
import logging
from bs4 import BeautifulSoup
from urllib.parse import quote
from cookies_manager import cookies_pool
import random

# 配置日志
now = datetime.now()
formatted_time = now.strftime("%Y-%m-%d-%H-%M-%S")
log_filename = f"error_{formatted_time}.log"
logging.basicConfig(
    filename=log_filename,
    level=logging.DEBUG,  # 设置更详细的日志级别
    format='%(asctime)s %(levelname)s %(message)s'
)

BASE_API_URL = 'https://m.weibo.cn/api/container/getIndex'
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36",
    "Referer": "https://weibo.com/",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "X-Requested-With": "XMLHttpRequest",
}

def extract_cookies(raw_cookie):
    """
    解析Cookies字符串为字典
    """
    cookies = re.split(r';\s*', raw_cookie)
    cookie_dict = {}
    for cookie in cookies:
        if '=' in cookie:
            key, value = cookie.split('=', 1)
            cookie_dict[key] = value
    return cookie_dict

def clean_weibo_text(raw_html):
    """
    清理微博 HTML 内容，提取纯文本
    """
    soup = BeautifulSoup(raw_html, 'html.parser')
    for a_tag in soup.find_all('a'):
        a_tag.decompose()
    for img_tag in soup.find_all('img'):
        if img_tag.has_attr('alt'):
            img_tag.replace_with(img_tag['alt'])
        else:
            img_tag.decompose()
    clean_text = soup.get_text(separator=' ', strip=True)
    return clean_text

def get_full_text(post_id, cookies):
    """
    获取长微博的完整内容
    """
    url = f"https://m.weibo.cn/statuses/extend?id={post_id}"
    try:
        response = requests.get(url, headers=HEADERS, cookies=cookies, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get('data', {}).get('longTextContent', '')
        else:
            logging.error(f"获取长微博失败，状态码：{response.status_code}")
    except Exception as e:
        logging.error(f"获取长微博失败，错误信息：{e}")
    return None

def handle_captcha():
    """
    处理验证码逻辑，暂停程序等待用户手动验证并输入更新后的 cookies
    """
    print("检测到验证码触发，请手动完成验证...")
    captcha_url = "https://m.weibo.cn/captcha"  # 假设验证码链接为此，需根据实际调整
    print(f"请在浏览器中访问以下链接完成验证：{captcha_url}")
    input("完成验证后按 Enter 键继续：")
    new_cookies = input("请输入更新后的 cookies：")
    logging.info("已更新 cookies，程序继续执行。")
    return extract_cookies(new_cookies)

def get_posts_by_keyword(keyword, cookies, page=1):
    """
    获取指定关键词的帖子，并清洗内容
    """
    posts = []
    params = {
        'containerid': f'100103type=61&q={quote(keyword)}',
        'page': page
    }

    retries = 500  # 最大重试次数
    for attempt in range(retries):
        try:
            response = requests.get(BASE_API_URL, headers=HEADERS, cookies=cookies, params=params, timeout=10)
            if response.status_code != 200:
                raise Exception(f"状态码异常: {response.status_code}")

            data = response.json()

            # 检测是否触发验证码
            if data.get("ok") == -100:
                logging.warning("触发验证码，暂停程序等待手动验证...")
                if attempt == retries - 1:
                    print("已达到最大重试次数。")
                    cookies = handle_captcha()
                else:
                    cookies = extract_cookies(random.choice(cookies_pool))
                    time.sleep(random.uniform(3, 7))
                continue

            # 解析正常返回的帖子数据
            cards = data.get('data', {}).get('cards', [])
            for card in cards:
                if card.get('card_type') == 9:
                    mblog = card.get('mblog', {})
                    post_id = mblog.get('id')
                    raw_text = mblog.get('text', '')
                    clean_text = clean_weibo_text(raw_text)

                    if mblog.get('isLongText'):
                        full_text = get_full_text(post_id, cookies)
                        if full_text:
                            clean_text = clean_weibo_text(full_text)

                    # 提取用户链接、日期、评论数
                    user_link = mblog.get('user', {}).get('profile_url', '')
                    date = mblog.get('created_at', '')
                    reply_count = mblog.get('comments_count', 0)

                    posts.append({
                        'mid': post_id,
                        'text': clean_text,
                        'user_link': user_link,
                        'date': date,
                        'reply_count': reply_count
                    })
            return posts, cookies

        except Exception as e:
            logging.error(f'第 {page} 页解析失败，错误信息：{e}')
            if attempt < retries - 1 and cookies_pool:
                cookies = extract_cookies(random.choice(cookies_pool))
                time.sleep(random.uniform(3, 7))
            else:
                break
        time.sleep(random.uniform(3, 7))

    return posts, cookies

def get_all_posts_by_keyword(keyword, cookies, delay=2):
    """
    分页获取所有相关微博帖子
    """
    all_posts = []
    page = 1

    while True:
        posts, cookies = get_posts_by_keyword(keyword, cookies, page=page)
        if not posts:
            break
        all_posts.extend(posts)
        page += 1
        
        # 随机延时，模拟真实用户操作
        time.sleep(random.uniform(3, 7))

    return all_posts

def save_to_csv(data, filename):
    """
    将数据保存到 CSV 文件
    """
    df = pd.DataFrame(data)
    df.to_csv(filename, index=False, encoding='utf-8-sig')
    print(f'数据已保存到 {filename}')

def get_sub1(sss, duplicated_name, sub1_foldername):
    """
    主流程：读取关键词并抓取数据
    """
    if not os.path.exists(sub1_foldername):
        os.makedirs(sub1_foldername)

    try:
        df = pd.read_csv(duplicated_name)
    except Exception as e:
        logging.error(f'无法读取文件 {duplicated_name}，错误信息：{e}')
        return

    if 'word' not in df.columns:
        logging.error(f"CSV 文件 {duplicated_name} 中缺少 'word' 列。")
        return

    hot_search_list = df['word'].tolist()
    cookies = extract_cookies(sss)

    for idx, keyword in enumerate(hot_search_list, start=1):
        posts = get_all_posts_by_keyword(keyword, cookies)
        output_path = os.path.join(sub1_foldername, f'{keyword}.csv')
        save_to_csv(posts, output_path)
        time.sleep(2)

    print("帖子爬取完成。")
