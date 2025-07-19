import os
from collections import Counter

def find_most_common_non_jpg_images(directory="."):
    """
    筛选指定目录及其子目录中所有非 JPG/JPEG 图片，
    统计出最多的文件名，并按多到少排序输出。

    Args:
        directory (str): 要扫描的起始目录。默认为当前目录。
    """

    # 定义常见的图片扩展名，不包含 .jpg 和 .jpeg
    # 注意：所有扩展名都小写，以确保不区分大小写地匹配
    image_extensions = {
        ".png", ".gif", ".bmp", ".tiff", ".tif", ".webp", ".svg", ".heic", ".heif"
    }

    # 用于存储所有符合条件的图片文件名（不包含路径）
    image_basenames = []

    print(f"正在扫描目录：{os.path.abspath(directory)}")
    print("-" * 30)

    # 遍历指定目录及其所有子目录
    for root, _, files in os.walk(directory):
        for filename in files:
            # 分离文件名和扩展名
            name, ext = os.path.splitext(filename)
            ext_lower = ext.lower() # 将扩展名转换为小写进行比较

            # 检查扩展名是否在我们定义的图片扩展名列表中
            if ext_lower in image_extensions:
                # 如果是，将文件名（不包含路径）添加到列表中
                # os.path.basename(filename) 在这里是多余的，因为 filename 本身就是 basename
                # 但为了清晰起见，保留它表示我们只关心文件名部分
                image_basenames.append(os.path.basename(filename))

    # 使用 Counter 统计每个文件名出现的次数
    filename_counts = Counter(image_basenames)

    print("\n统计结果 (非 JPG/JPEG 图片文件名及其出现次数)：")
    print("-" * 50)

    if not filename_counts:
        print("未找到任何符合条件的图片文件。")
    else:
        # most_common() 方法返回一个列表，其中包含元素和它们的计数，
        # 按照计数从高到低排序
        for filename, count in filename_counts.most_common():
            print(f"'{filename}': {count} 次")

    print("-" * 50)

if __name__ == "__main__":
    # 运行脚本，默认扫描当前目录
    find_most_common_non_jpg_images()

    # 如果你想扫描其他目录，可以这样调用：
    # find_most_common_non_jpg_images("/path/to/your/images")