# -*- coding: utf-8 -*-
"""AI 依赖智能安装脚本：自动检测本机是否有 NVIDIA GPU，安装对应版本的 torch/transformers

用途：
    requirements.txt 只包含 FastAPI 等基础依赖，不含 torch / transformers——
    这两个库体积大且分 GPU/CPU 版本，由本脚本按机器环境自动选择：

    - 检测到 NVIDIA GPU：从 PyTorch 官方 CUDA 索引安装 GPU 版 torch
      （默认 cu124，可通过 --cuda 参数调整，如 --cuda cu121）
    - 未检测到 GPU：从 PyTorch 官方 CPU 索引安装 CPU 版 torch
      （体积小、无 CUDA 依赖，普通电脑也能跑，只是推理较慢）
    - transformers 与设备无关，两种场景统一安装最新版；
      同时安装 sentence-transformers，用于智能采编本地语义相关度

用法（在 backend 目录执行）：
    python install_ai_deps.py            # 自动检测 GPU 并安装
    python install_ai_deps.py --cpu      # 强制安装 CPU 版（无 GPU 机器可显式指定）
    python install_ai_deps.py --gpu      # 强制安装 GPU 版
    python install_ai_deps.py --cuda cu121  # 指定 CUDA 版本（仅 GPU 场景有效）
    python install_ai_deps.py --dry-run  # 只打印检测结果与安装计划，不实际安装

说明：
    - 建议在虚拟环境（conda / venv）中运行，脚本会安装到当前 Python 环境；
    - 已安装 torch 且 CUDA 状态与目标一致时自动跳过 torch 安装，只确保 transformers；
    - 模型权重文件不入库（见 .gitignore），需自行放置到
      backend/app/aimodel/model/ 与 backend/app/aiVectorizationModel/model/ 下。
"""
import subprocess
import sys
import os


# PyTorch 索引（CPU 版默认走阿里云国内镜像，加快构建；可用 --torch-index 覆盖）
CPU_INDEX = "https://mirrors.aliyun.com/pytorch-wheels/cpu"
# GPU 版默认仍走 PyTorch 官方 CUDA 索引（镜像不一定同步 CUDA 版本）
GPU_INDEX = "https://download.pytorch.org/whl/cu124"


def has_nvidia_gpu() -> bool:
    """检测本机是否存在可用的 NVIDIA GPU（优先 nvidia-smi，其次尝试 torch）"""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return True
    except Exception:
        pass
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:
        return False


def torch_already_ok(cuda: bool) -> bool:
    """判断已安装的 torch 是否满足目标场景（版本可用且 CUDA 状态匹配）"""
    try:
        import torch

        return torch.__version__.startswith("2.") and bool(torch.cuda.is_available()) == cuda
    except Exception:
        return False


def pip_install(packages: list[str], index_url: str | None = None) -> bool:
    """调用当前解释器的 pip 安装依赖；返回是否成功"""
    cmd = [sys.executable, "-m", "pip", "install", "--progress-bar", "on", *packages]
    if index_url:
        # torch 从 PyTorch 官方索引安装；其余依赖回退到默认源（Docker 内为清华源），
        # 避免 --index-url 把 pip 索引完全切走后，flit_core 等构建依赖找不到。
        default_index = os.environ.get("PIP_INDEX_URL", "https://pypi.org/simple").strip()
        cmd += ["--index-url", index_url, "--extra-index-url", default_index]
    print(f"[install-ai] 执行: {' '.join(cmd)}")
    return subprocess.run(cmd).returncode == 0


def main() -> int:
    args = set(sys.argv[1:])
    dry_run = "--dry-run" in args
    force_cpu = "--cpu" in args
    force_gpu = "--gpu" in args
    torch_index_override = ""
    if "--torch-index" in args:
        idx = sys.argv.index("--torch-index") + 1
        if idx < len(sys.argv):
            torch_index_override = sys.argv[idx].strip()

    cuda_index = GPU_INDEX
    if "--cuda" in args:
        idx = sys.argv.index("--cuda") + 1
        if idx < len(sys.argv) and sys.argv[idx].startswith("cu"):
            cuda_index = f"https://download.pytorch.org/whl/{sys.argv[idx]}"

    gpu = has_nvidia_gpu()
    if force_cpu:
        gpu = False
    elif force_gpu:
        gpu = True

    print(f"[install-ai] 检测结果: {'检测到 NVIDIA GPU，将安装 GPU(CUDA) 版 torch' if gpu else '未检测到 NVIDIA GPU，将安装 CPU 版 torch'}")
    if dry_run:
        index = torch_index_override or (cuda_index if gpu else CPU_INDEX)
        default_index = os.environ.get("PIP_INDEX_URL", "https://pypi.org/simple").strip()
        print(f"[install-ai] [dry-run] 计划执行: pip install torch --index-url {index} --extra-index-url {default_index}")
        print("[install-ai] [dry-run] 计划执行: pip install transformers sentence-transformers")
        print("[install-ai] [dry-run] 提示: torch 约 190MB，下载速度取决于网络；长时间无进度可换 --torch-index 国内镜像")
        print("[install-ai] [dry-run] 结束（未安装任何包）")
        return 0

    # torch：目标场景一致时跳过，避免重复下载几个 GB 的安装包
    if torch_already_ok(gpu):
        print("[install-ai] 已存在满足条件的 torch，跳过 torch 安装")
    else:
        index = torch_index_override or (cuda_index if gpu else CPU_INDEX)
        print(f"[install-ai] 提示: torch 约 190MB，正在从 {index} 下载，请留意 pip 进度条；长期无进度可换国内镜像")
        if not pip_install(["torch"], index):
            print("[install-ai] torch 安装失败，请检查网络或改用国内镜像后重试")
            return 1

    # transformers / sentence-transformers：设备无关，统一安装
    if not pip_install(["transformers", "sentence-transformers==5.6.1"]):
        print("[install-ai] transformers/sentence-transformers 安装失败，请检查网络后重试")
        return 1

    print("[install-ai] AI 依赖安装完成。可运行 python -c \"import torch; print(torch.cuda.is_available())\" 验证。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
