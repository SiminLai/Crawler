import os
import pandas as pd
from getHotSearch import get_hot
from clean import clean_data
from sub1 import get_sub1
from sub2 import get_secondary_comments
from sub3 import get_child_comments
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

    # ========================= 2. 热搜榜处理 =========================
    if is_hotsearch in ['yes', 'y']:
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

            start_id += 1

    # ========================= 3. 评论爬取设置 =========================
    _duplicated_id = input("请输入已存在的去重热搜榜文件序号，比如6: ")
    duplicated_name = f'unique热搜榜test{_duplicated_id}.csv'
    sub1_foldername = f'topic_{_duplicated_id}'

    # ========================= 自动模式 =========================
    if auto_sub in ['yes', 'y']:
        # 1) 一级评论
        print(f'正在爬取榜单 {_duplicated_id} 的一级评论...')
        get_sub1(cookies, f'./{duplicated_name}', f'./{sub1_foldername}')
        print(f'榜单 {_duplicated_id} 的一级评论爬取完成！\n')

        # 2) 二级评论
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
                mid_str = str(int(float(mid)))  # 视你的实际情况是否需要 float->int->str

                df_secondary = get_secondary_comments(mid_str)
                if df_secondary.empty:
                    continue

                # 如果获取到了非空二级评论，再创建二级文件夹
                os.makedirs(sub2_folder, exist_ok=True)

                # 把每条mid对应的二级评论写到一个 CSV
                sub2_csv_path = os.path.join(sub2_folder, f"{mid_str}_secondary.csv")
                df_secondary.to_csv(sub2_csv_path, encoding='utf_8_sig', index=False)

            print(f"话题『{topic_name}』的二级评论爬取完成！\n")

            # 3) 三级评论
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
                        cid_2nd = mid_2nd  # 如果逻辑上 mid 与 cid 相同的话，直接赋值
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


    # ========================= 手动模式 =========================
    else:
        print("你选择了手动模式，将逐步询问每一步是否执行。")

        # 一级评论
        is_sub1 = input("是否执行一级评论爬取？(yes/y/no/n): ").strip().lower()
        if is_sub1 in ['yes', 'y']:
            print(f'正在爬取榜单 {_duplicated_id} 的一级评论...')
            get_sub1(cookies, f'./{duplicated_name}', f'./{sub1_foldername}')
            print(f'榜单 {_duplicated_id} 的一级评论爬取完成！')

        # 二级评论
        is_sub2 = input("是否执行二级评论爬取？(yes/y/no/n): ").strip().lower()
        if is_sub2 in ['yes', 'y']:
            for topic_file in os.listdir(f'./{sub1_foldername}'):
                topic_path = os.path.join(f'./{sub1_foldername}', topic_file)
                if os.path.getsize(topic_path) == 0:
                    continue
                topic_df = pd.read_csv(topic_path)
                if topic_df.empty:
                    continue

                topic_name = sanitize_filename(topic_file.replace('.csv', ''))
                sub2_folder = os.path.join(sub1_foldername, f'{topic_name}_二级')

                for mid in topic_df['mid']:
                    df_secondary = get_secondary_comments(mid)
                    if df_secondary.empty:
                        continue

                    os.makedirs(sub2_folder, exist_ok=True)
                    df_secondary.to_csv(f'{sub2_folder}/{mid}_secondary.csv', encoding='utf_8_sig', index=False)
       
        # 三级评论
        is_sub3 = input("是否爬取三级评论？(yes/y/no/n): ").strip().lower()
        if is_sub3 in ['yes', 'y']:
            for topic_file in os.listdir(f'./{sub1_foldername}'):
                topic_path = os.path.join(f'./{sub1_foldername}', topic_file)

                # 判断是否为文件且非空
                if not os.path.isfile(topic_path) or os.path.getsize(topic_path) == 0:
                    continue

                # 读取一级评论（若不需要，可省略）
                try:
                    topic_df = pd.read_csv(topic_path)
                except (pd.errors.EmptyDataError, UnicodeDecodeError):
                    continue

                # 话题名
                topic_name = sanitize_filename(topic_file.replace('.csv', ''))

                # 二级评论文件夹
                sub2_folder = os.path.join(sub1_foldername, f'{topic_name}_二级')
                if not os.path.exists(sub2_folder):
                    print(f"警告：未找到二级评论文件夹：{sub2_folder}，跳过『{topic_name}』。")
                    continue

                # 遍历二级评论文件夹下的所有文件
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

                    if 'parent_comment' not in sub2_df.columns:
                        continue

                    # ---- 针对当前二级评论文件，先不急着创建“三级评论文件夹” ----
                    sub2_file_name = sanitize_filename(sub2_file.replace('.csv', ''))
                    sub3_folder_for_this_sub2 = os.path.join(sub2_folder, sub2_file_name + "_三级")

                    # 用变量来标记是否已经有实际的三级评论需要保存
                    created_sub3_folder = False

                    # 遍历二级评论表
                    for _, row in sub2_df.iterrows():
                        mid = ''
                        cid = ''
                        if pd.notnull(row['parent_comment']) and row['parent_comment'] != '':
                            try:
                                mid = str(int(float(row['parent_comment'])))
                                cid = mid
                            except ValueError:
                                mid, cid = '', ''

                        if mid == '' or cid == '':
                            continue

                        print(f"正在爬取话题『{topic_name}』的三级评论 (MID: {mid}, CID: {cid}) ...")
                        df_tertiary = get_child_comments(mid, cid)

                        if df_tertiary.empty:
                            print(f"警告：三级评论为空 (MID: {mid}, CID: {cid})，跳过创建文件。")
                        else:
                            # ---- 若发现有不为空的三级评论，需要先创建文件夹 ----
                            if not created_sub3_folder:
                                os.makedirs(sub3_folder_for_this_sub2, exist_ok=True)
                                created_sub3_folder = True

                            # 写入 CSV
                            output_filename = f"{topic_name}_{mid}_{cid}_tertiary.csv"
                            output_path = os.path.join(sub3_folder_for_this_sub2, output_filename)
                            df_tertiary.to_csv(output_path, encoding='utf_8_sig', index=False)

                    # 如果遍历完所有行都没有创建文件夹，说明没有任何三级评论
                    if created_sub3_folder:
                        print(f"二级文件『{sub2_file}』生成了 三级评论文件夹：{sub2_file_name}_三级")
                    else:
                        print(f"二级文件『{sub2_file}』下没有任何有效三级评论，未创建文件夹。")

                print(f"话题『{topic_name}』的三级评论全部爬取完毕。\n")

        print("所有指定的三级评论爬取任务已执行完毕。")





if __name__ == '__main__':
    main()
