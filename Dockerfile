FROM nixos/nix:latest

WORKDIR /app
COPY shell.nix .

RUN nix-shell shell.nix --run true
COPY . .

CMD ["nix-shell", "shell.nix", "--run", "python main.py"]
