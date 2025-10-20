# Docker Setup for Soliplex Flutter Web

This directory contains Docker configuration for building and running the Soliplex Flutter web application.

## Files

- `Dockerfile` - Multi-stage build that compiles Flutter web and serves it with nginx
- `docker-compose.yml` - Orchestration for production and development environments
- `.dockerignore` - Excludes unnecessary files from the Docker build context

## Usage

### Production Build

Build and run the production web server:

```bash
cd src/flutter
docker-compose up --build
```

The web application will be available at `http://localhost:9000`

### Development with Hot Reload

Run the development server with hot reload:

```bash
cd src/flutter
docker-compose --profile dev up dev
```

The development server will be available at `http://localhost:9001`

## Building the Docker Image Directly

To build the Docker image without docker-compose:

```bash
cd src/flutter
docker build -f Dockerfile -t soliplex-web .
docker run soliplex-web
```
