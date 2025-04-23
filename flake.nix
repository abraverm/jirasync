{
  description = "JIRASync";
  inputs = {
    flake-utils.url = "github:numtide/flake-utils";
    nixpkgs.url = "github:NixOS/nixpkgs";
  };

  outputs = {
    self,
    nixpkgs,
    flake-utils,
  }:
    flake-utils.lib.eachDefaultSystem (system: let
      pkgs = import nixpkgs {
        inherit system;
        config.allowUnfree = true;
        config.allowBroken = true;
      };

      jira2markdown = with pkgs.python3Packages;
        buildPythonPackage rec {
          pname = "jira2markdown";
          version = "0.3.6";
          src = fetchPypi {
            inherit pname version;
            hash = "sha256-sBSq//Rr5lQ5M5Ew2EE+HxdVjctmBRx31RnjCjME4Z8=";
          };
          format = "pyproject";
          nativeBuildInputs = [poetry-core];
          dependencies = [pyparsing];
        };
    in {
      packages = {
        jirasync = with pkgs.python3Packages;
          buildPythonPackage rec {
            pname = "jirasync";
            src = ./.;
            format = "pyproject";
            version =
              if (self ? rev)
              then self.shortRev
              else self.dirtyShortRev;
            nativeBuildInputs = [poetry-core];
            propagatedBuildInputs = [poetry-core jira jinja2 python-frontmatter jira2markdown packaging typing-extensions pyparsing];

            meta = {
              description = "Sync Jira issues to Markdown files";
              homepage = "https://github.com/abraverm/jirasync";
            };
          };
        default = self.packages.${system}.jirasync;
      };
      devShells = {
        default =
          (pkgs.buildFHSEnv
            {
              name = "pixi-shell";
              targetPkgs = pkgs: [pkgs.pixi];
              runScript = "$SHELL";
            })
          .env;
      };
    });
}
