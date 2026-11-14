variable "location" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "name_prefix" {
  type = string
}

variable "acr_name" {
  type = string
}

variable "log_analytics_workspace_id" {
  type = string
}

variable "container_image" {
  type    = string
  default = "mcr.microsoft.com/azuredocs/containerapps-helloworld:latest"
}

variable "container_port" {
  type    = number
  default = 80
}

variable "min_replicas" {
  type    = number
  default = 1
}

variable "max_replicas" {
  type    = number
  default = 3
}

variable "django_secret_key" {
  type      = string
  sensitive = true
}

variable "postgres_host" {
  type = string
}

variable "postgres_db" {
  type = string
}

variable "postgres_user" {
  type = string
}

variable "postgres_password" {
  type      = string
  sensitive = true
}

variable "azure_storage_connection_string" {
  type      = string
  sensitive = true
}

variable "azure_storage_container" {
  type    = string
  default = "evidencias"
}

variable "app_insights_connection_string" {
  type      = string
  sensitive = true
}

variable "tags" {
  type    = map(string)
  default = {}
}
