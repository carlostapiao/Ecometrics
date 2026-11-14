resource "azurerm_container_registry" "this" {
  name                = var.acr_name
  resource_group_name = var.resource_group_name
  location            = var.location
  sku                 = "Basic"
  admin_enabled       = false
  tags                = var.tags
}

resource "azurerm_user_assigned_identity" "acr_pull" {
  name                = "id-${var.name_prefix}-acrpull"
  resource_group_name = var.resource_group_name
  location            = var.location
  tags                = var.tags
}

resource "azurerm_role_assignment" "acr_pull" {
  scope                = azurerm_container_registry.this.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.acr_pull.principal_id
}

resource "azurerm_container_app_environment" "this" {
  name                       = "cae-${var.name_prefix}"
  location                   = var.location
  resource_group_name        = var.resource_group_name
  log_analytics_workspace_id = var.log_analytics_workspace_id
  tags                       = var.tags
}

locals {
  app_name = "ca-${var.name_prefix}-web"
  app_fqdn = "${local.app_name}.${azurerm_container_app_environment.this.default_domain}"
}

resource "azurerm_container_app" "web" {
  name                         = local.app_name
  container_app_environment_id = azurerm_container_app_environment.this.id
  resource_group_name          = var.resource_group_name
  revision_mode                = "Single"
  tags                         = var.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.acr_pull.id]
  }

  registry {
    server   = azurerm_container_registry.this.login_server
    identity = azurerm_user_assigned_identity.acr_pull.id
  }

  secret {
    name  = "django-secret-key"
    value = var.django_secret_key
  }

  secret {
    name  = "postgres-password"
    value = var.postgres_password
  }

  secret {
    name  = "azure-storage-conn"
    value = var.azure_storage_connection_string
  }

  secret {
    name  = "appinsights-conn"
    value = var.app_insights_connection_string
  }

  ingress {
    external_enabled = true
    target_port      = var.container_port
    transport        = "auto"

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    min_replicas = var.min_replicas
    max_replicas = var.max_replicas

    container {
      name   = "web"
      image  = var.container_image
      cpu    = 0.5
      memory = "1Gi"

      env {
        name        = "DJANGO_SECRET_KEY"
        secret_name = "django-secret-key"
      }
      env {
        name  = "DJANGO_DEBUG"
        value = "false"
      }
      env {
        name  = "DJANGO_SECURE_SSL"
        value = "true"
      }
      env {
        name  = "DJANGO_ALLOWED_HOSTS"
        value = "${local.app_fqdn},localhost,127.0.0.1"
      }
      env {
        name  = "DJANGO_CSRF_TRUSTED_ORIGINS"
        value = "https://${local.app_fqdn}"
      }
      env {
        name  = "POSTGRES_HOST"
        value = var.postgres_host
      }
      env {
        name  = "POSTGRES_PORT"
        value = "5432"
      }
      env {
        name  = "POSTGRES_DB"
        value = var.postgres_db
      }
      env {
        name  = "POSTGRES_USER"
        value = var.postgres_user
      }
      env {
        name        = "POSTGRES_PASSWORD"
        secret_name = "postgres-password"
      }
      env {
        name  = "POSTGRES_SSLMODE"
        value = "require"
      }
      env {
        name        = "AZURE_STORAGE_CONNECTION_STRING"
        secret_name = "azure-storage-conn"
      }
      env {
        name  = "AZURE_STORAGE_CONTAINER"
        value = var.azure_storage_container
      }
      env {
        name        = "APPLICATIONINSIGHTS_CONNECTION_STRING"
        secret_name = "appinsights-conn"
      }
    }
  }

  lifecycle {
    ignore_changes = [
      template[0].container[0].image,
      ingress[0].target_port,
    ]
  }

  depends_on = [azurerm_role_assignment.acr_pull]
}
