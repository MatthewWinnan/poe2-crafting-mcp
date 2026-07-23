# Python package build overrides for uv2nix
# Add entries here when packages fail to build due to missing build system declarations
#
# Workflow:
#   1. Run `nix develop`
#   2. Read the error — which package failed, what's missing
#   3. Add an override below
#   4. Retry
#
# See docs/uv2nix-overrides.md for patterns and examples.
# Community overrides: https://github.com/TyberiusPrime/uv2nix_hammer_overrides
{pkgs, ...}: final: prev: {
  # lupa: C extension, needs LuaJIT headers
  # Uncomment and adjust once uv.lock is generated and build is attempted
  # lupa = prev.lupa.overrideAttrs (old: {
  #   buildInputs = (old.buildInputs or []) ++ [pkgs.luajit];
  #   nativeBuildInputs = (old.nativeBuildInputs or []) ++ [pkgs.pkg-config];
  # });
}
