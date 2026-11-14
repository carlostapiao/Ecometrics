variable "location" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "name_prefix" {
  type = string
}

variable "storage_account_name" {
  type = string
}

variable "postgres_admin_username" {
  type = string
}

variable "postgres_admin_password" {
  type      = string
  sensitive = true
}

variable "postgres_database_name" {
  type    = string
  default = "ecometrics"
}

variable "tags" {
  type    = map(string)
  default = {}
}
