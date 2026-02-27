FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir .
COPY src/ src/
COPY data/ data/
EXPOSE 8001
CMD ["python", "-m", "src.server", "--transport", "streamable-http", "--port", "8001"]
