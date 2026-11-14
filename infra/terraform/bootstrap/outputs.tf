output "resource_group_name" {
  value       = azurerm_resource_group.tfstate.name
  description = "Resource Group del almacenamiento de estado de Terraform."
}

output "storage_account_name" {
  value       = azurerm_storage_account.tfstate.name
  description = "Nombre único del Storage Account para el backend remoto."
}

output "container_name" {
  value       = azurerm_storage_container.tfstate.name
  description = "Nombre del contenedor privado de estado."
}
