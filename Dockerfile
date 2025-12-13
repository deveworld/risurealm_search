FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY main.py .
COPY searcher/ searcher/
COPY ui/ ui/

# Copy data (vector database)
COPY data/chroma_db/ data/chroma_db/

# Expose Gradio port
EXPOSE 7860

# Environment variable for Voyage API
ENV VOYAGE_API_KEY=""

# Run Gradio UI
CMD ["python", "main.py", "ui", "--port", "7860"]
