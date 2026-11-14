data "azurerm_client_config" "current" {}

resource "azuread_application" "github" {
  display_name = "sp-${var.name_prefix}-github-oidc"
}

resource "azuread_service_principal" "github" {
  client_id = azuread_application.github.client_id
}

resource "azuread_application_federated_identity_credential" "github_branch" {
  application_id = azuread_application.github.id
  display_name   = "github-${var.github_branch}"
  description    = "Despliegue CI/CD desde la rama ${var.github_branch} de ${var.github_repository}."
  audiences      = ["api://AzureADTokenExchange"]
  issuer         = "https://token.actions.githubusercontent.com"
  subject        = "repo:${var.github_repository}:ref:refs/heads/${var.github_branch}"
}

resource "azurerm_role_assignment" "rg_contributor" {
  scope                = var.resource_group_id
  role_definition_name = "Contributor"
  principal_id         = azuread_service_principal.github.object_id
}

resource "azurerm_role_assignment" "tfstate_blob_contributor" {
  count                = var.tfstate_storage_account_id != "" ? 1 : 0
  scope                = var.tfstate_storage_account_id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azuread_service_principal.github.object_id
}
