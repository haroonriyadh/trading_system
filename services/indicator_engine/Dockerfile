FROM python:3.12-alpine

WORKDIR /app

# Install requirements first (for caching)
COPY services/indicator_engine/requirements.txt ./
RUN python3 -m pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy shared module (includes symbols.json and symbols_loader.py)
COPY shared/ ./shared/

# Copy service files
COPY services/indicator_engine/*.py ./

CMD ["python3", "indicitor_Highs_Low.py"]
