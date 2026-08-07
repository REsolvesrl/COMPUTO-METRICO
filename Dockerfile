# Immagine per il deploy su Render (o qualsiasi host che supporti Docker).
#
# NOTA: Streamlit Community Cloud NON usa questo file: là vale solo
# requirements.txt. Questo serve agli host "veri" (Render, VPS, ecc.) dove
# anche i pacchetti di sistema vanno installati esplicitamente.

# Stessa minor version di Python usata in locale (3.14): le versioni pinnate
# in requirements.txt sono state collaudate lì, così si installano le stesse
# ruote precompilate.
FROM python:3.14-slim

# opencv-python-headless non apre finestre (niente libGL), ma le sue ruote
# restano legate a libgthread di GLib: senza questo pacchetto l'import di cv2
# fallisce con "libgthread-2.0.so.0: cannot open shared object file".
RUN apt-get update && apt-get install -y --no-install-recommends \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Le dipendenze prima del codice: così Docker riusa la cache quando
# cambiano solo i sorgenti.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# Render inietta $PORT a runtime; in locale si usa 8501.
EXPOSE 8501
CMD streamlit run streamlit_app.py \
    --server.port=${PORT:-8501} \
    --server.address=0.0.0.0
