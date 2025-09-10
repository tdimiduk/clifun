{ pkgs ? import <nixpkgs> { } }:

pkgs.python3Packages.buildPythonApplication {
  pname = "clifun";
  src = ./.;
  version = "0.1";
  propagatedBuildInputs = with pkgs.python3Packages; [
    python313
    uv
    ruff
  ];
}
