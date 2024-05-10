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
      pkgs = import nixpkgs {
        inherit system;
        config.allowUnfree = true;
      };

      inherit (poetry2nix.lib.mkPoetry2Nix { inherit pkgs; }) mkPoetryApplication;
      inherit (poetry2nix.lib.mkPoetry2Nix { inherit pkgs; }) defaultPoetryOverrides;

      devEnv = let
        name = "jirasync";
        in (pkgs.buildFHSUserEnv {
          inherit name;
        targetPkgs = pkgs: (with pkgs; [
          micromamba
          poetry
        ]);
        runScript = "zsh";

        profile = ''
          eval "$(micromamba shell hook -s posix)"
          export MAMBA_ROOT_PREFIX=./.mamba

          if ! [[ -d .mamba ]]; then
            if [[ -f "environment.yml" ]]; then
              micromamba create -q -n ${name} -y -f environment.yml
            else
              micromamba create -q -n ${name} -y -c conda-forge python="3.12"
              micromamba env export > environment.yml
            fi
          fi
          micromamba activate ${name}
          poetry install
          export JIRASYNC_CONFIG="~/.jirasync.conf"
        '';
      }).env;
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
              jira2markdown = super.jira2markdown.overridePythonAttrs
                (
                  old: {
                    buildInputs = (old.buildInputs or [ ]) ++ [ super.poetry ];
                  }
                );
            });
        };
        default = self.packages.${system}.jirasync;
      };

      devShells.default = devEnv;
    });
}

