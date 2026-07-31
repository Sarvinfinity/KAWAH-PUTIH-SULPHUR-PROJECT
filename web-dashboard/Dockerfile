# --- Build Stage ---
FROM node:20-alpine AS build

WORKDIR /app

# Copy package configurations
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source assets
COPY . .

# Build production bundles
RUN npm run build

# --- Production Stage ---
FROM nginx:alpine

# Copy built assets to Nginx html directory
COPY --from=build /app/dist /usr/share/nginx/html

# Copy custom Nginx configuration if needed, or use default
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
