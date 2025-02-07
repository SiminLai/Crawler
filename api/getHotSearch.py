import requests
import urllib
import pandas as pd

# 获取热搜榜数据
def get_hot():
    headers = {
        'authority': 'weibo.com',
        'accept': 'application/json, text/plain, */*',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'x-requested-with': 'XMLHttpRequest',
    }

    try:
        # 请求热搜榜接口
        response = requests.get('https://weibo.com/ajax/side/hotSearch', headers=headers)
        response.raise_for_status()  # 检查请求是否成功
    except Exception as e:
        print(f"请求失败: {e}")
        return pd.DataFrame()

    try:
        # 解析返回数据
        data = response.json()
        if 'data' not in data or 'realtime' not in data['data']:
            print("警告: 数据中缺少关键字段！")
            return pd.DataFrame()
    except Exception as e:
        print(f"数据解析错误: {e}")
        return pd.DataFrame()

    df = pd.DataFrame(data['data']['realtime'])

    # 添加时间列
    if 'onboard_time' in df.columns:
        df['onboard_time'] = pd.to_datetime(df['onboard_time'], unit='s')
    else:
        df['onboard_time'] = pd.Timestamp.now()

    # 修正 URL，将搜索词直接转换为具体查询 URL
    df['encoded_word'] = df['word'].map(lambda x: urllib.parse.quote(x))  # 编码搜索词
    df['url'] = df['encoded_word'].map(lambda x: f'https://s.weibo.com/weibo?q={x}')  # 生成搜索 URL

    return df
