import os
import csv

# 只要这两列：词条名字 (word) 和 url
OUTPUT_FIELDNAMES = ["word", "url"]


def ensure_master_exists(master_file):
    """
    如果 master_file 不存在，则创建并写入表头（只有 word, url）。
    """
    if not os.path.exists(master_file):
        with open(master_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDNAMES)
            writer.writeheader()


def load_master_into_set(master_file):
    """
    读取 master_file（跳过表头），只读 word, url 两列，
    并将其作为 tuple(word, url) 加载到一个 set 中返回。
    """
    seen = set()
    if os.path.exists(master_file) and os.path.getsize(master_file) > 0:
        with open(master_file, 'r', encoding='utf-8', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                word_val = row.get("word", "").strip()
                url_val = row.get("url", "").strip()
                seen.add((word_val, url_val))
    return seen


def merge_deduplicate(
    input_files,
    master_file='master.csv'
):
    """
    1) 若 master.csv 不存在，就创建，含表头 (word, url)。
    2) 把 master.csv 的内容读进一个 set (master_seen)。
    3) 对于每个 input_file：
       - 打开并读表头，找出 word, url 两列的索引位置
       - 输出文件: {原名}_dedup.csv (也只写 word, url 两列)
       - 对每行，只要 (word, url) 不在 master_seen，就写入并加入 master_seen
    最终所有数据汇总到 master.csv，也只保留 word, url 两列。
    """
    # 确保 master.csv 存在且含有 (word, url) 表头
    ensure_master_exists(master_file)

    # 把 master_file 中已有的 (word, url) 读到 set
    master_seen = load_master_into_set(master_file)

    # 逐个处理 input_files
    for in_file in input_files:
        if not os.path.isfile(in_file):
            print(f"警告：找不到文件 {in_file}，跳过。")
            continue
        if os.path.getsize(in_file) == 0:
            print(f"警告：文件 {in_file} 为空，跳过。")
            continue

        # 输出文件名称 (直接输出到当前目录)
        base_name = os.path.basename(in_file)
        name_only, ext = os.path.splitext(base_name)
        out_file_name = f"{name_only}_dedup{ext}"  # 输出同级目录
        output_file = os.path.join(os.getcwd(), out_file_name)  # 当前目录

        with open(in_file, 'r', encoding='utf-8', newline='') as f_in, \
             open(output_file, 'w', encoding='utf-8', newline='') as f_out, \
             open(master_file, 'a', encoding='utf-8', newline='') as f_master:

            # 准备阅读器/写入器
            reader_in = csv.reader(f_in)
            writer_out = csv.DictWriter(f_out, fieldnames=OUTPUT_FIELDNAMES)
            writer_master = csv.DictWriter(f_master, fieldnames=OUTPUT_FIELDNAMES)

            # 先读输入文件的表头
            input_header = next(reader_in, None)
            if not input_header:
                print(f"警告：文件 {in_file} 没有表头或无内容，跳过。")
                continue

            # 在输入文件的表头里找出 "word" 和 "url" 的列索引
            try:
                idx_word = input_header.index("word")
                idx_url = input_header.index("url")
            except ValueError:
                print(f"警告：{in_file} 中找不到 'word' 或 'url' 列，跳过去重。")
                continue

            # 写 output_file 表头
            writer_out.writeheader()

            # 逐行处理
            for row in reader_in:
                if len(row) < max(idx_word, idx_url) + 1:
                    # 如果该行列数不足，无效
                    continue

                word_val = row[idx_word].strip()
                url_val = row[idx_url].strip()

                # 如果 (word, url) 尚未出现，就写入
                if (word_val, url_val) not in master_seen:
                    # 写入到 _dedup.csv
                    writer_out.writerow({"word": word_val, "url": url_val})
                    # 也写到 master.csv
                    writer_master.writerow({"word": word_val, "url": url_val})
                    # 加入到 set
                    master_seen.add((word_val, url_val))

        print(f"文件『{in_file}』处理完成，去重后输出到：{output_file}")

    print("全部文件处理完毕。")
    print(f"去重汇总文件：{master_file} (只包含 word/url 两列)")
