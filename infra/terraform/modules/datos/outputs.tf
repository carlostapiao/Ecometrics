output "storage_account_name" {
  value = azurerm_storage_account.media.name
}

output "storage_connection_string" {
  value     = azurerm_storage_account.media.primary_connection_string
  sensitive = true
}

output "evidencias_container_name" {
  value = azurerm_storage_container.evidencias.name
}

output "postgres_server_name" {
  value = azurerm_postgresql_flexible_server.this.name
}

output "postgres_fqdn" {
  value = azurerm_postgresql_flexible_server.this.fqdn
}

output "postgres_database_name" {
  value = azurerm_postgresql_flexible_server_database.app.name
}
