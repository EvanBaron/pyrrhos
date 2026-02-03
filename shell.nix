{
  pkgs ? import <nixpkgs> { },
}:
let
  python-env = pkgs.python3.withPackages (
    ps: with ps; [
      discordpy
      python-dotenv
      pynacl
      psutil
      pip
      yt-dlp
      bgutil-ytdlp-pot-provider
      yt-dlp-ejs
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

    export PIP_PREFIX="$PWD/.pip_packages"
    export PYTHONPATH="$PIP_PREFIX/${python-env.sitePackages}:$PYTHONPATH"
    export PATH="$PIP_PREFIX/bin:$PATH"
    export PIP_CONFIG_FILE=/dev/null

    mkdir -p "$PIP_PREFIX"
    pip install --force-reinstall --ignore-installed "yt-dlp[default] @ https://github.com/yt-dlp/yt-dlp/archive/master.tar.gz"
    pip install --upgrade --ignore-installed --prefix="$PIP_PREFIX" bgutil-ytdlp-pot-provider --quiet
    pip install --prefix="$PIP_PREFIX" -r requirements.txt --quiet

    echo "Environment ready!"
    echo -n "yt-dlp version: "
    yt-dlp --version

    ln -sfn ${python-env} .venv
  '';
}
