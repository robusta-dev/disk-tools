FROM python:3.12-slim as builder

ENV LANG=C.UTF-8
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/app/venv/bin:$PATH"

WORKDIR /app/

RUN python -m venv /app/venv

RUN apt-get update \
  # required for psutil python package to install
  && apt-get install -y gcc \
  && dpkg --add-architecture arm64 \
  && apt-get purge -y --auto-remove \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir -r /app/requirements.txt

FROM python:3.12-slim

WORKDIR /app/

ENV PYTHONUNBUFFERED=1
ENV PATH="/venv/bin:$PATH"
ENV PYTHONPATH=$PYTHONPATH:.

COPY src /app/src
COPY --from=builder /app/venv /venv

# --- Fix CVE-2025-8869: Upgrade pip in system Python and clean up ---
RUN python -m pip uninstall -y pip && \
    rm -rf /usr/local/lib/python3.12/site-packages/pip* && \
    python -m ensurepip --upgrade && \
    python -m pip install --no-cache-dir pip==25.3 && \
    rm -rf /usr/local/lib/python3.12/ensurepip/_bundled/*

ENTRYPOINT ["python", "/app/src/disk_info.py"]