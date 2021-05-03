{ pkgs ? import <nixpkgs> {} }:

pkgs.python3Packages.buildPythonApplication {
  pname = "datacli";
  src = ./.;
  version = "0.1";
  propagatedBuildInputs = with pkgs.python3Packages; [attrs cattrs ipython mypy black isort wheel build];
}
