{
  description = "expert Filial-Checker – Produktpreis in allen expert-Märkten abfragen";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";

  outputs = { self, nixpkgs }:
    let
      systeme = [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];
      fuerAlle = f: nixpkgs.lib.genAttrs systeme (system: f nixpkgs.legacyPackages.${system});
    in
    {
      packages = fuerAlle (pkgs: {
        default = pkgs.writeShellApplication {
          name = "expert-checker";
          text = ''exec ${pkgs.python3}/bin/python3 -I -u ${./expert_checker.py} "$@"'';
        };
      });

      apps = fuerAlle (pkgs: {
        default = {
          type = "app";
          program = "${self.packages.${pkgs.stdenv.hostPlatform.system}.default}/bin/expert-checker";
        };
      });

      devShells = fuerAlle (pkgs: {
        default = pkgs.mkShell { packages = [ pkgs.python3 ]; };
      });
    };
}
