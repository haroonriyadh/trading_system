FROM python:3.12-alpine

WORKDIR /app

# Install requirements first (for caching)
COPY services/monitoring_engine/requirements.txt ./
RUN python3 -m pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy shared module
COPY shared/ ./shared/

# Copy service files
COPY services/monitoring_engine/*.py ./

CMD ["python3", "Position_Monitor.py"]
