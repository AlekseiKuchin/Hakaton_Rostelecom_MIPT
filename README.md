### Deploying (for development)

1. Start DB: `docker-compose up -d db` (for local dev usage, uncomment lines 9 and 10 in `docker-compose.yaml` file firstly)
2. Import data: `python3 logger.py logfile1.log`
3. Start backend: `python -m flask --app=logger run` (or run in VS code)
