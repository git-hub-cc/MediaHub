import os
import chardet
import codecs # 用于处理BOM

def convert_nfo_to_gbk(filepath):
    """
    检查NFO文件的编码，如果是UTF-8则转换为GBK。
    尝试修复转换过程中可能出现的乱码。
    """
    print(f"\n--- 处理文件: {filepath} ---")

    try:
        # 1. 读取文件内容为字节
        with open(filepath, 'rb') as f:
            raw_content = f.read()

        # 2. 使用chardet检测编码
        result = chardet.detect(raw_content)
        detected_encoding = result['encoding']
        confidence = result['confidence']

        print(f"  检测到编码: {detected_encoding} (置信度: {confidence:.2f})")

        # 3. 判断是否需要转换
        if detected_encoding and detected_encoding.lower() == 'utf-8':
            if confidence < 0.9: # 对低置信度的UTF-8发出警告
                print("  警告: UTF-8置信度较低，转换可能存在风险。")

            # 移除UTF-8 BOM，如果存在的话
            if raw_content.startswith(codecs.BOM_UTF8):
                raw_content = raw_content[len(codecs.BOM_UTF8):]
                print("  已移除UTF-8 BOM。")

            try:
                # 尝试以UTF-8解码
                content_str = raw_content.decode('utf-8')

                try:
                    # 尝试以GBK编码，如果遇到GBK不支持的字符，使用 'replace' 策略
                    # 'replace' 会将无法编码的字符替换为问号 '?' 或默认替换字符
                    converted_content_bytes = content_str.encode('gbk', errors='replace')

                    # 检查是否有字符被替换（简单的启发式判断）
                    # 注意：如果原始UTF-8字符串包含 '?'，这个判断会误报
                    # 更精确的判断需要比较原始字符串和GBK编码后解码回来的字符串
                    if '?' in content_str and '?' not in converted_content_bytes.decode('gbk', errors='ignore'):
                         # 这是一个非常粗略的检查，可能不准确
                        pass
                    elif b'?' in converted_content_bytes and '?' not in content_str:
                         print("  注意: 转换到GBK时，部分UTF-8字符无法映射，已被替换。")

                    # 写入转换后的内容
                    with open(filepath, 'wb') as f:
                        f.write(converted_content_bytes)
                    print("  成功将文件从UTF-8转换为GBK。")

                except UnicodeEncodeError as e:
                    print(f"  错误: 无法将UTF-8内容编码为GBK。可能包含GBK不支持的字符。{e}")
                    print("  文件未被修改。")

            except UnicodeDecodeError as e:
                print(f"  错误: 文件被chardet检测为UTF-8，但实际解码失败。可能不是纯粹的UTF-8编码。{e}")
                print("  文件未被修改。")

        elif detected_encoding and detected_encoding.lower() == 'gbk':
            print("  文件已经是GBK编码，无需转换。")
        else:
            print(f"  文件编码为 {detected_encoding}，不进行处理。")

    except Exception as e:
        print(f"  处理 {filepath} 时发生未知错误: {e}")

def main():
    print("NFO文件编码检查与转换工具")
    print("-----------------------------------")
    print("本工具将遍历当前目录及其子目录，检查所有.nfo文件。")
    print("如果文件被检测为UTF-8编码，则尝试将其转换为GBK编码。")
    print("在转换过程中，对于GBK无法表示的UTF-8字符，将替换为问号。")
    print("转换前请务必备份您的NFO文件！\n")

    confirm = input("是否继续执行？(y/n): ").lower()
    if confirm != 'y':
        print("操作已取消。")
        return

    nfo_found_count = 0
    converted_count = 0

    for root, _, files in os.walk('.'): # 遍历当前目录及子目录
        for file in files:
            if file.lower().endswith('.nfo'):
                nfo_found_count += 1
                full_path = os.path.join(root, file)
                # 调用处理函数
                convert_nfo_to_gbk(full_path)
                # 简单计数，后续可以根据日志判断是否真正转换成功
                # converted_count += 1 # 如果你想只统计成功转换的，需要修改convert_nfo_to_gbk返回状态

    print("\n-----------------------------------")
    print(f"扫描完成。共找到 {nfo_found_count} 个 .nfo 文件。")
    print("请查看上方输出日志，了解每个文件的处理情况。")
    print("强烈建议您手动检查转换后的文件，确保内容完整无误。")

if __name__ == "__main__":
    main()