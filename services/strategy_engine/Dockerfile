FROM python:3.12-alpine

WORKDIR /app

# Install requirements first (for caching)
COPY services/strategy_engine/requirements.txt ./
RUN python3 -m pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy shared module
COPY shared/ ./shared/

# Copy service files
COPY services/strategy_engine/*.py ./

CMD ["python3", "Strategy_Engine.py"]
