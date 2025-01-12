import os
import pandas as pd
from getHotSearch import get_hot
from clean import clean_data
from sub1 import get_sub1
from sub2 import get_secondary_comments
from sub3 import get_child_comments
from clean_same_topic import merge_deduplicate
import sys
import time

def sanitize_filename(filename):
    """替换文件名中的非法字符"""
    return ''.join(c if c.isalnum() or c in (' ', '_') else '_' for c in filename)

def main():
    # ========================= 1. 参数设置 =========================
    auto_sub = input("是否『自动一次性』执行 sub1, sub2, sub3？(yes/y/no/n): ").strip().lower()
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

            # deduped_path = os.path.join('output_files', f"unique热搜榜test{start_id}_dedup.csv")
            # final_unique_name = f"unique热搜榜test{start_id}.csv"
            # if os.path.exists(deduped_path):
            #     os.rename(deduped_path, final_unique_name)
            #     print(f"去重后的文件已重命名为：{final_unique_name}")
            # else:
            #     print(f"警告：未找到 {deduped_path}，无法重命名。")

            start_id += 1

        # 爬取完新的热搜榜后，再询问下面的逻辑
        # 依然需要后续的 sub1/sub2/sub3，默认对「最新爬取」或用户指定的一个榜单做处理

        _duplicated_id = input("请输入【想要执行评论爬取】的去重热搜榜文件序号(比如6): ")
        duplicated_name = f'unique热搜榜test{_duplicated_id}_dedup.csv'
        sub1_foldername = f'topic_{_duplicated_id}'

        # 根据 auto_sub 来决定后续自动或手动执行
        handle_sub_tasks(auto_sub, cookies, duplicated_name, sub1_foldername)

    else:
        # --- 2.2 不爬取新的热搜榜，而是用已经存在的榜单 ---
        print("你选择了『不爬取热搜榜』，请指定现有热搜榜的相关信息。")

        # 例如一个已经存放了大量 unique热搜榜testN.csv 的文件夹
        existing_folder = input("请输入已存在热搜榜文件所在的文件夹路径(例如: ./old_hotsearch ): ").strip()
        start_id = int(input("请输入开始的热搜榜序号: "))
        end_id   = int(input("请输入结束的热搜榜序号: "))

        # 针对 [start_id, end_id] 这几个编号，一一执行后续爬虫
        for _duplicated_id in range(start_id, end_id + 1):
            duplicated_name = os.path.join(existing_folder, f'unique热搜榜test{_duplicated_id}_dedup.csv')
            if not os.path.exists(duplicated_name):
                print(f"警告：{duplicated_name} 不存在，跳过此编号。")
                continue

            # 文件存在，则可以继续
            sub1_foldername = f'topic_{_duplicated_id}'
            
            # 根据 auto_sub 来决定后续自动或手动执行
            handle_sub_tasks(auto_sub, cookies, duplicated_name, sub1_foldername)

    print("程序执行完毕。")


def handle_sub_tasks(auto_sub, cookies, duplicated_name, sub1_foldername):
    """
    用于处理一级评论 (sub1)、二级评论 (sub2)、三级评论 (sub3) 的自动或手动执行逻辑。
    auto_sub: yes/y 表示自动一次性执行；no/n 表示手动一步步询问。
    cookies: 调用 sub1 / sub2 / sub3 时必需的登录态。
    duplicated_name: 已存在的去重热搜榜路径。
    sub1_foldername: 存放一级评论 CSV 的文件夹名称(比如 topic_6)。
    """
    if auto_sub in ['yes', 'y']:
        # ========================= 1) 一级评论 =========================
        print(f'正在爬取榜单文件 {duplicated_name} 的一级评论...')
        get_sub1(cookies, duplicated_name, f'./{sub1_foldername}')
        print(f'榜单 {duplicated_name} 的一级评论爬取完成！\n')

        # ========================= 2) 二级评论 =========================
        for topic_file in os.listdir(f'./{sub1_foldername}'):
            topic_path = os.path.join(f'./{sub1_foldername}', topic_file)
            # 如果不是文件或大小为 0，跳过
            if not os.path.isfile(topic_path) or os.path.getsize(topic_path) == 0:
                continue

            # 读取一级评论CSV
            try:
                topic_df = pd.read_csv(topic_path)
            except (pd.errors.EmptyDataError, UnicodeDecodeError):
                continue
            
            # 如果内容为空或没 'mid' 列，也跳过
            if topic_df.empty or 'mid' not in topic_df.columns:
                continue

            # 话题名（去掉 .csv 后缀）
            topic_name = sanitize_filename(topic_file.replace('.csv', ''))
            # 对应的二级评论文件夹
            sub2_folder = os.path.join(sub1_foldername, f'{topic_name}_二级')

            print(f"正在为话题『{topic_name}』爬取二级评论...")
            # 遍历每条一级评论（mid）以获取二级评论
            for mid in topic_df['mid']:
                if pd.isnull(mid) or str(mid).strip() == '':
                    continue
                mid_str = str(int(float(mid)))  # 根据需要转换

                df_secondary = get_secondary_comments(mid_str)
                if df_secondary.empty:
                    continue

                # 如果获取到了非空二级评论，再创建二级文件夹
                os.makedirs(sub2_folder, exist_ok=True)

                # 把每条mid对应的二级评论写到一个 CSV
                sub2_csv_path = os.path.join(sub2_folder, f"{mid_str}_secondary.csv")
                df_secondary.to_csv(sub2_csv_path, encoding='utf_8_sig', index=False)

            print(f"话题『{topic_name}』的二级评论爬取完成！\n")

            # ========================= 3) 三级评论 =========================
            if not os.path.exists(sub2_folder):
                # 如果根本没创建过二级文件夹，说明没有任何二级评论
                print(f"话题『{topic_name}』无二级评论，无法爬取三级评论。\n")
                continue

            print(f"正在为话题『{topic_name}』的所有二级评论爬取三级评论...")
            # 遍历二级评论文件夹下的所有 CSV
            for sub2_file in os.listdir(sub2_folder):
                sub2_file_path = os.path.join(sub2_folder, sub2_file)

                # 排除目录或非CSV文件
                if not os.path.isfile(sub2_file_path) or not sub2_file.lower().endswith('.csv'):
                    continue
                if os.path.getsize(sub2_file_path) == 0:
                    continue

                try:
                    sub2_df = pd.read_csv(sub2_file_path)
                except pd.errors.EmptyDataError:
                    continue

                # 如果没有 parent_comment 这列，则无法推断 mid/cid
                if sub2_df.empty or 'parent_comment' not in sub2_df.columns:
                    continue

                # ---- 为该「二级评论 CSV」单独准备一个三级文件夹 ----
                sub2_file_name = sub2_file.replace('.csv', '')
                sub2_file_name = sanitize_filename(sub2_file_name)
                sub3_folder_for_this_sub2 = os.path.join(sub2_folder, f"{sub2_file_name}_三级")

                # 标记：只有当确实有数据时才创建文件夹
                created_sub3_folder = False

                # 遍历二级评论的每一条
                for _, row in sub2_df.iterrows():
                    if pd.isnull(row['parent_comment']) or str(row['parent_comment']).strip() == '':
                        continue

                    mid_2nd = ''
                    cid_2nd = ''
                    try:
                        mid_2nd = str(int(float(row['parent_comment'])))
                        cid_2nd = mid_2nd  # 如果逻辑上 mid 与 cid 相同的话，可直接这样处理
                    except ValueError:
                        continue  # 转换失败就跳过

                    # 爬取三级评论
                    df_tertiary = get_child_comments(mid_2nd, cid_2nd)
                    if df_tertiary.empty:
                        continue

                    # 如果爬到了有效的三级评论，则先建文件夹（只建一次）
                    if not created_sub3_folder:
                        os.makedirs(sub3_folder_for_this_sub2, exist_ok=True)
                        created_sub3_folder = True

                    # 生成三级评论的 CSV 文件
                    tertiary_filename = f"{topic_name}_{mid_2nd}_{cid_2nd}_tertiary.csv"
                    tertiary_path = os.path.join(sub3_folder_for_this_sub2, tertiary_filename)
                    df_tertiary.to_csv(tertiary_path, encoding='utf_8_sig', index=False)

                if created_sub3_folder:
                    print(f"二级评论文件『{sub2_file}』已生成三级评论文件夹：{sub2_file_name}_三级")
                else:
                    print(f"二级评论文件『{sub2_file}』无有效三级评论，未创建文件夹。")

            print(f"话题『{topic_name}』的三级评论爬取完成！\n")

        print("自动模式：所有指定的一级/二级/三级评论爬取任务已执行完毕。")

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
            # 遍历一级评论所在的文件夹，找 CSV
            for topic_file in os.listdir(f'./{sub1_foldername}'):
                topic_path = os.path.join(f'./{sub1_foldername}', topic_file)

                # 判断是否为文件且非空
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

                # 遍历每条一级评论
                for mid in topic_df['mid']:
                    if pd.isnull(mid) or str(mid).strip() == '':
                        continue
                    mid_str = str(int(float(mid)))

                    df_secondary = get_secondary_comments(mid_str)
                    if df_secondary.empty:
                        continue

                    os.makedirs(sub2_folder, exist_ok=True)
                    sub2_csv_path = os.path.join(sub2_folder, f'{mid_str}_secondary.csv')
                    df_secondary.to_csv(sub2_csv_path, encoding='utf_8_sig', index=False)
       
        # 三、是否执行三级评论
        is_sub3 = input("是否爬取三级评论？(yes/y/no/n): ").strip().lower()
        if is_sub3 in ['yes', 'y']:
            for topic_file in os.listdir(f'./{sub1_foldername}'):
                topic_path = os.path.join(f'./{sub1_foldername}', topic_file)

                # 判断是否为文件且非空
                if not os.path.isfile(topic_path) or os.path.getsize(topic_path) == 0:
                    continue
                try:
                    topic_df = pd.read_csv(topic_path)
                except (pd.errors.EmptyDataError, UnicodeDecodeError):
                    continue

                # 话题名
                topic_name = sanitize_filename(topic_file.replace('.csv', ''))

                # 对应的二级评论文件夹
                sub2_folder = os.path.join(sub1_foldername, f'{topic_name}_二级')
                if not os.path.exists(sub2_folder):
                    print(f"警告：未找到二级评论文件夹：{sub2_folder}，跳过『{topic_name}』。")
                    continue

                for sub2_file in os.listdir(sub2_folder):
                    sub2_file_path = os.path.join(sub2_folder, sub2_file)

                    # 如果不是 CSV 文件或为空，直接跳过
                    if (
                        not os.path.isfile(sub2_file_path)
                        or not sub2_file.lower().endswith('.csv')
                        or os.path.getsize(sub2_file_path) == 0
                    ):
                        continue

                    try:
                        sub2_df = pd.read_csv(sub2_file_path)
                    except pd.errors.EmptyDataError:
                        continue

                    if sub2_df.empty or 'parent_comment' not in sub2_df.columns:
                        continue

                    sub2_file_name = sanitize_filename(sub2_file.replace('.csv', ''))
                    sub3_folder_for_this_sub2 = os.path.join(sub2_folder, sub2_file_name + "_三级")

                    created_sub3_folder = False

                    # 遍历二级评论表中的每一行
                    for _, row in sub2_df.iterrows():
                        parent_comment_val = str(row['parent_comment']).strip()
                        if pd.isnull(row['parent_comment']) or parent_comment_val == '':
                            continue

                        mid = ''
                        cid = ''
                        try:
                            mid = str(int(float(parent_comment_val)))
                            cid = mid
                        except ValueError:
                            continue

                        df_tertiary = get_child_comments(mid, cid)
                        if df_tertiary.empty:
                            print(f"警告：三级评论为空 (MID: {mid}, CID: {cid})，跳过创建文件。")
                            continue

                        # 若发现有不为空的三级评论，需要先创建文件夹
                        if not created_sub3_folder:
                            os.makedirs(sub3_folder_for_this_sub2, exist_ok=True)
                            created_sub3_folder = True

                        output_filename = f"{topic_name}_{mid}_{cid}_tertiary.csv"
                        output_path = os.path.join(sub3_folder_for_this_sub2, output_filename)
                        df_tertiary.to_csv(output_path, encoding='utf_8_sig', index=False)

                    if created_sub3_folder:
                        print(f"二级文件『{sub2_file}』生成了 三级评论文件夹：{sub2_file_name}_三级")
                    else:
                        print(f"二级文件『{sub2_file}』下没有任何有效三级评论，未创建文件夹。")

                print(f"话题『{topic_name}』的三级评论全部爬取完毕。\n")

        print("手动模式：所有指定的评论爬取任务已执行完毕。")



if __name__ == '__main__':
    main()
