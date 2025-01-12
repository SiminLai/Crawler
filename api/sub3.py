import os
import pandas as pd
import requests
import time
import random
import logging
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

def parse_comment_data(response_data):
    """
    解析微博子评论和根评论信息，包括 rootComment 的 user 信息
    """
    comments = []

    try:
        # 提取根评论信息
        root_comment = response_data.get('rootComment', [{}])[0]
        root_comment_id = root_comment.get('id', None)
        root_comment_text = BeautifulSoup(root_comment.get('text', ''), 'html.parser').get_text()

        root_user = root_comment.get('user', {})
        root_user_id = root_user.get('id', None)
        root_user_name = root_user.get('screen_name', '未知用户')
        root_user_verified = root_user.get('verified', False)

        # 提取子评论信息
        for comment in response_data.get('data', []):
            comment_id = comment.get('id', None)
            comment_text = BeautifulSoup(comment.get('text', ''), 'html.parser').get_text()
            created_at = format_time(comment.get('created_at', ''))
            user_name = comment.get('user', {}).get('screen_name', '未知用户')
            like_count = comment.get('like_count', 0)

            # 被回复内容
            reply_text = comment.get('reply_original_text', None)
            reply_id = comment.get('reply_id', None)

            # 保存评论数据
            comments.append({
                'root_comment_id': root_comment_id,
                'root_comment_text': root_comment_text,
                'root_user_id': root_user_id,
                'root_user_name': root_user_name,
                'root_user_verified': root_user_verified,
                'comment_id': comment_id,
                'comment_text': comment_text,
                'created_at': created_at,
                'user_name': user_name,
                'like_count': like_count,
                'reply_text': reply_text,  # 被回复内容
                'reply_id': reply_id,      # 被回复评论 ID
            })

    except Exception as e:
        logging.error(f"解析评论数据异常: {e}")

    return pd.DataFrame(comments)

def get_child_comments(root_comment_id):
    """
    获取评论数据，返回整合的 DataFrame
    """
    cookies = switch_cookies()
    headers = {
        'authority': 'm.weibo.cn',
        'accept': 'application/json, text/plain, */*',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'x-requested-with': 'XMLHttpRequest',
    }

    max_id = 0
    all_comments = []
    retries = 500  # 最大尝试次数
    attempt_count = 0

    while True:
        while attempt_count < retries:
            try:
                url = 'https://m.weibo.cn/comments/hotFlowChild'
                params = {'cid': root_comment_id, 'max_id': max_id}
                response = requests.get(url, headers=headers, cookies=cookies, params=params, timeout=10)
                response.encoding = 'utf-8'

                if response.status_code != 200:
                    logging.error(f"请求失败，状态码: {response.status_code}")
                    break

                data = response.json()

                if data.get("ok") == -100:
                    logging.warning("触发验证码，更换 Cookies...")
                    cookies = switch_cookies()
                    attempt_count += 1
                    time.sleep(random.uniform(1, 3))
                    continue

                if not data.get('data'):
                    logging.info("没有更多评论，结束抓取。")
                    return pd.concat(all_comments, ignore_index=True) if all_comments else pd.DataFrame()

                # 解析子评论并将结果加入整体列表
                comments_df = parse_comment_data(data)
                if not comments_df.empty:
                    all_comments.append(comments_df)

                max_id = data.get('max_id', 0)
                if max_id == 0:
                    return pd.concat(all_comments, ignore_index=True) if all_comments else pd.DataFrame()

                time.sleep(random.uniform(1, 3))
                break

            except Exception as e:
                logging.error(f"请求评论异常: {e}")
                time.sleep(random.uniform(3, 7))

        if attempt_count >= retries:
            print(f"请访问以下链接完成验证: https://m.weibo.cn/comments/hotFlowChild?cid={root_comment_id}")
            new_cookies = input("验证完成后，请输入新的 Cookies 并按回车键继续：")
            cookies = extract_cookies(new_cookies)
            logging.info("已更新新的 Cookies。")
            attempt_count = 0  # 重置尝试计数

    # 返回整合的 DataFrame
    return pd.concat(all_comments, ignore_index=True) if all_comments else pd.DataFrame()

# 主程序
if __name__ == "__main__":
    root_comment_id = input("请输入根评论 ID: ")
    print(f"正在抓取根评论 {root_comment_id} 的所有子评论...")

    all_comments_df = get_child_comments(root_comment_id)

    if not all_comments_df.empty:
        output_path = f'child_comments_{root_comment_id}.csv'
        all_comments_df.to_csv(output_path, index=False, encoding='utf-8-sig')
        print(f"所有子评论已保存到 {output_path}！")
    else:
        print("没有抓取到任何子评论！")

    print("爬取完成。")
