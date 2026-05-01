FROM python:3.10-slim

WORKDIR /app

# ✅ Install only necessary system deps + git
RUN apt-get update && apt-get install -y \
    git \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# ✅ Copy requirements first (for caching)
COPY requirements.txt .

# ✅ Install CPU-only PyTorch FIRST (faster & lighter)
RUN pip install --no-cache-dir \
    torch torchvision --index-url https://download.pytorch.org/whl/cpu

# ✅ Install remaining dependencies
RUN pip install --no-cache-dir -r requirements.txt

# ✅ Copy only needed project files (NOT everything)
COPY app.py .
COPY chat_ui ./chat_ui
COPY models ./models

# Create uploads folder
RUN mkdir -p uploads

EXPOSE 5000

CMD ["python", "app.py"]