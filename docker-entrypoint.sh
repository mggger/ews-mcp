#!/bin/bash
set -e

# Ensure log directories exist with proper permissions
echo "Setting up log directories..."

# Create main logs directory if it doesn't exist
if [ ! -d "/app/logs" ]; then
    echo "Creating /app/logs directory..."
    mkdir -p /app/logs
fi

# Create analysis subdirectory if it doesn't exist
if [ ! -d "/app/logs/analysis" ]; then
    echo "Creating /app/logs/analysis directory..."
    mkdir -p /app/logs/analysis
fi

# Ensure proper ownership (only if we have permission)
if [ -w "/app/logs" ]; then
    echo "Setting permissions on /app/logs..."
    chmod -R 755 /app/logs 2>/dev/null || echo "Warning: Could not set permissions on /app/logs"
else
    echo "Warning: /app/logs is not writable. Logs may fail to write."
fi

echo "Log directories ready."
echo "Starting EWS MCP Server..."

# Execute the main command
exec "$@"
