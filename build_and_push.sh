#!/bin/bash

# Build and push all Docker images to ACR with AMD platform
# ACR Registry: aksacr1.azurecr.io
# Version: v1
# Platform: linux/amd64 (AMD/Intel x86_64)

set -e  # Exit on error

ACR="aksacr1.azurecr.io"
VERSION="v1"
PLATFORM="linux/amd64"

cleanup_image() {
  local image="$1"
  echo "🧹 Removing old local image: $image"
  docker rmi -f "$image" >/dev/null 2>&1 || true
}

echo "============================================"
echo "Docker Build & Push to ACR"
echo "Platform: $PLATFORM"
echo "Registry: $ACR"
echo "Version: $VERSION"
echo "============================================"
echo ""

cd "$(dirname "$0")"

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

  if [ ! -f "$SERVICE_PATH/Dockerfile" ]; then
    echo "❌ ERROR: $SERVICE_PATH/Dockerfile not found"
    continue
  fi

  cleanup_image "$IMAGE_NAME"
  echo "🔨 Building: $IMAGE_NAME (platform: $PLATFORM, no-cache)"
  docker build --no-cache --platform $PLATFORM -t $IMAGE_NAME $SERVICE_PATH

  echo "📤 Pushing: $IMAGE_NAME"
  docker push $IMAGE_NAME

  echo "✅ $service completed!"
  echo ""
done

if [ -f "frontend/Dockerfile" ]; then
  echo "================================================"
  echo "Building: frontend"
  echo "================================================"

  FRONTEND_IMAGE="$ACR/frontend:$VERSION"
  cleanup_image "$FRONTEND_IMAGE"
  echo "🔨 Building: $FRONTEND_IMAGE (platform: $PLATFORM, no-cache)"
  docker build --no-cache --platform $PLATFORM -t $FRONTEND_IMAGE frontend/

  echo "📤 Pushing: $FRONTEND_IMAGE"
  docker push $FRONTEND_IMAGE

  echo "✅ frontend completed!"
else
  echo "⚠️  frontend/Dockerfile not found (skipping)"
fi

echo ""
echo "============================================"
echo "✅ ALL BUILDS AND PUSHES COMPLETED!"
echo "============================================"
echo ""
echo "Pushed images:"
for service in "${services[@]}"; do
  echo "  - $ACR/$service:$VERSION"
done
echo "  - $ACR/frontend:$VERSION (if exists)"