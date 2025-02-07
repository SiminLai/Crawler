import os
import pandas as pd
import requests
import time
import random
import logging
import re
from bs4 import BeautifulSoup
from datetime import datetime
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

# 清理评论文本内容
def clean_text(text):
    # 解析 HTML，去除嵌套回复内容
    parsed_text = BeautifulSoup(text, 'html.parser').get_text()
    return parsed_text.strip()

# 解析一级评论
def parse_secondary_comments(data):
    lst = []
    comments_list = data.get('data', {}).get('data', [])

    if not isinstance(comments_list, list):
        logging.error(f"评论数据结构异常: {comments_list}")
        return pd.DataFrame()

    for comment in comments_list:
        try:
            if 'reply_id' in comment and comment['reply_id']:
                logging.warning(f"发现评论的回复内容，跳过: {comment}")
                continue

            lst.append({
                'comment_id': comment.get('id'),
                'user': comment.get('user', {}).get('screen_name', '未知用户'),
                'user_profile': comment.get('user', {}).get('profile_url', ''),
                'text': clean_text(comment.get('text', '')),
                'likes': comment.get('like_counts', 0),
                'time': format_time(comment.get('created_at', ''))
            })
        except Exception as e:
            logging.error(f"解析评论异常: {e}，评论数据: {comment}")
    return pd.DataFrame(lst)


# 获取一级评论
def get_secondary_comments(post_id):
    cookies = switch_cookies()
    headers = {
        'authority': 'm.weibo.cn',
        'accept': 'application/json, text/plain, */*',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'x-requested-with': 'XMLHttpRequest',
    }

    comments = []
    page = 1
    retries = 200  # 这里示例设为5，实际可根据需要设置更大值

    while True:
        # 用于标记当前页是否成功获取到有效数据
        page_fetched_successfully = False

        for attempt in range(retries):
            try:
                url = 'https://m.weibo.cn/api/comments/show'
                params = {
                    'id': post_id,
                    'page': page
                }
                response = requests.get(url, headers=headers, cookies=cookies, params=params)
                response.encoding = 'utf-8'

                if response.status_code != 200:
                    logging.error(f"请求失败，状态码: {response.status_code}")
                    # 继续重试当前页
                    time.sleep(random.uniform(1, 3))
                    continue

                data = response.json()
                comment_list = data.get('data', {}).get('data', [])

                # 如果触发验证码
                if data.get("ok") == -100:
                    logging.warning("触发验证码，尝试更换 Cookies 或代理...")
                    # 还没到最后一次重试，则换一个cookies再试
                    if attempt < retries - 1:
                        cookies = extract_cookies(random.choice(cookies_pool))
                        time.sleep(random.uniform(1, 3))
                        # 继续重试本页
                        continue
                    else:
                        # 到达最后一次重试仍失败 => 让用户手动输入新的Cookies
                        logging.error("多次尝试后仍触发验证码，放弃本次请求，等待人工输入Cookies")
                        print(f"请访问以下链接并完成验证码验证: https://m.weibo.cn/{post_id}")
                        cookies_input = input("请输入新的 Cookies 并按回车键继续：")
                        cookies = extract_cookies(cookies_input)
                        logging.info("已更新新的 Cookies。")
                        # 再次继续重试
                        continue

                # 如果本页没有评论，认为是最后一页或无法获取更多评论
                if not comment_list:
                    logging.info(f"第 {page} 页无更多评论，爬取结束。")
                    # 如果已有评论数据，返回合并；否则返回空DataFrame
                    return pd.concat(comments, ignore_index=True) if comments else pd.DataFrame()

                # 能到这里说明本页获取成功
                df = parse_secondary_comments(data)
                if not df.empty:
                    comments.append(df)

                # 标记成功，跳出重试循环
                page_fetched_successfully = True
                break

            except Exception as e:
                logging.error(f"请求异常: {e}")
                time.sleep(random.uniform(3, 7))

        # for attempt in range(retries) 结束后，
        # 如果依然没拿到有效数据，说明当前页多次重试都失败了
        if not page_fetched_successfully:
            logging.error(f"当前页({page})多次尝试仍未获取成功，结束爬取。")
            # 根据需求，你也可以选择继续下一页，或者直接返回
            return pd.concat(comments, ignore_index=True) if comments else pd.DataFrame()

        # 如果本页成功获取，继续获取下一页
        page += 1
        # 休眠防止过快爬取
        time.sleep(random.uniform(3, 7))

    # 理论上不会执行到这里
    return pd.concat(comments, ignore_index=True) if comments else pd.DataFrame()

# 主程序
if __name__ == "__main__":
    post_id = input("请输入微博帖子ID: ")

    print(f"正在抓取微博 {post_id} 的一级评论...")
    primary_comments = get_secondary_comments(post_id)

    if not primary_comments.empty:
        output_path = f'primary_comments_{post_id}.csv'
        primary_comments.to_csv(output_path, index=False)
        print(f"微博 {post_id} 的一级评论已保存到 {output_path}！")
    else:
        print(f"微博 {post_id} 的一级评论为空或抓取失败！")

    print(f"微博 {post_id} 的一级评论爬取完成！")
