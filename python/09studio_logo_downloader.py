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
MAX_THREADS = 18

# 输入/输出文件和目录
INPUT_FILE = 'missing_studios.md'
IMAGE_OUTPUT_DIR = 'downloaded_studios'
JSON_OUTPUT_FILE = 'updated_studios_summary.json'
PROCESSED_LOG = 'processed_studios.log'
FAILED_LOG = 'failed_studios.log'
# TMDB速率限制为每秒40-50次，请合理设置 MAX_THREADS。

# --- 检查配置 ---
if TMDB_API_KEY == "在此处粘贴你的API密钥" or not TMDB_API_KEY:
    print("错误: 请在脚本中设置你的 TMDB_API_KEY。")
    exit()

# 创建一个全局锁用于线程安全的文件写入
log_lock = threading.Lock()

def sanitize_filename(name):
    """移除文件名中的非法字符，并替换/为空格"""
    name = name.replace('/', ' ') # Studios like '20th Century Fox / Twentieth Century Fox'
    return re.sub(r'[\\*?:"<>|]', "", name)

def parse_missing_studios_md(filepath):
    """从 missing_studios.md 文件中解析出制片厂名称列表"""
    if not os.path.exists(filepath):
        print(f"错误: 输入文件 '{filepath}' 不存在。")
        return []

    studios = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            # 匹配以 "- " 开头的行
            if line.strip().startswith('- '):
                # 提取- 后面的内容并去除首尾空格
                studio_name = line.strip()[2:].strip()
                if studio_name:
                    studios.append(studio_name)

    unique_studios = sorted(list(set(studios)))
    print(f"从 '{filepath}' 中解析出 {len(unique_studios)} 个独立的制片厂。")
    return unique_studios

def search_studio_tmdb(studio_name):
    """在 TMDB 中搜索制片厂并返回第一个结果的 ID 和 logo 路径"""
    search_url = "https://api.themoviedb.org/3/search/company"
    params = {'api_key': TMDB_API_KEY, 'query': studio_name}
    try:
        response = requests.get(search_url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data['results']:
            # 通常第一个结果最相关
            company = data['results'][0]
            return company.get('id'), company.get('logo_path')
        else:
            return None, None
    except requests.exceptions.RequestException as e:
        tqdm.write(f"\n网络错误 (搜索 {studio_name}): {e}")
        return None, None

def download_image(image_path, save_path):
    """下载图片"""
    if not image_path:
        return False
    # 使用原始尺寸以获得最佳质量
    image_base_url = "https://image.tmdb.org/t/p/original"
    full_url = f"{image_base_url}{image_path}"
    try:
        response = requests.get(full_url, stream=True, timeout=15)
        response.raise_for_status()
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    except requests.exceptions.RequestException as e:
        tqdm.write(f"\n图片下载失败: {full_url} -> {e}")
        return False

def append_to_log(filepath, message):
    """追加日志到文件（线程安全）"""
    with log_lock:
        with open(filepath, 'a', encoding='utf-8') as f:
            f.write(message + '\n')

def process_studio(studio_name):
    """
    处理单个制片厂信息的工作函数，供线程池调用。
    返回一个元组 (status, log_message, json_key, json_value)
    """
    company_id, logo_path = search_studio_tmdb(studio_name)

    if company_id and logo_path:
        sanitized_name = sanitize_filename(studio_name)
        studio_dir_path = os.path.join(IMAGE_OUTPUT_DIR, sanitized_name)
        os.makedirs(studio_dir_path, exist_ok=True)
        # 按照 studios_summary.json 的格式，图片名为 landscape.jpg
        save_path = os.path.join(studio_dir_path, "landscape.jpg")

        if download_image(logo_path, save_path):
            log_msg = f"成功: {studio_name} (ID: {company_id}) -> {save_path}"
            # JSON key 就是制片厂的原名
            json_key = studio_name
            # JSON value 是期望的Jellyfin/Emby路径
            json_value = f"config/metadata/studios/{sanitized_name}/landscape.jpg".replace("\\", "/")
            return ('success', log_msg, json_key, json_value)
        else:
            log_msg = f"失败: {studio_name} (ID: {company_id}) - 图片下载失败。"
            return ('failure', log_msg, None, None)
    elif company_id and not logo_path:
        log_msg = f"失败: {studio_name} (ID: {company_id}) - 在TMDB上找到，但无可用logo。"
        return ('failure', log_msg, None, None)
    else:
        log_msg = f"失败: {studio_name} - 在TMDB上未找到。"
        return ('failure', log_msg, None, None)

def run_downloader():
    """主执行函数"""
    studio_list = parse_missing_studios_md(INPUT_FILE)
    if not studio_list:
        return

    os.makedirs(IMAGE_OUTPUT_DIR, exist_ok=True)

    updated_studios_summary = {}
    if os.path.exists(JSON_OUTPUT_FILE):
        with open(JSON_OUTPUT_FILE, 'r', encoding='utf-8') as f:
            try:
                updated_studios_summary = json.load(f)
            except json.JSONDecodeError:
                print(f"警告: '{JSON_OUTPUT_FILE}' 文件内容不是有效的JSON，将创建一个新的。")
                updated_studios_summary = {}

    # 过滤掉已经处理过的制片厂
    studios_to_process = [
        studio for studio in studio_list
        if studio not in updated_studios_summary
    ]

    if not studios_to_process:
        print("所有在 miss.md 中的制片厂似乎都已经被处理。脚本结束。")
        return

    print(f"\n共 {len(studios_to_process)} 个新制片厂待处理。使用 {MAX_THREADS} 个线程开始下载...")

    # 使用线程池执行任务
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        future_to_studio = {executor.submit(process_studio, studio): studio for studio in studios_to_process}
        progress_bar = tqdm(as_completed(future_to_studio), total=len(studios_to_process), desc="处理制片厂")

        for future in progress_bar:
            studio_name = future_to_studio[future]
            try:
                status, log_msg, json_key, json_value = future.result()
                tqdm.write(f"  > {log_msg}")

                if status == 'success':
                    append_to_log(PROCESSED_LOG, log_msg)
                    updated_studios_summary[json_key] = json_value
                    # 每次成功后保存一次JSON，保证断点续存
                    with open(JSON_OUTPUT_FILE, 'w', encoding='utf-8') as f:
                        json.dump(updated_studios_summary, f, ensure_ascii=False, indent=4)
                else: # 'failure'
                    append_to_log(FAILED_LOG, log_msg)

            except Exception as exc:
                error_msg = f"制片厂 '{studio_name}' 在处理过程中产生异常: {exc}"
                tqdm.write(error_msg)
                append_to_log(FAILED_LOG, error_msg)

    print("\n\n处理完成！")
    print(f"图片已下载到 '{IMAGE_OUTPUT_DIR}' 目录下的对应子文件夹中。")
    print(f"可合并的JSON数据已更新到 '{JSON_OUTPUT_FILE}' 文件。")
    print(f"成功日志请查看: '{PROCESSED_LOG}'")
    print(f"失败日志请查看: '{FAILED_LOG}'")

if __name__ == "__main__":
    run_downloader()