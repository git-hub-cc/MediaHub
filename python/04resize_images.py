import os
from PIL import Image

# --- !!! 警告 !!! ---
# 请注意，此脚本会直接覆盖你的原始图片文件。
# 在运行脚本之前，请务必备份你的图片！
# 一旦覆盖，原始的、更高质量/尺寸的图片将无法恢复。
# --- !!! 警告 !!! ---

# --- 配置参数 ---
TARGET_HEIGHT = 50  # 目标高度 (px)
TARGET_FILENAME = "landscape.jpg" # 指定要查找和压缩的文件名
# 支持的图片扩展名 (用于compress_image内部的健壮性检查)
IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff']
# --- /配置参数 ---

def compress_image(image_path, target_height):
    """
    压缩单个图片文件到指定高度，并保持宽高比，然后覆盖原文件。
    此函数现在返回一个字符串表示操作结果："compressed", "skipped", "error"。
    """
    try:
        # 确保文件存在
        if not os.path.exists(image_path):
            print(f"  错误: 未找到文件 '{image_path}'")
            return "error"

        # 获取文件扩展名
        file_extension = os.path.splitext(image_path)[1].lower()

        # --- 新增：跳过PNG格式的文件 ---
        if file_extension == '.png':
            print(f"  跳过 '{image_path}': 格式为 PNG，按要求跳过。")
            return "skipped"

        # 检查文件扩展名是否符合预期
        if file_extension not in IMAGE_EXTENSIONS:
            print(f"  错误: '{image_path}' 的扩展名不是支持的图片格式。跳过。")
            return "error"

        with Image.open(image_path) as img:
            original_width, original_height = img.size

            # 如果原始高度小于或等于目标高度，则不处理
            if original_height <= target_height:
                print(f"  跳过 '{image_path}': 高度 ({original_height}px) 已小于或等于目标高度 ({target_height}px)。")
                return "skipped"

            # 计算新的宽度以保持宽高比
            new_width = int(original_width * (target_height / original_height))
            new_dimensions = (new_width, target_height)

            # 使用Lanczos采样进行高质量缩放 (适用于缩小)
            img = img.resize(new_dimensions, Image.Resampling.LANCZOS)

            # --- 修复: 强制将各种模式转换为JPEG兼容模式 (RGB/L)，并处理透明度 ---

            # 第一步：处理P模式。如果P模式有透明度，先转为RGBA；否则转为RGB。
            if img.mode == 'P':
                # 'transparency' in img.info 可以检查调色板是否有透明度信息
                if 'transparency' in img.info or img.getpalette() and len(img.getpalette()) > 768:
                    # 如果有透明度或调色板过大（可能暗示RGBA调色板），转换为RGBA
                    img = img.convert('RGBA')
                else:
                    # 没有透明度的P模式，直接转换为RGB
                    img = img.convert('RGB')

            # 第二步：处理所有带有Alpha通道的模式 (RGBA, LA)
            # 在此之后，如果图像是RGBA或LA，意味着它有透明度需要处理
            if img.mode == 'RGBA':
                # 将RGBA转换为RGB，透明部分填充为白色
                background = Image.new('RGB', img.size, (255, 255, 255))
                background.paste(img, (0, 0), img) # img 作为掩码
                img = background
            elif img.mode == 'LA':
                # 将LA转换为L (灰度)，透明部分填充为白色 (255)
                # L 模式的白色是 255
                background = Image.new('L', img.size, 255)
                background.paste(img, (0, 0), img) # img 作为掩码
                img = background

            # 第三步：最终确保图像模式是RGB或L。
            # 如果经过上述处理后，图像仍然不是RGB或L (例如：CMYK, 1, I等其他不常见模式)
            # 则强制转换为RGB，以兼容JPEG保存。
            if img.mode not in ('RGB', 'L'):
                img = img.convert('RGB')

            # 根据图片格式选择保存参数以优化文件大小
            # 注意：由于上方已跳过PNG，此处的PNG保存逻辑实际上不会被执行，但保留以防将来修改需求
            if file_extension in ['.jpg', '.jpeg']:
                # 对于JPEG，使用85%质量和优化，以及渐进式编码
                img.save(image_path, quality=85, optimize=True, progressive=True)
            elif file_extension == '.png': # 此分支理论上不会被触发，因为PNG已被提前跳过
                # 对于PNG，使用optimize=True进行无损压缩
                img.save(image_path, optimize=True)
            else:
                # 对于其他格式，直接保存
                img.save(image_path)

            print(f"  成功压缩并覆盖 '{image_path}' ({original_width}x{original_height} -> {new_dimensions[0]}x{new_dimensions[1]})")
            return "compressed"
    except Exception as e:
        print(f"  处理 '{image_path}' 时发生错误: {e}")
        return "error"

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
    print(f"目标高度: {TARGET_HEIGHT}px")

    compressed_count = 0
    skipped_count = 0
    error_count = 0
    files_found_count = 0

    # 遍历当前目录及其所有子目录
    for root, _, files in os.walk(current_dir):
        for file in files:
            # 检查文件名是否与 TARGET_FILENAME 匹配 (不区分大小写)
            if file.lower() == TARGET_FILENAME.lower():
                files_found_count += 1
                file_path = os.path.join(root, file)
                print(f"\n正在处理文件: {file_path}")

                result = compress_image(file_path, TARGET_HEIGHT)
                if result == "compressed":
                    compressed_count += 1
                elif result == "skipped":
                    skipped_count += 1
                elif result == "error":
                    error_count += 1

    print("\n--- 压缩完成 ---")
    if files_found_count == 0:
        print(f"未在 '{current_dir}' 及其子目录中找到任何名为 '{TARGET_FILENAME}' 的文件。")
    else:
        print(f"总共找到 '{TARGET_FILENAME}' 文件: {files_found_count} 个")
        print(f"成功压缩并覆盖: {compressed_count} 个")
        print(f"跳过 (原图高度已小于目标高度 或 格式为PNG): {skipped_count} 个")
        print(f"处理失败: {error_count} 个")
    print("请检查你的目录以确认结果。")

if __name__ == "__main__":
    main()