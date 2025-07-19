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
TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w185" # 常见的图片大小，可根据需求更改 (e.g., w92, w185, w300, original)
MAX_WORKERS = 20 # 线程池最大工作线程数，用于并发请求TMDb API (可根据网络和TMDb限制调整)

# 图片下载目录，相对路径
IMAGE_DOWNLOAD_DIR = "people"

# 全局字典，用于存储已处理的演员及其图片URL，防止重复请求和重复存储
# 使用线程锁来确保多线程写入时的安全
processed_people_images = {}
processed_people_lock = threading.Lock()

# --- 辅助函数：文件名安全处理 ---
def sanitize_filename(filename: str) -> str:
    """
    清洗文件名，移除或替换在文件系统中不安全的字符。
    """
    # 替换非法字符为下划线
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # 移除或替换 Windows 保留名称（COM1, LPT1等，虽然这里不常见，但可以避免）
    # 这里我们只处理常见的非法字符，对于更复杂的场景可能需要更强的正则
    return sanitized

# --- 图片下载函数 ---
def download_image(image_url: str, person_name: str) -> str | None:
    """
    下载图片到本地指定目录，并返回其相对路径。
    Args:
        image_url: TMDb 图片的完整 URL。
        person_name: 人物名称，用于构建本地文件名。
    Returns:
        下载图片的本地相对路径，如果下载失败则返回 None。
    """
    if not image_url:
        return None

    # 从URL中提取原始文件名（通常是TMDb的hash值 + .jpg）
    original_filename_part = image_url.split('/')[-1] # 例如：2gABjGzC4kYF1MBlbKz1D.jpg
    if not original_filename_part or '.' not in original_filename_part:
        # 如果URL结构异常，尝试用人物名作为基础
        filename_base = sanitize_filename(person_name)
        ext = ".jpg" # 假设是jpg
    else:
        # 结合人物名和TMDb的hash部分，提高文件名可读性和唯一性
        name_part = sanitize_filename(person_name)
        filename_base = f"{name_part}_{original_filename_part.split('.')[0]}" # 去掉原始扩展名
        ext = "." + original_filename_part.split('.')[-1] # 保留原始扩展名

    local_filename = f"{filename_base}{ext}"
    local_file_path = os.path.join(IMAGE_DOWNLOAD_DIR, local_filename)

    # 确保下载目录存在
    os.makedirs(IMAGE_DOWNLOAD_DIR, exist_ok=True)

    # 检查文件是否已存在，如果存在则跳过下载
    if os.path.exists(local_file_path):
        print(f"  图片已存在：'{local_file_path}'，跳过下载。")
        return local_file_path # 返回已存在文件的相对路径

    try:
        response = requests.get(image_url, stream=True, timeout=10)
        response.raise_for_status() # 检查HTTP请求是否成功

        with open(local_file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"  已下载图片：'{local_file_path}'")
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

# --- TMDb API 辅助函数 ---
def get_person_details_from_tmdb(person_id: str, api_key: str) -> str | None:
    """
    通过人物ID在TMDb上获取人物详情，并返回其头像路径。
    Args:
        person_id: TMDb人物ID。
        api_key: TMDb API Key。
    Returns:
        头像的相对路径 (profile_path)，如果获取失败则返回None。
    """
    details_url = f"{TMDB_BASE_URL}/person/{person_id}"
    params = {
        "api_key": api_key
    }
    try:
        response = requests.get(details_url, params=params, timeout=10) # 设置超时
        response.raise_for_status() # 检查HTTP请求是否成功
        data = response.json()
        return data.get("profile_path")
    except requests.exceptions.RequestException as e:
        print(f"警告：请求TMDb API时发生错误（获取人物ID {person_id} 详情）：{e}")
        return None

def search_person_on_tmdb(person_name: str, api_key: str) -> str | None:
    """
    通过姓名在TMDb上搜索人物，并返回其头像路径。
    Args:
        person_name: 要搜索的人物姓名。
        api_key: TMDb API Key。
    Returns:
        头像的相对路径 (profile_path)，如果找到则返回，否则返回None。
    """
    search_url = f"{TMDB_BASE_URL}/search/person"
    params = {
        "api_key": api_key,
        "query": person_name,
        "language": "zh-CN" # 可以指定语言
    }
    try:
        response = requests.get(search_url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data and data.get("results"):
            # 返回第一个匹配结果的头像路径
            person = data["results"][0]
            return person.get("profile_path")
        else:
            print(f"警告：在TMDb上未找到人物：'{person_name}'")
            return None
    except requests.exceptions.RequestException as e:
        print(f"警告：请求TMDb API时发生错误（搜索人物 '{person_name}'）：{e}")
        return None

def fetch_person_image(person_name: str, tmdb_id: str | None) -> tuple[str, str | None]:
    """
    根据人物姓名和可选的TMDb ID获取其在TMDb上的图片URL，并下载到本地。
    Args:
        person_name: 演员姓名。
        tmdb_id: 演员在TMDb上的ID (可选)。
    Returns:
        (person_name, downloaded_image_relative_path) 元组。如果获取或下载失败，downloaded_image_relative_path为None。
    """
    # 检查API Key是否已配置
    if not TMDB_API_KEY or TMDB_API_KEY == "YOUR_TMDB_API_KEY":
        print("错误：请在脚本中配置您的TMDb API Key。")
        return person_name, None

    # 首先尝试从全局缓存中获取（这里存储的是本地下载路径）
    with processed_people_lock:
        if person_name in processed_people_images:
            return person_name, processed_people_images[person_name]

    profile_path = None
    if tmdb_id:
        # 如果NFO中提供了TMDb ID，优先使用ID获取详情
        profile_path = get_person_details_from_tmdb(tmdb_id, TMDB_API_KEY)

    if not profile_path:
        # 如果没有ID或通过ID未获取到，则尝试通过姓名搜索
        profile_path = search_person_on_tmdb(person_name, TMDB_API_KEY)

    downloaded_path = None
    if profile_path:
        full_tmdb_image_url = f"{TMDB_IMAGE_BASE_URL}{profile_path}"
        # 调用下载函数，并获取本地相对路径
        downloaded_path = download_image(full_tmdb_image_url, person_name)

    # 无论成功与否，将结果（本地路径或None）存入全局缓存
    with processed_people_lock:
        processed_people_images[person_name] = downloaded_path

    return person_name, downloaded_path

# --- NFO 文件解析辅助函数 ---
def parse_nfo_for_actors(nfo_file_path: str) -> set[tuple[str, str | None]]:
    """
    解析NFO文件，提取演员的姓名和TMDb ID。
    Args:
        nfo_file_path: NFO文件的完整路径。
    Returns:
        一个包含 (actor_name, tmdb_id) 元组的集合，tmdb_id可能为None。
    """
    actors_info = set()
    if not os.path.exists(nfo_file_path):
        # print(f"警告：NFO文件不存在：{nfo_file_path}") # 避免过多输出
        return actors_info

    try:
        # 尝试以UTF-8编码解析，如果失败则尝试GBK或其他常用编码
        tree = ET.parse(nfo_file_path)
        root = tree.getroot()
    except ET.ParseError as e:
        try: # 尝试不同的编码
            with open(nfo_file_path, 'r', encoding='gbk', errors='ignore') as f: # errors='ignore' 忽略无法解码的字符
                content = f.read()
            root = ET.fromstring(content)
            # print(f"信息：NFO文件 '{nfo_file_path}' 以GBK编码解析成功。") # 避免过多输出
        except Exception as e_gbk:
            print(f"错误：无法解析NFO文件 '{nfo_file_path}'：{e}. 尝试GBK失败：{e_gbk}")
            return actors_info
    except Exception as e:
        print(f"错误：读取NFO文件 '{nfo_file_path}' 时发生未知错误：{e}")
        return actors_info

    for actor_elem in root.findall('actor'):
        name = actor_elem.find('name')
        tmdbid = actor_elem.find('tmdbid')
        if name is not None and name.text:
            actor_name = name.text.strip()
            actor_tmdbid = tmdbid.text.strip() if tmdbid is not None and tmdbid.text else None
            actors_info.add((actor_name, actor_tmdbid))
    return actors_info

# --- 主处理函数 ---
def process_media_index(input_file: str = "media_index.json", output_file: str = "people_summary.json"):
    """
    解析media_index.json文件，提取NFO文件路径，解析NFO中的演员信息，
    并通过TMDb API获取人物图片地址并下载，支持多线程。
    Args:
        input_file: 输入的media_index.json文件路径。
        output_file: 输出的people_summary.json文件路径。
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
                    nfo_data = file_info["nfo"] # 'nfo' 字段可能是字符串或列表
                    if isinstance(nfo_data, list):
                        for nfo_filename in nfo_data:
                            if nfo_filename: # 确保路径不为空
                                full_nfo_path = os.path.normpath(os.path.join(movie_base_path, nfo_filename))
                                all_nfo_paths.append(full_nfo_path)
                    elif isinstance(nfo_data, str):
                        full_nfo_path = os.path.normpath(os.path.join(movie_base_path, nfo_data))
                        all_nfo_paths.append(full_nfo_path)
                    else:
                        print(f"警告：电影 '{movie_base_path}' 的 'nfo' 字段类型未知 ({type(nfo_data)}), 跳过。")

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
                if isinstance(tvshow_nfo_data, list): # 如果是列表
                    for tvshow_nfo_rel_path in tvshow_nfo_data:
                        if tvshow_nfo_rel_path:
                            full_tvshow_nfo_path = os.path.normpath(os.path.join(tv_show_base_path, tvshow_nfo_rel_path))
                            all_nfo_paths.append(full_tvshow_nfo_path)
                elif isinstance(tvshow_nfo_data, str): # 如果是单个字符串
                    full_tvshow_nfo_path = os.path.normpath(os.path.join(tv_show_base_path, tvshow_nfo_data))
                    all_nfo_paths.append(full_tvshow_nfo_path)
                else:
                    print(f"警告：电视剧 '{tv_show_base_path}' 的 'tvshow_nfo' 类型未知，跳过。")


            # 添加季NFO (season_nfo)
            if "season_nfo" in files_data and files_data["season_nfo"]:
                season_nfo_data = files_data["season_nfo"]
                if isinstance(season_nfo_data, list): # 确保是列表
                    for season_nfo_rel_path in season_nfo_data:
                        if season_nfo_rel_path:
                            full_season_nfo_path = os.path.normpath(os.path.join(tv_show_base_path, season_nfo_rel_path))
                            all_nfo_paths.append(full_season_nfo_path)
                elif isinstance(season_nfo_data, str): # 如果是单个字符串
                     full_season_nfo_path = os.path.normpath(os.path.join(tv_show_base_path, season_nfo_data))
                     all_nfo_paths.append(full_season_nfo_path)
                else:
                    print(f"警告：电视剧 '{tv_show_base_path}' 的 'season_nfo' 类型未知，跳过。")


            # 添加单集NFO (nfo)
            if "nfo" in files_data and files_data["nfo"]:
                # 假设 'nfo' 是一个包含季字典的列表，每个季字典又包含一个文件名列表
                episode_nfo_data = files_data["nfo"]
                if isinstance(episode_nfo_data, list):
                    for season_dict in episode_nfo_data:
                        if isinstance(season_dict, dict):
                            for season_folder, episode_nfo_list in season_dict.items():
                                if isinstance(episode_nfo_list, list):
                                    for episode_nfo_rel_path in episode_nfo_list:
                                        if episode_nfo_rel_path:
                                            # 拼接基础路径和相对路径
                                            full_episode_nfo_path = os.path.normpath(os.path.join(tv_show_base_path, episode_nfo_rel_path))
                                            all_nfo_paths.append(full_episode_nfo_path)
                                else:
                                    print(f"警告：电视剧 '{tv_show_base_path}' 中季 '{season_folder}' 的集NFO格式异常（非列表），跳过。")
                        else:
                            print(f"警告：电视剧 '{tv_show_base_path}' 的 'nfo' 字段中的季字典格式异常（非字典），跳过。")
                else:
                    print(f"警告：电视剧 '{tv_show_base_path}' 的 'nfo' 字段类型未知（非列表），跳过。")


    # 对所有NFO路径进行去重，因为可能存在重复的NFO文件路径
    unique_nfo_paths = sorted(list(set(all_nfo_paths)))

    print("\n--- 收集到的独特NFO文件路径 ---")
    for path in unique_nfo_paths:
        print(path)
    print(f"\n总共找到 {len(unique_nfo_paths)} 个独特的NFO文件路径。\n")

    # --- 从NFO文件中解析所有演员信息 ---
    all_actors_to_fetch = set() # 存储待处理的 (actor_name, tmdb_id) 元组，用于去重
    for nfo_path in unique_nfo_paths:
        actors_in_nfo = parse_nfo_for_actors(nfo_path)
        all_actors_to_fetch.update(actors_in_nfo)

    print(f"从NFO文件中解析到 {len(all_actors_to_fetch)} 个独特的演员信息。\n")

    # --- 通过TMDb API获取演员图片地址并下载（多线程）---
    print("--- 正在通过TMDb API获取人物图片地址并下载（多线程）---")

    # 收集需要通过TMDb查找的演员任务 (姓名，ID)
    tasks = []
    for name, tmdb_id in all_actors_to_fetch:
        tasks.append((name, tmdb_id))

    # 使用线程池并发请求TMDb API
    if not tasks:
        print("没有需要获取图片的人物。")
        return

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # 提交任务到线程池
        futures = {executor.submit(fetch_person_image, name, tmdb_id): (name, tmdb_id) for name, tmdb_id in tasks}

        for i, future in enumerate(as_completed(futures)):
            original_task_info = futures[future] # (name, tmdb_id)
            person_name, downloaded_path = future.result() # fetch_person_image的返回值 (name, downloaded_path)

            progress = f"({i + 1}/{len(tasks)})"
            if downloaded_path:
                print(f"[{progress}] 已处理 '{person_name}'，图片路径：{downloaded_path}")
            else:
                print(f"[{progress}] 未能获取或下载 '{person_name}' 的图片。")

    # 最终的 `processed_people_images` 字典包含了所有成功获取和下载的演员图片信息（本地相对路径）
    # 将结果写入people_summary.json文件
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(processed_people_images, f, indent=4, ensure_ascii=False)
        print(f"\n成功创建文件 '{output_file}'，包含 {len(processed_people_images)} 位人物的图片信息。")
    except IOError as e:
        print(f"写入文件 '{output_file}' 时发生错误：{e}")

# --- 脚本执行入口 ---
if __name__ == "__main__":
    process_media_index()