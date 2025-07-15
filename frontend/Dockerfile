# Stage 1: Build the application                                                        
FROM node:24-bookworm AS builder                                                        
WORKDIR /app                                                                            
                                                                                        
# Copy package files and install dependencies                                           
COPY package*.json ./                                                                   
RUN npm install                                                                         
                                                                                        
# Copy application source and build                                                     
COPY . .                                                                                
RUN npm run build                                                                       
                                                                                        
# Stage 2: Serve the application with Nginx                                             
FROM nginx:stable-alpine                                                                
                                                                                        
# Copy built assets from the builder stage                                              
COPY --from=builder /app/dist /usr/share/nginx/html                                     
                                                                                        
# Remove default Nginx config and add custom config to serve SPA on port 3000
RUN rm /etc/nginx/conf.d/default.conf
COPY <<EOF /etc/nginx/conf.d/app.conf
server {
    listen 3000;
    location / {
        root /usr/share/nginx/html;
        index index.html;
        try_files \$uri \$uri/ /index.html;
    }
}
EOF
                                                                                        
# Expose port 3000                                                                      
EXPOSE 3000                                                                             
                                                                                        
# Start Nginx                                                                           
CMD ["nginx", "-g", "daemon off;"]
