variable "subscription_id" {
  type        = string
  description = "ID de la suscripción de Azure donde se creará el backend remoto de Terraform."
}

variable "location" {
  type        = string
  description = "Región de Azure para el estado remoto de Terraform."
  default     = "mexicocentral"

  validation {
    condition     = contains(["mexicocentral", "northcentralus", "chilecentral", "canadacentral", "westcentralus"], var.location)
    error_message = "La región debe ser una de las admitidas por la política sys.regionrestriction de Azure for Students."
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
