FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# SnapDeploy can override this with its assigned PORT environment variable.
ENV PORT=1024
EXPOSE 1024

CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT} app:app"]
