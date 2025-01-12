import os
import pandas as pd
import requests
import time
import random
import logging
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from cookies_manager import cookies_pool

# 日志配置
now = datetime.now()
formatted_time = now.strftime("%Y-%m-%d-%H-%M-%S")
log_filename = f"error_{formatted_time}.log"
logging.basicConfig(filename=log_filename, level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

# Cookie处理
def extract_cookies(raw_cookie):
    cookies = raw_cookie.split("; ")
    return {c.split("=")[0]: c.split("=")[1] for c in cookies if '=' in c}

def switch_cookies():
    return extract_cookies(random.choice(cookies_pool))

# 时间格式化
def format_time(time_str):
    try:
        return datetime.strptime(time_str, '%a %b %d %H:%M:%S %z %Y').strftime('%Y-%m-%d %H:%M:%S')
    except ValueError as e:
        logging.error(f"时间解析错误: {e}, 输入时间: {time_str}")
        return time_str

# 解析二级评论
def parse_secondary_comments(data):
    """解析二级评论"""
    lst = []
    # 确保 'data' 字段存在且为列表
    comments_list = data.get('data', [])

    if not isinstance(comments_list, list):
        logging.error(f"评论数据结构异常: {comments_list}")
        return pd.DataFrame()

    # 解析评论内容
    for comment in comments_list:
        try:
            lst.append({
            'user': comment.get('user', {}).get('screen_name', '未知用户'),
            'text': BeautifulSoup(comment.get('text', ''), 'html.parser').get_text(),
            'likes': comment.get('like_counts', comment.get('like_count', 0)),  # 增强 likes 提取
            'time': format_time(comment.get('created_at', '')),
            'parent_comment': comment.get('reply_comment', {}).get('text', comment.get('rootid', ''))  # 增强 parent_comment 提取
        })

        except Exception as e:
            logging.error(f"解析评论异常: {e}，评论数据: {comment}")
    return pd.DataFrame(lst)


# 获取二级评论
def get_secondary_comments(mid):
    """获取二级评论"""
    cookies = switch_cookies()
    headers = {
        'authority': 'weibo.com',
        'accept': 'application/json, text/plain, */*',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'x-requested-with': 'XMLHttpRequest',
    }

    comments = []
    max_id = 0  # 分页标识
    retries = 5

    while True:  # 动态分页循环
        for attempt in range(retries):
            try:
                # 更新 URL，使用 max_id 控制分页
                url = f'https://weibo.com/ajax/statuses/buildComments?flow=0&is_reload=1&id={mid}&is_show_bulletin=2&is_mix=0&count=20&max_id={max_id}'
                response = requests.get(url, headers=headers, cookies=cookies)
                response.encoding = 'utf-8'

                # 检查防爬
                if response.status_code == 418 or "<html>" in response.text.lower():
                    logging.error("反爬触发或 Cookies 已失效，切换 Cookies")
                    cookies = switch_cookies()
                    continue

                # 解析 JSON 数据
                data = response.json()
                logging.error(f"解析后的数据: {data}")

                # 判断数据有效性
                if 'data' not in data or len(data.get('data', [])) == 0:
                    logging.warning(f"当前分页没有数据或爬取完毕")
                    return pd.concat(comments, ignore_index=True) if comments else pd.DataFrame()

                # 解析评论数据
                df = parse_secondary_comments(data)
                if not df.empty:
                    comments.append(df)
                else:
                    logging.warning(f"当前分页解析后无数据")

                # 更新分页 ID
                max_id = data.get('max_id', 0)
                if max_id == 0:  # 无更多数据时退出
                    return pd.concat(comments, ignore_index=True) if comments else pd.DataFrame()

            except Exception as e:
                logging.error(f"请求异常: {e}")
                time.sleep(2 ** attempt + random.uniform(0, 2))


# 主程序
if __name__ == "__main__":
    # 输入微博 MID
    mid = input("请输入微博 MID: ")

    print(f"正在抓取微博 {mid} 的二级评论...")
    sec_comments = get_secondary_comments(mid)

    if not sec_comments.empty:
        output_path = f'secondary_comments_{mid}.csv'
        sec_comments.to_csv(output_path, index=False)
        print(f"微博 {mid} 的二级评论已保存到 {output_path}！")
    else:
        print(f"微博 {mid} 的二级评论为空或抓取失败！")

    print(f"微博 {mid} 的二级评论爬取完成！")
