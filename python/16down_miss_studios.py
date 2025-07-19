import requests
import os
import time
import re
import concurrent.futures # 引入多线程模块

# --- 配置 ---
# 从环境变量中获取 TMDb API Key，如果未设置，则提示用户输入
TMDB_API_KEY = os.environ.get("TMDB_API_KEY")
if not TMDB_API_KEY:
    TMDB_API_KEY = input("请粘贴你的 TMDb API Key 并按回车键: ")
    if not TMDB_API_KEY:
        print("错误: TMDb API Key 是必需的。程序退出。")
        exit()

# TMDb API 和图片的基本URL
TMDB_API_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/"

# 制片厂Logo图片的尺寸要求：高度大于50px的最小尺寸。
# TMDb 提供的公司Logo尺寸通常有 w45, w92, w154, w185, w300, w500, original。
# w92 (92px 宽) 的Logo通常其高度会大于50px，且是满足条件中最小的一个。
LOGO_IMAGE_SIZE = "w92"

# 图片下载保存的目录结构
BASE_DOWNLOAD_DIR = "download" # 例如: download
STUDIO_SUBDIR = "Studio"       # 例如: download/Studio
OUTPUT_ROOT_DIR = os.path.join(BASE_DOWNLOAD_DIR, STUDIO_SUBDIR) # 完整的根目录

# 报告文件的名称
REPORT_STUDIOS_FILE_NAME = "report_studios.txt"

# 多线程配置
MAX_WORKERS = 25 # 根据你的网络带宽和API速率限制调整线程数，不要设置过高

# --- 辅助函数 ---

def extract_names_from_report(file_path):
    """
    从报告文件中提取“缺失制片厂”列表中的名称。
    支持带引号和不带引号的名称。
    """
    names = []
    in_missing_section = False
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # 检查是否进入缺失制片厂报告部分
                if "--- Missing Studios Report ---" in line:
                    in_missing_section = True
                    continue
                # 检查是否到达报告的统计部分，停止读取
                if "Total missing studios:" in line:
                    break

                if in_missing_section:
                    # 匹配 - "Name" 或 - Name 格式
                    match_quoted = re.match(r'^- "([^"]+)"$', line)
                    match_unquoted = re.match(r'^- (.+)$', line)

                    if match_quoted:
                        name = match_quoted.group(1).strip()
                        if name:
                            names.append(name)
                    elif match_unquoted:
                        name = match_unquoted.group(1).strip()
                        if name:
                            names.append(name)
    except FileNotFoundError:
        print(f"错误: 文件 '{file_path}' 未找到。请确保 '{REPORT_STUDIOS_FILE_NAME}' 在脚本的同级目录中。")
    except Exception as e:
        print(f"读取文件时发生错误: {e}")
    return names

def sanitize_filename(name):
    """
    清理字符串，使其适合作为文件名或目录名。
    移除无效字符，并将多个空格替换为单个下划线。
    """
    # 移除 Windows/Linux 文件名中不允许的字符
    s = re.sub(r'[<>:"/\\|?*]', '', name)
    # 将多个空格替换为单个下划线，并去除首尾空格
    s = re.sub(r'\s+', '_', s).strip()
    # 确保文件名不为空，如果为空则给一个默认值
    if not s:
        s = "unknown_studio"
    return s

def search_company_tmdb(company_name, api_key):
    """
    在 TMDb 上搜索公司（制片厂），返回第一个匹配公司的 ID、Logo路径和搜索状态。
    返回值: (company_id, logo_path, status)
    status: "found", "not_found", "no_logo_path", "api_error"
    """
    search_url = f"{TMDB_API_BASE_URL}/search/company"
    params = {
        "api_key": api_key,
        "query": company_name,
        "language": "zh-CN" # 优先搜索中文结果
    }
    try:
        response = requests.get(search_url, params=params, timeout=10)
        response.raise_for_status() # 对HTTP错误（4xx或5xx）引发异常
        data = response.json()
        if data['results']:
            # 查找第一个有Logo图片的结果
            for result in data['results']:
                if result.get('logo_path'):
                    return result['id'], result['logo_path'], "found"
            # 如果找到了公司但没有Logo图片
            return data['results'][0]['id'], None, "no_logo_path"
        return None, None, "not_found" # 未找到公司
    except requests.exceptions.RequestException as e:
        # print(f"搜索 '{company_name}' 时发生API错误: {e}") # 避免多线程日志混乱
        return None, None, "api_error"

def download_logo_image(logo_path, company_name, output_root_dir):
    """
    从 TMDb 下载公司Logo图片并保存到指定目录结构：
    output_root_dir/<Company_Name>/landscape.jpg
    返回值: "success", "already_exists", "download_error", "no_logo_path"
    """
    if not logo_path:
        return "no_logo_path"

    image_full_url = f"{TMDB_IMAGE_BASE_URL}{LOGO_IMAGE_SIZE}{logo_path}"

    # 获取公司名称的目录名称
    company_folder_name = sanitize_filename(company_name)

    # 构建最终的图片保存目录
    target_dir = os.path.join(output_root_dir, company_folder_name)

    # 图片文件名为 landscape.jpg
    filename = "landscape.jpg"
    filepath = os.path.join(target_dir, filename)

    # 检查目标文件是否已存在
    if os.path.exists(filepath):
        # print(f"  跳过 '{company_name}': 图片 '{filepath}' 已存在。") # 避免多线程日志混乱
        return "already_exists"

    # 创建目录（如果不存在）
    try:
        os.makedirs(target_dir, exist_ok=True)
    except OSError as e:
        # print(f"  创建目录 '{target_dir}' 失败: {e}") # 避免多线程日志混乱
        return "download_error"

    try:
        response = requests.get(image_full_url, stream=True, timeout=20)
        response.raise_for_status() # 检查HTTP请求是否成功

        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        # print(f"  成功下载 '{company_name}' 的图片到 '{filepath}'。") # 避免多线程日志混乱
        return "success"
    except requests.exceptions.RequestException as e:
        # print(f"  下载 '{company_name}' 的图片 '{image_full_url}' 时发生错误: {e}") # 避免多线程日志混乱
        return "download_error"

def process_studio(studio_name, api_key, output_root_dir):
    """
    处理单个任务：搜索制片厂并尝试下载Logo图片。
    此函数将在线程池中执行。
    返回一个字典，包含处理结果，用于主线程统计。
    """
    result = {
        "name": studio_name,
        "search_status": "unknown",
        "download_status": "not_attempted"
    }

    # print(f"正在处理: '{studio_name}'") # 可以打开此行查看实时进度，但会很混乱

    company_id, logo_path, search_status = search_company_tmdb(studio_name, api_key)
    time.sleep(0.1) # 每次API请求之间添加短暂停顿

    result["search_status"] = search_status

    if search_status == "found":
        download_status = download_logo_image(logo_path, studio_name, output_root_dir)
        result["download_status"] = download_status

    return result

# --- 主程序逻辑 ---

def main():
    # 确保根输出目录存在 (e.g., "download/Studio")
    os.makedirs(OUTPUT_ROOT_DIR, exist_ok=True)

    # 将示例报告内容写入文件，如果文件不存在的话。实际使用时，请确保你有自己的 report_studios.txt
    # 注意: 如果你已经有 report_studios.txt，这部分代码可以移除或注释掉。
    if not os.path.exists(REPORT_STUDIOS_FILE_NAME):
        print(f"'{REPORT_STUDIOS_FILE_NAME}' 不存在，正在创建示例文件...")
        example_report_content = """--- START OF FILE report_studios.txt ---

Scanning NFO files for studios...
NFO scanning complete.

--- Missing Studios Report ---
The following studios were found in NFO files but are NOT in studios_summary.json:
- 3BlackDot
- A24
- Aardman Animations
- ABC Studios
- Alibaba Pictures
- Amazon Studios
- Amblin Entertainment
- Annapurna Pictures
- Apple Studios
- Bad Robot
- BBC Films
- Blumhouse Productions
- Buena Vista Pictures
- Canal+
- Caviar
- Cinetel Films
- Columbia Pictures
- Concorde-New Horizons
- Constantin Film
- Dimension Films
- Disney+ Originals
- DreamWorks Pictures
- DreamWorks Animation
- EuropaCorp
- FilmNation Entertainment
- Focus Features
- Fox Searchlight Pictures
- Gaumont
- HBO Films
- Imagine Entertainment
- Indian Paintbrush
- Lakeshore Entertainment
- Legendary Entertainment
- Lionsgate
- Lucasfilm
- Marvel Studios
- MGM
- Miramax
- Monkeypaw Productions
- Neon
- Netflix
- New Line Cinema
- Nordisk Film
- Orion Pictures
- Paramount Pictures
- Participant Media
- Pixar Animation Studios
- Plan B Entertainment
- Revolution Studios
- Roadside Attractions
- Searchlight Pictures
- Sierra/Affinity
- Sony Pictures
- StudioCanal
- STX Entertainment
- Summit Entertainment
- Tezuka Productions
- The Weinstein Company
- Toho
- TriStar Pictures
- Twentieth Century Fox
- Universal Pictures
- Village Roadshow Pictures
- Walt Disney Pictures
- Warner Bros. Pictures
- Working Title Films
- XYZ Films
- Zodiac Features

Total missing studios: 70
"""
        with open(REPORT_STUDIOS_FILE_NAME, 'w', encoding='utf-8') as f:
            f.write(example_report_content)
        print(f"示例文件 '{REPORT_STUDIOS_FILE_NAME}' 已创建。请根据需要编辑其内容。")

    # 检查报告文件是否存在
    if not os.path.exists(REPORT_STUDIOS_FILE_NAME):
        print(f"错误: 报告文件 '{REPORT_STUDIOS_FILE_NAME}' 未找到。程序退出。")
        return

    missing_studio_names = extract_names_from_report(REPORT_STUDIOS_FILE_NAME)

    if not missing_studio_names:
        print(f"未从 '{REPORT_STUDIOS_FILE_NAME}' 中提取到任何制片厂名称。请检查文件内容和格式。")
        return

    print(f"从 '{REPORT_STUDIOS_FILE_NAME}' 中找到了 {len(missing_studio_names)} 个需要处理的缺失制片厂名称。")
    print(f"将使用 {MAX_WORKERS} 个线程进行处理...")

    # 统计变量
    processed_count = 0
    downloaded_count = 0
    skipped_no_tmdb_match = 0
    skipped_no_logo_img = 0
    skipped_already_exists = 0
    api_search_error_count = 0
    image_download_error_count = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # 提交所有任务给线程池
        futures = {executor.submit(process_studio, name, TMDB_API_KEY, OUTPUT_ROOT_DIR): name
                   for name in missing_studio_names}

        # 遍历已完成的任务
        for future in concurrent.futures.as_completed(futures):
            processed_count += 1
            name = futures[future] # 获取对应的任务名称
            try:
                result = future.result() # 获取线程执行的结果

                # 根据结果更新统计
                if result["search_status"] == "api_error":
                    api_search_error_count += 1
                    print(f"错误: '{name}' 的 TMDb 搜索失败。")
                elif result["search_status"] == "not_found":
                    skipped_no_tmdb_match += 1
                    print(f"跳过: '{name}' 在 TMDb 上未找到。")
                elif result["search_status"] == "no_logo_path":
                    skipped_no_logo_img += 1
                    print(f"跳过: '{name}' 在 TMDb 上找到，但无Logo图片。")
                elif result["search_status"] == "found":
                    if result["download_status"] == "success":
                        downloaded_count += 1
                        # print(f"成功: '{name}' Logo图片已下载。") # 避免与成功下载的函数内的print重复
                    elif result["download_status"] == "already_exists":
                        skipped_already_exists += 1
                        # print(f"跳过: '{name}' Logo图片已存在。") # 避免与成功下载的函数内的print重复
                    elif result["download_status"] == "download_error":
                        image_download_error_count += 1
                        print(f"错误: '{name}' Logo图片下载失败。")

            except Exception as exc:
                print(f"'{name}' 生成了一个未预期的异常: {exc}")
                api_search_error_count += 1 # 捕获任何未预料的异常

            # 打印进度 (每处理一定数量的请求)
            if processed_count % 50 == 0:
                print(f"\n--- 进度: 已处理 {processed_count}/{len(missing_studio_names)} 个制片厂 ---")
                print(f"已下载: {downloaded_count}, 未找到: {skipped_no_tmdb_match}, 无图: {skipped_no_logo_img}, 已存在: {skipped_already_exists}, 错误: {api_search_error_count + image_download_error_count}")
                # 可以在这里添加一个较长的暂停，如果发现有API速率限制问题
                # time.sleep(1)

    print(f"\n--- 处理完成 ---")
    print(f"总计处理制片厂: {processed_count}")
    print(f"成功下载Logo图片: {downloaded_count}")
    print(f"跳过 (TMDb 未找到): {skipped_no_tmdb_match}")
    print(f"跳过 (TMDb 上无Logo图片): {skipped_no_logo_img}")
    print(f"跳过 (图片本地已存在): {skipped_already_exists}")
    print(f"API 搜索错误: {api_search_error_count}")
    print(f"图片下载错误: {image_download_error_count}")

if __name__ == "__main__":
    main()