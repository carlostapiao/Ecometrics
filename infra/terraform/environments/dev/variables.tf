variable "subscription_id" {
  type        = string
  description = "ID de la suscripción de Azure."
}

variable "location" {
  type        = string
  description = "Región de Azure para el entorno."
  default     = "mexicocentral"

  validation {
    condition     = contains(["mexicocentral", "northcentralus", "chilecentral", "canadacentral", "westcentralus"], var.location)
    error_message = "La región debe ser una de las admitidas por las políticas y cuotas de Azure for Students."
  }
}

variable "region_code" {
  type        = string
  description = "Código abreviado de región para nomenclatura CAF."
  default     = "mxc"
}

variable "project_name" {
  type        = string
  description = "Prefijo del proyecto para nomenclatura CAF."
  default     = "ecom"
}

variable "environment" {
  type        = string
  description = "Nombre del entorno."
  default     = "dev"
}

variable "postgres_admin_username" {
  type        = string
  description = "Usuario administrador de PostgreSQL Flexible Server."
  default     = "ecomadmin"
}

variable "postgres_admin_password" {
  type        = string
  description = "Contraseña del administrador de PostgreSQL Flexible Server."
  sensitive   = true
}

variable "django_secret_key" {
  type        = string
  description = "Clave secreta de Django para producción en Azure."
  sensitive   = true
}

variable "github_repository" {
  type        = string
  description = "Repositorio GitHub autorizado para OIDC (propietario/repositorio)."
  default     = "carlostapiao/Ecometrics"
}

variable "github_branch" {
  type        = string
  description = "Rama de GitHub autorizada para despliegue."
  default     = "main"
}

variable "github_oidc_subject" {
  type        = string
  description = "Subject claim OIDC exacto emitido por GitHub Actions."
  default     = "repo:carlostapiao@264424726/Ecometrics@1458150944:ref:refs/heads/main"
}

variable "min_replicas" {
  type        = number
  description = "Réplicas mínimas de Container Apps (0 para ahorrar fuera de demostración)."
  default     = 1
}

variable "tfstate_resource_group_name" {
  type        = string
  description = "Resource Group del bootstrap de Terraform (para otorgar acceso OIDC al tfstate)."
  default     = ""
}

variable "tfstate_storage_account_name" {
  type        = string
  description = "Storage Account del bootstrap de Terraform (para otorgar acceso OIDC al tfstate)."
  default     = ""
}
