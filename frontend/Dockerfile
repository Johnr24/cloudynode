FROM node:24-bookworm AS builder

# Set the working directory
WORKDIR /app
# Copy the package.json and package-lock.json files
COPY package*.json ./
# Copy the application code
COPY . .
# Install dependencies
RUN npm install
# Build the application
RUN npm run build
# Set the command to run the application
CMD ["npm", "run", "preview", "--", "--port", "3000"]
# Expose the port the app runs on
EXPOSE 3000
