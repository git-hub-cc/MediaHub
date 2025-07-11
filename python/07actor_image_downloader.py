import os
import re
import json
import time
import requests
import threading
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- 配置区 ---
# 在这里填入你的 TMDB API v3 密钥
TMDB_API_KEY = "在此处粘贴你的API密钥"
# 设置并发线程数
MAX_THREADS = 8

INPUT_FILE = 'miss.md'
IMAGE_OUTPUT_DIR = 'downloaded_actors'
JSON_OUTPUT_FILE = 'updated_people_summary.json'
PROCESSED_LOG = 'processed_actors.log'
FAILED_LOG = 'failed_actors.log'
# API_DELAY_SECONDS 在多线程模式下已移除，速率由 MAX_THREADS 和网络延迟共同决定。
# TMDB速率限制为每秒40-50次，请合理设置 MAX_THREADS。

# --- 检查配置 ---
if TMDB_API_KEY == "在此处粘贴你的API密钥" or not TMDB_API_KEY:
    print("错误: 请在脚本中设置你的 TMDB_API_KEY。")
    exit()

# 创建一个全局锁用于线程安全的文件写入
log_lock = threading.Lock()

def sanitize_filename(name):
    """移除文件名中的非法字符"""
    return re.sub(r'[\\/*?:"<>|]', "", name)

def parse_miss_md(filepath):
    """从 miss.md 文件中解析出演员姓名和可选的TMDB ID"""
    if not os.path.exists(filepath):
        print(f"错误: 输入文件 '{filepath}' 不存在。")
        return []

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    actors_info = []
    actor_blocks = re.findall(r'<actor>.*?</actor>', content, re.DOTALL)
    unique_actors_dict = {}

    for block in actor_blocks:
        name_match = re.search(r'<name>(.*?)</name>', block)
        tmdbid_match = re.search(r'<tmdbid>(.*?)</tmdbid>', block)

        if name_match:
            name = name_match.group(1).strip()
            name = name.replace('&', '&').replace('<', '<').replace('>', '>')
            tmdbid = tmdbid_match.group(1).strip() if tmdbid_match else None
            if name not in unique_actors_dict or (tmdbid and not unique_actors_dict[name].get('tmdbid')):
                 unique_actors_dict[name] = {'name': name, 'tmdbid': tmdbid}

    actors_info = list(unique_actors_dict.values())
    print(f"从 '{filepath}' 中解析出 {len(actors_info)} 位独立演员。")
    return actors_info

def get_actor_details_tmdb(person_id):
    """通过TMDB ID获取演员的个人资料路径"""
    details_url = f"https://api.themoviedb.org/3/person/{person_id}"
    params = {'api_key': TMDB_API_KEY}
    try:
        response = requests.get(details_url, params=params)
        response.raise_for_status()
        data = response.json()
        return data.get('profile_path')
    except requests.exceptions.RequestException as e:
        print(f"\n网络错误 (获取详情): {e}")
        return None

def search_actor_tmdb(actor_name):
    """在 TMDB 中搜索演员并返回第一个结果的 ID 和 个人资料路径"""
    search_url = "https://api.themoviedb.org/3/search/person"
    params = {'api_key': TMDB_API_KEY, 'query': actor_name, 'include_adult': 'false'}
    try:
        response = requests.get(search_url, params=params)
        response.raise_for_status()
        data = response.json()
        if data['results']:
            person = data['results'][0]
            return person.get('id'), person.get('profile_path')
        else:
            return None, None
    except requests.exceptions.RequestException as e:
        print(f"\n网络错误 (搜索): {e}")
        return None, None

def download_image(image_path, save_path):
    """下载图片"""
    if not image_path:
        return False
    image_base_url = "https://image.tmdb.org/t/p/w500"
    full_url = f"{image_base_url}{image_path}"
    try:
        response = requests.get(full_url, stream=True)
        response.raise_for_status()
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    except requests.exceptions.RequestException as e:
        # 在多线程中，直接打印可能会扰乱tqdm进度条，但对于错误提示是必要的
        tqdm.write(f"\n图片下载失败: {full_url} -> {e}")
        return False

def append_to_log(filepath, message):
    """追加日志到文件（线程安全）"""
    with log_lock:
        with open(filepath, 'a', encoding='utf-8') as f:
            f.write(message + '\n')

def process_actor(actor_info):
    """
    处理单个演员信息的工作函数，供线程池调用。
    返回一个元组 (status, log_message, json_key, json_value)
    """
    name = actor_info['name']
    provided_tmdbid = actor_info['tmdbid']
    person_id, profile_path = None, None

    if provided_tmdbid:
        person_id = provided_tmdbid
        profile_path = get_actor_details_tmdb(person_id)
    else:
        person_id, profile_path = search_actor_tmdb(name)

    if person_id and profile_path:
        sanitized_name = sanitize_filename(name)
        actor_folder_name = f"{sanitized_name}-tmdb-{person_id}"
        actor_dir_path = os.path.join(IMAGE_OUTPUT_DIR, actor_folder_name)
        os.makedirs(actor_dir_path, exist_ok=True)
        save_path = os.path.join(actor_dir_path, "folder.jpg")

        if download_image(profile_path, save_path):
            log_msg = f"成功: {name} (ID: {person_id}) -> {save_path}"
            json_key = f"{name}-tmdb-{person_id}"
            first_char = sanitized_name[0]
            json_value = f"config/metadata/People/{first_char}/{json_key}/folder.jpg".replace("\\", "/")
            return ('success', log_msg, json_key, json_value)
        else:
            log_msg = f"失败: {name} (ID: {person_id}) - 图片下载失败。"
            return ('failure', log_msg, None, None)
    elif person_id and not profile_path:
        log_msg = f"失败: {name} (ID: {person_id}) - 在TMDB上找到，但无可用头像。"
        return ('failure', log_msg, None, None)
    else:
        log_msg = f"失败: {name} - 在TMDB上未找到。"
        return ('failure', log_msg, None, None)

def run_scraper():
    """主执行函数"""
    actors_info_list = parse_miss_md(INPUT_FILE)
    if not actors_info_list:
        return

    os.makedirs(IMAGE_OUTPUT_DIR, exist_ok=True)

    updated_people_summary = {}
    if os.path.exists(JSON_OUTPUT_FILE):
        with open(JSON_OUTPUT_FILE, 'r', encoding='utf-8') as f:
            try:
                updated_people_summary = json.load(f)
            except json.JSONDecodeError:
                print(f"警告: '{JSON_OUTPUT_FILE}' 文件内容不是有效的JSON，将创建一个新的。")
                updated_people_summary = {}

    actors_to_process = [
        actor for actor in actors_info_list
        if not any(key.startswith(f"{actor['name']}-tmdb-") for key in updated_people_summary.keys())
    ]

    if not actors_to_process:
        print("所有在 miss.md 中的演员似乎都已经被处理。脚本结束。")
        return

    print(f"\n共 {len(actors_to_process)} 位新演员待处理。使用 {MAX_THREADS} 个线程开始下载...")

    # 使用线程池执行任务
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        # 提交所有任务
        future_to_actor = {executor.submit(process_actor, actor): actor for actor in actors_to_process}

        # 使用tqdm来包装as_completed，实现实时进度条
        progress_bar = tqdm(as_completed(future_to_actor), total=len(actors_to_process), desc="处理演员")

        for future in progress_bar:
            actor_name = future_to_actor[future]['name']
            try:
                status, log_msg, json_key, json_value = future.result()

                # 在进度条下方打印单条日志
                tqdm.write(f"  > {log_msg}")

                if status == 'success':
                    append_to_log(PROCESSED_LOG, log_msg)
                    updated_people_summary[json_key] = json_value
                    # 每次成功后保存一次JSON，保证断点续存
                    with open(JSON_OUTPUT_FILE, 'w', encoding='utf-8') as f:
                        json.dump(updated_people_summary, f, ensure_ascii=False, indent=4)
                else: # 'failure'
                    append_to_log(FAILED_LOG, log_msg)

            except Exception as exc:
                error_msg = f"演员 '{actor_name}' 在处理过程中产生异常: {exc}"
                tqdm.write(error_msg)
                append_to_log(FAILED_LOG, error_msg)


    print("\n\n处理完成！")
    print(f"图片已下载到 '{IMAGE_OUTPUT_DIR}' 目录下的对应子文件夹中。")
    print(f"可合并的JSON数据已更新到 '{JSON_OUTPUT_FILE}' 文件。")
    print(f"成功日志请查看: '{PROCESSED_LOG}'")
    print(f"失败日志请查看: '{FAILED_LOG}'")

if __name__ == "__main__":
    run_scraper()