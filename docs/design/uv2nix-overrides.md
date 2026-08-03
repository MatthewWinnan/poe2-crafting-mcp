# uv2nix Override Pattern

## When You Need Overrides

When `nix develop` or `nix build` fails because a Python package doesn't declare its build system properly in pyproject metadata. Nix builds are pure — if a package needs `setuptools` to build but doesn't list it, the build fails.

## Symptoms

```
error: Package 'lupa' is missing a build system dependency: setuptools
```

or

```
error: builder failed with exit code 1
  ... ModuleNotFoundError: No module named 'setuptools'
```

## The Fix Pattern

Create `nix/overrides.nix`:

```nix
# Python package build overrides for uv2nix
# Add entries here when packages fail to build due to missing build system declarations
# Reference: https://github.com/pyproject-nix/uv2nix/issues/117
# Community overrides: https://github.com/TyberiusPrime/uv2nix_hammer_overrides
{pkgs, ...}: final: prev: {
  # Example: package needs setuptools but doesn't declare it
  # some-package = prev.some-package.overrideAttrs (old: {
  #   buildInputs = (old.buildInputs or []) ++ final.resolveBuildSystem {setuptools = [];};
  # });

  # lupa: needs LuaJIT headers for C extension compilation
  # lupa = prev.lupa.overrideAttrs (old: {
  #   buildInputs = (old.buildInputs or []) ++ [pkgs.luajit];
  #   nativeBuildInputs = (old.nativeBuildInputs or []) ++ [pkgs.pkg-config];
  # });
}
```

Then wire it into `flake.nix` in the `pythonSet` composition:

```nix
pythonSet = let
  baseSet = pkgs.callPackage inputs.pyproject-nix.build.packages {
    python = pkgs.python312;
  };

  pypackageOverrides = import ./nix/overrides.nix {inherit pkgs;};
in
  baseSet.overrideScope (
    lib.composeManyExtensions [
      inputs.pyproject-build-systems.overlays.default
      overlay
      pypackageOverrides  # ← Add it here
    ]
  );
```

## Common Override Patterns

### Package needs setuptools (most common)

```nix
package-name = prev.package-name.overrideAttrs (old: {
  buildInputs = (old.buildInputs or []) ++ final.resolveBuildSystem {setuptools = [];};
});
```

### Package needs poetry-core

```nix
package-name = prev.package-name.overrideAttrs (old: {
  buildInputs = (old.buildInputs or []) ++ final.resolveBuildSystem {poetry-core = [];};
});
```

### Package needs a C library (like lupa needing LuaJIT)

```nix
lupa = prev.lupa.overrideAttrs (old: {
  buildInputs = (old.buildInputs or []) ++ [pkgs.luajit];
  nativeBuildInputs = (old.nativeBuildInputs or []) ++ [pkgs.pkg-config];
  env = {
    LUAJIT_INCLUDE_DIR = "${pkgs.luajit}/include/luajit-2.1";
    LUAJIT_LIB = "${pkgs.luajit}/lib";
  };
});
```

### Package needs numpy at build time

```nix
package-name = prev.package-name.overrideAttrs (old: {
  buildInputs = (old.buildInputs or []) ++ final.resolveBuildSystem {
    setuptools = [];
    numpy = [];
  };
});
```

## Workflow

1. Run `nix develop` (or `nix build`)
2. Read the error — identify which package failed and what it's missing
3. Add an override to `nix/overrides.nix`
4. Retry
5. Repeat until all packages build

## Reference

- uv2nix issue discussing overrides: https://github.com/pyproject-nix/uv2nix/issues/117
- Community-maintained overrides collection: https://github.com/TyberiusPrime/uv2nix_hammer_overrides
- nse_perf example: `/home/matthew/DEV/nse_perf/nix/utils/uv2nix_overrides.nix`
- uv2nix boilerplate pattern: `/home/matthew/DEV/nse_perf/nix/utils/uv2nix_boilerplate.nix`
