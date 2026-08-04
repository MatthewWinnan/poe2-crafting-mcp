{
  description = "PoE2 Crafting MCP Server";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";

    pyproject-nix = {
      url = "github:pyproject-nix/pyproject.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    uv2nix = {
      url = "github:pyproject-nix/uv2nix";
      inputs = {
        pyproject-nix.follows = "pyproject-nix";
        nixpkgs.follows = "nixpkgs";
      };
    };

    pyproject-build-systems = {
      url = "github:pyproject-nix/build-system-pkgs";
      inputs = {
        pyproject-nix.follows = "pyproject-nix";
        uv2nix.follows = "uv2nix";
        nixpkgs.follows = "nixpkgs";
      };
    };

    rust-overlay = {
      url = "github:oxalica/rust-overlay";
    };
  };

  outputs = {
    self,
    nixpkgs,
    ...
  } @ inputs: let
    supportedSystems = ["x86_64-linux" "x86_64-darwin"];

    forAllSystems = function:
      nixpkgs.lib.genAttrs supportedSystems (system: function system);
  in {
    devShells = forAllSystems (system: let
      pkgs = import nixpkgs {
        inherit system;
        overlays = [(import inputs.rust-overlay)];
      };
      inherit (nixpkgs) lib;

      # Rust toolchain (latest stable from oxalica overlay)
      rustToolchain = pkgs.rust-bin.stable.latest.default.override {
        extensions = ["rust-src" "rust-analyzer"];
      };

      # uv2nix workspace
      workspace = inputs.uv2nix.lib.workspace.loadWorkspace {workspaceRoot = ./.;};

      overlay = workspace.mkPyprojectOverlay {
        sourcePreference = "wheel";
      };

      # Package overrides (for packages with missing build system declarations)
      pypackageOverrides = import ./nix/overrides.nix {inherit pkgs;};

      # Base Python set
      pythonSet = let
        baseSet = pkgs.callPackage inputs.pyproject-nix.build.packages {
          python = pkgs.python312;
        };
      in
        baseSet.overrideScope (
          lib.composeManyExtensions [
            inputs.pyproject-build-systems.overlays.default
            overlay
            pypackageOverrides
          ]
        );

      # Editable overlay for development
      editableOverlay = workspace.mkEditablePyprojectOverlay {
        root = "$REPO_ROOT";
      };

      editablePythonSet = pythonSet.overrideScope (
        lib.composeManyExtensions [
          editableOverlay
          (final: prev: {
            poe2-crafting-mcp = prev.poe2-crafting-mcp.overrideAttrs (old: {
              nativeBuildInputs =
                old.nativeBuildInputs
                ++ final.resolveBuildSystem {editables = [];};
            });
          })
          # Fileset override to avoid copying the entire repo into the store
          (_final: prev: {
            poe2-crafting-mcp = prev.poe2-crafting-mcp.overrideAttrs (old: {
              src = lib.fileset.toSource {
                root = old.src;
                fileset = lib.fileset.unions [
                  (old.src + "/pyproject.toml")
                ];
              };
            });
          })
        ]
      );

      venv = editablePythonSet.mkVirtualEnv "poe2-craft-mcp-env" workspace.deps.all;
    in {
      default = pkgs.mkShell {
        packages = [
          venv
          pkgs.uv
          pkgs.git
          pkgs.luajit
          pkgs.lua51Packages.luasocket
          pkgs.lua51Packages.luautf8
          pkgs.sqlite
          pkgs.jq

          # Rust toolchain (optimizer crate)
          rustToolchain
          pkgs.maturin
        ];

        env = {
          UV_NO_SYNC = "1";
          UV_PYTHON = "${venv}/bin/python";
          UV_PYTHON_DOWNLOADS = "never";
        };

        shellHook = ''
          unset PYTHONPATH

          export REPO_ROOT=$(${pkgs.git}/bin/git rev-parse --show-toplevel)
          export PYTHONPATH="$REPO_ROOT"
          export POB_PATH="$REPO_ROOT/vendor/PathOfBuilding-PoE2"
          export POE2_CRAFT_DB="$REPO_ROOT/data/poe2_craft.db"

          # Build & install the Rust optimizer extension into target/release/
          # so bridge.py's fallback import finds it without a virtualenv.
          _build_rust_optimizer() {
            local crate_dir="$REPO_ROOT/crates/poe2-optimizer"
            local wheel_dir="$REPO_ROOT/target/wheels"
            local dest="$REPO_ROOT/target/release/poe2_optimizer"
            local src_hash

            # Hash source files to detect changes
            src_hash=$(cat "$crate_dir/Cargo.toml" "$crate_dir/src/"*.rs 2>/dev/null | sha256sum | cut -d' ' -f1)

            if [ -f "$dest/.src_hash" ] && [ "$(cat "$dest/.src_hash")" = "$src_hash" ]; then
              return 0  # already up to date
            fi

            echo "  Building Rust optimizer..."
            if (cd "$crate_dir" && maturin build --release --quiet 2>/dev/null); then
              local whl
              whl=$(ls -t "$wheel_dir"/poe2_optimizer-*.whl 2>/dev/null | head -1)
              if [ -n "$whl" ]; then
                mkdir -p "$dest"
                ${pkgs.python312}/bin/python -c "
import zipfile, os, sys
with zipfile.ZipFile(sys.argv[1]) as z:
    for name in z.namelist():
        if name.startswith('poe2_optimizer/') and not name.startswith('poe2_optimizer-'):
            data = z.read(name)
            out = os.path.join(sys.argv[2], os.path.basename(name))
            with open(out, 'wb') as f:
                f.write(data)
" "$whl" "$dest"
                echo "$src_hash" > "$dest/.src_hash"
                echo "  Rust optimizer built and installed."
              fi
            else
              echo "  Warning: Rust optimizer build failed (non-fatal)."
            fi
          }
          _build_rust_optimizer

          echo ""
          echo "  PoE2 Crafting MCP - Dev Environment"
          echo "  ────────────────────────────────────"
          echo "  Python:  $(python --version 2>&1)"
          echo "  Rust:    $(rustc --version 2>&1)"
          echo "  LuaJIT:  $(${pkgs.luajit}/bin/luajit -v 2>&1 | head -1)"
          echo "  PoB:     $POB_PATH"
          echo "  DB:      $POE2_CRAFT_DB"
          if [ -f "$REPO_ROOT/target/release/poe2_optimizer/__init__.py" ]; then
            echo "  Rust:    poe2_optimizer loaded"
          else
            echo "  Rust:    poe2_optimizer NOT available"
          fi
          echo ""
        '';
      };
    });
  };
}
