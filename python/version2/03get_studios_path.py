import json
import os
import requests
import xml.etree.ElementTree as ET # 用于解析XML (NFO) 文件
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading # 用于锁，防止多线程写入共享数据时冲突
import re # 用于文件名安全处理

# --- 配置信息 ---
# 请替换为您的TMDb API Key
TMDB_API_KEY = "841f3672326ee6128f45cffbfecedd92"
TMDB_BASE_URL = "https://api.themoviedb.org/3"
# 制片厂Logo通常使用w185或w300大小，这里沿用w185
TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w185" # Changed to themoviedb.org for consistency
MAX_WORKERS = 20 # 线程池最大工作线程数，用于并发请求TMDb API

# 图片下载目录，相对路径
IMAGE_DOWNLOAD_DIR = "studios" # 修改为 studios 文件夹

# 全局字典，用于存储已处理的制片厂及其Logo URL，防止重复请求和重复存储
# 使用线程锁来确保多线程写入时的安全
processed_studios_logos = {}
processed_studios_lock = threading.Lock()

# --- 辅助函数：文件名安全处理 ---
def sanitize_filename(filename: str) -> str:
    """
    清洗文件名，移除或替换在文件系统中不安全的字符。
    """
    # 替换非法字符为下划线
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # 移除或替换 Windows 保留名称（COM1, LPT1等，虽然这里不常见，但可以避免）
    return sanitized

# --- 图片下载函数 ---
def download_image(image_url: str, entity_name: str, download_dir: str) -> str | None:
    """
    下载图片到本地指定目录，并返回其相对路径。
    Args:
        image_url: TMDb 图片的完整 URL。
        entity_name: 实体名称（制片厂名称），用于构建本地文件名。
        download_dir: 下载图片的目标目录。
    Returns:
        下载图片的本地相对路径，如果下载失败则返回 None。
    """
    if not image_url:
        return None

    # 从URL中提取原始文件名（通常是TMDb的hash值 + .png/.jpg）
    original_filename_part = image_url.split('/')[-1] # 例如：/path/to/logo_hash.png -> logo_hash.png

    # 检查原始文件名部分是否包含扩展名，如果TMDb的logo_path是 "/asdfghj.png" 这样的形式，那么直接用它。
    # 如果是其他形式，如只有ID，需要补充一个默认扩展名。
    if '.' not in original_filename_part:
        # 如果没有扩展名，假设为 .png (Logo常见格式)
        ext = ".png"
        filename_hash = original_filename_part # TMDb logo_path有时就是hash值
    else:
        # 提取文件名（不含扩展名）和扩展名
        filename_hash, ext = os.path.splitext(original_filename_part)

    # 结合实体名和TMDb的hash部分，提高文件名可读性和唯一性
    name_part = sanitize_filename(entity_name)
    local_filename = f"{name_part}_{filename_hash}{ext}"
    local_file_path = os.path.join(download_dir, local_filename)

    # 确保下载目录存在
    os.makedirs(download_dir, exist_ok=True)

    # 检查文件是否已存在，如果存在则跳过下载
    if os.path.exists(local_file_path):
        # print(f"  图片已存在：'{local_file_path}'，跳过下载。") # 频繁打印可能刷屏
        return local_file_path # 返回已存在文件的相对路径

    try:
        response = requests.get(image_url, stream=True, timeout=10)
        response.raise_for_status() # 检查HTTP请求是否成功

        with open(local_file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        # print(f"  已下载图片：'{local_file_path}'") # 频繁打印可能刷屏
        return local_file_path # 返回下载成功的相对路径
    except requests.exceptions.RequestException as e:
        print(f"警告：下载图片 '{image_url}' 失败：{e}")
        # 如果下载失败，尝试删除可能已创建的空文件
        if os.path.exists(local_file_path):
            os.remove(local_file_path)
        return None
    except IOError as e:
        print(f"警告：写入文件 '{local_file_path}' 失败：{e}")
        return None


# --- TMDb API 辅助函数 (针对制片厂) ---
def search_company_on_tmdb(company_name: str, api_key: str) -> str | None:
    """
    通过名称在TMDb上搜索制片厂，并返回其Logo路径。
    Args:
        company_name: 要搜索的制片厂名称。
        api_key: TMDb API Key。
    Returns:
        制片厂Logo的相对路径 (logo_path)，如果找到则返回，否则返回None。
    """
    search_url = f"{TMDB_BASE_URL}/search/company"
    params = {
        "api_key": api_key,
        "query": company_name,
        "language": "zh-CN" # 可以指定语言
    }
    try:
        response = requests.get(search_url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data and data.get("results"):
            # 尝试查找精确匹配的制片厂名称
            for company in data["results"]:
                if company.get("name", "").lower() == company_name.lower():
                    # 如果找到了精确匹配且有logo_path，直接返回
                    if company.get("logo_path"):
                        return company.get("logo_path")
            # 如果没有精确匹配的logo_path，或者没有精确匹配，则返回第一个结果的logo_path（如果存在）
            return data["results"][0].get("logo_path")
        else:
            # print(f"警告：在TMDb上未找到制片厂：'{company_name}'") # 频繁打印可能刷屏，改为内部处理
            return None
    except requests.exceptions.RequestException as e:
        print(f"警告：请求TMDb API时发生错误（搜索制片厂 '{company_name}'）：{e}")
        return None

def fetch_studio_logo(studio_name: str) -> tuple[str, str | None]:
    """
    根据制片厂名称获取其在TMDb上的Logo图片URL，并下载到本地。
    Args:
        studio_name: 制片厂名称。
    Returns:
        (studio_name, downloaded_image_relative_path) 元组。如果获取或下载失败，downloaded_image_relative_path为None。
    """
    # 检查API Key是否已配置
    if not TMDB_API_KEY or TMDB_API_KEY == "YOUR_TMDB_API_KEY":
        print("错误：请在脚本中配置您的TMDb API Key。")
        return studio_name, None

    # 首先尝试从全局缓存中获取（这里存储的是本地下载路径）
    with processed_studios_lock:
        if studio_name in processed_studios_logos:
            return studio_name, processed_studios_logos[studio_name]

    logo_path = search_company_on_tmdb(studio_name, TMDB_API_KEY)

    downloaded_path = None
    if logo_path:
        full_tmdb_image_url = f"{TMDB_IMAGE_BASE_URL}{logo_path}"
        # 调用下载函数，并获取本地相对路径
        downloaded_path = download_image(full_tmdb_image_url, studio_name, IMAGE_DOWNLOAD_DIR)
    else:
        # 只有在确实未能获取到logo时才打印警告，避免成功获取但没有logo的情况也打印警告
        print(f"警告：未能为制片厂 '{studio_name}' 找到可用的Logo路径。")

    # 无论成功与否，将结果（本地路径或None）存入全局缓存
    with processed_studios_lock:
        processed_studios_logos[studio_name] = downloaded_path

    return studio_name, downloaded_path

# --- NFO 文件解析辅助函数 (针对制片厂) ---
def parse_nfo_for_studios(nfo_file_path: str) -> set[str]:
    """
    解析NFO文件，提取制片厂的名称。
    Args:
        nfo_file_path: NFO文件的完整路径。
    Returns:
        一个包含制片厂名称字符串的集合。
    """
    studios_info = set()
    if not os.path.exists(nfo_file_path):
        # print(f"警告：NFO文件不存在：{nfo_file_path}") # Suppress for common cases
        return studios_info

    try:
        # 尝试以UTF-8编码解析，如果失败则尝试GBK或其他常用编码
        tree = ET.parse(nfo_file_path)
        root = tree.getroot()
    except ET.ParseError as e:
        try: # 尝试不同的编码
            with open(nfo_file_path, 'r', encoding='gbk', errors='ignore') as f: # Added errors='ignore'
                content = f.read()
            root = ET.fromstring(content)
            # print(f"信息：NFO文件 '{nfo_file_path}' 以GBK编码解析成功。") # Suppress for common cases
        except Exception as e_gbk:
            print(f"错误：无法解析NFO文件 '{nfo_file_path}'：{e}. 尝试GBK失败：{e_gbk}")
            return studios_info
    except Exception as e:
        print(f"错误：读取NFO文件 '{nfo_file_path}' 时发生未知错误：{e}")
        return studios_info

    # 查找所有 <studio> 标签
    for studio_elem in root.findall('studio'):
        if studio_elem is not None and studio_elem.text:
            studios_info.add(studio_elem.text.strip())
    return studios_info

# --- 主处理函数 ---
def process_media_index(input_file: str = "media_index.json", output_file: str = "studios_summary.json"):
    """
    解析media_index.json文件，提取NFO文件路径，解析NFO中的制片厂信息，
    并通过TMDb API获取制片厂Logo地址并下载，支持多线程。
    Args:
        input_file: 输入的media_index.json文件路径。
        output_file: 输出的studios_summary.json文件路径。
    """
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            media_data = json.load(f)
    except FileNotFoundError:
        print(f"错误：输入文件 '{input_file}' 未找到。")
        return
    except json.JSONDecodeError:
        print(f"错误：无法从文件 '{input_file}' 解析JSON。请检查文件格式。")
        return

    all_nfo_paths = []

    # --- 收集所有电影的NFO路径 ---
    if "movies" in media_data:
        print("--- 正在收集电影NFO路径 ---")
        for movie in media_data["movies"]:
            movie_base_path = movie["path"]
            if not movie.get("files"):
                print(f"警告：电影 '{movie_base_path}' 没有找到 'files' 信息，跳过。")
                continue
            for file_info in movie["files"]:
                if "nfo" in file_info and file_info["nfo"]:
                    nfo_data = file_info["nfo"] # 'nfo' field can be a string or a list
                    if isinstance(nfo_data, list):
                        for nfo_filename in nfo_data:
                            if nfo_filename: # Ensure path is not empty
                                full_nfo_path = os.path.normpath(os.path.join(movie_base_path, nfo_filename))
                                all_nfo_paths.append(full_nfo_path)
                    elif isinstance(nfo_data, str):
                        full_nfo_path = os.path.normpath(os.path.join(movie_base_path, nfo_data))
                        all_nfo_paths.append(full_nfo_path)
                    else:
                        print(f"警告：电影 '{movie_base_path}' 的 'nfo' 字段类型未知 ({type(nfo_data).__name__}), 跳过。")


    # --- 收集所有电视剧的NFO路径 ---
    if "tv_shows" in media_data:
        print("\n--- 正在收集电视剧NFO路径 ---")
        for tv_show in media_data["tv_shows"]:
            tv_show_base_path = tv_show["path"]
            if not tv_show.get("files"):
                print(f"警告：电视剧 '{tv_show_base_path}' 没有找到 'files' 信息，跳过。")
                continue

            # 假设每个tv_show的'files'列表中只有一个字典，包含了所有NFO信息
            files_data = tv_show["files"][0]

            # 添加剧集NFO (tvshow_nfo)
            if "tvshow_nfo" in files_data and files_data["tvshow_nfo"]:
                tvshow_nfo_data = files_data["tvshow_nfo"]
                if isinstance(tvshow_nfo_data, list):
                    for tvshow_nfo_rel_path in tvshow_nfo_data:
                        if tvshow_nfo_rel_path:
                            full_tvshow_nfo_path = os.path.normpath(os.path.join(tv_show_base_path, tvshow_nfo_rel_path))
                            all_nfo_paths.append(full_tvshow_nfo_path)
                elif isinstance(tvshow_nfo_data, str):
                    full_tvshow_nfo_path = os.path.normpath(os.path.join(tv_show_base_path, tvshow_nfo_data))
                    all_nfo_paths.append(full_tvshow_nfo_path)
                else:
                    print(f"警告：电视剧 '{tv_show_base_path}' 的 'tvshow_nfo' 类型未知 ({type(tvshow_nfo_data).__name__})，跳过。")


            # 添加季NFO (season_nfo)
            if "season_nfo" in files_data and files_data["season_nfo"]:
                season_nfo_data = files_data["season_nfo"]
                if isinstance(season_nfo_data, list):
                    for season_nfo_rel_path in season_nfo_data:
                        if season_nfo_rel_path:
                            full_season_nfo_path = os.path.normpath(os.path.join(tv_show_base_path, season_nfo_rel_path))
                            all_nfo_paths.append(full_season_nfo_path)
                elif isinstance(season_nfo_data, str):
                     full_season_nfo_path = os.path.normpath(os.path.join(tv_show_base_path, season_nfo_data))
                     all_nfo_paths.append(full_season_nfo_path)
                else:
                    print(f"警告：电视剧 '{tv_show_base_path}' 的 'season_nfo' 类型未知 ({type(season_nfo_data).__name__})，跳过。")


            # 添加单集NFO (nfo)
            if "nfo" in files_data and files_data["nfo"]:
                episode_nfo_data = files_data["nfo"]
                if isinstance(episode_nfo_data, list):
                    for season_dict in episode_nfo_data:
                        if isinstance(season_dict, dict):
                            for season_folder, episode_nfo_list in season_dict.items():
                                if isinstance(episode_nfo_list, list):
                                    for episode_nfo_rel_path in episode_nfo_list:
                                        if episode_nfo_rel_path:
                                            full_episode_nfo_path = os.path.normpath(os.path.join(tv_show_base_path, episode_nfo_rel_path))
                                            all_nfo_paths.append(full_episode_nfo_path)
                                else:
                                    print(f"警告：电视剧 '{tv_show_base_path}' 中季 '{season_folder}' 的集NFO格式异常（应为列表），跳过。")
                        else:
                            print(f"警告：电视剧 '{tv_show_base_path}' 的 'nfo' 字段中的季字典格式异常（应为字典），跳过。")
                else:
                    print(f"警告：电视剧 '{tv_show_base_path}' 的 'nfo' 字段类型未知（应为列表），跳过。")

    # 对所有NFO路径进行去重
    unique_nfo_paths = sorted(list(set(all_nfo_paths)))

    print("\n--- 收集到的独特NFO文件路径 ---")
    for path in unique_nfo_paths:
        print(path)
    print(f"\n总共找到 {len(unique_nfo_paths)} 个独特的NFO文件路径。\n")

    # --- 从NFO文件中解析所有制片厂信息 ---
    all_studios_to_fetch = set() # 存储待处理的制片厂名称，用于去重
    for nfo_path in unique_nfo_paths:
        studios_in_nfo = parse_nfo_for_studios(nfo_path)
        all_studios_to_fetch.update(studios_in_nfo)

    print(f"从NFO文件中解析到 {len(all_studios_to_fetch)} 个独特的制片厂信息。\n")

    # --- 通过TMDb API获取制片厂Logo地址并下载（多线程）---
    print("--- 正在通过TMDb API获取制片厂Logo地址并下载（多线程）---")

    # 收集需要通过TMDb查找的制片厂任务 (名称)
    tasks = list(all_studios_to_fetch) # 将集合转为列表以便迭代

    # Add a check for empty tasks to avoid ThreadPoolExecutor if nothing to do
    if not tasks:
        print("没有需要获取Logo的制片厂。")
        return

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(fetch_studio_logo, name): name for name in tasks}

        for i, future in enumerate(as_completed(futures)):
            original_studio_name = futures[future]
            studio_name, downloaded_path = future.result()
            progress = f"({i + 1}/{len(tasks)})"

            if downloaded_path:
                print(f"[{progress}] 已处理 '{studio_name}'，Logo路径：{downloaded_path}")
            else:
                print(f"[{progress}] 未能获取或下载 '{studio_name}' 的Logo。")

    # 最终的 `processed_studios_logos` 字典包含了所有成功获取和下载的制片厂Logo信息（本地相对路径）
    # 将结果写入studios_summary.json文件
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(processed_studios_logos, f, indent=4, ensure_ascii=False)
        print(f"\n成功创建文件 '{output_file}'，包含 {len(processed_studios_logos)} 个制片厂的Logo信息。")
    except IOError as e:
        print(f"写入文件 '{output_file}' 时发生错误：{e}")

# --- 脚本执行入口 ---
if __name__ == "__main__":
    process_media_index()