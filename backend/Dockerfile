FROM python:3.13-slim AS builder

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
# Set the working directory
WORKDIR /app
# Copy the requirements file
COPY requirements.txt /app/requirements.txt
# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt
# Copy the application code
COPY . /app
EXPOSE 2155
# Command to run the application
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "2155"]
