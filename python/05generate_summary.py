import os

# --- 配置 ---
# 要生成的Markdown文件名
OUTPUT_FILENAME = "部分内容.md"
# 每个文件最多读取的行数
MAX_LINES = 100
# --- 配置结束 ---

def generate_file_summary():
    """
    扫描当前目录中的所有文件，并创建一个包含其部分内容的Markdown摘要文件。
    """
    # 获取当前脚本的文件名，以避免读取自身
    try:
        # 在正常运行脚本时，__file__ 会被定义
        current_script_name = os.path.basename(__file__)
    except NameError:
        # 如果在交互式解释器中运行，__file__ 可能未定义
        current_script_name = ""

    # 使用 'with' 语句安全地打开（或创建）输出文件
    # encoding='utf-8' 对于处理中文文件名和内容至关重要
    with open(OUTPUT_FILENAME, 'w', encoding='utf-8') as md_file:
        # 写入Markdown文件的总标题
        md_file.write("# 当前目录文件内容摘要\n\n")
        print(f"开始生成摘要文件: {OUTPUT_FILENAME}")

        # 获取当前目录下的所有文件和文件夹，并排序
        # 使用 sorted() 可以让输出的文件顺序更可预测
        for filename in sorted(os.listdir('.')):
            # 检查当前项是否为文件，并且不是脚本自身或输出文件
            if os.path.isfile(filename) and filename not in [current_script_name, OUTPUT_FILENAME]:
                print(f"正在处理: {filename}...")

                # 将文件名作为二级标题写入
                md_file.write(f"## {filename}\n\n")

                try:
                    # 尝试以UTF-8编码读取文件
                    with open(filename, 'r', encoding='utf-8') as content_file:
                        # 写入Markdown代码块的起始标记
                        md_file.write("```\n")

                        line_count = 0
                        for line in content_file:
                            if line_count >= MAX_LINES:
                                md_file.write("... (内容超过100行，已截断)\n")
                                break
                            md_file.write(line)
                            line_count += 1

                        # 写入Markdown代码块的结束标记
                        md_file.write("\n```\n\n")

                except (UnicodeDecodeError, PermissionError):
                    # 如果文件不是UTF-8编码（如图片、压缩包等二进制文件）或没有读取权限
                    md_file.write("`[无法读取内容：可能是二进制文件或无读取权限]`\n\n")
                except Exception as e:
                    # 捕获其他可能的读取错误
                    md_file.write(f"`[读取时发生未知错误: {e}]`\n\n")

    print(f"\n处理完成！摘要文件 '{OUTPUT_FILENAME}' 已生成。")

if __name__ == "__main__":
    generate_file_summary()