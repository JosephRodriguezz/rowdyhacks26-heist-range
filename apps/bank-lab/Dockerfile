FROM node:24-alpine AS builder
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm install --global pnpm@11.19.0
COPY package.json pnpm-lock.yaml .npmrc ./
RUN pnpm install --frozen-lockfile --ignore-scripts
COPY . .
RUN pnpm build

FROM node:24-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 HOSTNAME=0.0.0.0 PORT=3000
RUN addgroup -S -g 1001 bank && adduser -S -u 1001 -G bank bank
COPY --from=builder --chown=bank:bank /app/.next/standalone ./
COPY --from=builder --chown=bank:bank /app/.next/static ./.next/static
COPY --from=builder --chown=bank:bank /app/src/lib ./src/lib
COPY --from=builder --chown=bank:bank /app/scripts ./scripts
USER bank
EXPOSE 3000
CMD ["node", "server.js"]
