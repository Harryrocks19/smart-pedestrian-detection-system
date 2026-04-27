#!/usr/bin/env bash
set -e

SUBSCRIPTION_ID="YOUR_SUBSCRIPTION_ID"
RESOURCE_GROUP="ai-insem-rg"
LOCATION="eastus"
ACR_NAME="aiinsemacr"
CONTAINERAPPS_ENV="aiinsem-env"
APP_INSIGHTS_NAME="aiinsem-ai"
LOG_ANALYTICS_NAME="aiinsem-law"
IMAGE_NAME="aiinsem-api"
IMAGE_TAG="v1"

echo "Setting Azure subscription..."
az account set --subscription "$SUBSCRIPTION_ID"

echo "Creating resource group..."
az group create --name "$RESOURCE_GROUP" --location "$LOCATION"

echo "Creating Azure Container Registry..."
az acr create --resource-group "$RESOURCE_GROUP" --name "$ACR_NAME" --sku Basic

echo "Creating Log Analytics workspace..."
az monitor log-analytics workspace create --resource-group "$RESOURCE_GROUP" --workspace-name "$LOG_ANALYTICS_NAME" --location "$LOCATION"

echo "Creating Application Insights..."
az monitor app-insights component create --app "$APP_INSIGHTS_NAME" --location "$LOCATION" --kind web --resource-group "$RESOURCE_GROUP" --application-type web --workspace "$LOG_ANALYTICS_NAME"

echo "Creating Container Apps environment..."
LOG_ANALYTICS_ID=$(az monitor log-analytics workspace show --resource-group "$RESOURCE_GROUP" --workspace-name "$LOG_ANALYTICS_NAME" --query id -o tsv)
az containerapp env create --name "$CONTAINERAPPS_ENV" --resource-group "$RESOURCE_GROUP" --location "$LOCATION" --logs-workspace-id "$LOG_ANALYTICS_ID"

echo "Building Docker image..."
docker build -t "$ACR_NAME.azurecr.io/$IMAGE_NAME:$IMAGE_TAG" .

echo "Logging in to ACR..."
az acr login --name "$ACR_NAME"

echo "Pushing image to ACR..."
docker push "$ACR_NAME.azurecr.io/$IMAGE_NAME:$IMAGE_TAG"

echo "Deploying Container App..."
az containerapp create --name ai-insem-api --resource-group "$RESOURCE_GROUP" --environment "$CONTAINERAPPS_ENV" --image "$ACR_NAME.azurecr.io/$IMAGE_NAME:$IMAGE_TAG" --ingress external --target-port 5000 --registry-server "$ACR_NAME.azurecr.io" --min-replicas 1 --max-replicas 2 --cpu 0.5 --memory 1.0Gi

echo "Deployment complete."
