import os
from PIL import Image

# --- !!! 警告 !!! ---
# 请注意，此脚本会直接覆盖你的原始图片文件。
# 在运行脚本之前，请务必备份你的图片！
# 一旦覆盖，原始的、更高质量/尺寸的图片将无法恢复。
# --- !!! 警告 !!! ---

# --- 配置参数 ---
TARGET_WIDTH = 200  # 目标宽度 (px)
# 支持的图片扩展名 (不区分大小写)
IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff']
# --- /配置参数 ---

def compress_image(image_path, target_width):
    """
    压缩单个图片文件到指定宽度，并保持宽高比，然后覆盖原文件。
    """
    try:
        with Image.open(image_path) as img:
            original_width, original_height = img.size

            # 如果原始宽度小于或等于目标宽度，则不处理
            if original_width <= target_width:
                print(f"  跳过 '{image_path}': 宽度 ({original_width}px) 已小于或等于目标宽度 ({target_width}px)。")
                return False # 表示未进行实际压缩

            # 计算新的高度以保持宽高比
            new_height = int(original_height * (target_width / original_width))
            new_dimensions = (target_width, new_height)

            # 使用Lanczos采样进行高质量缩放 (适用于缩小)
            img = img.resize(new_dimensions, Image.Resampling.LANCZOS)

            # 根据图片格式选择保存参数以优化文件大小
            file_extension = os.path.splitext(image_path)[1].lower()

            # 保存到原文件路径，覆盖原文件
            if file_extension in ['.jpg', '.jpeg']:
                # 对于JPEG，使用85%质量和优化，以及渐进式编码
                # 质量参数范围 1-95，85通常是很好的平衡点
                img.save(image_path, quality=85, optimize=True, progressive=True)
            elif file_extension == '.png':
                # 对于PNG，使用optimize=True进行无损压缩
                img.save(image_path, optimize=True)
            else:
                # 对于其他格式，直接保存
                img.save(image_path)

            print(f"  成功压缩并覆盖 '{image_path}' ({original_width}x{original_height} -> {new_dimensions[0]}x{new_dimensions[1]})")
            return True # 表示成功压缩
    except FileNotFoundError:
        print(f"  错误: 未找到文件 '{image_path}'")
        return False
    except Exception as e:
        print(f"  处理 '{image_path}' 时发生错误: {e}")
        return False

def main():
    """
    主函数，遍历目录并压缩图片。
    """
    current_dir = os.getcwd()

    print(f"--- !!! 警告 !!! ---")
    print(f"此脚本将直接压缩并覆盖当前目录 '{current_dir}' 及其所有子目录下的原始图片文件。")
    print(f"在运行脚本之前，请务必备份你的图片！")
    print(f"--- !!! 警告 !!! ---")
    print(f"\n开始压缩图片...")
    print(f"目标宽度: {TARGET_WIDTH}px")

    processed_count = 0
    skipped_count = 0
    error_count = 0

    # 遍历当前目录及其所有子目录
    for root, _, files in os.walk(current_dir):
        for file in files:
            file_path = os.path.join(root, file)
            file_extension = os.path.splitext(file_path)[1].lower()

            if file_extension in IMAGE_EXTENSIONS:
                if compress_image(file_path, TARGET_WIDTH):
                    processed_count += 1
                else:
                    # compress_image返回False表示跳过或错误
                    if "已小于或等于目标宽度" in (f"  跳过 '{file_path}': 宽度" if "跳过" in f"  跳过 '{file_path}': 宽度" else ""):
                         skipped_count += 1 # 如果是因为宽度不足而跳过
                    else:
                        error_count += 1 # 否则就是错误
            # else:
            #     print(f"跳过非图片文件: {file_path}") # 如果需要显示跳过的非图片文件

    print("\n--- 压缩完成 ---")
    print(f"共处理图片: {processed_count} 张 (已覆盖原文件)")
    print(f"跳过图片: {skipped_count} 张 (原图宽度已小于目标宽度)")
    print(f"处理失败图片: {error_count} 张")
    print("请检查你的目录以确认结果。")

if __name__ == "__main__":
    main()