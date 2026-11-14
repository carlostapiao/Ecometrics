variable "name_prefix" {
  type = string
}

variable "resource_group_id" {
  type = string
}

variable "tfstate_storage_account_id" {
  type        = string
  description = "ID del Storage Account de bootstrap para habilitar lectura/escritura del estado en CI/CD."
  default     = ""
}

variable "github_repository" {
  type        = string
  description = "Repositorio GitHub en formato propietario/repositorio."
}

variable "github_branch" {
  type    = string
  default = "main"
}

variable "github_oidc_subject" {
  type        = string
  description = "Subject claim OIDC exacto emitido por GitHub Actions (opcional si incluye IDs únicos)."
  default     = ""
}
