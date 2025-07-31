#!/bin/bash

# Check if docker is installed
if ! command -v docker &> /dev/null
then
    echo "Docker is not installed. Please install Docker and try again."
    exit
fi

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "Virtual environment (.venv) not found. Please create and activate the virtual environment first."
    exit 1
fi

# Generate requirements.txt from virtual environment
echo "Generating requirements.txt from virtual environment..."
.venv/bin/pip freeze | sed 's/==\([0-9]\+\)\.\([0-9]\+\)\.\([0-9]\+\)/==\1.*/' > requirements.txt
echo "Requirements generated successfully."

# Define the Docker image name and tag
IMAGE_NAME="rapp_energy-saver"
TAG="TNSM-25"

# Define the Docker Hub username
DOCKER_HUB_USERNAME="zanattabruno"

# Define the local Docker registry (adjust the URL and port as needed)
LOCAL_REGISTRY="registry-docker-registry.registry.svc.cluster.local:5000"

# Build the Docker image
echo "Building Docker image..."
docker build -t ${IMAGE_NAME}:${TAG} .

# Tag the Docker image for Docker Hub
echo "Tagging image for Docker Hub..."
docker tag ${IMAGE_NAME}:${TAG} ${DOCKER_HUB_USERNAME}/${IMAGE_NAME}:${TAG}

# Tag the Docker image for local registry
echo "Tagging image for local registry..."
docker tag ${IMAGE_NAME}:${TAG} ${LOCAL_REGISTRY}/${IMAGE_NAME}:${TAG}

# Function to check if registry is accessible
check_registry() {
    local registry_url=$1
    local registry_name=$2
    
    echo "Checking connectivity to $registry_name..."
    if curl -s -f "http://$registry_url/v2/" > /dev/null 2>&1; then
        echo "$registry_name is accessible."
        return 0
    else
        echo "Warning: $registry_name ($registry_url) is not accessible."
        return 1
    fi
}

# Push to Docker Hub
echo "=== Pushing to Docker Hub ==="
# Check if user is logged in to Docker Hub
if ! docker info | grep -q Username
then
    echo "Not logged in to Docker Hub. Skipping Docker Hub push."
    echo "To push to Docker Hub, please run: docker login"
else
    echo "Pushing to Docker Hub..."
    if docker push ${DOCKER_HUB_USERNAME}/${IMAGE_NAME}:${TAG}; then
        echo "✓ Successfully pushed to Docker Hub: ${DOCKER_HUB_USERNAME}/${IMAGE_NAME}:${TAG}"
    else
        echo "✗ Failed to push to Docker Hub"
    fi
fi

# Push to local registry
echo "=== Pushing to Local Registry ==="
if check_registry "$LOCAL_REGISTRY" "Local Registry"; then
    echo "Pushing to local registry..."
    if docker push ${LOCAL_REGISTRY}/${IMAGE_NAME}:${TAG}; then
        echo "✓ Successfully pushed to local registry: ${LOCAL_REGISTRY}/${IMAGE_NAME}:${TAG}"
    else
        echo "✗ Failed to push to local registry"
    fi
else
    echo "Skipping local registry push due to connectivity issues."
    echo "Make sure your local registry is running and accessible at: $LOCAL_REGISTRY"
fi

echo ""
echo "=== Summary ==="
echo "Image built: ${IMAGE_NAME}:${TAG}"
echo "Docker Hub: ${DOCKER_HUB_USERNAME}/${IMAGE_NAME}:${TAG}"
echo "Local Registry: ${LOCAL_REGISTRY}/${IMAGE_NAME}:${TAG}"