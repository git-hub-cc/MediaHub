import os
import re
import json
import collections
import shutil # 导入 shutil 模块用于文件复制

# --- 自然排序键函数 ---
def natural_sort_key(s):
    """
    为包含数字的字符串返回一个自然排序的键。
    例如，"file10.txt" 会排在 "file2.txt" 之后。
    在比较非数字部分时，会转换为小写以实现不区分大小写的排序。
    """
    def convert(text):
        return int(text) if text.isdigit() else text.lower()
    # 使用正则表达式将字符串分割成数字和非数字部分
    # `([0-9]+)` 捕获一个或多个数字，re.split 会在捕获组处分割，并保留捕获组
    # 例如："Day10.nfo" -> ["Day", "10", ".nfo"]
    return [convert(c) for c in re.split('([0-9]+)', s)]

def scan_media_library_and_index(start_directory):
    """
    扫描指定目录及其子目录，识别电影和剧集，并建立分类文件索引。
    在找到5个电影和5部剧集后停止。

    Args:
        start_directory (str): 开始扫描的根目录。

    Returns:
        dict: 包含电影和剧集索引的字典。
    """

    # 存储最终的索引数据
    media_index_data = {
        "movies": [],
        "tv_shows": []
    }

    # 用于存储已经识别的媒体项目的绝对根路径，避免重复处理其子目录
    processed_media_roots = set()

    MAX_MOVIES = 50000
    MAX_TV_SHOWS = 50000

    # 剧集根目录的常见文件指示器（优先级更高）
    TVSHOW_NFO_NAME = 'tvshow.nfo'
    # 剧集季目录的正则匹配
    SEASON_DIR_PATTERN = re.compile(r"^season\s*\d+$", re.IGNORECASE)

    # 电影根目录的常见文件指示器
    MOVIE_NFO_NAME = 'movie.nfo'
    # 电影根目录可能有的图片文件，结合nfo文件进行判断
    MOVIE_IMAGE_INDICATORS = {'poster.jpg', 'fanart.jpg', 'cover.jpg', 'folder.jpg', 'movie.jpg'}

    if not os.path.isdir(start_directory):
        print(f"错误: '{start_directory}' 不是一个有效的目录。")
        return media_index_data

    # 将起始目录标准化为绝对路径，用于后续的相对路径计算和根目录判断
    start_directory_abs = os.path.abspath(start_directory)

    print(f"开始扫描目录: {start_directory_abs}")
    print("-" * 30)

    # os.walk 会返回 (当前目录路径, 子目录列表, 文件列表)
    for dirpath, dirnames, filenames in os.walk(start_directory_abs):
        # 检查是否已达到查找限制
        if len(media_index_data["movies"]) >= MAX_MOVIES and \
           len(media_index_data["tv_shows"]) >= MAX_TV_SHOWS:
            print("\n已达到查找限制，停止扫描。")
            break

        # 检查当前目录是否已包含在已识别的媒体项目根路径下（即是某个已识别项目的子目录）
        is_child_of_processed_root = False
        for root_path in processed_media_roots:
            # os.path.normpath 用于处理不同操作系统的路径分隔符问题
            if os.path.normpath(dirpath).startswith(os.path.normpath(root_path) + os.sep):
                is_child_of_processed_root = True
                break
        if is_child_of_processed_root:
            continue # 跳过已处理媒体项目内部的子目录

        # 将文件名转换为小写集合以便进行不区分大小写的比较
        filenames_lower = {f.lower() for f in filenames}

        # --- 识别当前目录是电影还是剧集根目录 ---
        current_media_type = None

        # 尝试识别为剧集
        # 1. 检查 tvshow.nfo
        if TVSHOW_NFO_NAME.lower() in filenames_lower:
            current_media_type = "tv_show"
        # 2. 检查是否存在 'Season X' 子目录 (如果还没有被 tvshow.nfo 识别为剧集)
        if current_media_type is None:
            for d in dirnames:
                if SEASON_DIR_PATTERN.match(d):
                    current_media_type = "tv_show"
                    break

        # 尝试识别为电影（仅在未识别为剧集的情况下）
        if current_media_type is None:
            # 1. 检查 movie.nfo
            if MOVIE_NFO_NAME.lower() in filenames_lower:
                current_media_type = "movie"
            else:
                # 2. 检查 *.nfo 结合常见电影图片文件
                found_nfo_in_root = False
                for f in filenames_lower:
                    # 排除 tvshow.nfo 和 season.nfo，只考虑电影可能的主NFO
                    if f.endswith('.nfo') and f != TVSHOW_NFO_NAME.lower() and f != 'season.nfo':
                        found_nfo_in_root = True
                        break

                if found_nfo_in_root:
                    for img_indicator in MOVIE_IMAGE_INDICATORS:
                        if img_indicator in filenames_lower:
                            current_media_type = "movie"
                            break

        # 如果当前目录被识别为媒体项目，并且未达到该类型的上限
        if current_media_type:
            if (current_media_type == "movie" and len(media_index_data["movies"]) >= MAX_MOVIES) or \
               (current_media_type == "tv_show" and len(media_index_data["tv_shows"]) >= MAX_TV_SHOWS):
                continue # 达到该类型的上限，跳过

            media_root_path_abs = dirpath # 绝对路径
            processed_media_roots.add(media_root_path_abs) # 将此路径标记为已处理的媒体根

            # 获取相对于 start_directory 的相对路径
            media_root_path_relative = os.path.relpath(media_root_path_abs, start=start_directory_abs)
            # 转换路径分隔符，以匹配用户示例中的Windows风格
            media_root_path_relative = media_root_path_relative.replace(os.sep, '\\')

            # 用于存储各类文件的原始列表
            categorized_files_raw = collections.defaultdict(list)
            # 专门用于存储剧集内部按目录分组的NFO文件和STRM文件
            tv_episode_nfo_grouped = collections.defaultdict(list)
            tv_episode_strm_grouped = collections.defaultdict(list)

            # 遍历当前媒体项目目录及其所有子目录，收集文件信息
            for sub_dirpath, _, sub_filenames in os.walk(media_root_path_abs):
                for sub_filename in sub_filenames:
                    full_file_path = os.path.join(sub_dirpath, sub_filename)
                    # 文件相对于媒体项目根目录的路径
                    relative_file_path_in_media_item = os.path.relpath(full_file_path, start=media_root_path_abs)
                    # 统一路径分隔符为 Windows 风格
                    relative_file_path_in_media_item = relative_file_path_in_media_item.replace(os.sep, '\\')

                    filename_lower = sub_filename.lower()

                    # 获取父目录名用于分组。如果文件直接在媒体项目根目录，则使用媒体项目根目录的名称作为分组键。
                    parent_dir_relative_to_media_item_root = os.path.dirname(relative_file_path_in_media_item)
                    dir_group_name = os.path.basename(parent_dir_relative_to_media_item_root)
                    if not dir_group_name and media_root_path_relative == ".": # 如果文件在扫描的根目录，且此目录是媒体根
                        dir_group_name = os.path.basename(os.path.abspath(media_root_path_abs))
                    elif not dir_group_name: # 如果文件在子媒体根目录，直接用其名称作为分组键
                         dir_group_name = os.path.basename(media_root_path_abs)


                    # --- NFO 文件处理 ---
                    if filename_lower == TVSHOW_NFO_NAME.lower():
                        categorized_files_raw['tvshow_nfo'].append(relative_file_path_in_media_item)
                    elif filename_lower == MOVIE_NFO_NAME.lower():
                        categorized_files_raw['movie_nfo'].append(relative_file_path_in_media_item)
                    elif filename_lower == 'season.nfo':
                        categorized_files_raw['season_nfo'].append(relative_file_path_in_media_item)
                    elif filename_lower.endswith('.nfo'): # 处理其他所有 .nfo 文件
                        if current_media_type == "tv_show":
                            tv_episode_nfo_grouped[dir_group_name].append(relative_file_path_in_media_item)
                        else: # 对于电影，非 movie.nfo 的其他NFO文件
                            categorized_files_raw['nfo'].append(relative_file_path_in_media_item)

                    # --- STRM 文件处理 ---
                    elif filename_lower.endswith('.strm'):
                        if current_media_type == "tv_show":
                            tv_episode_strm_grouped[dir_group_name].append(relative_file_path_in_media_item)
                        else: # 对于电影，STRM 文件也可能存在，不做特殊分组
                            categorized_files_raw['strm'].append(relative_file_path_in_media_item)

                    # --- 图像文件处理 (统一归类) ---
                    elif filename_lower in {'folder.jpg', 'cover.jpg', 'movie.jpg', 'poster.jpg'}:
                        categorized_files_raw['poster_image'].append(relative_file_path_in_media_item)
                    elif filename_lower in {'banner.jpg', 'fanart.jpg'}:
                        categorized_files_raw['fanart_image'].append(relative_file_path_in_media_item)
                    # 特定季的图像
                    elif re.match(r"season\d+-banner\.jpg", filename_lower):
                        categorized_files_raw['season_banner_images'].append(relative_file_path_in_media_item)
                    elif re.match(r"season\d+-poster\.jpg", filename_lower):
                        categorized_files_raw['season_poster_images'].append(relative_file_path_in_media_item)

                    # --- 其他已知文件类型处理 ---
                    elif filename_lower.endswith('.ass'):
                        categorized_files_raw['ass'].append(relative_file_path_in_media_item)
                    elif filename_lower.endswith('-mediainfo.json'):
                        categorized_files_raw['mediainfo_json'].append(relative_file_path_in_media_item)
                    else:
                        # 对于不符合任何已知模式的文件，归入 'other_files'
                        categorized_files_raw['other_files'].append(relative_file_path_in_media_item)

            # --- 构建最终的 'files' 字典 ---
            final_files_data = {}

            # 将原始列表转换为单字符串或列表
            for key, value_list in categorized_files_raw.items():
                if value_list: # 仅当列表非空时才添加
                    if len(value_list) == 1:
                        final_files_data[key] = value_list[0]
                    else:
                        final_files_data[key] = value_list

            # 添加特别分组的剧集NFO (如果有的话)
            if current_media_type == "tv_show" and tv_episode_nfo_grouped:
                grouped_nfo_output_list = []
                for dir_name, nfo_paths in tv_episode_nfo_grouped.items():
                    # 在这里应用自然排序
                    grouped_nfo_output_list.append({dir_name: sorted(nfo_paths, key=natural_sort_key)})
                final_files_data['nfo'] = grouped_nfo_output_list

            # 添加特别分组的剧集STRM (如果有的话)
            if current_media_type == "tv_show" and tv_episode_strm_grouped:
                grouped_strm_output_list = []
                for dir_name, strm_paths in tv_episode_strm_grouped.items():
                    # 在这里应用自然排序
                    grouped_strm_output_list.append({dir_name: sorted(strm_paths, key=natural_sort_key)})
                final_files_data['strm'] = grouped_strm_output_list

            # 构建媒体条目
            media_entry = {
                "path": media_root_path_relative,
                "files": [final_files_data] # 'files' 键是一个包含一个字典的列表
            }

            if current_media_type == "movie":
                media_index_data["movies"].append(media_entry)
                print(f"  [电影 Found]: {media_root_path_relative}")
            elif current_media_type == "tv_show":
                media_index_data["tv_shows"].append(media_entry)
                print(f"  [剧集 Found]: {media_root_path_relative}")

    print("-" * 30)
    print("\n扫描完成。")

    return media_index_data

def copy_indexed_files(media_data, original_scan_root, copy_destination_dir_name="copyFile"):
    """
    根据索引数据将文件复制到指定的目标目录。

    Args:
        media_data (dict): 包含电影和剧集索引的字典。
        original_scan_root (str): 原始扫描的根目录（绝对路径），用于构建源文件路径。
        copy_destination_dir_name (str): 目标复制目录的名称，将在脚本目录下创建。
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    copy_root_dir = os.path.join(script_dir, copy_destination_dir_name)

    print(f"\n开始复制文件到: {copy_root_dir}")
    print("-" * 30)

    copied_count = 0

    # 确保目标复制目录存在
    os.makedirs(copy_root_dir, exist_ok=True)

    # 遍历电影和剧集
    for media_type_key in ["movies", "tv_shows"]:
        for media_item in media_data[media_type_key]:
            # 获取媒体项目在原始扫描目录下的相对路径
            media_item_relative_path_from_scan_root = media_item["path"]
            # 构建媒体项目在原始扫描目录下的绝对路径
            original_media_item_abs_path = os.path.join(original_scan_root, media_item_relative_path_from_scan_root)

            # 获取文件信息（是files列表中的第一个字典）
            if not media_item["files"]: # 检查 files 列表是否为空
                continue

            file_category_dict = media_item["files"][0]

            for category_key, file_paths_or_grouped_list in file_category_dict.items():
                if category_key in ['nfo', 'strm'] and media_type_key == 'tv_shows' and isinstance(file_paths_or_grouped_list, list) and file_paths_or_grouped_list and isinstance(file_paths_or_grouped_list[0], dict):
                    # 处理按目录分组的NFO或STRM文件 (TV Shows 特有)
                    for group_dict in file_paths_or_grouped_list:
                        for group_name, files_in_group_list in group_dict.items():
                            for file_relative_path_in_item in files_in_group_list:
                                source_abs_file_path = os.path.join(original_media_item_abs_path, file_relative_path_in_item)
                                # 目标文件的相对路径（相对于 copy_root_dir）
                                destination_relative_path = os.path.join(media_item_relative_path_from_scan_root, file_relative_path_in_item)
                                destination_abs_file_path = os.path.join(copy_root_dir, destination_relative_path)

                                try:
                                    os.makedirs(os.path.dirname(destination_abs_file_path), exist_ok=True)
                                    shutil.copy2(source_abs_file_path, destination_abs_file_path)
                                    copied_count += 1
                                    # print(f"  复制: {file_relative_path_in_item} -> {destination_abs_file_path}") # 复制成功日志可以根据需要取消注释
                                except FileNotFoundError:
                                    print(f"  警告: 源文件不存在，无法复制: {source_abs_file_path}")
                                except Exception as e:
                                    print(f"  错误: 复制文件失败 {source_abs_file_path} -> {destination_abs_file_path}: {e}")
                else:
                    # 处理其他所有扁平的文件列表（包括电影的nfo/strm，或所有图像文件等）
                    files_to_copy = []
                    if isinstance(file_paths_or_grouped_list, str):
                        files_to_copy.append(file_paths_or_grouped_list)
                    elif isinstance(file_paths_or_grouped_list, list):
                        files_to_copy.extend(file_paths_or_grouped_list)

                    for file_relative_path_in_item in files_to_copy:
                        source_abs_file_path = os.path.join(original_media_item_abs_path, file_relative_path_in_item)
                        # 目标文件的相对路径（相对于 copy_root_dir）
                        destination_relative_path = os.path.join(media_item_relative_path_from_scan_root, file_relative_path_in_item)
                        destination_abs_file_path = os.path.join(copy_root_dir, destination_relative_path)

                        try:
                            os.makedirs(os.path.dirname(destination_abs_file_path), exist_ok=True)
                            shutil.copy2(source_abs_file_path, destination_abs_file_path)
                            copied_count += 1
                            # print(f"  复制: {file_relative_path_in_item} -> {destination_abs_file_path}") # 复制成功日志可以根据需要取消注释
                        except FileNotFoundError:
                            print(f"  警告: 源文件不存在，无法复制: {source_abs_file_path}")
                        except Exception as e:
                            print(f"  错误: 复制文件失败 {source_abs_file_path} -> {destination_abs_file_path}: {e}")

    print("-" * 30)
    print(f"复制完成。总共复制了 {copied_count} 个文件。")

# --- 使用示例 ---
if __name__ == "__main__":
    # 请将此路径替换为你的媒体库根目录
    # start_path = r"C:\media\all"
    # 或者留空让用户输入
    start_path = input("请输入要扫描的根目录路径（例如 C:\\media\\all）：").strip()

    if not start_path:
        print("未输入路径，程序退出。")
    else:
        # 验证路径是否存在
        if not os.path.exists(start_path):
            print(f"错误: 指定的路径 '{start_path}' 不存在。")
        else:
            media_data = scan_media_library_and_index(start_path)

            output_filename = "media_index.json"
            script_dir = os.path.dirname(os.path.abspath(__file__))
            output_full_path = os.path.join(script_dir, output_filename)

            try:
                with open(output_full_path, 'w', encoding='utf-8') as f:
                    json.dump(media_data, f, ensure_ascii=False, indent=4)
                print(f"\n索引已保存到: {output_full_path}")
            except IOError as e:
                print(f"错误: 无法写入文件 {output_full_path}: {e}")

            # 打印摘要
            print(f"\n--- 扫描结果摘要 ---")
            print(f"找到的电影数量: {len(media_data['movies'])}")
            print(f"找到的剧集数量: {len(media_data['tv_shows'])}")

            # --- 修改部分：默认不复制文件，通过用户确认来决定是否复制 ---
            perform_copy_choice = input("\n是否要复制已索引的文件？(y/N): ").strip().lower()
            if perform_copy_choice == 'y':
                print("\n用户选择复制文件。")
                # original_scan_root 必须是扫描时使用的绝对路径，以便正确构建源路径
                copy_indexed_files(media_data, os.path.abspath(start_path), "copyFile")
            else:
                print("\n未选择复制文件，跳过文件复制步骤。")