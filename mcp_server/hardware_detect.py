#!/usr/bin/env python3
"""
Hardware detection for automatic PyTorch installation
Detects GPU type and determines correct PyTorch version
"""

import contextlib
import platform
import re
import subprocess


def detect_nvidia_gpu():
    """Detect if NVIDIA GPU is available"""
    try:
        result = subprocess.run(["nvidia-smi"], capture_output=True, text=True, timeout=5)
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def get_nvidia_compute_capability():
    """Return the LOWEST NVIDIA GPU compute capability as a float, or None.

    nvidia-smi reports one compute_cap per GPU. We return the minimum so the
    oldest card in the system drives wheel selection: cu126 covers sm_50-sm_90,
    so if any GPU is pre-Turing the whole system must use cu126. Non-numeric
    lines (warnings, headers) are skipped rather than failing detection.

    e.g. GTX 1080 (Pascal) -> 6.1, RTX 3090 (Ampere) -> 8.6, RTX 5090 -> 12.0;
    a mixed 6.1 + 8.6 system -> 6.1.
    """
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=compute_cap", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            caps = []
            for line in result.stdout.splitlines():
                cleaned = line.strip()
                if cleaned:
                    with contextlib.suppress(ValueError):
                        caps.append(float(cleaned))
            if caps:
                return min(caps)
    except (subprocess.TimeoutExpired, OSError):
        pass
    return None


def detect_apple_silicon():
    """Detect if running on Apple Silicon (M1/M2/M3)"""
    if platform.system() != "Darwin":
        return False
    try:
        result = subprocess.run(
            ["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True, timeout=5
        )
        return "Apple" in result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def get_pytorch_install_command():
    """
    Determine correct PyTorch installation command based on hardware

    Returns:
        tuple: (package_spec, index_url or None, description)
    """
    has_nvidia = detect_nvidia_gpu()
    has_apple_silicon = detect_apple_silicon()

    if has_nvidia:
        compute_cap = get_nvidia_compute_capability()
        # cu128 wheels only ship compiled kernels for sm_75+ (Turing and newer).
        # Pre-Turing cards (Pascal sm_61, Volta sm_70, Maxwell sm_5x) get a
        # "no kernel image is available for execution on the device" error with
        # cu128. The cu126 build of torch 2.7.1 still bundles sm_50..sm_90, so
        # route older GPUs there. Unknown capability falls through to cu128.
        if compute_cap is not None and compute_cap < 7.5:
            return (
                "torch==2.7.1 torchvision==0.22.1",
                "https://download.pytorch.org/whl/cu126",
                f"[GPU] NVIDIA GPU (compute {compute_cap}) detected - installing "
                "PyTorch 2.7.1 with CUDA 12.6 (legacy GPU architecture support)",
            )
        return (
            "torch>=2.0.0",
            "https://download.pytorch.org/whl/cu128",
            "[GPU] NVIDIA GPU detected - installing PyTorch with CUDA 12.8 support",
        )
    elif has_apple_silicon:
        return (
            "torch>=2.0.0",
            None,  # Default PyPI has MPS support
            "[GPU] Apple Silicon detected - installing PyTorch with MPS support",
        )
    else:
        return (
            "torch>=2.0.0",
            "https://download.pytorch.org/whl/cpu",
            "[CPU] No GPU detected - installing PyTorch CPU version",
        )


def check_pytorch_installation():
    """
    Check if PyTorch is installed and if it matches hardware

    Returns:
        dict: Status information about PyTorch installation
    """
    try:
        import torch

        has_nvidia = detect_nvidia_gpu()
        cuda_available = torch.cuda.is_available()

        status = {
            "installed": True,
            "version": torch.__version__,
            "cuda_available": cuda_available,
            "hardware_match": True,
        }

        # Check if NVIDIA GPU present but CUDA not available
        if has_nvidia and not cuda_available:
            status["hardware_match"] = False
            status["warning"] = "NVIDIA GPU detected but PyTorch has no CUDA support"

        # CUDA can report "available" while still lacking compiled kernels for
        # this specific GPU architecture. That manifests at kernel-launch time
        # as "no kernel image is available for execution on the device". Detect
        # it up front by checking the device's compute capability against the
        # architectures this PyTorch build was compiled for.
        if has_nvidia and cuda_available:
            try:
                arch_list = torch.cuda.get_arch_list()
                if arch_list:
                    # Parse the build's compiled architectures into (major, minor)
                    # pairs. PyTorch wheels list baselines (e.g. sm_80, sm_86) and
                    # rely on intra-major backward compatibility, so an exact
                    # sm_XX string match would false-positive on minor versions
                    # not explicitly listed (e.g. sm_89 / RTX 40-series).
                    supported = []
                    for arch in arch_list:
                        m = re.match(r"^(?:sm|compute)_(\d+)(\d)[a-z]?$", arch)
                        if m:
                            supported.append((int(m.group(1)), int(m.group(2))))
                    # Check every CUDA device: device 0 may be supported while a
                    # second, older GPU in the system is not. A device is
                    # compatible when the build has a kernel with the same major
                    # version and a minor <= the device's minor (NVIDIA guarantees
                    # backward compatibility within a major architecture).
                    for i in range(torch.cuda.device_count()):
                        major, minor = torch.cuda.get_device_capability(i)
                        compatible = any(
                            a_major == major and a_minor <= minor for a_major, a_minor in supported
                        )
                        if not compatible:
                            status["hardware_match"] = False
                            status["warning"] = (
                                f"PyTorch {torch.__version__} has no compiled kernels "
                                f"for GPU {i} ({torch.cuda.get_device_name(i)}, "
                                f"sm_{major}{minor}); build supports {arch_list}"
                            )
                            break
            except Exception:
                pass

        # Check if Apple Silicon
        if detect_apple_silicon():
            try:
                mps_available = torch.backends.mps.is_available()
                status["mps_available"] = mps_available
            except AttributeError:
                status["mps_available"] = False

        return status

    except ImportError:
        return {
            "installed": False,
            "version": None,
            "cuda_available": False,
            "hardware_match": False,
        }
