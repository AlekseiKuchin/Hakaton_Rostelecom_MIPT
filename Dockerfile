FROM python:3.13.3-bookworm

WORKDIR /root

COPY requirements.txt /root/requirements.txt

RUN pip3 install --break-system-packages -r requirements.txt

COPY logger.py /root/logger.py
COPY static /root/static

ENTRYPOINT ["python3", "-m", "flask", "--app=logger", "run", "--host=0.0.0.0"]

EXPOSE 5000
