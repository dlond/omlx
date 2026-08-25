# SPDX-License-Identifier: Apache-2.0
"""Tests that built custom-kernel extensions match the running interpreter.

Distinct from the nanobind probe in ``test_custom_kernel_abi_probe.py``:
this covers the *CPython* ABI tag baked into the ``.so`` filename. An
extension built by a different interpreter is not a broken import — it is
an invisible one, because CPython only looks for the suffixes in
``EXTENSION_SUFFIXES``. The symptom is a "No module named ..._ext" for a
file sitting right there on disk.

Stale artifacts persist because ``build_ext --inplace`` writes next to the
sources and nothing prunes tags from an earlier interpreter, so a rebuild
under a new Python leaves both behind and the packaging step copies
whatever it finds.
"""

from importlib.machinery import EXTENSION_SUFFIXES
from pathlib import Path

import pytest

import omlx

CUSTOM_KERNELS_DIR = Path(omlx.__file__).resolve().parent / "custom_kernels"


def _built_extensions() -> list[Path]:
    if not CUSTOM_KERNELS_DIR.is_dir():
        return []
    return sorted(CUSTOM_KERNELS_DIR.glob("*/_ext*.so"))


def _loadable_names() -> set[str]:
    """Filenames CPython would actually try when importing ``_ext``.

    Not an ``endswith`` test: ``EXTENSION_SUFFIXES`` ends with a bare
    ``.so``, so suffix matching accepts every tag including foreign ones.
    The finder joins the module name to each suffix, so only these exact
    names resolve.
    """
    return {f"_ext{suffix}" for suffix in EXTENSION_SUFFIXES}


def _is_loadable(path: Path) -> bool:
    return path.name in _loadable_names()


def test_built_extensions_match_running_interpreter_abi():
    built = _built_extensions()
    if not built:
        pytest.skip("no native custom kernels built in this tree")

    foreign = [p for p in built if not _is_loadable(p)]
    assert not foreign, (
        "custom-kernel extensions present that this interpreter cannot load: "
        + ", ".join(f"{p.parent.name}/{p.name}" for p in foreign)
        + f"; expected one of {EXTENSION_SUFFIXES}. Rebuild with "
        "OMLX_WITH_CUSTOM_KERNEL=1 and remove the stale artifacts, or they "
        "will be packaged alongside the correct ones."
    )


def test_each_kernel_package_has_a_single_extension():
    """Two tags in one directory means an earlier build was never pruned."""
    built = _built_extensions()
    if not built:
        pytest.skip("no native custom kernels built in this tree")

    by_package: dict[str, list[str]] = {}
    for path in built:
        by_package.setdefault(path.parent.name, []).append(path.name)

    duplicated = {pkg: names for pkg, names in by_package.items() if len(names) > 1}
    assert not duplicated, f"stale extension builds left in tree: {duplicated}"
