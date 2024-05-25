FROM us-central1-docker.pkg.dev/genuine-flight-317411/devel/base/python3.12-dev as builder

ENV LANG=C.UTF-8
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/app/venv/bin:$PATH"

WORKDIR /app/

RUN python -m venv /app/venv
COPY requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir -r /app/requirements.txt

FROM us-central1-docker.pkg.dev/genuine-flight-317411/devel/base/python3.12

WORKDIR /app/

ENV PYTHONUNBUFFERED=1
ENV PATH="/venv/bin:$PATH"
ENV PYTHONPATH=$PYTHONPATH:.

COPY src /app/src
COPY --from=builder /app/venv /venv

ENTRYPOINT ["python", "/app/src/disk_info.py"]