FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# trading-bot may have its own deps for approve/execute; install lightly if present
COPY vendor/trading-bot/requirements.txt /tmp/bot-requirements.txt
RUN pip install --no-cache-dir -r /tmp/bot-requirements.txt || true
COPY . .
ENV STAGE_APP_PIN=""
ENV BOT_ROOT=/app/vendor/trading-bot
ENV EQUITY_SCAN_DIR=/app/vendor/equity-scan
ENV PORT=8787
EXPOSE 8787
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8787}"]
