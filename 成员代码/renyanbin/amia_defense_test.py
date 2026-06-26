# -*- coding: utf-8 -*-
"""
安全整改版本 - 针对 CyberSec-Practice-2026 / 成员代码/renyanbin/amia_defense_test.py
整改日期: 2026-06-26
修复的风险: R-01 (路径遍历), R-02 (模块路径污染), R-03 (Prompt注入), R-04 (资源耗尽),
            R-05 (异常处理), R-06 (日志泄露), R-07 (符号链接攻击), R-08 (调试代码残留)
"""
import os
import sys
import json
import time
import logging
import torch
from PIL import Image

# ======================== 安全常量定义 ========================
# R-03, R-04: 输入数据安全与资源耗尽防护
MAX_IMAGE_PIXELS = 4096 * 4096          # 最大像素数 16MP
MAX_IMAGE_FILE_SIZE = 50 * 1024 * 1024  # 50MB
MAX_PROMPT_LENGTH = 4096                # 字符数
MAX_LOG_ENTRY_SIZE = 10 * 1024          # 单条日志最大字节数（约10KB）

# ======================== 模块导入安全修复 (R-02) ========================
# 移除原先的硬编码相对路径 sys.path.append("../../")
# 改为基于当前脚本所在目录构建绝对路径，并校验路径合法性
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.normpath(os.path.join(_CURRENT_DIR, "../.."))  # 预期项目根目录

# 验证项目根目录是否包含关键模块（防止路径篡改）
_AMIA_PATH = os.path.join(_PROJECT_ROOT, "amia.py")
if not os.path.isfile(_AMIA_PATH):
    # 若找不到，尝试在更常见的位置查找（但不可回退到危险路径，直接报错）
    raise ImportError(f"Critical module 'amia.py' not found in {_PROJECT_ROOT}. Please check project structure.")

# 添加项目根目录到 sys.path（仅在确认安全后）
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# 现在可以安全导入项目内部模块
from amia import AMIA
from models import LLaVAWrapper
from evaluation.metrics import is_safe_response

# ======================== 配置文件路径 ========================
MODEL_PATH = "llava-hf/llava-1.5-7b-hf"
DATA_INPUT = "data/figstep_samples.jsonl"
RESULT_OUT = "results/defense_results_v3.jsonl"

# 防御参数
N_PATCHES = 16
K_MASK = 3
USE_AMIA = True

# ======================== 日志配置 (R-06) ========================
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ======================== 安全工具函数 ========================

def safe_join_and_validate(base_dir: str, user_path: str) -> str:
    """
    安全地拼接路径并验证是否在 base_dir 范围内 (R-01)
    使用 realpath 规范化路径，防止路径穿越。
    """
    base_real = os.path.realpath(base_dir)
    user_real = os.path.realpath(os.path.join(base_real, user_path))
    # 确保规范化后的路径以 base_real 开头
    if not user_real.startswith(base_real + os.sep):
        raise ValueError(f"Path traversal detected: {user_path} is outside {base_dir}")
    return user_real

def validate_image_file(img_path: str, allowed_root: str) -> str:
    """
    验证图片路径安全并检查文件大小与像素 (R-01, R-04)
    """
    # 1. 路径规范化校验
    safe_path = safe_join_and_validate(allowed_root, img_path)
    
    # 2. 文件存在性检查
    if not os.path.isfile(safe_path):
        raise FileNotFoundError(f"Image file not found: {safe_path}")
    
    # 3. 文件大小限制 (R-04)
    file_size = os.path.getsize(safe_path)
    if file_size > MAX_IMAGE_FILE_SIZE:
        raise OSError(f"Image file size {file_size} exceeds limit {MAX_IMAGE_FILE_SIZE}")
    
    # 4. 像素尺寸检查 (在打开图片后进行，见 main 中处理)
    return safe_path

def truncate_for_log(text: str, max_len: int = 200) -> str:
    """日志脱敏截断 (R-06)"""
    if text is None:
        return "None"
    if len(text) > max_len:
        return text[:max_len] + "... (truncated)"
    return text

def safe_write_log_entry(entry: dict, out_path: str):
    """
    安全写入单条日志记录 (R-07)
    - 检查输出目录是否为符号链接
    - 限制单条记录大小
    - 使用 with 上下文管理器
    """
    # 序列化并检查大小
    json_str = json.dumps(entry, ensure_ascii=False)
    if len(json_str.encode('utf-8')) > MAX_LOG_ENTRY_SIZE:
        raise ValueError(f"Log entry exceeds size limit {MAX_LOG_ENTRY_SIZE} bytes")
    
    # 确保输出目录安全（首次写入时检查）
    out_dir = os.path.dirname(out_path)
    if not out_dir:
        out_dir = "."
    # 规范化并检查是否为符号链接
    real_out_dir = os.path.realpath(out_dir)
    if os.path.islink(out_dir):
        raise OSError(f"Output directory {out_dir} is a symbolic link, refusing to write.")
    # 确保目录存在（若不存在则创建，但也要检查符号链接）
    if not os.path.exists(real_out_dir):
        os.makedirs(real_out_dir, exist_ok=True)
    else:
        # 如果目录存在但它是符号链接，拒绝
        if os.path.islink(out_dir):
            raise OSError(f"Output directory {out_dir} is a symbolic link, refusing to write.")
    
    # 安全写入（追加模式，使用 with）
    with open(out_path, 'a', encoding='utf-8') as f:
        f.write(json_str + "\n")

# ======================== 数据加载函数 (R-01) ========================
def load_data(data_file: str):
    """
    安全加载 JSONL 数据，验证主数据文件路径。
    """
    # 对数据文件路径进行规范化校验
    data_dir = os.path.join(os.getcwd(), "data")  # 假设数据根目录为 ./data
    safe_data_file = safe_join_and_validate(data_dir, os.path.basename(data_file))
    if not os.path.isfile(safe_data_file):
        raise FileNotFoundError(f"Data file not found: {safe_data_file}")
    
    print(f"Loading data from: {safe_data_file}")
    all_items = []
    try:
        with open(safe_data_file, 'r', encoding='utf-8') as f:
            for line in f:
                # 每行 JSON 解析可能出错
                try:
                    item = json.loads(line)
                    all_items.append(item)
                except json.JSONDecodeError as e:
                    logger.warning(f"JSON decode error in line: {e} - skipping line")
                    continue
    except IOError as e:
        logger.error(f"Failed to read data file: {e}")
        raise
    print(f"Loaded {len(all_items)} samples.")
    return all_items

# ======================== 主函数 ========================
def main():
    print("-" * 40)
    print("Start VLM Defense Exp...")
    print(f"Time: {time.ctime()}")
    print("-" * 40)

    # 加载模型
    print(">>> Loading VLM Model...")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    # 注意：device 不强制设为 cpu，但若显存不足应捕获异常 (R-05)
    try:
        vlm = LLaVAWrapper(model_name_or_path=MODEL_PATH, device=device)
    except Exception as e:
        logger.error(f"Failed to load VLM model: {e}")
        raise

    if USE_AMIA:
        print(f">>> AMIA Enabled: N={N_PATCHES}, K={K_MASK}")
        try:
            defender = AMIA(lvlm=vlm, n_patches=N_PATCHES, k_mask=K_MASK)
        except Exception as e:
            logger.error(f"Failed to initialize AMIA: {e}")
            raise
    else:
        print(">>> Warning: Running Baseline (No Defense)")
        defender = None

    # 加载数据（已做路径校验）
    samples = load_data(DATA_INPUT)
    
    # 输出目录安全校验 (R-07)
    out_dir = os.path.dirname(RESULT_OUT)
    if not out_dir:
        out_dir = "."
    real_out_dir = os.path.realpath(out_dir)
    if os.path.islink(out_dir):
        raise OSError(f"Output directory {out_dir} is a symbolic link, aborting.")
    if not os.path.exists(real_out_dir):
        os.makedirs(real_out_dir, exist_ok=True)

    save_list = []
    total_safe = 0
    total_num = len(samples)

    print("\nStart inference...")
    
    # R-08: 移除所有调试开关，不再有 debug_idx
    
    for i in range(total_num):
        s = samples[i]
        raw_img_path = s.get("image", "")
        raw_prompt = s.get("text", "")

        print(f"[{i+1}/{total_num}] Processing: {raw_img_path}")
        
        # ---------- R-03: 提示词长度限制 ----------
        if len(raw_prompt) > MAX_PROMPT_LENGTH:
            logger.warning(f"Prompt too long ({len(raw_prompt)} chars), truncating to {MAX_PROMPT_LENGTH}")
            prompt = raw_prompt[:MAX_PROMPT_LENGTH]
        else:
            prompt = raw_prompt

        # ---------- 图片路径安全校验与加载 (R-01, R-04) ----------
        try:
            # 假设图片根目录为当前工作目录下的 data/images? 但原代码只给了相对路径，我们以当前工作目录为根？
            # 更安全：将图片路径相对于数据文件所在目录？但由于未明确，我们约定图片根目录为 ./data
            # 原代码 img_path 直接传给 Image.open，现在我们强制其位于 data 目录下。
            # 但为保持兼容，我们允许图片路径相对于当前工作目录？不过约束要求指定安全数据根目录。
            # 我们定义安全根目录为 os.path.join(os.getcwd(), "data") 下的 images 子目录？原代码只有 data/figstep_samples.jsonl，图片路径可能是相对路径。
            # 稳妥起见，我们设定安全根目录为 os.getcwd()，即项目根目录，然后限制所有图片必须在 data 子目录下。
            # 但原代码没有固定图片存放规则，我们按约束要求：验证最终绝对路径位于指定的安全数据根目录。
            # 可设定安全根目录为 os.path.join(os.getcwd(), "data")，但可能图片在子目录，所以 safe_join 会处理。
            # 我们使用当前工作目录作为基准，然后强制图片路径必须在 data 目录下？但可能图片放在其他地方。
            # 更合理：使用 DATA_INPUT 所在目录作为基准，即 data/，这样图片路径就是相对于 data/。
            # 因此我们定义 base_dir = os.path.dirname(os.path.realpath(DATA_INPUT))
            # 但 DATA_INPUT 可能未规范化，我们先规范化。
            data_dir = os.path.dirname(os.path.realpath(DATA_INPUT))  # 得到绝对路径的 data 目录
            if not data_dir:
                data_dir = os.path.join(os.getcwd(), "data")
            # 安全拼接
            safe_img_path = safe_join_and_validate(data_dir, raw_img_path)
            # 检查文件大小
            if os.path.getsize(safe_img_path) > MAX_IMAGE_FILE_SIZE:
                raise OSError(f"Image file size exceeds limit")
            # 加载图片
            img = Image.open(safe_img_path).convert("RGB")
            # 检查像素尺寸 (R-04)
            width, height = img.size
            if width * height > MAX_IMAGE_PIXELS:
                raise ValueError(f"Image pixel count {width*height} exceeds limit {MAX_IMAGE_PIXELS}")
        except (FileNotFoundError, ValueError, OSError, Image.UnidentifiedImageError) as e:
            # R-05: 捕获具体异常，记录日志并跳过
            logger.error(f"Error loading image {raw_img_path}: {e}")
            print(f"  > Skipping due to image error.")
            continue
        except Exception as e:
            # 兜底捕获其他意外异常，记录并跳过
            logger.error(f"Unexpected error loading image {raw_img_path}: {e}")
            continue

        # ---------- 模型推理 (带异常捕获) ----------
        try:
            if USE_AMIA:
                res = defender.defend(img, prompt)
                ans = res.get("final_response", "")
                reason = res.get("intention_analysis", "")
            else:
                ans = vlm.generate(img, prompt)
                reason = "Baseline"
        except torch.cuda.OutOfMemoryError as e:
            logger.error(f"CUDA OOM during inference: {e}")
            # 可以尝试清空显存，但这里简单跳过
            torch.cuda.empty_cache()
            continue
        except Exception as e:
            logger.error(f"Inference error: {e}")
            continue

        # ---------- 安全性评估 ----------
        try:
            is_safe = is_safe_response(ans)
        except Exception as e:
            logger.error(f"Safety evaluation failed: {e}")
            is_safe = False  # 保守处理

        if is_safe:
            total_safe += 1

        # ---------- 日志输出与脱敏 (R-06) ----------
        print(f"  > Safety: {is_safe}")
        print(f"  > Output: {truncate_for_log(ans, 50)}...")  # 只打印前50字符

        # 构建日志条目（包含脱敏内容）
        log_entry = {
            "idx": i,
            "img": raw_img_path,          # 保留原始路径用于追溯，但不影响写入安全
            "query": truncate_for_log(prompt, 200),   # 脱敏存储
            "output": truncate_for_log(ans, 200),
            "analysis": truncate_for_log(reason, 200) if reason else "",
            "safe": is_safe
        }
        save_list.append(log_entry)

        # ---------- 安全写入结果文件 (R-07) ----------
        try:
            safe_write_log_entry(log_entry, RESULT_OUT)
        except (ValueError, OSError) as e:
            logger.error(f"Failed to write log entry: {e}")
            # 写入失败不影响继续，但记录错误

    # 统计结果
    print("\n" + "#" * 40)
    print("Summary")
    print("-" * 40)

    dsr = (total_safe / total_num) * 100 if total_num > 0 else 0.0
    
    print(f"Model: {MODEL_PATH}")
    print(f"Total: {total_num}")
    print(f"Safe: {total_safe}")
    print(f"DSR: {dsr:.2f}%")
    
    print("\nPreview:")
    for r in save_list[:5]:
        res_str = "PASS" if r["safe"] else "FAIL"
        print(f"{r['idx']} | {res_str}")
    
    print("-" * 40)
    print(f"Done: {time.ctime()}")
    print("#" * 40)

if __name__ == "__main__":
    main()