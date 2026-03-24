FROM mcr.microsoft.com/playwright:v1.58.2-noble

WORKDIR /app

ENV NODE_ENV=production
ENV PORT=20000

COPY package.json package-lock.json ./
RUN npm ci --omit=dev

COPY --chown=pwuser:pwuser bin/ ./bin/
COPY --chown=pwuser:pwuser src/ ./src/
COPY --chown=pwuser:pwuser web/ ./web/

RUN mkdir -p /app/output && chown -R pwuser:pwuser /app/output

EXPOSE 20000

USER pwuser

CMD ["node", "bin/cli.js", "ui"]
