locals {
  name_prefix = "${var.project_name}-${var.environment}-${var.region_code}"
  common_tags = {
    project     = var.project_name
    environment = var.environment
    managed_by  = "terraform"
  }
}

resource "random_string" "suffix" {
  length  = 6
  special = false
  upper   = false
}

resource "azurerm_resource_group" "this" {
  name     = "rg-${local.name_prefix}"
  location = var.location
  tags     = local.common_tags
}

module "observabilidad" {
  source = "../../modules/observabilidad"

  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
  name_prefix         = local.name_prefix
  tags                = local.common_tags
}

module "datos" {
  source = "../../modules/datos"

  location                = azurerm_resource_group.this.location
  resource_group_name     = azurerm_resource_group.this.name
  name_prefix             = local.name_prefix
  storage_account_name    = "st${var.project_name}media${random_string.suffix.result}"
  postgres_admin_username = var.postgres_admin_username
  postgres_admin_password = var.postgres_admin_password
  tags                    = local.common_tags
}

module "aplicacion" {
  source = "../../modules/aplicacion"

  location                        = azurerm_resource_group.this.location
  resource_group_name             = azurerm_resource_group.this.name
  name_prefix                     = local.name_prefix
  acr_name                        = "acr${var.project_name}${var.environment}${random_string.suffix.result}"
  log_analytics_workspace_id      = module.observabilidad.log_analytics_workspace_id
  min_replicas                    = var.min_replicas
  django_secret_key               = var.django_secret_key
  postgres_host                   = module.datos.postgres_fqdn
  postgres_db                     = module.datos.postgres_database_name
  postgres_user                   = var.postgres_admin_username
  postgres_password               = var.postgres_admin_password
  azure_storage_connection_string = module.datos.storage_connection_string
  azure_storage_container         = module.datos.evidencias_container_name
  app_insights_connection_string  = module.observabilidad.application_insights_connection_string
  tags                            = local.common_tags
}

data "azurerm_storage_account" "tfstate" {
  count               = var.tfstate_storage_account_name != "" && var.tfstate_resource_group_name != "" ? 1 : 0
  name                = var.tfstate_storage_account_name
  resource_group_name = var.tfstate_resource_group_name
}

module "github_oidc" {
  source = "../../modules/github_oidc"

  name_prefix                = local.name_prefix
  resource_group_id          = azurerm_resource_group.this.id
  tfstate_storage_account_id = length(data.azurerm_storage_account.tfstate) > 0 ? data.azurerm_storage_account.tfstate[0].id : ""
  github_repository          = var.github_repository
  github_branch              = var.github_branch
}
