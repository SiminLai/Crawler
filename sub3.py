#!/usr/bin/env python
# coding: utf-8

"""
文件名: sub3.py

功能: 爬取某一条“父评论”下的所有“子评论”。
用法: 
1) 需要先获得父评论的 comment_id (或 rootid)。假设它叫 parent_id
2) 在爬虫启动时指定微博 MID 以及该父评论 ID
3) 脚本会将爬到的数据保存到一个 CSV 文件里
"""

import os
import pandas as pd
import requests
import time
import random
import logging
from bs4 import BeautifulSoup
from datetime import datetime
from cookies_manager import cookies_pool  # 你项目中的 cookies 管理

# 日志配置
now = datetime.now()
formatted_time = now.strftime("%Y-%m-%d-%H-%M-%S")
log_filename = f"error_sub3_{formatted_time}.log"
logging.basicConfig(filename=log_filename, level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

# Cookie处理
def extract_cookies(raw_cookie: str) -> dict:
    cookies = raw_cookie.split("; ")
    return {c.split("=")[0]: c.split("=")[1] for c in cookies if '=' in c}

def switch_cookies():
    """从 cookies_pool 中随机选取一条 Cookie 并转换成 requests 可用的字典"""
    return extract_cookies(random.choice(cookies_pool))

# 时间格式化
def format_time(time_str: str) -> str:
    """
    将微博返回的时间字符串转换为标准格式。
    微博时间通常类似: 'Fri Dec 25 09:30:00 +0800 2020'
    """
    try:
        return datetime.strptime(time_str, '%a %b %d %H:%M:%S %z %Y').strftime('%Y-%m-%d %H:%M:%S')
    except ValueError as e:
        logging.error(f"时间解析错误: {e}, 输入时间: {time_str}")
        return time_str

def parse_child_comments(data: dict) -> pd.DataFrame:
    """
    解析接口返回的子评论 JSON 数据，返回一个 DataFrame。
    """
    # data 里通常有 { "data": [...] } 结构
    comments_list = data.get('data', [])
    
    if not isinstance(comments_list, list):
        logging.error(f"评论数据结构异常: {comments_list}")
        return pd.DataFrame()

    rows = []
    for comment in comments_list:
        try:
            # 清理文本: 把 HTML 标签去掉
            comment_text = BeautifulSoup(comment.get('text', ''), 'html.parser').get_text()
            user_name = comment.get('user', {}).get('screen_name', '未知用户')
            like_count = comment.get('like_counts', comment.get('like_count', 0))
            create_time = format_time(comment.get('created_at', ''))

            # 父评论文本也可以取出来看一看
            parent_txt = ""
            parent_info = comment.get('reply_comment', {})
            if parent_info:
                # 如果是对父评论再次回复，可以拿到 parent_info 的 text
                parent_txt = BeautifulSoup(parent_info.get('text', ''), 'html.parser').get_text()

            rows.append({
                'user': user_name,
                'child_text': comment_text,
                'child_likes': like_count,
                'child_time': create_time,
                'parent_comment': parent_txt,
                'child_comment_id': comment.get('id', None),
            })
        except Exception as e:
            logging.error(f"解析子评论异常: {e}，评论数据: {comment}")
            continue

    return pd.DataFrame(rows)

def get_child_comments(mid: str, parent_id: str) -> pd.DataFrame:
    """
    根据微博MID和某条评论(父评论)的parent_id获取所有子评论。
    
    参数:
    mid       : 该条微博的 MID
    parent_id : 父评论的 comment_id 或 rootid
    
    返回:
    全部子评论的 DataFrame，如果为空则说明没有子评论或请求失败。
    """
    cookies = switch_cookies()
    headers = {
        'authority': 'weibo.com',
        'accept': 'application/json, text/plain, */*',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'x-requested-with': 'XMLHttpRequest',
    }

    all_child_comments = []
    max_id = 0  # 分页标识
    retries = 5

    while True:
        for attempt in range(retries):
            try:
                # 注意这里要带上 parent_id(父评论ID) 和 fetch_level=1
                # count=20 每页多少条，max_id 用于翻页
                url = (
                    "https://weibo.com/ajax/statuses/buildComments"
                    f"?flow=0&is_reload=1&id={mid}"
                    "&is_show_bulletin=2&is_mix=0"
                    "&fetch_level=1"
                    f"&count=20&max_id={max_id}"
                    f"&parent_id={parent_id}"
                )

                response = requests.get(url, headers=headers, cookies=cookies, timeout=10)
                response.encoding = 'utf-8'

                # 检查防爬
                if response.status_code == 418 or "<html>" in response.text.lower():
                    logging.error("触发反爬或Cookies已失效，切换Cookies重试...")
                    cookies = switch_cookies()
                    time.sleep(1)
                    continue

                data = response.json()
                logging.info(f"子评论接口返回: {data}")

                # 如果 data 里没有 'data' 或者 data['data'] 是空，说明无更多子评论
                if 'data' not in data or len(data.get('data', [])) == 0:
                    logging.warning("没有更多子评论了，或已全部爬取完成。")
                    # 如果已经有累积数据，就合并返回
                    if all_child_comments:
                        return pd.concat(all_child_comments, ignore_index=True)
                    else:
                        return pd.DataFrame()

                # 解析子评论
                df = parse_child_comments(data)
                if not df.empty:
                    all_child_comments.append(df)

                # 翻页: 更新 max_id
                new_max_id = data.get('max_id', 0)
                if new_max_id == 0 or new_max_id == max_id:
                    # 如果下一页 max_id 还是0 或者没变化，就表示已经到底了
                    return pd.concat(all_child_comments, ignore_index=True)
                max_id = new_max_id
                # 成功拿到数据后 break 出 for retry
                break

            except Exception as e:
                logging.error(f"子评论请求异常: {e}")
                # 指数退避策略：遇到异常先休息再重试
                time.sleep(2 ** attempt + random.uniform(0, 2))

        else:
            # 如果重试完都失败，就返回已经获取到的数据，或者空
            logging.error("多次请求失败，提前结束爬取。")
            return pd.concat(all_child_comments, ignore_index=True) if all_child_comments else pd.DataFrame()

# 主程序
if __name__ == "__main__":
    """
    1) 先获取微博的 MID
    2) 再获取指定父评论的 parent_id (在微博JSON中一般是 comment_id 或 rootid)
    """
    mid = input("请输入微博 MID: ")
    parent_id = input("请输入父评论的 comment_id 或 rootid: ")
    
    print(f"正在抓取微博 {mid} 下 parent_id={parent_id} 的子评论...")
    child_comments = get_child_comments(mid, parent_id)

    if not child_comments.empty:
        output_path = f'child_comments_{mid}_{parent_id}.csv'
        child_comments.to_csv(output_path, index=False, encoding='utf-8-sig')
        print(f"微博 {mid} 的子评论(父评论ID={parent_id})已保存到 {output_path}！")
    else:
        print(f"微博 {mid} 的子评论为空或抓取失败！")

    print("爬取完成。")
