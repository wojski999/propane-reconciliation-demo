// Propane reconciliation demo (synthetic data) on Azure Container Apps,
// Consumption plan, scale to zero, default HTTPS ingress. No log workspace.
@description('Public container image reference, for example ghcr.io/OWNER/REPO:main.')
param image string

@description('Azure region; defaults to the resource group location.')
param location string = resourceGroup().location

var name = 'propane-reconciliation-demo'

resource environment 'Microsoft.App/managedEnvironments@2026-07-01' = {
  name: '${name}-env'
  location: location
  properties: {}
}

resource app 'Microsoft.App/containerApps@2026-07-01' = {
  name: name
  location: location
  properties: {
    environmentId: environment.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8080
        transport: 'auto'
        allowInsecure: false
      }
    }
    template: {
      containers: [
        {
          name: 'web'
          image: image
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          probes: [
            {
              type: 'Liveness'
              httpGet: {
                path: '/healthz'
                port: 8080
              }
            }
            {
              type: 'Readiness'
              httpGet: {
                path: '/healthz'
                port: 8080
              }
            }
          ]
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 1
      }
    }
  }
}

output url string = 'https://${app.properties.configuration.ingress.fqdn}'
