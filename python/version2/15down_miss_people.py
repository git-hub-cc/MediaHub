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

# 个人资料图片的尺寸要求：宽度大于100px的最小尺寸。
# TMDb 提供的个人资料图片尺寸通常有 w45, w185, h632, original。
# w185 (185px 宽) 是满足条件“大于100px的最小格式”的最佳选择。
PROFILE_IMAGE_SIZE = "w185"

# 图片下载保存的目录结构
BASE_DOWNLOAD_DIR = "download" # 例如: download
PEOPLE_SUBDIR = "People"       # 例如: download/People
OUTPUT_ROOT_DIR = os.path.join(BASE_DOWNLOAD_DIR, PEOPLE_SUBDIR) # 完整的根目录

# 报告文件的名称
REPORT_FILE_NAME = "report_people.txt"

# 多线程配置
MAX_WORKERS = 25 # 根据你的网络带宽和API速率限制调整线程数，不要设置过高

# --- 辅助函数 ---

def extract_names_from_report(file_path):
    """
    从报告文件中提取“缺失人员”列表中的姓名。
    支持带引号和不带引号的姓名。
    """
    names = []
    in_missing_section = False
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if "--- Missing People Report ---" in line:
                    in_missing_section = True
                    continue
                if "Total missing people:" in line:
                    break  # 到达报告的统计部分，停止读取

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
        print(f"错误: 文件 '{file_path}' 未找到。请确保 '{REPORT_FILE_NAME}' 在脚本的同级目录中。")
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
        s = "unknown_person"
    return s

def get_first_char_folder_name(person_name):
    """
    根据人物姓名的第一个字符确定第一级子文件夹的名称。
    数字开头的归类为数字，字母开头的归类为大写字母，其他字符直接使用。
    """
    if not person_name:
        return "_" # 空姓名归类到特殊目录

    first_char = person_name[0]

    # 判断字符类型
    if '0' <= first_char <= '9': # 数字
        return first_char
    elif 'a' <= first_char <= 'z' or 'A' <= first_char <= 'Z': # 英文字母
        return first_char.upper()
    else:
        # 对于其他非字母数字字符（如中文、特殊符号、引号等）
        # 尝试清理名称，然后取清理后的第一个字符。
        # 这样可以避免文件夹名以 ' 或 " 开头。
        sanitized_name = sanitize_filename(person_name)
        if sanitized_name:
            return sanitized_name[0]
        else:
            return "_" # 如果清理后仍然无法获得有效首字符，则归类为特殊目录

def search_person_tmdb(person_name, api_key):
    """
    在 TMDb 上搜索人物，返回第一个匹配人物的 ID、个人资料路径和搜索状态。
    返回值: (person_id, profile_path, status)
    status: "found", "not_found", "no_profile_path", "api_error"
    """
    search_url = f"{TMDB_API_BASE_URL}/search/person"
    params = {
        "api_key": api_key,
        "query": person_name,
        "language": "zh-CN"  # 优先搜索中文结果
    }
    try:
        response = requests.get(search_url, params=params, timeout=10)
        response.raise_for_status()  # 对HTTP错误（4xx或5xx）引发异常
        data = response.json()
        if data['results']:
            # 查找第一个有个人资料图片的结果
            for result in data['results']:
                if result.get('profile_path'):
                    return result['id'], result['profile_path'], "found"
            # 如果找到了人物但没有个人资料图片
            # 这里返回第一个结果的ID，但 profile_path 为 None
            return data['results'][0]['id'], None, "no_profile_path"
        return None, None, "not_found"  # 未找到人物
    except requests.exceptions.RequestException as e:
        # print(f"搜索 '{person_name}' 时发生API错误: {e}") # 避免多线程日志混乱
        return None, None, "api_error"

def download_image(image_path, person_name, output_root_dir):
    """
    从 TMDb 下载图片并保存到指定目录结构：
    output_root_dir/<first_char_of_name>/<full_name>/folder.jpg
    返回值: "success", "already_exists", "download_error", "no_image_path"
    """
    if not image_path:
        return "no_image_path"

    image_full_url = f"{TMDB_IMAGE_BASE_URL}{PROFILE_IMAGE_SIZE}{image_path}"

    # 获取第一级子文件夹名称
    first_char_folder = get_first_char_folder_name(person_name)

    # 获取人物完整名称的目录名称
    person_folder_name = sanitize_filename(person_name)

    # 构建最终的图片保存目录
    target_dir = os.path.join(output_root_dir, first_char_folder, person_folder_name)

    # 图片文件名为 folder.jpg
    filename = "folder.jpg"
    filepath = os.path.join(target_dir, filename)

    # 检查目标文件是否已存在
    if os.path.exists(filepath):
        # print(f"  跳过 '{person_name}': 图片 '{filepath}' 已存在。") # 避免多线程日志混乱
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
        # print(f"  成功下载 '{person_name}' 的图片到 '{filepath}'。") # 避免多线程日志混乱
        return "success"
    except requests.exceptions.RequestException as e:
        # print(f"  下载 '{person_name}' 的图片 '{image_full_url}' 时发生错误: {e}") # 避免多线程日志混乱
        return "download_error"

def process_person(person_name, api_key, output_root_dir):
    """
    处理单个任务：搜索人物并尝试下载图片。
    此函数将在线程池中执行。
    返回一个字典，包含处理结果，用于主线程统计。
    """
    result = {
        "name": person_name,
        "search_status": "unknown",
        "download_status": "not_attempted"
    }

    # print(f"正在处理: '{person_name}'") # 可以打开此行查看实时进度，但会很混乱

    person_id, profile_path, search_status = search_person_tmdb(person_name, api_key)
    time.sleep(0.1) # 每次API请求之间添加短暂停顿

    result["search_status"] = search_status

    if search_status == "found":
        download_status = download_image(profile_path, person_name, output_root_dir)
        result["download_status"] = download_status

    return result

# --- 主程序逻辑 ---

def main():
    # 确保根输出目录存在 (e.g., "download/People")
    os.makedirs(OUTPUT_ROOT_DIR, exist_ok=True)

    # 检查报告文件是否存在
    if not os.path.exists(REPORT_FILE_NAME):
        print(f"错误: 报告文件 '{REPORT_FILE_NAME}' 未找到。请确保它在脚本的同级目录中。")
        return

    missing_people_names = extract_names_from_report(REPORT_FILE_NAME)

    if not missing_people_names:
        print(f"未从 '{REPORT_FILE_NAME}' 中提取到任何人员姓名。请检查文件内容和格式。")
        return

    print(f"从 '{REPORT_FILE_NAME}' 中找到了 {len(missing_people_names)} 个需要处理的缺失人员姓名。")
    print(f"将使用 {MAX_WORKERS} 个线程进行处理...")

    # 统计变量
    processed_count = 0
    downloaded_count = 0
    skipped_no_tmdb_match = 0
    skipped_no_profile_img = 0
    skipped_already_exists = 0
    api_search_error_count = 0
    image_download_error_count = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # 提交所有任务给线程池
        # 使用 functools.partial 可以方便地绑定固定参数，但这里直接用 lambda 更直观
        futures = {executor.submit(process_person, name, TMDB_API_KEY, OUTPUT_ROOT_DIR): name
                   for name in missing_people_names}

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
                elif result["search_status"] == "no_profile_path":
                    skipped_no_profile_img += 1
                    print(f"跳过: '{name}' 在 TMDb 上找到，但无个人资料图片。")
                elif result["search_status"] == "found":
                    if result["download_status"] == "success":
                        downloaded_count += 1
                        # print(f"成功: '{name}' 图片已下载。") # 避免与成功下载的函数内的print重复，或移除函数内的print
                    elif result["download_status"] == "already_exists":
                        skipped_already_exists += 1
                        # print(f"跳过: '{name}' 图片已存在。") # 避免与成功下载的函数内的print重复，或移除函数内的print
                    elif result["download_status"] == "download_error":
                        image_download_error_count += 1
                        print(f"错误: '{name}' 图片下载失败。")

            except Exception as exc:
                print(f"'{name}' 生成了一个异常: {exc}")
                api_search_error_count += 1 # 捕获任何未预料的异常

            # 打印进度 (每处理一定数量的请求)
            if processed_count % 50 == 0:
                print(f"\n--- 进度: 已处理 {processed_count}/{len(missing_people_names)} 个姓名 ---")
                print(f"已下载: {downloaded_count}, 未找到: {skipped_no_tmdb_match}, 无图: {skipped_no_profile_img}, 已存在: {skipped_already_exists}, 错误: {api_search_error_count + image_download_error_count}")
                # 可以在这里添加一个较长的暂停，如果发现有API速率限制问题
                # time.sleep(1) # 如果需要，取消注释此行，但对于多线程可能效果不如单线程明显

    print(f"\n--- 处理完成 ---")
    print(f"总计处理姓名: {processed_count}")
    print(f"成功下载图片: {downloaded_count}")
    print(f"跳过 (TMDb 未找到): {skipped_no_tmdb_match}")
    print(f"跳过 (TMDb 上无个人资料图片): {skipped_no_profile_img}")
    print(f"跳过 (图片本地已存在): {skipped_already_exists}")
    print(f"API 搜索错误: {api_search_error_count}")
    print(f"图片下载错误: {image_download_error_count}")

if __name__ == "__main__":
    main()