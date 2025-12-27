#!/bin/bash
# Startup script for Render.com

echo "Starting PDF Telegram Bot..."

# Activate Python environment (Render handles this automatically)
# source venv/bin/activate  # Uncomment if using virtualenv

# Set environment variables
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Create necessary directories
mkdir -p logs
mkdir -p temp

# Set proper permissions
chmod -R 755 temp/

# Run the application
echo "Starting Gunicorn server..."
exec gunicorn bot:app \
    --bind 0.0.0.0:$PORT \
    --workers 1 \
    --threads 8 \
    --timeout 120 \
    --access-logfile logs/access.log \
    --error-logfile logs/error.log \
    --log-level info
