output "acr_name" {
  value = azurerm_container_registry.this.name
}

output "acr_login_server" {
  value = azurerm_container_registry.this.login_server
}

output "container_app_name" {
  value = azurerm_container_app.web.name
}

output "container_app_fqdn" {
  value = azurerm_container_app.web.ingress[0].fqdn
}

output "container_app_url" {
  value = "https://${azurerm_container_app.web.ingress[0].fqdn}"
}
