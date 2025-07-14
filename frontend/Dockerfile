FROM node:24-bookworm AS builder

# Set environment variables
ENV NODE_ENV=production
# Set the working directory
WORKDIR /app
# Copy the package.json and package-lock.json files
COPY package.json /app/
# Copy the application code
COPY .* /app
# Install dependencies
RUN npm install --production
# Build the application
RUN npm run build
# Set the working directory for the production build
CMD ["npm", "start"]
# Expose the port the app runs on
EXPOSE 3000