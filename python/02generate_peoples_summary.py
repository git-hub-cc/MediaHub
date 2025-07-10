# -*- coding: utf-8 -*-
import os
import json

def create_path_map(root_dir, target_filename='folder.jpg', ignore_dirs=None, ignore_files=None):
    """
    遍历指定目录，查找目标文件，并生成一个扁平的 JSON 映射。

    这个版本会忽略指定的目录和文件。

    :param root_dir: 要遍历的根目录路径。
    :param target_filename: 要查找的目标文件名（不区分大小写）。
    :param ignore_dirs: 一个包含要忽略的目录名的集合。
    :param ignore_files: 一个包含要忽略的文件名的集合。
    :return: 一个代表路径映射的字典。
    """
    if ignore_dirs is None:
        ignore_dirs = set()
    if ignore_files is None:
        ignore_files = set()

    path_map = {}

    for dirpath, dirnames, filenames in os.walk(root_dir):
        dirnames[:] = [d for d in dirnames if d not in ignore_dirs]

        for filename in filenames:
            if filename.lower() == target_filename.lower():
                key = os.path.basename(dirpath)

                full_file_path = os.path.join(dirpath, filename)
                relative_path = os.path.relpath(full_file_path, root_dir)

                value = relative_path.replace(os.sep, '/')

                path_map[key] = value

                break

    return path_map

if __name__ == "__main__":
    try:
        script_path = os.path.dirname(os.path.abspath(__file__))
    except NameError:
        script_path = os.getcwd()

    root_directory = script_path
    print(f"--- 正在扫描根目录: {root_directory} ---")

    dirs_to_ignore = {'.git', '.idea', '__pycache__'}

    file_map = create_path_map(
        root_dir=root_directory,
        target_filename='folder.jpg',
        ignore_dirs=dirs_to_ignore
    )

    if file_map:
        sorted_file_map = dict(sorted(file_map.items()))
        json_output = json.dumps(sorted_file_map, indent=4, ensure_ascii=False)

        print("\n--- 生成的 JSON 结构 ---")
        print(json_output)

        output_filename = 'people_summary.json'
        try:
            # 在Python 2中，需要使用 io.open 来正确处理UTF-8写入
            import io
            with io.open(output_filename, 'w', encoding='utf-8') as f:
                # 在Python 2中，json.dumps需要一个额外参数来处理unicode
                # 但由于我们用了io.open，可以直接写入
                if isinstance(json_output, bytes):
                    # Python 3 dumps to str, Python 2 might dump to bytes
                    json_output = json_output.decode('utf-8')
                f.write(json_output)
            print(f"\n结果已成功保存到文件: {output_filename}")
        except IOError as e:
            print(f"\n保存文件时出错: {e}")
    else:
        print("\n在指定目录中未找到任何 'folder.jpg' 文件。")