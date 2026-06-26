variable "subscription_id" {
  description = "ID de tu suscripción Azure for Students"
  type        = string
}

variable "location" {
  description = "Región de Azure disponible para tu suscripción"
  type        = string
  default     = "chilecentral"   # ✅ confirmado disponible en tu suscripción
}

variable "vm_size" {
  description = "Tamaño de la VM"
  type        = string
  default     = "Standard_B1s"  # ✅ confirmado disponible en chilecentral
}

variable "admin_username" {
  description = "Usuario administrador de la VM"
  type        = string
  default     = "smartliquor"
}

variable "ssh_public_key_path" {
  description = "Ruta a tu clave SSH pública"
  type        = string
  default     = "~/.ssh/id_rsa.pub"
}
