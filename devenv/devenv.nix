{ pkgs, lib, config, ... }:

{
  languages.python = {
    enable = true;
    directory = "..";
    venv.enable = true;
    uv = {
      enable = true;
      sync.enable = true;
    };
  };

  services.postgres = {
    enable = true;
    listen_addresses = "127.0.0.1";
    initialDatabases = [
      { name = "soliplex"; }
    ];
  };

  packages = [
    pkgs.git
  ];

  dotenv.enable = true;

  env.UV_PYTHON = lib.mkForce (config.env.DEVENV_STATE + "/venv/bin/python");
  env.UV_CACHE_DIR = config.env.DEVENV_STATE + "/uv_cache";

  scripts = let
    root = builtins.dirOf config.devenv.root;
  in {
    serve.exec = ''
      exec uv run soliplex-cli serve ${root}/example/minimal.yaml --no-auth-mode --port 8555 "$@"
    '';

    init-rag.exec = ''
      mkdir -p ${root}/db/rag
      haiku-rag --config ${config.devenv.root}/haiku.rag.yaml init --db ${root}/db/rag/rag.lancedb
      haiku-rag --config ${config.devenv.root}/haiku.rag.yaml migrate --db ${root}/db/rag/rag.lancedb
      haiku-rag --config ${config.devenv.root}/haiku.rag.yaml add-src --db ${root}/db/rag/rag.lancedb ${root}/docs/
    '';

    init-ollama.exec = ''
      ollama pull qwen3-embedding:4b
      ollama pull gpt-oss:latest
    '';

    audit.exec = ''
      exec uv run soliplex-cli audit ${root}/example/minimal.yaml "$@"
    '';

    init.exec = ''
      echo "Initializing soliplex development environment..."
      init-rag
      echo ""
      echo "Running config audit..."
      audit
      echo ""
      echo "Done! Run 'devenv up' or 'serve' to start the server."
    '';
  };

  processes.docling-serve.exec = ''
    trap 'docker stop devenv-docling-serve 2>/dev/null' EXIT
    docker run --rm --name devenv-docling-serve -p 5001:5001 quay.io/docling-project/docling-serve
  '';

  processes.soliplex.exec = "serve";

  enterShell = ''
    echo "soliplex dev environment ready"
    echo "Python: $(python --version 2>&1)"
    echo "uv: $(uv --version)"
    echo ""
    echo "Commands:"
    echo "  init           - First-time setup (RAG db + audit)"
    echo "  init-ollama    - Pull required Ollama models"
    echo "  init-rag       - Initialize RAG database"
    echo "  audit          - Validate configuration"
    echo "  serve          - Start the dev server (no auth)"
    echo "  uv run pytest  - Run tests"
  '';
}
