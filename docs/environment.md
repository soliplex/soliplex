# Environment Variables

Non-secret environment variables can and mostly should be configured
directly in the `installation.yaml` file (e.g. `example/installation.yaml`,
`example/minimal.yaml`, etc.).

Those files are checked into the Soliplex repository, and cannot know
the URL of your Ollama server (if you use Ollama), They therefore declare
the `OLLAMA_BASE_URL` variable without a value, meaning that the configuration
expects the value to be present in the environments (see:
<https://soliplex.github.io/soliplex/config/environment/>).

Those files also must not contain secrets (API keys, etc.):  instead,
they configure secret values to be found from the environment (see
<https://soliplex.github.io/soliplex/config/secrets/>).

If your installation configures such values to be found from the OS
environment, you can create a `.env` file which defines them, and arrange
for the file to be sourced into your environment before startin the Soliplex
application.

Copy `.env.example` to `.env` and edit it to configure your values:

```bash
cp .env.example .env
```
