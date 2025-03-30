### Backend dependencies

Installing dependencies:
```bash
pip install flask
pip install clickhouse-driver[numpy]
```

### DB

To run clickhouse db using docker:
```bash
# See https://hub.docker.com/_/clickhouse
docker run -it \
    --ulimit nofile=262144:262144 \
    -p 18123:8123 -p 19000:9000 \
    -e CLICKHOUSE_DB=logger \
    -e CLICKHOUSE_USER=test \
    -e CLICKHOUSE_DEFAULT_ACCESS_MANAGEMENT=1 \
    -e CLICKHOUSE_PASSWORD=test \
    clickhouse:25.3.2.39-jammy
```