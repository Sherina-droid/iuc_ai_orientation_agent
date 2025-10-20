FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js and npm
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs

# Copy backend requirements and install Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create n8n directory and install n8n with dependencies
RUN mkdir -p /opt/n8n
WORKDIR /opt/n8n
RUN npm init -y
RUN npm install n8n franc langs

# Copy application files
WORKDIR /app
COPY backend/ ./backend/
COPY UI/ ./UI/
COPY workflow.json ./

# Create n8n config directory
RUN mkdir -p /root/.n8n

# Expose ports
EXPOSE 8000 5678 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start script
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

CMD ["/app/start.sh"]
