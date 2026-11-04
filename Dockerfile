FROM debian:trixie-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
      python3 python3-venv iproute2 iperf3 iputils-ping procps ca-certificates \
    && rm -rf /var/lib/apt/lists/*
RUN python3 -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH PYTHONUNBUFFERED=1
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
WORKDIR /demo
