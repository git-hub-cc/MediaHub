import json
import xml.etree.ElementTree as ET
import os
from collections import deque

# --- Configuration ---
MEDIA_INDEX_FILE = 'media_index.json'
PEOPLE_SUMMARY_FILE = 'people_summary.json'
REPORT_FILE_NAME = 'report_people.txt' # 新增：指定输出文件名为 report_people.txt
# 设置为 True 会在报告文件中包含关于缺失/损坏 NFO 的详细警告
# 设置为 False (默认) 则只报告缺失的人员信息和高级别错误
VERBOSE_WARNINGS = False
# 假设脚本在根目录下运行，例如 "动漫", "People" 等文件夹所在的位置
# 如果脚本相对于媒体文件路径不同，请调整此基本路径
BASE_MEDIA_PATH = '.'
# --- End Configuration ---

def get_all_nfo_paths(media_data_entry, current_base_path, f_report=None):
    """
    递归收集给定媒体条目的所有 NFO 文件路径。
    处理 tv_shows 中嵌套的结构。
    """
    nfo_paths = []

    # 构造当前媒体项的完整基本路径
    full_item_path = os.path.join(current_base_path, media_data_entry['path'])

    files_info = media_data_entry.get('files', [])
    if not files_info:
        return nfo_paths

    for file_entry in files_info:
        # 检查所有可能的 NFO 键
        potential_nfo_keys = ['tvshow_nfo', 'season_nfo', 'nfo', 'movie_nfo'] # Added movie_nfo for completeness

        for key in potential_nfo_keys:
            if key in file_entry:
                nfo_data = file_entry[key]
                if isinstance(nfo_data, str):
                    full_nfo_path = os.path.join(full_item_path, nfo_data)
                    # 只有当文件存在时才添加，并根据 VERBOSE_WARNINGS 记录警告
                    if os.path.exists(full_nfo_path):
                        nfo_paths.append(full_nfo_path)
                    elif VERBOSE_WARNINGS and f_report:
                        print(f"Warning: NFO file not found: {full_nfo_path}", file=f_report)
                elif isinstance(nfo_data, list):
                    for item_or_dict in nfo_data:
                        if isinstance(item_or_dict, dict):
                            for folder_name, nfo_list in item_or_dict.items():
                                for nfo_rel_path in nfo_list:
                                    full_nfo_path = os.path.join(full_item_path, nfo_rel_path)
                                    if os.path.exists(full_nfo_path):
                                        nfo_paths.append(full_nfo_path)
                                    elif VERBOSE_WARNINGS and f_report:
                                        print(f"Warning: NFO file not found: {full_nfo_path}", file=f_report)
                        elif isinstance(item_or_dict, str):
                            full_nfo_path = os.path.join(full_item_path, item_or_dict)
                            if os.path.exists(full_nfo_path):
                                nfo_paths.append(full_nfo_path)
                            elif VERBOSE_WARNINGS and f_report:
                                print(f"Warning: NFO file not found: {full_nfo_path}", file=f_report)

    return nfo_paths

def parse_nfo_for_actors(nfo_file_path, f_report=None):
    """
    解析 NFO XML 文件并提取所有演员姓名。
    根据 VERBOSE_WARNINGS 决定是否将错误记录到报告文件。
    """
    actors = set()

    try:
        with open(nfo_file_path, 'rb') as f:
            raw_xml = f.read()
            try:
                tree = ET.fromstring(raw_xml.decode('utf-8'))
            except UnicodeDecodeError:
                tree = ET.fromstring(raw_xml.decode('latin-1')) # 尝试常见的备用编码
            except ET.ParseError as e:
                if VERBOSE_WARNINGS and f_report:
                    print(f"Warning: XML parsing failed for {nfo_file_path}. Trying with 'ignore'. Error: {e}", file=f_report)
                tree = ET.fromstring(raw_xml.decode('utf-8', errors='ignore')) # 忽略问题字符

        for actor_elem in tree.findall('actor'):
            name_elem = actor_elem.find('name')
            if name_elem is not None and name_elem.text:
                actor_name = name_elem.text.strip()
                if actor_name: # 确保姓名不是纯空白
                    actors.add(actor_name)
    except ET.ParseError as e:
        if VERBOSE_WARNINGS and f_report:
            print(f"Error parsing XML for {nfo_file_path}: {e}", file=f_report)
    except Exception as e:
        if VERBOSE_WARNINGS and f_report:
            print(f"An unexpected error occurred reading/parsing {nfo_file_path}: {e}", file=f_report)
    return actors

def main():
    # 在程序开始时打开报告文件
    with open(REPORT_FILE_NAME, 'w', encoding='utf-8') as f_report:
        # 1. 加载数据 - 这里的错误是关键的，直接打印到控制台
        try:
            with open(MEDIA_INDEX_FILE, 'r', encoding='utf-8') as f:
                media_index_data = json.load(f)
        except FileNotFoundError:
            print(f"Error: {MEDIA_INDEX_FILE} not found. Please ensure it's in the correct directory.")
            print(f"Error: {MEDIA_INDEX_FILE} not found.", file=f_report)
            return
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON from {MEDIA_INDEX_FILE}: {e}")
            print(f"Error decoding JSON from {MEDIA_INDEX_FILE}: {e}", file=f_report)
            return

        try:
            with open(PEOPLE_SUMMARY_FILE, 'r', encoding='utf-8') as f:
                people_summary_data = json.load(f)
        except FileNotFoundError:
            print(f"Error: {PEOPLE_SUMMARY_FILE} not found. Please ensure it's in the correct directory.")
            print(f"Error: {PEOPLE_SUMMARY_FILE} not found.", file=f_report)
            return
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON from {PEOPLE_SUMMARY_FILE}: {e}")
            print(f"Error decoding JSON from {PEOPLE_SUMMARY_FILE}: {e}", file=f_report)
            return

        # 2. 获取 existing_people_in_summary 中的现有人员
        existing_people_in_summary = set(people_summary_data.keys())

        # 3. 从 media_index 收集所有 NFO 路径
        all_nfo_paths_to_process = set() # 使用集合避免重复处理同一个 NFO

        for media_type in ['movies', 'tv_shows']:
            for entry in media_index_data.get(media_type, []):
                # 将 f_report 传递给辅助函数，以便在其中进行日志记录
                paths = get_all_nfo_paths(entry, BASE_MEDIA_PATH, f_report)
                all_nfo_paths_to_process.update(paths)

        # 4. 解析所有收集到的 NFO 并提取演员姓名
        all_actors_from_nfo = set()

        # 打印进度到控制台，并向报告文件写入初始信息
        print(f"Scanning {len(all_nfo_paths_to_process)} NFO files for people...")
        print(f"Scanning {len(all_nfo_paths_to_process)} NFO files for people...", file=f_report)

        for i, nfo_path in enumerate(all_nfo_paths_to_process):
            # 打印进度到控制台（使用 \r 进行原地更新）
            if (i + 1) % 50 == 0 or (i + 1) == len(all_nfo_paths_to_process): # 减少更新频率
                 print(f"Processed {i+1}/{len(all_nfo_paths_to_process)} NFOs.", end='\r')

            # 将 f_report 传递给辅助函数，以便在其中进行日志记录
            actors_in_nfo = parse_nfo_for_actors(nfo_path, f_report)
            all_actors_from_nfo.update(actors_in_nfo)

        # 清除控制台上的进度行
        print("\nNFO scanning complete.")
        print("NFO scanning complete.", file=f_report) # 也写入文件

        # 5. 查找缺失人员
        missing_people = sorted(list(all_actors_from_nfo - existing_people_in_summary))

        # 6. 将结果报告到文件和控制台
        if missing_people:
            print("\n--- Missing People Report ---", file=f_report)
            print("The following people were found in NFO files but are NOT in people_summary.json:", file=f_report)
            for person in missing_people:
                print(f"- {person}", file=f_report)
            print(f"\nTotal missing people: {len(missing_people)}", file=f_report)

            # 同时向控制台打印摘要
            print(f"\nFound {len(missing_people)} missing people. See '{REPORT_FILE_NAME}' for details.")
        else:
            print("\nGood news! All people mentioned in NFO files are present in people_summary.json.", file=f_report)
            print("\nGood news! All people mentioned in NFO files are present in people_summary.json.")


if __name__ == "__main__":
    main()