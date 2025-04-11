### Deploying (for development)

1. Start DB: `docker-compose up -d db`
2. Import data: `python3 logger.py logfile1.log`
3. Start backend: `python -m flask --app=logger run` (or run in VS code)
