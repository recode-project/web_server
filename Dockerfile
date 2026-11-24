# Gunakan base image Python yang ringan
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install system dependencies (GCC diperlukan untuk psutil & file_lister.c)
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements dan install dependencies Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy seluruh source code backend ke dalam container
COPY . .

# Compile file_lister.c agar executable di dalam container
RUN gcc -o file_lister file_lister.c

# Expose port Flask (default 5000, tapi kita pakai Gunicorn nanti di 80/custom)
EXPOSE 5000

# Environment Variable biar Python output langsung tampil di logs
ENV PYTHONUNBUFFERED=1

# Command untuk menjalankan aplikasi menggunakan Gunicorn (Production Server)
# Worker class 'eventlet' wajib untuk SocketIO
CMD ["gunicorn", "--worker-class", "eventlet", "-w", "1", "-b", "0.0.0.0:5000", "--access-logfile", "-", "app:app"]
