FROM node:24-bookworm AS builder

# Set the working directory
WORKDIR /app
# Copy the package.json file
COPY package.json ./
# Install dependencies
RUN npm install
# Copy the application code
COPY . .
# Build the application
RUN npm run build
# Set the command to run the application
CMD ["npm", "run", "preview", "--", "--port", "3000"]
# Expose the port the app runs on
EXPOSE 3000
