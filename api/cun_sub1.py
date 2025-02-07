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
    # 使用 BeautifulSoup 解析 HTML
    soup = BeautifulSoup(raw_html, 'html.parser')
    
    # 删除所有 <a> 链接
    for a_tag in soup.find_all('a'):
        a_tag.decompose()
    
    # 替换表情图标 (img) 的 alt 属性内容
    for img_tag in soup.find_all('img'):
        if img_tag.has_attr('alt'):
            img_tag.replace_with(img_tag['alt'])  # 替换为表情的文本描述
        else:
            img_tag.decompose()  # 如果没有 alt 属性，直接删除 img 标签
    
    # 提取纯文本内容
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
            return data.get('data', {}).get('longTextContent', '')  # 返回长文内容
        else:
            logging.error(f"获取长微博失败，状态码：{response.status_code}")
    except Exception as e:
        logging.error(f"获取长微博失败，错误信息：{e}")
    return None


    
def get_posts_by_keyword(keyword, cookies, page=1, delay=2):
    """
    获取指定关键词的帖子，并清洗内容
    """
    posts = []
    params = {
        'containerid': f'100103type=61&q={quote(keyword)}',  # 使用实时分类 containerid
        'page': page
    }

    retries = 20  # 重试次数                                                   
    for attempt in range(retries):
        try:
            response = requests.get(BASE_API_URL, headers=HEADERS, cookies=cookies, params=params, timeout=10)
            if response.status_code != 200:
                raise Exception(f"状态码异常: {response.status_code}")

            print(f"请求 URL: {response.url}")  # 打印调试 URL
            data = response.json()

            # 解析帖子数据
            cards = data.get('data', {}).get('cards', [])
            for card in cards:
                if card.get('card_type') == 9:  # 检查是否为帖子类型
                    mblog = card.get('mblog', {})
                    post_id = mblog.get('id')
                    raw_text = mblog.get('text', '')  # 原始 HTML 文本

                    # 调用清理函数提取纯文本内容
                    clean_text = clean_weibo_text(raw_text)

                    # 检查是否为长文，获取全文内容
                    if mblog.get('isLongText'):
                        full_text = get_full_text(post_id, cookies)
                        if full_text:
                            clean_text = clean_weibo_text(full_text)

                    posts.append({
                        'post_id': post_id,
                        'text': clean_text
                    })
            return posts, cookies  # 返回帖子和当前 Cookies

        except Exception as e:
            logging.error(f'第 {page} 页解析失败，错误信息：{e}')
            if attempt < retries - 1 and cookies_pool:
                # 替换 Cookies 并继续尝试
                new_cookies = extract_cookies(random.choice(cookies_pool))
                print(f"切换 Cookies 重试: {new_cookies}")
                cookies = new_cookies
                time.sleep(2 ** attempt)  # 指数退避
            else:
                break  # 重试失败后退出

        time.sleep(delay)
    return posts, cookies


def get_all_posts_by_keyword(keyword, cookies, delay=2):
    """
    分页获取所有相关微博帖子
    """
    all_posts = []
    page = 1

    while True:
        print(f'  获取第 {page} 页的帖子...')
        posts, cookies = get_posts_by_keyword(keyword, cookies, page=page, delay=delay)

        if not posts:  # 如果没有帖子，结束循环
            print(f'  第 {page} 页无更多帖子。')
            break

        all_posts.extend(posts)
        print(f'  获取到 {len(posts)} 篇帖子。')

        page += 1
        time.sleep(1)  # 控制请求速率

    return all_posts


def save_to_json(data, filename):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
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
        print(f"无法读取文件 {duplicated_name}，错误信息：{e}")
        return

    if 'word' not in df.columns:
        logging.error(f"CSV 文件 {duplicated_name} 中缺少 'word' 列。")
        print(f"CSV 文件 {duplicated_name} 中缺少 'word' 列。")
        return

    hot_search_list = df['word'].tolist()

    # 设置初始Cookies
    cookies = extract_cookies(sss)

    for idx, keyword in enumerate(hot_search_list, start=1):
        print(f"\n处理热搜 {idx}/{len(hot_search_list)}: 关键词 '{keyword}'")

        posts = get_all_posts_by_keyword(keyword, cookies)
        print(f"  获取到 {len(posts)} 篇相关帖子。")

        result = {
            'keyword': keyword,
            'posts': posts
        }
        output_path = os.path.join(sub1_foldername, f'{keyword}.json')
        save_to_json(result, output_path)
        print(f'话题 {keyword} 的帖子已保存到: {output_path}')

        time.sleep(2)

    print("帖子爬取完成。")


