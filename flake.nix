{
  description = "oMLX development shell (uv + host Xcode toolchain)";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
  };

  outputs = {nixpkgs, ...}: let
    # oMLX is Apple Silicon only (MLX + Metal).
    system = "aarch64-darwin";
    pkgs = import nixpkgs {inherit system;};
  in {
    # mkShellNoCC, not mkShell: the darwin CC stdenv pins DEVELOPER_DIR and
    # SDKROOT to nixpkgs' apple-sdk and puts an xcbuild `xcrun` stub ahead of
    # /usr/bin/xcrun. The native kernels shell out to `xcrun -sdk macosx metal`
    # (omlx/custom_kernels/*/csrc/CMakeLists.txt) and nixpkgs ships no Metal
    # compiler, so native compilation is host Xcode's job; nix provides only
    # the Python-side tooling below.
    devShells.${system}.default = pkgs.mkShellNoCC {
      packages = [
        pkgs.uv
        # Used when building with --no-build-isolation; isolated builds get
        # their own pinned cmake from the build-system requires.
        pkgs.cmake
        # uv resolves two dependencies over git+https.
        pkgs.git
      ];

      shellHook = ''
        # Defensive: stdenvNoCC does not set these, but a parent nix shell
        # may have, and either one redirects the build away from Xcode.
        unset DEVELOPER_DIR SDKROOT
        # setup.py defaults to 15.0 and oMLX requires macOS 15+;
        # stdenv would otherwise pin 14.0.
        export MACOSX_DEPLOYMENT_TARGET=15.0

        echo "oMLX dev shell — uv $(uv --version | cut -d' ' -f2), $(xcodebuild -version 2>/dev/null | head -1)"

        # Build the native kernels by default: they are what the shipped app
        # uses, and the fallback paths are far slower. Gate on the compiler
        # actually running rather than on `xcrun --find metal` — since Xcode 26
        # the tool resolves even when the separately downloaded MetalToolchain
        # component is absent, so a find-based check would enable a build that
        # always dies at the Metal step. With no usable compiler, fall back to
        # upstream's default of leaving OMLX_WITH_CUSTOM_KERNEL unset.
        if xcrun metal --version >/dev/null 2>&1; then
          export OMLX_WITH_CUSTOM_KERNEL=1
          echo "  custom kernels: ON  (OMLX_WITH_CUSTOM_KERNEL=1)"
        else
          unset OMLX_WITH_CUSTOM_KERNEL
          echo "  custom kernels: OFF — no working Metal compiler; enable with"
          echo "                  sudo xcodebuild -downloadComponent MetalToolchain"
        fi

        echo "  uv sync --dev && uv run pytest -m 'not slow'"
      '';
    };
  };
}
