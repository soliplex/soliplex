# Multi-stage build for Flutter web application
# Stage 1: Builder
FROM ghcr.io/cirruslabs/flutter:3.37.0-0.1.pre AS builder

WORKDIR /app

COPY ./pubspec.yaml ./pubspec.lock ./
RUN flutter pub get

COPY . .

RUN flutter build web --release

# Stage 2:  nginx
FROM nginx:alpine

COPY --from=builder /app/build/web /usr/share/nginx/html

# Copy nginx configuration (optional, using default for now)
# This should be uncommented to include the routing for /api 
COPY nginx.conf /etc/nginx/conf.d/soliplex.conf
RUN rm -f /etc/nginx/conf.d/default.conf

# Expose port 9000
EXPOSE 9000

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
