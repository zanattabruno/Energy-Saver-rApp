FROM zanattabruno/cplex-python38:latest

# Update system packages
RUN apt update && apt upgrade -y && apt autoremove -y

# Set working directory
WORKDIR /app

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN /usr/local/bin/python3.8 -m pip install --upgrade pip && \
    /usr/local/bin/python3.8 -m pip install -r requirements.txt

# Copy the entire src directory with proper structure
COPY src/ ./src/

# Copy any additional configuration or policy files if needed
COPY policies/ ./policies/

# Set Python path to include the src directory
ENV PYTHONPATH=/app/src:/app

# Create a non-root user for security
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Set the entrypoint to bash for interactive use
ENTRYPOINT ["/bin/bash"]

# Default command (can be overridden)
CMD []
