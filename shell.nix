{
  pkgs ? import <nixpkgs> { },
}:
let
  yt-dlp-latest = pkgs.python3Packages.buildPythonPackage rec {
    pname = "yt-dlp";
    version = "2026.01.29";
    format = "pyproject";

    src = pkgs.fetchFromGitHub {
      owner = "yt-dlp";
      repo = "yt-dlp";
      rev = version;
      hash = "sha256-nw/L71aoAJSCbW1y8ir8obrFPSbVlBA0UtlrxL6YtCQ=";
    };

    nativeBuildInputs = [ pkgs.python3Packages.hatchling ];
  };

  bgutil-ytdlp-pot-provider = pkgs.python3Packages.buildPythonPackage rec {
    pname = "bgutil-ytdlp-pot-provider";
    version = "1.2.2";
    format = "pyproject";

    src = pkgs.fetchFromGitHub {
      owner = "Brainicism";
      repo = "bgutil-ytdlp-pot-provider";
      rev = "v${version}";
      hash = "sha256-KKImGxFGjClM2wAk/L8nwauOkM/gEwRVMZhTP62ETqY=";
    };

    sourceRoot = "source/plugin";

    nativeBuildInputs = [ pkgs.python3Packages.hatchling ];
    propagatedBuildInputs = [ pkgs.python3Packages.requests ];
  };

  python-env = pkgs.python3.withPackages (
    ps: with ps; [
      discordpy
      python-dotenv
      pynacl
      psutil
      pip
      setuptools
      wheel
      requests
      yt-dlp-latest
      bgutil-ytdlp-pot-provider
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
