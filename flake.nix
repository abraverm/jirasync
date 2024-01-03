{
  inputs.flake-utils.url = "github:numtide/flake-utils";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs";
  outputs = { self, nixpkgs, flake-utils,  ... }:
    flake-utils.lib.eachDefaultSystem
      (system:
        let
          pkgs = import nixpkgs {
            inherit system;
          };
        in 
          {
            devShells.default = pkgs.mkShell {
              LD_LIBRARY_PATH = "${pkgs.stdenv.cc.cc.lib}/lib";
              buildInputs = [
                pkgs.poetry
                pkgs.python3
              ];

              shellHook = ''
                poetry install

                # Activate the virtual environment
                source .venv/bin/activate
              '';
            };
          }
      );
}

