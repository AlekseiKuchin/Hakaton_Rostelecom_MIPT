### Backend dependencies

Installing dependencies:
```bash
pip install flask clickhouse-driver pandas pyarrow
```

### DB

Starting DB:
```bash
docker-compose up -d db
```

Importing data (from `logfile1.log`):
```bash
python3 logger.py logfile1.log
```
