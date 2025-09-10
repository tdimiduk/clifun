{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  # The name of our shell
  name = "clifun-dev-shell";

  # The packages available in the shell
  packages = with pkgs; [
    python313  # Or your preferred Python version
    uv
    ruff
    steam-run
  ];

  # A command to run when entering the shell
  shellHook = ''
    echo "Welcome to the clifun dev environment!"
    echo "Run 'uv venv' to create a virtual environment."
    echo "Run 'uv pip sync requirements.lock requirements-dev.lock' to install dependencies."
  '';
}
