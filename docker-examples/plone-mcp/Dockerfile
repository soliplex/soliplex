FROM node:20-slim AS base-build

RUN apt-get update && apt-get install -y \
    git \
    openssh-client \
    && rm -rf /var/lib/apt/lists/*

RUN corepack enable && corepack prepare pnpm@latest --activate

WORKDIR /app

RUN mkdir -p /root/.ssh && \
    ssh-keyscan github.com >> /root/.ssh/known_hosts

RUN git clone https://github.com/plone/plone-mcp.git . && \
    pnpm install && \
    pnpm run build

FROM node:20-slim

WORKDIR /app
COPY --from=base-build /app/dist ./dist
COPY --from=base-build /app/package.json ./
COPY --from=base-build /app/pnpm-lock.yaml ./

RUN corepack enable && \
    corepack prepare pnpm@latest --activate && \
    pnpm install --prod

EXPOSE 3000

CMD ["node", "/app/dist/index.js"]
