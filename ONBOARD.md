# Onboarding Soliplex

## Backend

Main repo to clone, [this one](https://github.com/soliplex/soliplex):
```
$ git clone git@github.com:soliplex/soliplex.git
```

Once cloned, copy the `.env.example` as `.env` and assign your values to the relevant environment variables.
Next, build:
```
$ cd soliplex/
$ cp .env.example .env
$ docker compose build
```

Generate your `installation` directory. Either start from scratch, or copy the `example` one:
```
cp -R example installation
```
Notice that by default, `soliplex` will look for a `installation.yaml` file inside the `installation` folder. You can either change this with your own command for starting `soliplex-cli` or simply by making sure your config is properly made inside this file.

Once built, start the process:
```
$ docker compose up
```

### Debugging

`debugpy` is included as a `dev` dependency for soliplex, and it should listen on port `5678`. There is already a `.vscode/launch.json` included at the root of the repo, so if you are using VSCode, after the process is up, you can go to the `Debug` tab in VSCode and connect to the running process.

### Sandboxed python modules

You can include Python modules, to be executed in rooms in their own sandbox. A "server_time" is included as example at `sandbox/environments/server_time`, configured to be used in the `example/rooms/server_time` room. It is important to notice that a proper description should be included in the `pyproject.toml` for your module, in order for the AI agent to pass the correct `environment_name` to the `execute_script` call.
Notice that changes to these modules will require a `docker compose build` in order for the code to be updated and used.

### Indexing documents automatically

Automatically, a `haiku.rag.lancedb` will be created in `db/rag` folder. And automatically, it will index `PDF` documents from inside the `documents` folder. New files will be created next to each `PDF` file with a `.index` extension will be created so the script knows this `PDF` was already indexed. If you want to have the automatic process re-index this `PDF`, simply delete the `.index` file and restart.

### Running haiku.rag commands manually

You can jump inside the docker container with `docker compose run soliplex_backend /bin/bash` and manually run `haiku-rag` commands.


## Frontend

In order to add the Flutter frontend to the mix, you should clone the [Flutter frontend](https://github.com/soliplex/frontend) into `src/`:
```
$ cd src/
$ git clone git@github.com:soliplex/frontend.git
```

Once cloned, go back to the main `soliplex` repo, uncomment the relevant lines in `docker-compose.yaml`:

```
  soliplex_frontend:
    build:
      context: ./src/frontend
      dockerfile: Dockerfile
      target: dev
    ports:
      - "9000:9000"
    volumes:
      - ./src/frontend:/app
    networks:
      - soliplex_net
```

And build again
```
$ docker compose build
```

Once finished, start all
```
$ docker compose up
```

Once up, you can visit http://localhost:9000/ in your browser. The soliplex backend can be reached at http://localhost:8000


## Chatbot widget

In order to add the chatbot widget to the mix, you should clone the [chatbot repo](https://github.com/soliplex/chatbot) into `src/`:
```
$ cd src/
$ git clone git@github.com:soliplex/chatbot.git
```

Once cloned, go back to the main `soliplex` repo, uncomment the relevant lines in `docker-compose.yaml`:

```
  chatbot_builder:
    build:
      context: ./src/chatbot
      dockerfile: Dockerfile
    ports:
      - "35729:35729"
    volumes:
      - ./src/chatbot:/app
      - /app/node_modules
    environment:
      - ESBUILD_POLL=true
    networks:
      - soliplex_net

  chatbot_dev:
    build:
      context: ./src/chatbot
      dockerfile: Dockerfile
    command: npm run dev
    ports:
      - "3000:3000"
    volumes:
      - ./src/chatbot:/app
      - /app/node_modules
    environment:
      - WATCHPACK_POLLING=true
    networks:
      - soliplex_net

  chatbot_widget:
    image: nginx:alpine
    ports:
      - "8080:80"
    volumes:
      - ./src/chatbot/public:/usr/share/nginx/html:ro
      - ./src/chatbot/nginx-widget.conf:/etc/nginx/conf.d/default.conf:ro
    depends_on:
      - chatbot_builder
    networks:
      - soliplex_net
```

And build again
```
$ docker compose build
```

Once finished, start all
```
$ docker compose up
```

At this point, you can access the widget in "dev mode" at http://localhost:3000/ where changes to the code are applied live, as a normal React App.
In addition, you can access http://localhost:8080/ to use it through Nginx, with the compiled JS embedded. Changes to the code, will reload the whole page.
