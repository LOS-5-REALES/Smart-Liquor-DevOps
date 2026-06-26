output "ip_publica" {
  description = "IP pública de la VM — comparte esta IP con la dueña en Chincha"
  value       = azurerm_public_ip.ip_publica.ip_address
}

output "comando_ssh" {
  description = "Comando listo para conectarte a la VM"
  value       = "ssh ${var.admin_username}@${azurerm_public_ip.ip_publica.ip_address}"
}

output "url_dashboard" {
  description = "URL del dashboard Smart-Liquor"
  value       = "http://${azurerm_public_ip.ip_publica.ip_address}:8000"
}
