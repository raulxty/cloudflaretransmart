import os
import subprocess
import sys
import time
import requests
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

# 检查并安装必要的库
try:
    import requests
except ImportError:
    print("检测到缺少 'requests' 库，正在安装...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests

try:
    import chardet
except ImportError:
    print("检测到缺少 'chardet' 库，正在安装...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "chardet"])
    import chardet

def detect_encoding(file_path):
    """
    检测文件的编码。
    
    :param file_path: 文件路径。
    :return: 文件的编码类型。
    """
    with open(file_path, 'rb') as f:
        raw_data = f.read()
        result = chardet.detect(raw_data)
        return result['encoding']

def read_file_with_fallback_encodings(file_path, fallback_encodings=['utf-8', 'gbk', 'gb18030']):
    """
    尝试使用多个编码读取文件内容。
    
    :param file_path: 文件路径。
    :param fallback_encodings: 备选编码列表。
    :return: 文件内容。
    """
    detected_encoding = detect_encoding(file_path)
    encodings_to_try = [detected_encoding] + fallback_encodings
    
    for encoding in encodings_to_try:
        try:
            with open(file_path, 'r', encoding=encoding) as file:
                content = file.readlines()  # 逐行读取文件内容
            print(f"成功使用编码 {encoding} 读取文件 {file_path}")
            return content
        except UnicodeDecodeError:
            if encoding == encodings_to_try[-1]:
                raise
            continue

def translate_text_segment(text, source_lang, target_lang, secret_pass, retries=2, delay=5):
    """
    使用 Cloudflare Worker 将给定的文本段落从源语言翻译为目标语言。
    
    :param text: 需要翻译的文本段落。
    :param source_lang: 源语言代码（例如 'en' 表示英语）。
    :param target_lang: 目标语言代码（例如 'fr' 表示法语）。
    :param secret_pass: 访问密钥。
    :param retries: 重试次数。
    :param delay: 重试间隔时间（秒）。
    :return: 翻译后的文本段落。
    """
    if not text.strip():
        print("翻译文本为空，跳过此段落")
        return ""
    
    url = "https://trans.zhbook.store/"  # 你的 Cloudflare Worker 的 URL
    data = {
        'text': text,
        'source_language': source_lang[:2],  # 确保只取前两个字符
        'target_language': target_lang[:2],  # 确保只取前两个字符
        'secret': secret_pass
    }
    headers = {
        'Content-Type': 'application/json'
    }
    
    attempt = 0
    while attempt <= retries:
        try:
            response = requests.post(url, json=data, headers=headers, timeout=30, verify=False)  # 使用 POST 请求并禁用 SSL 验证
            print(f"请求详情:\nURL: {url}\nHeaders: {headers}\nData: {data}\n")
            print(f"响应详情:\nStatus Code: {response.status_code}\nResponse Text: {response.text}\n")
            
            if response.status_code == 200:
                response_json = response.json()
                code = response_json.get('code')
                msg = response_json.get('msg')
                translated_text = response_json.get('text', '')
                
                if code == 0:
                    print(f"翻译成功: {translated_text.strip()}")  # 打印翻译后的内容
                    return translated_text
                else:
                    print(f"翻译失败，状态码: {code}, 错误信息: {msg}")
                    return None
            else:
                print(f"翻译失败，状态码: {response.status_code}, 错误信息: {response.text}")
        except requests.RequestException as e:
            print(f"请求异常: {e}")
        
        if attempt < retries:
            print(f"尝试重新翻译，第 {attempt + 1}/{retries} 次")
            time.sleep(delay)
        attempt += 1
    
    print("达到最大重试次数，跳过此段落")
    return None

def process_file(input_path, output_path, source_lang, target_lang, secret_pass, output_format='original_above_translation'):
    """
    读取文件内容，按指定字节数分段进行翻译，并将翻译后的内容保存到另一个文件。
    
    :param input_path: 输入文件的路径。
    :param output_path: 输出文件的路径。
    :param source_lang: 源语言代码。
    :param target_lang: 目标语言代码。
    :param secret_pass: 访问密钥。
    :param output_format: 输出格式 ('translation_only', 'original_above_translation', 'translation_above_original')
    """
    try:
        lines = read_file_with_fallback_encodings(input_path)
    except Exception as e:
        print(f"读取文件 {input_path} 时发生错误: {e}")
        return
    
    with open(output_path, 'a', encoding='utf-8') as output_file:  # 追加模式打开文件
        for line_number, line in enumerate(lines):
            print(f"正在翻译第 {line_number + 1} 行: {line.strip()}")  # 打印当前行内容
            
            # 检查行是否只包含等号符号
            if line.strip() == '=' * len(line.strip()):
                print("行只包含等号符号，跳过此行")
                translated_line = line
            else:
                translated_line = translate_text_segment(line, source_lang, target_lang, secret_pass)
                if translated_line is None:
                    translated_line = line  # 如果翻译失败，则保留原始行
            
            if output_format == 'translation_only':
                append_content = translated_line
            elif output_format == 'original_above_translation':
                append_content = f"{line.strip()}\n{translated_line.strip()}\n\n"
            elif output_format == 'translation_above_original':
                append_content = f"{translated_line.strip()}\n{line.strip()}\n\n"
            
            output_file.write(append_content)
            output_file.flush()  # 强制刷新缓冲区，确保内容立即写入文件

def find_txt_files(directory):
    """
    递归查找目录及其子目录中的所有 .txt 文件。
    
    :param directory: 要搜索的目录路径。
    :return: 包含所有 .txt 文件路径的列表。
    """
    txt_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".txt"):
                txt_files.append(os.path.join(root, file))
    return txt_files

def create_translated_directory_structure(input_folder, output_folder, source_lang, target_lang, secret_pass):
    """
    创建翻译后的目录结构，并翻译文件内容。
    
    :param input_folder: 输入文件夹路径。
    :param output_folder: 输出文件夹路径。
    :param source_lang: 源语言代码。
    :param target_lang: 目标语言代码。
    :param secret_pass: 访问密钥。
    """
    txt_files = find_txt_files(input_folder)
    
    if not txt_files:
        print(f"未找到任何 .txt 文件在输入文件夹及其子目录: {input_folder}")
        return
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {}
        for original_file_path in txt_files:
            relative_root = os.path.relpath(os.path.dirname(original_file_path), input_folder)
            output_dir = os.path.join(output_folder, relative_root)
            
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
                print(f"创建输出子文件夹: {output_dir}")
            
            output_file_path = os.path.join(output_dir, os.path.basename(original_file_path))
            future = executor.submit(process_file, original_file_path, output_file_path, source_lang, target_lang, secret_pass)
            futures[future] = (original_file_path, output_file_path)
        
        for future in as_completed(futures):
            original_file_path, output_file_path = futures[future]
            try:
                future.result()
                print(f"文件 {original_file_path} 翻译完成，结果保存到 {output_file_path}\n")
            except Exception as e:
                print(f"翻译文件 {original_file_path} 时发生错误: {e}")

if __name__ == "__main__":
    # 配置部分 - 替换这些值为你实际的路径和设置
    input_folder = r"C:\Users\XTY-2\Desktop\transtest\input"  # 替换为你的实际输入文件夹路径
    output_folder = r"C:\Users\XTY-2\Desktop\transtest\output"  # 替换为你的实际输出文件夹路径
    source_lang = "zh"  # 替换为你使用的源语言代码（例如 'en' 表示英语）
    target_lang = "en"  # 替换为你使用的目标语言代码（例如 'fr' 表示法语）
    api_key = "123456"  # 替换为你的实际 API 密钥
    output_format_code = 2  # 输出格式代码：1, 2, 3
    
    # 定义输出格式映射
    output_format_mapping = {
        1: 'translation_only',
        2: 'original_above_translation',
        3: 'translation_above_original'
    }
    
    # 获取对应的输出格式字符串
    output_format = output_format_mapping.get(output_format_code)
    
    if output_format is None:
        raise ValueError(f"输出格式代码 '{output_format_code}' 不受支持。请参考以下支持的格式代码：1, 2, 3")
    
    # 支持的语言代码列表
    supported_languages = {
        "af": "南非荷兰语",
        "am": "阿姆哈拉语",
        "ar": "阿拉伯语",
        "az": "阿塞拜疆语",
        "be": "白俄罗斯语",
        "bg": "保加利亚语",
        "bn": "孟加拉语",
        "bs": "波斯尼亚语",
        "ca": "加泰罗尼亚语",
        "ceb": "宿务语",
        "co": "科西嘉语",
        "cs": "捷克语",
        "cy": "威尔士语",
        "da": "丹麦语",
        "de": "德语",
        "el": "希腊语",
        "en": "英语",
        "eo": "世界语",
        "es": "西班牙语",
        "et": "爱沙尼亚语",
        "eu": "巴斯克语",
        "fa": "波斯语",
        "fi": "芬兰语",
        "fr": "法语",
        "fy": "弗里斯兰语",
        "ga": "爱尔兰语",
        "gd": "苏格兰盖尔语",
        "gl": "加利西亚语",
        "gu": "古吉拉特语",
        "ha": "豪萨语",
        "haw": "夏威夷语",
        "he": "希伯来语",
        "hi": "印地语",
        "hmn": "苗语",
        "hr": "克罗地亚语",
        "ht": "海地克里奥尔语",
        "hu": "匈牙利语",
        "hy": "亚美尼亚语",
        "id": "印尼语",
        "ig": "伊博语",
        "is": "冰岛语",
        "it": "意大利语",
        "iw": "希伯来语",
        "ja": "日语",
        "jv": "爪哇语",
        "ka": "格鲁吉亚语",
        "kk": "哈萨克语",
        "km": "高棉语",
        "kn": "卡纳达语",
        "ko": "韩语",
        "ku": "库尔德语",
        "ky": "吉尔吉斯语",
        "la": "拉丁语",
        "lb": "卢森堡语",
        "lo": "老挝语",
        "lt": "立陶宛语",
        "lu": "卢巴语",
        "lv": "拉脱维亚语",
        "mg": "马尔加什语",
        "mi": "毛利语",
        "mk": "马其顿语",
        "ml": "马拉雅拉姆语",
        "mn": "蒙古语",
        "mr": "马拉提语",
        "ms": "马来语",
        "mt": "马耳他语",
        "my": "缅甸语",
        "ne": "尼泊尔语",
        "nl": "荷兰语",
        "no": "挪威语",
        "ny": "齐切瓦语",
        "or": "奥里亚语",
        "pa": "旁遮普语",
        "pl": "波兰语",
        "ps": "普什图语",
        "pt": "葡萄牙语",
        "ro": "罗马尼亚语",
        "ru": "俄语",
        "sd": "信德语",
        "si": "僧伽罗语",
        "sk": "斯洛伐克语",
        "sl": "斯洛文尼亚语",
        "sm": "萨摩亚语",
        "sn": "绍纳语",
        "so": "索马里语",
        "sq": "阿尔巴尼亚语",
        "sr": "塞尔维亚语",
        "st": "塞索托语",
        "su": "巽他语",
        "sv": "瑞典语",
        "sw": "斯瓦希里语",
        "ta": "泰米尔语",
        "te": "泰卢固语",
        "tg": "塔吉克语",
        "th": "泰语",
        "tl": "菲律宾语",
        "tr": "土耳其语",
        "ug": "维吾尔语",
        "uk": "乌克兰语",
        "ur": "乌尔都语",
        "uz": "乌兹别克语",
        "vi": "越南语",
        "wo": "沃洛夫语",
        "xh": "科萨语",
        "yi": "意第绪语",
        "yo": "约鲁巴语",
        "zh": "中文",
        "zu": "祖鲁语"
    }
    
    # 检查源语言和目标语言是否在支持列表中
    if source_lang not in supported_languages:
        raise ValueError(f"源语言代码 '{source_lang}' 不受支持。请参考以下支持的语言代码：{list(supported_languages.keys())}")
    
    if target_lang not in supported_languages:
        raise ValueError(f"目标语言代码 '{target_lang}' 不受支持。请参考以下支持的语言代码：{list(supported_languages.keys())}")
    
    # 创建输出文件夹（如果不存在）
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        print(f"创建输出文件夹: {output_folder}")
    
    create_translated_directory_structure(input_folder, output_folder, source_lang, target_lang, api_key)



