#!/bin/bash
SERVICES=("api-gateway" "user-service" "auth-service" "product-service" "cart-service" "order-service" "payment-service" "review-service" "vault-service" "wishlist-service")
REGISTRY="aksacr1.azurecr.io"
TAG="v1"
PLATFORM="linux/amd64"

# Build and push microservices
for service in "${SERVICES[@]}"; do
    echo "Building and pushing $service..."
    docker build --platform $PLATFORM -t $REGISTRY/$service:$TAG services/$service/ && docker push $REGISTRY/$service:$TAG
done

# Build and push frontend
echo "Building and pushing frontend..."
docker build --platform $PLATFORM -t $REGISTRY/frontend:$TAG frontend/ && docker push $REGISTRY/frontend:$TAG

echo "All images pushed successfully with tag $TAG for $PLATFORM"
