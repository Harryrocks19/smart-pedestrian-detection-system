# Azure deploy script for AI Insem

param(
    [string]$subscriptionId = "YOUR_SUBSCRIPTION_ID",
    [string]$resourceGroup = "ai-insem-rg",
    [string]$location = "eastus",
    [string]$acrName = "aiinsemacr",
    [string]$containerAppEnv = "aiinsem-env",
    [string]$appInsightsName = "aiinsem-ai",
    [string]$logAnalyticsName = "aiinsem-law",
    [string]$imageName = "aiinsem-api",
    [string]$imageTag = "v1"
)

Write-Host "Validating Azure CLI login and subscription..."
az account show --query id
az account set --subscription $subscriptionId

Write-Host "Creating resource group..."
az group create --name $resourceGroup --location $location

Write-Host "Creating Azure Container Registry..."
az acr create --resource-group $resourceGroup --name $acrName --sku Basic

Write-Host "Creating Log Analytics workspace..."
az monitor log-analytics workspace create --resource-group $resourceGroup --workspace-name $logAnalyticsName --location $location

Write-Host "Creating Application Insights..."
az monitor app-insights component create --app $appInsightsName --location $location --kind web --resource-group $resourceGroup --application-type web --workspace $logAnalyticsName

Write-Host "Creating Container Apps environment..."
az containerapp env create --name $containerAppEnv --resource-group $resourceGroup --location $location --logs-workspace-id $(az monitor log-analytics workspace show --resource-group $resourceGroup --workspace-name $logAnalyticsName --query id -o tsv)

Write-Host "Building Docker image..."
docker build -t $acrName.azurecr.io/$imageName:$imageTag .

Write-Host "Logging in to ACR..."
az acr login --name $acrName

Write-Host "Pushing image to ACR..."
docker push $acrName.azurecr.io/$imageName:$imageTag

Write-Host "Deploying Container App..."
az containerapp create --name ai-insem-api --resource-group $resourceGroup --environment $containerAppEnv --image $acrName.azurecr.io/$imageName:$imageTag --ingress external --target-port 5000 --registry-server $acrName.azurecr.io --min-replicas 1 --max-replicas 2 --cpu 0.5 --memory 1.0Gi

Write-Host "Deployment complete. Use az containerapp show to get the URL."
