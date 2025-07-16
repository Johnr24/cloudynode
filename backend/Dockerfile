# Stage 1: Build frontend
FROM node:24-bookworm AS frontend-builder
WORKDIR /app
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ .
RUN npm run build

# Stage 2: Create final image
FROM python:3.13-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
# Set the working directory
WORKDIR /app
# Copy the requirements file
COPY backend/requirements.txt /app/requirements.txt
# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt
# Copy the application code
COPY backend/ /app
# Copy built frontend from builder stage
COPY --from=frontend-builder /app/dist /app/static

EXPOSE 2155
# Command to run the application
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "2155"]
