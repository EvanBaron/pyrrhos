{
  pkgs ? import <nixpkgs> { },
}:
let
  yt-dlp-latest = pkgs.python3Packages.yt-dlp.overridePythonAttrs (old: rec {
    version = "2026.01.29";
    src = pkgs.fetchFromGitHub {
      owner = "yt-dlp";
      repo = "yt-dlp";
      rev = version;
      hash = "sha256-nw/L71aoAJSCbW1y8ir8obrFPSbVlBA0UtlrxL6YtCQ=";
    };
    patches = [ ];
    postPatch = "";
  });

  python-env = pkgs.python3.withPackages (
    ps: with ps; [
      discordpy
      python-dotenv
      pynacl
      psutil
      pip
      setuptools
      wheel
      yt-dlp-latest
    ]
  );
in
pkgs.mkShell {
  buildInputs = [
    python-env
    pkgs.ffmpeg
  ];

  shellHook = ''
    export LD_LIBRARY_PATH=${pkgs.lib.makeLibraryPath [ pkgs.ffmpeg ]}:$LD_LIBRARY_PATH
    export ENVIRONMENT=dev

    ln -sfn ${python-env} .venv

    echo "Environment ready!"
    echo "yt-dlp version: $(yt-dlp --version)"
  '';
}
