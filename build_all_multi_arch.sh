#!/bin/bash

# Build and push all Docker images to ACR with Multi-arch support (AMD64 & ARM64)
# ACR Registry: aksacr1.azurecr.io
# Version: latest
# Platforms: linux/amd64, linux/arm64

set -e  # Exit on error

ACR="aksacr1.azurecr.io"
VERSION="latest"
PLATFORM="linux/amd64,linux/arm64"

echo "============================================"
echo "Multi-Arch Docker Build & Push to ACR"
echo "Platforms: $PLATFORM"
echo "Registry: $ACR"
echo "Version: $VERSION"
echo "============================================"
echo ""

# Change to Ecomm directory
cd "$(dirname "$0")"

# Setup Docker Buildx builder for multi-platform support
echo "🔧 Setting up Docker Buildx builder..."
if ! docker buildx inspect multiarch-builder > /dev/null 2>&1; then
  docker buildx create --name multiarch-builder --driver docker-container --use
  docker buildx inspect --bootstrap
else
  docker buildx use multiarch-builder
fi

# Array of microservices to build
services=(
  "api-gateway"
  "auth-service"
  "cart-service"
  "order-service"
  "payment-service"
  "product-service"
  "review-service"
  "user-service"
  "vault-service"
  "wishlist-service"
)

# Build and Push Microservices
for service in "${services[@]}"; do
  echo "================================================"
  echo "Building: $service"
  echo "================================================"
  
  SERVICE_PATH="services/$service"
  IMAGE_NAME="$ACR/$service:$VERSION"
  
  if [ ! -d "$SERVICE_PATH" ]; then
    echo "❌ ERROR: $SERVICE_PATH not found"
    continue
  fi
  
  echo "🔨 Building & Pushing: $IMAGE_NAME"
  docker buildx build --platform $PLATFORM -t $IMAGE_NAME "$SERVICE_PATH" --push
  
  echo "✅ $service completed!"
  echo ""
done

# Build and Push Frontend
if [ -d "frontend" ]; then
  echo "================================================"
  echo "Building: frontend"
  echo "================================================"
  
  FRONTEND_IMAGE="$ACR/frontend:$VERSION"
  echo "🔨 Building & Pushing: $FRONTEND_IMAGE"
  docker buildx build --platform $PLATFORM -t $FRONTEND_IMAGE frontend/ --push
  
  echo "✅ frontend completed!"
else
  echo "⚠️  frontend directory not found (skipping)"
fi

echo ""
echo "============================================"
echo "✅ ALL MULTI-ARCH BUILDS AND PUSHES COMPLETED!"
echo "============================================"
echo ""
