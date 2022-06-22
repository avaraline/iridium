FROM python:alpine

ENV LANG=C.UTF-8 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    YARL_NO_EXTENSIONS=1 \
    MULTIDICT_NO_EXTENSIONS=1

COPY requirements.txt /iridium/
RUN pip install --no-cache-dir -Ur /iridium/requirements.txt

COPY . /iridium

RUN set -x && \
    mkdir -p /data && \
    python -m compileall -f -q /iridium

WORKDIR /iridium

VOLUME ["/data"]

EXPOSE 6667

CMD ["python", "-m", "iridium", "-c", "/etc/iridium.toml"]
