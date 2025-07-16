import os
import sys
from collections import Counter # 导入 Counter 类

def find_and_count_and_filter_jpg_filenames(start_directory, min_count=3):
    """
    查找指定目录及其子目录下所有JPG/JPEG文件的文件名，统计其出现次数，
    并返回出现次数大于 min_count 的文件名及其计数。

    Args:
        start_directory (str): 开始搜索的目录路径。
        min_count (int): 文件的最小出现次数，只输出出现次数大于此值的文件名。

    Returns:
        list: 包含元组 (filename, count) 的列表，按 count 降序排列，
              如果 count 相同则按 filename 字母升序排列。
              如果指定目录无效或未找到符合条件的文件，则返回空列表。
    """
    if not os.path.isdir(start_directory):
        print(f"错误：'{start_directory}' 不是一个有效的目录。")
        return []

    all_jpg_filenames = []
    jpg_extensions = ('.jpg', '.jpeg')

    print(f"正在扫描 '{start_directory}' 及其子目录中的JPG/JPEG文件并统计...")

    for root, _, files in os.walk(start_directory):
        for file_name in files:
            if file_name.lower().endswith(jpg_extensions):
                all_jpg_filenames.append(file_name.lower())

    filename_counts = Counter(all_jpg_filenames)

    # 过滤出出现次数大于 min_count 的文件名及其计数
    filtered_items = []
    for filename, count in filename_counts.items():
        if count > min_count:
            filtered_items.append((filename, count)) # 存储为 (文件名, 计数) 的元组

    # 对过滤后的结果进行排序：
    # 1. 首先按计数（count）降序排列 (x[1] 表示元组的第二个元素即计数，-x[1] 表示降序)
    # 2. 如果计数相同，则按文件名（filename）升序排列 (x[0] 表示元组的第一个元素即文件名)
    return sorted(filtered_items, key=lambda x: (-x[1], x[0]))

if __name__ == "__main__":
    if len(sys.argv) > 1:
        target_directory = sys.argv[1]
    else:
        target_directory = '.' # 当前目录

    MIN_OCCURRENCES = 3 # 设定最小计数为 3 (即大于3张，所以是 > 3)

    # 调用函数查找和过滤文件名及数量
    found_filtered_items = find_and_count_and_filter_jpg_filenames(target_directory, MIN_OCCURRENCES)

    if found_filtered_items:
        print(f"\n找到以下 JPG/JPEG 文件名及其数量 (出现次数大于 {MIN_OCCURRENCES} 次，按数量降序排列)：")
        print("-" * 50)
        for filename, count in found_filtered_items:
            print(f"文件名: {filename:<30} 数量: {count}") # 使用f-string格式化输出，文件名左对齐
        print("-" * 50)
    else:
        if os.path.isdir(target_directory):
            print(f"\n在 '{target_directory}' 中未找到出现次数大于 {MIN_OCCURRENCES} 次的JPG/JPEG文件。")