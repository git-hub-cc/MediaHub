import json
import os

# --- 配置 ---
MOVIE_SUMMARY_FILE = 'movie_summary.json'
STUDIOS_SUMMARY_FILE = 'studios_summary.json'
OUTPUT_FILE = 'missing_studios.md'

def check_files_exist():
    """检查所需文件是否存在"""
    required_files = [MOVIE_SUMMARY_FILE, STUDIOS_SUMMARY_FILE]
    for filename in required_files:
        if not os.path.exists(filename):
            print(f"错误: 找不到文件 '{filename}'。请确保它在当前目录中。")
            return False
    return True

def load_json_data(filepath):
    """从文件加载 JSON 数据，并进行错误处理"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"错误: 解析 JSON 文件 '{filepath}' 失败: {e}")
        return None
    except FileNotFoundError:
        # This case is already handled by check_files_exist, but it's good practice.
        print(f"错误: 文件 '{filepath}' 未找到。")
        return None

def main():
    """主执行函数"""
    print("开始检查缺失的制片厂资源...")

    if not check_files_exist():
        return

    print("正在加载 JSON 数据...")
    movies_data = load_json_data(MOVIE_SUMMARY_FILE)
    studios_data = load_json_data(STUDIOS_SUMMARY_FILE)

    if movies_data is None or studios_data is None:
        print("因数据加载失败，脚本已中止。")
        return

    # 步骤 1: 从所有电影的元数据中提取所有使用到的制片厂名称
    print("步骤 1/3: 提取所有电影中引用的制片厂...")
    studios_in_use = set()
    if not isinstance(movies_data, list):
        print(f"警告: '{MOVIE_SUMMARY_FILE}' 的顶层内容不是一个列表。")
    else:
        for movie in movies_data:
            # 使用 .get() 安全地访问嵌套的字典，避免因缺少键而导致的错误
            studios_list = movie.get('metadata', {}).get('studios', [])
            if studios_list and isinstance(studios_list, list):
                # 使用 set.update() 高效地添加所有制片厂，并自动去重
                studios_in_use.update(studios_list)

    # 移除任何可能的空字符串
    studios_in_use.discard('')
    studios_in_use.discard(None)

    print(f"完成。共找到 {len(studios_in_use)} 个被引用的独立制片厂。")

    # 步骤 2: 获取所有已存在资源的制片厂名称
    print("步骤 2/3: 匹配已有的制片厂资源...")
    available_studios = set(studios_data.keys())
    print(f"完成。共找到 {len(available_studios)} 个已有的制片厂资源。")

    # 步骤 3: 找出差异，即缺失的制片厂
    missing_studios = studios_in_use - available_studios
    missing_sorted = sorted(list(missing_studios))

    print(f"完成。发现 {len(missing_sorted)} 个缺失的制片厂资源。")

    # 步骤 4: 生成报告文件
    print(f"步骤 3/3: 生成报告文件 '{OUTPUT_FILE}'...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write("# 缺失的制片厂资源列表\n\n")
        if not missing_sorted:
            f.write("恭喜！没有发现任何缺失的制片厂资源。\n")
        else:
            f.write(f"总计缺失 {len(missing_sorted)} 个制片厂的资源。\n\n")
            for studio_name in missing_sorted:
                f.write(f"- {studio_name}\n")

    print(f"\n处理完毕！结果已写入 '{OUTPUT_FILE}'。")


if __name__ == "__main__":
    main()