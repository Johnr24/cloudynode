# Stage 1: Build the application                                                        
FROM node:24-bookworm AS builder
ARG VITE_BACKEND_HOST
ENV VITE_BACKEND_HOST=${VITE_BACKEND_HOST:-localhost:2155}
WORKDIR /app                                                                            
                                                                                        
# Copy package files and install dependencies                                           
COPY package*.json ./                                                                   
RUN npm install                                                                         
                                                                                        
# Copy application source and build                                                     
COPY . .                                                                                
RUN npm run build                                                                       
                                                                                        
# Stage 2: Serve the application with Nginx                                             
FROM nginx:stable-alpine                                                                
                                                                                        
# Create a non-root user with UID/GID 3000 for Nginx.
# Alpine linux uses 'adduser' and 'addgroup'.
RUN addgroup -g 3000 -S appgroup && adduser -u 3000 -S -G appgroup appuser

# Copy built assets from the builder stage and set ownership
COPY --from=builder --chown=appuser:appgroup /app/dist/. /usr/share/nginx/html

# Set permissions for directories to be owned by user 3000.
# This is necessary when running the container with a specific user ID,
# as Nginx needs to write to its cache.
RUN mkdir -p /var/cache/nginx && \
    chown -R appuser:appgroup /var/cache/nginx

# Update nginx.conf to use a writable pid path and comment out user directive.
# This is necessary for running as a non-root user.
RUN sed -i -e 's#pid\s+/var/run/nginx.pid;#pid /tmp/nginx.pid;#' -e 's/^user\s+nginx;/#user nginx;/' /etc/nginx/nginx.conf
                                                                                        
# Remove default Nginx config and add custom config to serve SPA on port 2156
RUN rm /etc/nginx/conf.d/default.conf
COPY <<EOF /etc/nginx/conf.d/app.conf
server {
    listen 2156;
    location / {
        root /usr/share/nginx/html;
        index index.html;
        try_files \$uri \$uri/ /index.html;
    }
}
EOF
                                                                                        
# Expose port 2156                                                                      
EXPOSE 2156                                                                             

# Switch to the non-root user
USER appuser
                                                                                        
# Start Nginx                                                                           
CMD ["nginx", "-g", "daemon off;"]
