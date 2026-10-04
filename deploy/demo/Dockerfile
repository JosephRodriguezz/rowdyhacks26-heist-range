FROM node:24-bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends python3 \
    && rm -rf /var/lib/apt/lists/* \
    && npm install -g pnpm@11.19.0
WORKDIR /demo/apps/bank-lab
COPY apps/bank-lab/package.json apps/bank-lab/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile --ignore-scripts
WORKDIR /demo
COPY core ./core
COPY red ./red
COPY backend/app ./backend/app
COPY integrations/mayo ./integrations/mayo
COPY apps/bank-lab/src/lib ./apps/bank-lab/src/lib
COPY apps/bank-lab/integration ./apps/bank-lab/integration
RUN mkdir -p /demo/.core-state && chown node:node /demo/.core-state
USER node
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
CMD ["python3", "-m", "core.cli", "demo", "--no-browser", "--port", "8765"]
