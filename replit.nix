{ pkgs }:

pkgs.mkShell {
  packages = [
    pkgs.python39
    pkgs.python39Packages.requests
    pkgs.python39Packages.beautifulsoup4
    pkgs.python39Packages.cachetools
    pkgs.python39Packages.python-telegram-bot
  ];
}