# Python 3.12 image
FROM python:3.12-slim

# System tools
RUN apt-get update && apt-get install -y \
    build-essential \
    pkg-config \
    libasound2-dev \
    curl \
    git \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Rust o‘rnatish
RUN curl https://sh.rustup.rs -sSf | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

# Working directory
WORKDIR /app

# Requirements faylini containerga ko‘chirish
COPY requirements.txt .

# Python paketlarini o‘rnatish
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Loyiha fayllarini ko‘chirish
COPY . .

# Botni ishga tushirish
CMD ["python", "bot.py"]

