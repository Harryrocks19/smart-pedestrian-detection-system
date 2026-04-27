@description('The location into which resources should be deployed.')
param location string = resourceGroup().location

@description('Unique name for the Azure Container Registry.')
param acrName string = 'aiinsemacr'

@description('Name of the Container Apps environment.')
param containerAppEnvName string = 'aiinsem-env'

@description('Name of the Application Insights component.')
param appInsightsName string = 'aiinsem-ai'

@description('Name of the Log Analytics workspace.')
param logAnalyticsName string = 'aiinsem-law'

@description('Name of the Container App.')
param containerAppName string = 'ai-insem-api'

@description('Fully qualified ACR image name including tag.')
param containerImage string = 'REPLACE_WITH_ACR_NAME.azurecr.io/aiinsem-api:v1'

@description('CPU allocation for the container app.')
param cpu string = '0.5'

@description('Memory allocation for the container app.')
param memory string = '1.0Gi'

@description('Optional database connection string for the app.')
param databaseUrl string = ''

@description('Optional Azure Storage connection string.')
param storageConnectionString string = ''

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-03-01-preview' = {
  name: logAnalyticsName
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  kind: 'web'
  properties: {
    applicationType: 'web'
    workspaceResourceId: logAnalytics.id
  }
}

resource acr 'Microsoft.ContainerRegistry/registries@2023-05-01' = {
  name: acrName
  location: location
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: false
  }
}

resource containerAppEnv 'Microsoft.App/managedEnvironments@2024-01-01-preview' = {
  name: containerAppEnvName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: listKeys(logAnalytics.id, logAnalytics.apiVersion).primarySharedKey
      }
    }
  }
}

resource containerApp 'Microsoft.App/containerApps@2024-01-01-preview' = {
  name: containerAppName
  location: location
  properties: {
    managedEnvironmentId: containerAppEnv.id
    configuration: {
      ingress: {
        external: true
        targetPort: 5000
        transport: 'Auto'
      }
      registries: [
        {
          server: '${acr.name}.azurecr.io'
          identity: {
            type: 'SystemAssigned'
          }
        }
      ]
      secrets: [
        {
          name: 'databaseUrl'
          value: databaseUrl
        }
        {
          name: 'storageConnectionString'
          value: storageConnectionString
        }
      ]
      environmentVariables: [
        {
          name: 'DATABASE_URL'
          secretRef: 'databaseUrl'
        }
        {
          name: 'AZURE_STORAGE_CONNECTION_STRING'
          secretRef: 'storageConnectionString'
        }
        {
          name: 'APPINSIGHTS_INSTRUMENTATIONKEY'
          value: appInsights.properties.InstrumentationKey
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'ai-insem-api'
          image: containerImage
          resources: {
            cpu: cpu
            memory: memory
          }
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 2
      }
    }
  }
}

output containerAppUrl string = containerApp.properties.configuration.ingress.fqdn
output acrLoginServer string = acr.properties.loginServer
