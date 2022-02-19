FROM python:3.8-slim-buster

WORKDIR /app/
COPY src /app/src
COPY requirements.txt /app/requirements.txt

RUN ["pip3", "install", "-r", "/app/requirements.txt"]

CMD ["python3", "/app/src/pods_distribution.py"]
