import os
from PIL import Image

# --- !!! 警告 !!! ---
# 请注意，此脚本会直接覆盖你的原始图片文件。
# 在运行脚本之前，请务必备份你的图片！
# 一旦覆盖，原始的、更高质量/尺寸的图片将无法恢复。
# --- !!! 警告 !!! ---

# --- 配置参数 ---
TARGET_WIDTH = 200  # 目标宽度 (px)
TARGET_FILENAME = "poster.jpg" # 指定要查找和压缩的文件名
# 支持的图片扩展名 (用于compress_image内部的健壮性检查，TARGET_FILENAME已明确为.jpg)
IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff']
# --- /配置参数 ---

def compress_image(image_path, target_width):
    """
    压缩单个图片文件到指定宽度，并保持宽高比，然后覆盖原文件。
    此函数现在返回一个字符串表示操作结果："compressed", "skipped", "error"。
    """
    try:
        # 确保文件存在
        if not os.path.exists(image_path):
            print(f"  错误: 未找到文件 '{image_path}'")
            return "error"

        # 检查文件扩展名是否符合预期 (即使针对特定文件，也是个好习惯)
        file_extension = os.path.splitext(image_path)[1].lower()
        if file_extension not in IMAGE_EXTENSIONS:
            print(f"  错误: '{image_path}' 的扩展名不是支持的图片格式。跳过。")
            return "error" # 视为错误，因为它不是一个预期可处理的图片

        with Image.open(image_path) as img:
            original_width, original_height = img.size

            # 如果原始宽度小于或等于目标宽度，则不处理
            if original_width <= target_width:
                print(f"  跳过 '{image_path}': 宽度 ({original_width}px) 已小于或等于目标宽度 ({target_width}px)。")
                return "skipped" # 表示跳过

            # 计算新的高度以保持宽高比
            new_height = int(original_height * (target_width / original_width))
            new_dimensions = (target_width, new_height)

            # 使用Lanczos采样进行高质量缩放 (适用于缩小)
            img = img.resize(new_dimensions, Image.Resampling.LANCZOS)

            # 根据图片格式选择保存参数以优化文件大小

            # 保存到原文件路径，覆盖原文件
            if file_extension in ['.jpg', '.jpeg']:
                # 对于JPEG，使用85%质量和优化，以及渐进式编码
                img.save(image_path, quality=85, optimize=True, progressive=True)
            elif file_extension == '.png':
                # 对于PNG，使用optimize=True进行无损压缩
                img.save(image_path, optimize=True)
            else:
                # 对于其他格式，直接保存
                img.save(image_path)

            print(f"  成功压缩并覆盖 '{image_path}' ({original_width}x{original_height} -> {new_dimensions[0]}x{new_dimensions[1]})")
            return "compressed" # 表示成功压缩
    except Exception as e:
        print(f"  处理 '{image_path}' 时发生错误: {e}")
        return "error" # 表示发生错误

def main():
    """
    主函数，遍历当前目录及其子目录，查找并压缩所有名为 TARGET_FILENAME 的文件。
    """
    current_dir = os.getcwd()

    print(f"--- !!! 警告 !!! ---")
    print(f"此脚本将直接压缩并覆盖在当前目录 '{current_dir}' 及其所有子目录中找到的所有名为 '{TARGET_FILENAME}' 的文件。")
    print(f"在运行脚本之前，请务必备份你的图片！")
    print(f"--- !!! 警告 !!! ---")
    print(f"\n开始在 '{current_dir}' 及其子目录中查找并压缩 '{TARGET_FILENAME}'...")
    print(f"目标宽度: {TARGET_WIDTH}px")

    compressed_count = 0
    skipped_count = 0
    error_count = 0
    files_found_count = 0 # 实际找到的符合条件的文件数量

    # 遍历当前目录及其所有子目录
    for root, _, files in os.walk(current_dir):
        for file in files:
            # 检查文件名是否与 TARGET_FILENAME 匹配 (不区分大小写)
            if file.lower() == TARGET_FILENAME.lower():
                files_found_count += 1
                file_path = os.path.join(root, file)
                print(f"\n正在处理文件: {file_path}") # 在处理每个文件前打印一行，提供更好的进度反馈

                result = compress_image(file_path, TARGET_WIDTH)
                if result == "compressed":
                    compressed_count += 1
                elif result == "skipped":
                    skipped_count += 1
                elif result == "error":
                    error_count += 1
            # else:
            #     print(f"跳过非目标文件: {os.path.join(root, file)}") # 如果需要显示跳过的非目标文件

    print("\n--- 压缩完成 ---")
    if files_found_count == 0:
        print(f"未在 '{current_dir}' 及其子目录中找到任何名为 '{TARGET_FILENAME}' 的文件。")
    else:
        print(f"总共找到 '{TARGET_FILENAME}' 文件: {files_found_count} 个")
        print(f"成功压缩并覆盖: {compressed_count} 个")
        print(f"跳过 (原图宽度已小于目标宽度): {skipped_count} 个")
        print(f"处理失败: {error_count} 个")
    print("请检查你的目录以确认结果。")

if __name__ == "__main__":
    main()