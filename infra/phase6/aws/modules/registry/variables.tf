variable "name_prefix" {
  type = string
}

variable "retained_image_count" {
  type    = number
  default = 20

  validation {
    condition     = var.retained_image_count >= 5 && var.retained_image_count <= 100
    error_message = "retained_image_count must remain within the reviewed staging bound."
  }
}

variable "tags" {
  type = map(string)
}
