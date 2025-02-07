import os
import pandas as pd
import json

def convert_json_to_csv(json_folder, csv_folder):
    """
    将 JSON 文件中的数据转换为 CSV 文件并保存
    :param json_folder: 包含 JSON 文件的文件夹路径
    :param csv_folder: 用于保存 CSV 文件的文件夹路径
    """
    if not os.path.exists(csv_folder):
        os.makedirs(csv_folder)

    json_files = [f for f in os.listdir(json_folder) if f.endswith('.json')]
    if not json_files:
        print(f"文件夹 {json_folder} 中没有找到 JSON 文件。")
        return

    for json_file in json_files:
        json_path = os.path.join(json_folder, json_file)
        csv_path = os.path.join(csv_folder, json_file.replace('.json', '.csv'))

        try:
            # 读取 JSON 文件
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 提取关键数据
            keyword = data.get('keyword', '未知关键词')
            posts = data.get('posts', [])

            if not posts:
                print(f"文件 {json_file} 中没有找到帖子数据。")
                continue

            # 将帖子列表转换为 DataFrame
            df = pd.DataFrame(posts)
            df.insert(0, 'keyword', keyword)  # 添加关键词列

            # 保存为 CSV 文件
            df.to_csv(csv_path, index=False, encoding='utf-8-sig')
            print(f"文件 {json_file} 已成功转换为 {csv_path}。")

        except Exception as e:
            print(f"转换文件 {json_file} 时出错：{e}")

# 使用示例
json_folder = 'C:/Users/laisi/Desktop/舆论/dataset1/hahaha(2)/topic_105'  # JSON 文件夹路径
csv_folder = 'C:/Users/laisi/Desktop/舆论/dataset1/hahaha(2)/topic_105/csv'  # 保存 CSV 文件的文件夹路径
convert_json_to_csv(json_folder, csv_folder)
