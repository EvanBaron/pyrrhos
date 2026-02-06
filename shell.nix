{
  pkgs ? import <nixpkgs> { },
}:

pkgs.mkShell {
  buildInputs = [
    (pkgs.python3.withPackages (ps: [ ps.pip ]))
    pkgs.ffmpeg
  ];

  shellHook = ''
    if [ -L .venv ]; then rm .venv; fi

    if [ ! -d .venv ]; then
      echo "Creating virtual environment..."
      python -m venv .venv
    fi

    source .venv/bin/activate

    export LD_LIBRARY_PATH=${
      pkgs.lib.makeLibraryPath [
        pkgs.ffmpeg
        pkgs.libsodium
      ]
    }:$LD_LIBRARY_PATH
    export PIP_USER=0

    pip install --upgrade pip --quiet

    pip install --upgrade --force-reinstall "yt-dlp[default] @ https://github.com/yt-dlp/yt-dlp/archive/master.tar.gz" --quiet
    pip install --upgrade bgutil-ytdlp-pot-provider --quiet

    if [ -f requirements.txt ]; then
        pip install -r requirements.txt --quiet
    fi

    echo "Environment ready!"
    echo -n "yt-dlp version: "
    yt-dlp --version
  '';
}
