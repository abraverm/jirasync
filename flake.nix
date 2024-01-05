{
  description = "JIRASync";
  inputs  = {
    flake-utils.url = "github:numtide/flake-utils";
    nixpkgs.url = "github:NixOS/nixpkgs";
    poetry2nix = {
      url = "github:nix-community/poetry2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

  };

  outputs = { self, nixpkgs, flake-utils, poetry2nix }:
  flake-utils.lib.eachDefaultSystem (system:
    let
      pkgs = nixpkgs.legacyPackages.${system};
      # What is more correct? ^ or >
      # pkgs = import nixpkgs { inherit system; };
      inherit (poetry2nix.lib.mkPoetry2Nix { inherit pkgs; }) mkPoetryApplication;
      inherit (poetry2nix.lib.mkPoetry2Nix { inherit pkgs; }) defaultPoetryOverrides;
    in 
    {
      packages = {
        jirasync = mkPoetryApplication {
          projectDir = self;
          overrides = defaultPoetryOverrides.extend
            (self: super: {
              sphinxcontrib-jquery = super.sphinxcontrib-jquery.overridePythonAttrs
                (
                  old: {
                    buildInputs = (old.buildInputs or [ ]) ++ [ super.sphinx ];
                  }
                );
            });
        };
        default = self.packages.${system}.jirasync;
      };

      devShells.default = pkgs.mkShell {
        buildInputs = [
          pkgs.poetry
          pkgs.python3
        ];

        shellHook = ''
          poetry install

          # Activate the virtual environment
          # source .venv/bin/activate
        '';
      };
    });
}

