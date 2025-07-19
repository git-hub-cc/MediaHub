import os
import sys

# --- 配置区 ---
# 定义要删除的图片文件名列表 (所有输入文件名都会被转换为小写进行匹配)
# 注意：这里的列表只包含文件名，不包含路径
FILENAMES_TO_DELETE = { # 使用集合 (set) 可以提高查找效率
    'clearlogo.png',
    'logo.png',
    'clearart.png',
    'discart.png',
    'disc.png',
    'characterart.png',
    'folder.png',
    'poster.png',
    'fanart.png',
    '阿里云盘资源共享群二维码.png',
    'season02-poster.png',
    '习题1.png',
    '习题2.png',
    '1-2.png',
    'season01-poster.png',
    'season03-poster.png',
    '3-1.png',
    '3-2.png',
    '2-1.png',
    '2-2.png',
    'movieset-clearart.png',
    'movieset-clearlogo.png',
    'movieset-disc.png',
    'movieset-logo.png',
    '1-1.png',
    'thumb.png',
    'logo.svg',
    '顺序错乱恢复方法.png',
    '4-1.png',
    '4-2.png',
    'IMG_5997.PNG', # 注意：这里是PNG，不是png，但我们做了大小写不敏感处理
    'poster.webp',
    'S01E13.png',
    '文件信息.png',
    'logo.PNG',     # 注意：这里是PNG，不是png，但我们做了大小写不敏感处理
    '橘子搜索.png',
    '0.png',
    'design-ah.png',
    'FomalhautABC.png'
}

# 将所有文件名转换为小写，确保后续匹配时大小写不敏感
FILENAMES_TO_DELETE_LOWER = {f.lower() for f in FILENAMES_TO_DELETE}

START_DIRECTORY = "."  # 从当前目录开始扫描，可以修改为其他路径，例如 "/path/to/your/images"

# --- 操作模式设置 (非常重要!) ---
DRY_RUN = False         # 默认为 True (试运行模式)。如果为 True，则只打印将要删除的文件，不实际删除。
                       # 设为 False 才会实际删除文件！
CONFIRM_DELETION = True # 在实际删除前是否要求用户确认 (仅在 DRY_RUN 为 False 时生效)。
# -----------------------------

def delete_specified_images(directory, filenames_to_delete_lower, dry_run=True, confirm=True):
    """
    在指定目录及其子目录中查找并删除特定文件名的图片。

    Args:
        directory (str): 要扫描的起始目录。
        filenames_to_delete_lower (set): 包含要删除的图片文件名的集合 (小写)。
        dry_run (bool): 如果为 True，则只模拟删除并打印信息，不实际删除文件。
        confirm (bool): 如果为 True 并且不是 dry_run，则在删除前要求用户确认。
    """
    print(f"模式: {'试运行' if dry_run else '实际删除文件'}")
    print(f"正在扫描目录：{os.path.abspath(directory)}")
    print(f"将要处理的文件名 (不区分大小写)：{sorted(list(filenames_to_delete_lower))}")
    print("-" * 50)

    deleted_count = 0
    skipped_count = 0
    error_count = 0
    found_in_dry_run = [] # 用于在试运行模式下记录找到的文件

    if not dry_run and confirm:
        user_input = input("\n警告：此操作将实际删除文件！您确定要继续吗？(输入 'yes' 继续): ").lower()
        if user_input != 'yes':
            print("操作已取消。")
            sys.exit() # 退出脚本

    for root, _, files in os.walk(directory):
        for filename in files:
            # 获取文件的基本名并转换为小写，以便进行大小写不敏感的匹配
            basename_lower = os.path.basename(filename).lower()

            if basename_lower in filenames_to_delete_lower:
                full_path = os.path.join(root, filename)
                if dry_run:
                    print(f"[试运行] 将删除：{full_path}")
                    found_in_dry_run.append(full_path)
                    skipped_count += 1 # 在试运行中，这些文件被“跳过”了实际删除
                else:
                    try:
                        os.remove(full_path)
                        print(f"[已删除]：{full_path}")
                        deleted_count += 1
                    except FileNotFoundError:
                        print(f"[错误] 文件未找到 (可能已被删除)：{full_path}")
                        error_count += 1
                    except PermissionError:
                        print(f"[错误] 权限不足，无法删除：{full_path}")
                        error_count += 1
                    except Exception as e:
                        print(f"[错误] 删除 {full_path} 时发生未知错误: {e}")
                        error_count += 1
            # else:
            #     # 如果你想看到哪些文件被跳过（不在删除列表中），可以取消下面一行的注释
            #     print(f"跳过：{filename} (不在删除列表中)")

    print("\n" + "=" * 50)
    print("操作总结：")
    print(f"扫描目录: {os.path.abspath(directory)}")
    if dry_run:
        print(f"在试运行模式下，共找到 {len(found_in_dry_run)} 个匹配文件。")
        print("未实际删除任何文件。")
    else:
        print(f"成功删除文件数量: {deleted_count}")
        print(f"因错误跳过的文件数量: {error_count}")
    print("请注意：如果文件有特殊权限或正在使用中，可能无法删除。")
    print("=" * 50)

if __name__ == "__main__":
    print("--- 图片文件批量删除工具 ---")
    print("请仔细检查脚本顶部的 'DRY_RUN' 和 'CONFIRM_DELETION' 配置！")
    print(f"当前 DRY_RUN 设置: {DRY_RUN}")
    print(f"当前 CONFIRM_DELETION 设置: {CONFIRM_DELETION}")
    print("-" * 50)

    # 运行主函数
    delete_specified_images(START_DIRECTORY, FILENAMES_TO_DELETE_LOWER, DRY_RUN, CONFIRM_DELETION)

    if DRY_RUN:
        print("\n!!! 脚本当前处于 '试运行' 模式 (DRY_RUN = True)。")
        print("!!! 文件未实际删除。")
        print("!!! 如果要实际删除文件，请将脚本顶部的 'DRY_RUN' 设置为 'False' 并再次运行。")