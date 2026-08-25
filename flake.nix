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

        # Deliberately does NOT set OMLX_WITH_CUSTOM_KERNEL. Whether the native
        # kernels get built is project policy, and nix is optional tooling — if
        # the policy lived here, the same command would produce different
        # artifacts depending on whether the caller happened to use this shell.
        # setup.py and apps/omlx-mac/Scripts/build.sh own that decision, so it
        # applies to everyone. This shell only undoes nix-specific interference
        # (the SDK variables above), and reports whether Metal is usable so the
        # outcome is visible on entry.
        if xcrun metal --version >/dev/null 2>&1; then
          echo "  metal: available — custom kernels will be built by default"
        else
          echo "  metal: UNAVAILABLE — builds will skip the custom kernels; enable with"
          echo "         sudo xcodebuild -downloadComponent MetalToolchain"
        fi

        echo "  uv sync --dev && uv run pytest -m 'not slow'"
      '';
    };
  };
}
