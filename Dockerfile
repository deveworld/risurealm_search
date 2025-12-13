FROM python:3.11-slim

WORKDIR /app

# Install uv
RUN pip install uv

# Copy dependency files
COPY pyproject.toml .

# Install dependencies
RUN uv pip install --system -e .

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
