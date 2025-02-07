import os
import pandas as pd
from getHotSearch import get_hot
from clean import clean_data
from sub1 import get_sub1
from sub2 import get_secondary_comments
# from sub3 import get_child_comments  # <-- 已去除

from clean_same_topic import merge_deduplicate
import sys
import time

def sanitize_filename(filename):
    """替换文件名中的非法字符"""
    return ''.join(c if c.isalnum() or c in (' ', '_') else '_' for c in filename)

def main():
    # ========================= 1. 参数设置 =========================
    auto_sub = input("是否『自动一次性』执行 sub1, sub2？(yes/y/no/n): ").strip().lower()
    is_hotsearch = input("是否爬取热搜榜？(yes/y/no/n): ").strip().lower()
    cookies = input("请输入cookie, 整个一长串就可以. (可以检查一下是否都是那些字串):")
    
    # 注意：下面这两个变量只在“爬取热搜榜 = yes”时有用
    max_count = 0
    start_id = 0

    # ========================= 2. 是否爬取热搜榜 =========================
    if is_hotsearch in ['yes', 'y']:
        # --- 2.1 爬取新的热搜榜 ---
        max_count = int(input("请输入想要获取的热搜榜单的最大数量(例如: 114（24h）): "))
        start_id = int(input("请输入想要开始命名的数字, 比如之前已经有了5个榜单，那么最新的一个会从（6）开始排序，请输入6: "))
        for count in range(max_count):
            df = get_hot()
            if df.empty:
                continue

            hotsearchList_name = f'热搜榜test{start_id}.csv'
            df.to_csv(f'./{hotsearchList_name}', encoding='utf_8_sig', mode='a', header=True)

            cleaned_name = f'cleaned_data#{start_id}.csv'
            clean_data(f'./{hotsearchList_name}', output_file=f'./{cleaned_name}')

            duplicated_name = f'unique热搜榜test{start_id}.csv'
            df_unique = df.drop_duplicates(subset=['word'])
            df_unique.to_csv(f'./{duplicated_name}', encoding='utf_8_sig', index=False)

            merge_deduplicate(
                input_files=[duplicated_name],
                master_file='master.csv',
                # output_dir='output_files'
            )

            start_id += 1

        _duplicated_id = input("请输入【想要执行评论爬取】的去重热搜榜文件序号(比如6): ")
        duplicated_name = f'unique热搜榜test{_duplicated_id}_dedup.csv'
        sub1_foldername = f'topic_{_duplicated_id}'

        # 根据 auto_sub 来决定后续自动或手动执行
        handle_sub_tasks(auto_sub, cookies, duplicated_name, sub1_foldername)

    else:
        # --- 2.2 不爬取新的热搜榜，而是用已经存在的榜单 ---
        print("你选择了『不爬取热搜榜』，请指定现有热搜榜的相关信息。")

        existing_folder = input("请输入已存在热搜榜文件所在的文件夹路径(例如: ./old_hotsearch ): ").strip()
        start_id = int(input("请输入开始的热搜榜序号: "))
        end_id   = int(input("请输入结束的热搜榜序号: "))

        for _duplicated_id in range(start_id, end_id + 1):
            duplicated_name = os.path.join(existing_folder, f'unique热搜榜test{_duplicated_id}_dedup.csv')
            if not os.path.exists(duplicated_name):
                print(f"警告：{duplicated_name} 不存在，跳过此编号。")
                continue

            sub1_foldername = f'topic_{_duplicated_id}'
            handle_sub_tasks(auto_sub, cookies, duplicated_name, sub1_foldername)

    print("程序执行完毕。")

def handle_sub_tasks(auto_sub, cookies, duplicated_name, sub1_foldername):
    """
    用于处理一级评论 (sub1) 和二级评论 (sub2) 的自动或手动执行逻辑。
    NOTE: 已去除对『三级评论』(sub3) 的相关操作。
    """
    if auto_sub in ['yes', 'y']:
        # ========================= 1) 一级评论 =========================
        print(f'正在爬取榜单文件 {duplicated_name} 的一级评论...')
        get_sub1(cookies, duplicated_name, f'./{sub1_foldername}')
        print(f'榜单 {duplicated_name} 的一级评论爬取完成！\n')

        # ========================= 2) 二级评论 =========================
        for topic_file in os.listdir(f'./{sub1_foldername}'):
            topic_path = os.path.join(f'./{sub1_foldername}', topic_file)
            if not os.path.isfile(topic_path) or os.path.getsize(topic_path) == 0:
                continue

            try:
                topic_df = pd.read_csv(topic_path)
            except (pd.errors.EmptyDataError, UnicodeDecodeError):
                continue
            
            if topic_df.empty or 'mid' not in topic_df.columns:
                continue

            topic_name = sanitize_filename(topic_file.replace('.csv', ''))
            sub2_folder = os.path.join(sub1_foldername, f'{topic_name}_二级')

            print(f"正在为话题『{topic_name}』爬取二级评论...")
            for mid in topic_df['mid']:
                if pd.isnull(mid) or str(mid).strip() == '':
                    continue
                mid_str = str(int(float(mid)))

                df_secondary, df_tertiary = get_secondary_comments(mid_str, topic_name)
                # 保存二级评论
                if not df_secondary.empty:
                    os.makedirs(sub2_folder, exist_ok=True)
                    sub2_csv_path = os.path.join(sub2_folder, f"{mid_str}_secondary.csv")
                    df_secondary.to_csv(sub2_csv_path, encoding='utf_8_sig', index=False)

                # 保存三级评论
                if not df_tertiary.empty:
                    sub3_folder = os.path.join(sub2_folder, "三级评论")
                    os.makedirs(sub3_folder, exist_ok=True)
                    sub3_csv_path = os.path.join(sub3_folder, f"{mid_str}_tertiary.csv")
                    df_tertiary.to_csv(sub3_csv_path, encoding='utf_8_sig', index=False)
            print(f"话题『{topic_name}』的二级评论爬取完成！\n")

        print("自动模式：所有指定的一级/二级评论爬取任务已执行完毕。")

    else:
        # ============= 手动模式：分步骤询问 =============
        print("你选择了手动模式，将逐步询问每一步是否执行。")
        
        # 一、是否执行一级评论
        is_sub1 = input("是否执行一级评论爬取？(yes/y/no/n): ").strip().lower()
        if is_sub1 in ['yes', 'y']:
            print(f'正在爬取榜单文件 {duplicated_name} 的一级评论...')
            get_sub1(cookies, duplicated_name, f'./{sub1_foldername}')
            print(f'榜单 {duplicated_name} 的一级评论爬取完成！')

        # 二、是否执行二级评论
        is_sub2 = input("是否执行二级评论爬取？(yes/y/no/n): ").strip().lower()
        if is_sub2 in ['yes', 'y']:
            for topic_file in os.listdir(f'./{sub1_foldername}'):
                topic_path = os.path.join(f'./{sub1_foldername}', topic_file)

                if not os.path.isfile(topic_path) or os.path.getsize(topic_path) == 0:
                    continue
                try:
                    topic_df = pd.read_csv(topic_path)
                except (pd.errors.EmptyDataError, UnicodeDecodeError):
                    continue

                if topic_df.empty or 'mid' not in topic_df.columns:
                    continue

                topic_name = sanitize_filename(topic_file.replace('.csv', ''))
                sub2_folder = os.path.join(sub1_foldername, f'{topic_name}_二级')

                for mid in topic_df['mid']:
                    if pd.isnull(mid) or str(mid).strip() == '':
                        continue
                    mid_str = str(int(float(mid)))

                    df_secondary, df_tertiary = get_secondary_comments(mid_str, topic_name)
                    # 保存二级评论
                    if not df_secondary.empty:
                        os.makedirs(sub2_folder, exist_ok=True)
                        sub2_csv_path = os.path.join(sub2_folder, f"{mid_str}_secondary.csv")
                        df_secondary.to_csv(sub2_csv_path, encoding='utf_8_sig', index=False)

                    # 保存三级评论
                    if not df_tertiary.empty:
                        sub3_folder = os.path.join(sub2_folder, "三级评论")
                        os.makedirs(sub3_folder, exist_ok=True)
                        sub3_csv_path = os.path.join(sub3_folder, f"{mid_str}_tertiary.csv")
                        df_tertiary.to_csv(sub3_csv_path, encoding='utf_8_sig', index=False)
            print(f"话题『{topic_name}』的二级评论爬取完成！\n")
        print("手动模式：所有指定的一级/二级评论爬取任务已执行完毕。")


if __name__ == '__main__':
    main()
