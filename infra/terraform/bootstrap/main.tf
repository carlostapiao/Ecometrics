resource "random_string" "suffix" {
  length  = 6
  special = false
  upper   = false
}

resource "azurerm_resource_group" "tfstate" {
  name     = "rg-${var.project_name}-tfstate-${var.region_code}"
  location = var.location

  tags = {
    project     = var.project_name
    purpose     = "terraform-state"
    environment = "shared"
  }
}

resource "azurerm_storage_account" "tfstate" {
  name                            = "st${var.project_name}tf${random_string.suffix.result}"
  resource_group_name             = azurerm_resource_group.tfstate.name
  location                        = azurerm_resource_group.tfstate.location
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  min_tls_version                 = "TLS1_2"
  allow_nested_items_to_be_public = false
  shared_access_key_enabled       = true

  blob_properties {
    versioning_enabled = true
  }

  tags = {
    project     = var.project_name
    purpose     = "terraform-state"
    environment = "shared"
  }
}

resource "azurerm_storage_container" "tfstate" {
  name                  = "tfstate"
  storage_account_id    = azurerm_storage_account.tfstate.id
  container_access_type = "private"
}
