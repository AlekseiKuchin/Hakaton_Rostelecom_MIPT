FROM debian:bookworm-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    python3-flask && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY logger.py /logger.py
COPY static /static

ENTRYPOINT ["python3", "-m", "flask", "--app", "logger", "run"]

EXPOSE 5000
