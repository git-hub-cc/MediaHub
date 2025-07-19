import os
import sys

def delete_specific_jpg_files(start_directory):
    """
    扫描指定目录及其子目录，删除所有是 JPG/JPEG 文件，但不是
    'folder.jpg', 'poster.jpg', 'fanart.jpg', 'banner.jpg', 'landscape.jpg'
    的文件。

    Args:
        start_directory (str): 开始搜索的目录路径。
    """
    # 检查起始目录是否存在且是一个目录
    if not os.path.isdir(start_directory):
        print(f"错误：'{start_directory}' 不是一个有效的目录。请提供一个存在的目录。")
        return

    # 定义要保留的文件名（不区分大小写）
    # 使用集合(set)进行快速查找
    files_to_keep = {
        'folder.jpg',
        'poster.jpg',
        'fanart.jpg',
        'banner.jpg',
        'landscape.jpg',
        'thumb.jpg',
        'cover.jpg',
        'background.jpg',
        'season-specials-poster.jpg',
        'movie.jpg',
        'keyart.jpg',
        'movieset-poster.jpg',
        'backdrop.jpg',
        'movieset-fanart.jpg'
    }

    jpg_extensions = ('.jpg', '.jpeg')
    deleted_count = 0
    skipped_count = 0
    error_count = 0

    print(f"正在扫描 '{start_directory}' 及其子目录中的JPG/JPEG文件进行删除...")
    print(f"以下文件将被跳过 (不区分大小写): {', '.join(files_to_keep)}")
    print("-" * 60)

    for root, _, files in os.walk(start_directory):
        for file_name in files:
            # 1. 检查文件是否是JPG/JPEG
            if file_name.lower().endswith(jpg_extensions):
                # 2. 提取不含路径的文件名并转换为小写，以便与 files_to_keep 集合中的名称进行比较
                base_name = os.path.basename(file_name).lower()

                # 3. 检查文件是否在要保留的列表中
                if base_name in files_to_keep:
                    print(f"跳过: {os.path.join(root, file_name)} (保留文件)")
                    skipped_count += 1
                else:
                    # 这是要删除的文件
                    full_path = os.path.join(root, file_name)
                    try:
                        os.remove(full_path)
                        print(f"已删除: {full_path}")
                        deleted_count += 1
                    except OSError as e:
                        print(f"错误: 无法删除文件 {full_path} - {e}")
                        error_count += 1
    
    print("-" * 60)
    print(f"操作完成！")
    print(f"总计删除文件: {deleted_count}")
    print(f"总计跳过文件: {skipped_count}")
    if error_count > 0:
        print(f"删除失败文件: {error_count} (请检查权限或文件是否被占用)")

if __name__ == "__main__":
    # 允许用户通过命令行参数指定目录
    # 如果没有提供参数，则默认为当前工作目录 '.'
    if len(sys.argv) > 1:
        target_directory = sys.argv[1]
    else:
        target_directory = '.' # 当前目录

    # 调用函数执行删除操作
    delete_specific_jpg_files(target_directory)