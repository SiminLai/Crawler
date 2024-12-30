import pandas as pd

def clean_data(file_path, output_file=None):
    """
    清洗数据并保存到新的 CSV 文件。
    """
    # 读取数据
    data = pd.read_csv(file_path)

    # 调试代码：打印列名和前几行数据
    print("列名：", data.columns)
    print("前几行数据：", data.head())

    # 检查是否包含必需列
    required_columns = ['word_scheme', 'onboard_time']  # 不再强制要求 'raw_hot'
    missing_columns = [col for col in required_columns if col not in data.columns]
    if missing_columns:
        print(f"缺少列: {missing_columns}")
        raise KeyError(f"缺少列: {missing_columns}")

    # 处理数据，保留必需列
    data_filtered = data[required_columns]

    # 如果存在 'raw_hot' 列，则保留；否则填充默认值
    if 'raw_hot' in data.columns:
        data_filtered['raw_hot'] = data['raw_hot']
    else:
        data_filtered['raw_hot'] = 0  # 设置默认值 0

    # 删除空值和异常行
    data_filtered = data_filtered.dropna(subset=['onboard_time'])
    data_filtered['onboard_time'] = pd.to_datetime(data_filtered['onboard_time'], errors='coerce')

    # 按时间排序
    data_filtered = data_filtered.sort_values(by='onboard_time')

    # 保存到新文件
    if output_file:
        data_filtered.to_csv(output_file, index=False)

    return data_filtered


# 示例调用
# clean_data('热搜榜test2.csv', 'cleaned_data2.csv')
