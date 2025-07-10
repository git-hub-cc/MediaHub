import os
import json
import xml.etree.ElementTree as ET
from datetime import datetime

# --- 新增: NFO解析函数 (无变化) ---
def parse_nfo(nfo_path):
    """解析.nfo文件，提取关键元数据。"""
    try:
        tree = ET.parse(nfo_path)
        root = tree.getroot()

        # 辅助函数，安全地获取文本内容
        def get_text(element_name):
            element = root.find(element_name)
            return element.text if element is not None and element.text else ''

        # 提取演员信息，包括姓名和角色
        actors = [
            {
                "name": actor.find('name').text if actor.find('name') is not None else '',
                "role": actor.find('role').text if actor.find('role') is not None else ''
            }
            for actor in root.findall('actor')
        ]

        # 提取合集信息
        set_info = root.find('set')
        collection_name = set_info.find('name').text if set_info is not None and set_info.find('name') is not None else ''

        # 汇总数据
        data = {
            "plot": get_text('plot'),
            "year": int(get_text('year')) if get_text('year').isdigit() else None,
            "rating": float(get_text('rating')) if get_text('rating') else None,
            "runtime": int(get_text('runtime')) if get_text('runtime').isdigit() else None,
            "genres": [g.text for g in root.findall('genre')],
            "studios": [s.text for s in root.findall('studio')],
            "collection": collection_name,
            "actors": actors
        }
        return data
    except (ET.ParseError, FileNotFoundError, AttributeError) as e:
        print(f"    ❗️ 解析NFO文件 '{os.path.basename(nfo_path)}' 时出错: {e}")
        return None

def summarize_media_library(root_dir, output_file='movie_summary.json'):
    print(f"🚀 开始扫描媒体库: {root_dir}")
    current_working_dir = os.getcwd()

    movie_database = []
    required_keys = {'strm', 'nfo', 'poster', 'fanart'}

    for root, dirs, files in os.walk(root_dir):
        # 简单判断是否是媒体文件夹（包含nfo文件）
        if any(f.lower().endswith('.nfo') for f in files):
            title = os.path.basename(root)
            print(f"  🔍 发现影视目录: {title}")

            file_group = {}

            # --- 核心改动开始 ---
            # 1. 优先处理NFO文件，实现'movie.nfo'优先
            nfo_files_in_dir = [f for f in files if f.lower().endswith('.nfo')]
            preferred_nfo_filename = None

            # 2. 查找 'movie.nfo'
            for f in nfo_files_in_dir:
                if f.lower() == 'movie.nfo':
                    preferred_nfo_filename = f
                    break

            # 3. 如果没有 'movie.nfo'，则使用找到的第一个NFO文件作为备选
            if not preferred_nfo_filename and nfo_files_in_dir:
                preferred_nfo_filename = nfo_files_in_dir[0]

            # 4. 如果确定了要使用的NFO文件，则记录其路径
            if preferred_nfo_filename:
                print(f"    - 选定NFO: {preferred_nfo_filename}")
                full_nfo_path = os.path.join(root, preferred_nfo_filename)
                file_group['nfo'] = os.path.relpath(full_nfo_path, current_working_dir).replace(os.path.sep, '/')
            # --- 核心改动结束 ---

            # 遍历所有文件，填充其他文件类型 (strm, poster, fanart)
            for filename in files:
                lower_filename = filename.lower()
                full_file_path = os.path.join(root, filename)
                relative_path = os.path.relpath(full_file_path, current_working_dir).replace(os.path.sep, '/')

                if lower_filename.endswith('.strm'):
                    file_group['strm'] = relative_path
                elif lower_filename == 'poster.jpg':
                    file_group['poster'] = relative_path
                elif lower_filename == 'fanart.jpg':
                    file_group['fanart'] = relative_path

            # 检查是否所有必需文件都已找到
            if required_keys.issubset(file_group.keys()):
                nfo_data = parse_nfo(os.path.join(current_working_dir, file_group['nfo']))
                if nfo_data:
                    movie_info = {
                        'title': title,
                        'files': file_group,
                        'metadata': nfo_data
                    }
                    movie_database.append(movie_info)
                else:
                    print(f"    ❌ 因NFO解析失败，跳过: {title}")
            elif file_group:
                missing_keys = required_keys - set(file_group.keys())
                print(f"    ⚠️  跳过不完整的资源集: {title}. 缺少: {', '.join(sorted(missing_keys))}")

            dirs[:] = [] # 停止深入

    print("-" * 30)
    if movie_database:
        # 按年份降序排序
        movie_database.sort(key=lambda x: (x.get('metadata', {}).get('year') or 0), reverse=True)

        print(f"✅ 扫描完成！共找到 {len(movie_database)} 个符合条件的影视资源。")
        output_path = os.path.join(current_working_dir, output_file)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(movie_database, f, ensure_ascii=False, indent=4)
        print(f"💾 汇总信息已成功保存到: {output_path}")
    else:
        print("🤷‍♂️ 未找到任何符合条件的影视资源目录。")

if __name__ == "__main__":
    start_directory = os.path.join(os.getcwd(), 'all')
    if not os.path.isdir(start_directory):
        print(f"提示: 目标目录 '{start_directory}' 不存在，请确保路径正确。")
    else:
        summarize_media_library(start_directory)