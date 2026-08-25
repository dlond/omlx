import os
import subprocess
import sys

from setuptools import setup


CUSTOM_KERNEL_FLAG = "--with-custom-kernel"
TRUTHY = {"1", "true", "yes", "on"}
DEFAULT_CUSTOM_KERNEL_DEPLOYMENT_TARGET = "15.0"


def _metal_compiler_usable() -> bool:
    """Whether `metal` can actually run, not merely be located.

    Since Xcode 26 the Metal toolchain is a separately downloaded
    component: `xcrun --find metal` resolves a path while invoking the
    tool fails with "cannot execute tool 'metal' due to missing Metal
    Toolchain". Only running it distinguishes the two.
    """
    try:
        completed = subprocess.run(
            ["xcrun", "metal", "--version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=120,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return completed.returncode == 0


def _with_custom_kernel() -> bool:
    """Custom kernels are opt-out: build them wherever Metal can.

    The fallback paths are far slower (roughly 30x on GLM-5.2 prefill),
    so silently shipping them is the worse default. An explicit choice
    always wins over detection -- OMLX_WITH_CUSTOM_KERNEL=0 opts out --
    and detection only decides when nothing was specified.
    """
    if CUSTOM_KERNEL_FLAG in sys.argv:
        sys.argv.remove(CUSTOM_KERNEL_FLAG)
        return True
    requested = os.environ.get("OMLX_WITH_CUSTOM_KERNEL", "").strip().lower()
    if requested:
        return requested in TRUTHY
    if _metal_compiler_usable():
        return True
    print(
        "omlx: no usable Metal compiler, building without native custom "
        "kernels; the affected model families will use much slower "
        "fallback paths. Install full Xcode plus the Metal toolchain "
        "(xcodebuild -downloadComponent MetalToolchain) to enable them.",
        file=sys.stderr,
    )
    return False


def _custom_kernel_build_kwargs() -> dict:
    if not _with_custom_kernel():
        return {}

    target = (
        os.environ.get("OMLX_CUSTOM_KERNEL_DEPLOYMENT_TARGET")
        or os.environ.get("MACOSX_DEPLOYMENT_TARGET")
        or DEFAULT_CUSTOM_KERNEL_DEPLOYMENT_TARGET
    )
    os.environ.setdefault("MACOSX_DEPLOYMENT_TARGET", target)
    cmake_args = os.environ.get("CMAKE_ARGS", "").strip()
    if "CMAKE_OSX_DEPLOYMENT_TARGET" not in cmake_args:
        target_arg = f"-DCMAKE_OSX_DEPLOYMENT_TARGET={target}"
        os.environ["CMAKE_ARGS"] = (
            f"{cmake_args} {target_arg}".strip() if cmake_args else target_arg
        )
        cmake_args = os.environ["CMAKE_ARGS"]

    # CMake otherwise chooses the first framework Python on PATH, which can
    # differ from the interpreter running pip (and lack nanobind / MLX).  The
    # extensions must use the active environment's ABI and CMake packages.
    python_args = " ".join(
        (
            f"-DPython_EXECUTABLE={sys.executable}",
            f"-DPython3_EXECUTABLE={sys.executable}",
        )
    )
    if "Python_EXECUTABLE" not in cmake_args:
        os.environ["CMAKE_ARGS"] = f"{cmake_args} {python_args}".strip()

    from mlx import extension

    return {
        "ext_modules": [
            extension.CMakeExtension(
                "omlx.custom_kernels.bonsai._ext",
                sourcedir="omlx/custom_kernels/bonsai/csrc",
            ),
            extension.CMakeExtension(
                "omlx.custom_kernels.glm_moe_dsa._ext",
                sourcedir="omlx/custom_kernels/glm_moe_dsa/csrc",
            ),
            extension.CMakeExtension(
                "omlx.custom_kernels.minimax_m3._ext",
                sourcedir="omlx/custom_kernels/minimax_m3/csrc",
            ),
            extension.CMakeExtension(
                "omlx.custom_kernels.qwen35_prefill._ext",
                sourcedir="omlx/custom_kernels/qwen35_prefill/csrc",
            ),
        ],
        "cmdclass": {"build_ext": extension.CMakeBuild},
    }


if __name__ == "__main__":
    setup(**_custom_kernel_build_kwargs())
