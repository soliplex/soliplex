# Soliplex

Soliplex is an AI Chat Client built with Flutter.

## Web Support & CORS

When running the Soliplex Web App (hosted at `https://soliplex.github.io/soliplex/webapp/` or locally) and connecting to a **local** backend or LLM provider (like Ollama on `localhost:11434`), you will likely encounter **CORS (Cross-Origin Resource Sharing)** errors.

This happens because the browser blocks the web page (origin `https://soliplex.github.io`) from reading data from your local server (origin `http://localhost:11434`) unless the server explicitly allows it.

### Fixing CORS for Ollama

If you are connecting directly to Ollama:

1.  **Stop Ollama** (ensure the menu bar icon is gone).
2.  **Set the `OLLAMA_ORIGINS` environment variable** to allow the Soliplex domain.

#### macOS
```bash
launchctl setenv OLLAMA_ORIGINS "https://soliplex.github.io"
# Restart Ollama app
```

#### Linux
Run the server with the variable:
```bash
OLLAMA_ORIGINS="https://soliplex.github.io" ollama serve
```

#### Windows
Set the environment variable in System Properties or PowerShell:
```powershell
$env:OLLAMA_ORIGINS="https://soliplex.github.io"; ollama serve
```

### Fixing CORS for Soliplex Server

If you are running the Python `soliplex` backend:

Ensure you start the server with CORS enabled for the web origin (this is usually the default in dev, but verify `middleware.cors` configuration).

## Getting Started

This project is a starting point for a Flutter application.

A few resources to get you started if this is your first Flutter project:

- [Lab: Write your first Flutter app](https://docs.flutter.dev/get-started/codelab)
- [Cookbook: Useful Flutter samples](https://docs.flutter.dev/cookbook)

For help getting started with Flutter development, view the
[online documentation](https://docs.flutter.dev/), which offers tutorials,
samples, guidance on mobile development, and a full API reference.
