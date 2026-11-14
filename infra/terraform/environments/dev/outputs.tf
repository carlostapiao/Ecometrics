output "resource_group_name" {
  value = azurerm_resource_group.this.name
}

output "acr_name" {
  value = module.aplicacion.acr_name
}

output "acr_login_server" {
  value = module.aplicacion.acr_login_server
}

output "container_app_name" {
  value = module.aplicacion.container_app_name
}

output "container_app_url" {
  value = module.aplicacion.container_app_url
}

output "postgres_server_name" {
  value = module.datos.postgres_server_name
}

output "postgres_fqdn" {
  value = module.datos.postgres_fqdn
}

output "postgres_database_name" {
  value = module.datos.postgres_database_name
}

output "media_storage_account_name" {
  value = module.datos.storage_account_name
}

output "azure_client_id" {
  value = module.github_oidc.client_id
}

output "azure_tenant_id" {
  value = module.github_oidc.tenant_id
}

output "azure_subscription_id" {
  value = module.github_oidc.subscription_id
}
