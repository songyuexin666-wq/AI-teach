"""
检查本地 Marker 模型是否可用（仅使用本地模型，不下载）。

使用方式：
    python scripts/preload_marker_models.py

可选参数：
    python scripts/preload_marker_models.py --cache-dir D:\\hf_cache
    python scripts/preload_marker_models.py --verbose

功能：
1. 强制离线模式，仅使用本地缓存模型
2. 校验 Marker 所需模型是否已存在于本地
3. 若未安装 marker-pdf 或本地缺少模型，会提示错误
"""

from __future__ import annotations

import argparse
import platform
import sys
import traceback
from pathlib import Path
from processpdf.model_cache import (
    configure_local_model_environment,
    ensure_required_local_models,
    get_default_cache_root,
    get_compatible_text_recognition_version,
    get_requested_text_recognition_version,
)


def setup_environment(cache_dir: str, verbose=False):
    """
    配置 HuggingFace / Marker 本地模型缓存环境（仅离线）
    """
    cache_path = Path(cache_dir).expanduser().resolve()
    if not cache_path.exists():
        print(f"\n警告: 缓存目录不存在: {cache_path}")
        print("请先确保已将 Marker 所需模型放置到该目录，或通过 .env 的 HF_HOME / MARKER_MODEL_CACHE 指定正确路径。")
    else:
        cache_path.mkdir(parents=True, exist_ok=True)

    # 强制将运行时和 PDF 解析链路对齐到同一套本地缓存目录。
    os.environ["HF_HOME"] = str(cache_path)
    os.environ["MARKER_MODEL_CACHE"] = str(cache_path)
    os.environ["DATALAB_CACHE_HOME"] = str(cache_path)
    configured_root = Path(configure_local_model_environment()).resolve()

    if verbose:
        print("\n环境变量配置（仅本地）:")
        print("HF_HUB_OFFLINE =", os.environ.get("HF_HUB_OFFLINE"))
        print("TRANSFORMERS_OFFLINE =", os.environ.get("TRANSFORMERS_OFFLINE"))
        print("HF_HOME =", os.environ.get("HF_HOME"))
        print("MARKER_MODEL_CACHE =", os.environ.get("MARKER_MODEL_CACHE"))
        print("DATALAB_CACHE_HOME =", os.environ.get("DATALAB_CACHE_HOME"))
        print("XDG_CACHE_HOME =", os.environ.get("XDG_CACHE_HOME"))
        print("RECOGNITION_MODEL_CHECKPOINT =", os.environ.get("RECOGNITION_MODEL_CHECKPOINT"))
        print("HUGGINGFACE_HUB_CACHE =", os.environ.get("HUGGINGFACE_HUB_CACHE"))
        print("TORCH_HOME =", os.environ.get("TORCH_HOME"))

    return configured_root


def import_marker():
    """
    检查 marker 是否安装
    """
    try:
        from marker.models import create_model_dict
        return create_model_dict
    except ImportError:
        print("\n错误: 未检测到 marker-pdf")
        print("请先安装:")
        print("pip install marker-pdf")
        sys.exit(1)


def verify_local_models(verbose=False):
    """
    校验本地 Marker 模型是否可用（不下载）
    """
    create_model_dict = import_marker()

    print("\n正在校验本地 Marker 模型（离线，不下载）...\n")

    ensure_required_local_models(os.environ["HF_HOME"])
    print("surya 期望 OCR 版本:", get_requested_text_recognition_version())
    print("当前可用兼容 OCR 版本:", get_compatible_text_recognition_version(os.environ["HF_HOME"]))
    artifact_dict = create_model_dict()

    if artifact_dict is None:
        raise RuntimeError("create_model_dict() 返回 None，请确认本地模型已就绪。")

    try:
        return len(artifact_dict)
    except Exception:
        return 0


def parse_args():
    parser = argparse.ArgumentParser(description="校验本地 Marker PDF 模型（不下载）")

    parser.add_argument(
        "--cache-dir",
        default=os.environ.get("HF_HOME") or os.environ.get("MARKER_MODEL_CACHE") or get_default_cache_root(),
        help="本地模型缓存目录（需已存在并包含模型）",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="输出调试信息",
    )

    return parser.parse_args()


def print_failure_help(cache_dir):
    print("\n本地模型校验失败，可能原因:")
    print("1. 缓存目录下尚未放置 Marker 所需模型")
    print("2. 路径配置错误（可设置 .env 的 HF_HOME 或 MARKER_MODEL_CACHE）")
    print("3. 缓存损坏或版本不匹配")

    print("\n建议:")
    print("1. 将 Marker 所需模型放到本地目录后，再上传 PDF")
    print("2. 确保与 marker-pdf 版本对应的模型已在该目录")

    print("\n当前使用的缓存目录:")
    print(cache_dir)


def main():
    args = parse_args()

    try:
        cache_dir = setup_environment(
            cache_dir=args.cache_dir,
            verbose=args.verbose,
        )

        print("模型缓存目录:", cache_dir)

        model_count = verify_local_models(verbose=args.verbose)

        print("\n==============================")
        print("本地 Marker 模型校验通过")
        print("共加载模型数量:", model_count)
        print("==============================\n")

        print("上传 PDF 后将直接使用上述本地模型，不会进行任何下载。")

    except KeyboardInterrupt:
        print("\n用户取消")

    except Exception as e:
        print("\n发生错误:", str(e))

        if args.verbose:
            traceback.print_exc()

        print_failure_help(args.cache_dir)

        sys.exit(1)


if __name__ == "__main__":
    main()
