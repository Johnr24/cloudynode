FROM python:3.13-slim AS builder

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Create a non-root user with UID/GID 3000
RUN groupadd -r -g 3000 appgroup && useradd --no-log-init -r -g appgroup -u 3000 appuser
# Set the working directory
WORKDIR /app
# Copy the requirements file
COPY requirements.txt /app/requirements.txt
# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt
# Copy the application code
COPY . /app

# Change ownership of the app directory to the new user
RUN chown -R appuser:appgroup /app

# Switch to the non-root user
USER appuser

EXPOSE 2155
# Command to run the application
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "2155"]
