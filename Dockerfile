FROM python:3.10-slim

WORKDIR /app/
COPY src /app/src
COPY requirements.txt /app/requirements.txt

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc

RUN ["pip3", "install", "-r", "/app/requirements.txt"]

CMD ["python3", "/app/src/disk_info.py"]
