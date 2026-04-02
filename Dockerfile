FROM python:3.11

# ============================================================
# 1. DÉPENDANCES SYSTÈME
# ============================================================
RUN apt-get update && apt-get install -y --no-install-recommends \
    # WeasyPrint dependencies
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libpangoft2-1.0-0 \
    libffi-dev \
    libgdk-pixbuf-2.0-0 \
    libcairo2 \
    libgirepository1.0-dev \
    gir1.2-pango-1.0 \
    # Réseau bas niveau
    arp-scan \
    iputils-ping \
    net-tools \
    iproute2 \
    # mDNS/Avahi
    avahi-utils \
    # NetBIOS (Windows discovery) - Temporarily removed due to AV blocking
    # nbtscan \
    # SNMP
    snmp \
    libsnmp-dev \
    # DNS
    dnsutils \
    # Compilation
    gcc \
    python3-dev \
    libpcap-dev \
    # SSH client
    openssh-client \
    && rm -rf /var/lib/apt/lists/*

# ============================================================
# 2. INSTALLATION PYTHON
# ============================================================
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --default-timeout=1000 -r requirements.txt

# ============================================================
# 3. CODE APPLICATION
# ============================================================
COPY . .

# ============================================================
# 4. COLLECTSTATIC
# ============================================================
RUN python manage.py collectstatic --noinput || true

# ============================================================
# 5. EXPOSITION PORT
# ============================================================
EXPOSE 8000

# ============================================================
# 6. ENTRYPOINT
# ============================================================
CMD ["gunicorn", "InfraContol.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120"]
