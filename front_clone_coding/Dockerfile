FROM mcr.microsoft.com/playwright:v1.49.0-noble

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --omit=dev

COPY bin/ ./bin/
COPY src/ ./src/
COPY web/ ./web/

RUN mkdir -p /app/output && chown -R pwuser:pwuser /app

EXPOSE 20000

USER pwuser

CMD ["node", "bin/cli.js", "ui"]
