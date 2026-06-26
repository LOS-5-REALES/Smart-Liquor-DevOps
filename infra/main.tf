terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
}

provider "azurerm" {
  features {}
  subscription_id = var.subscription_id
}

resource "azurerm_resource_group" "smart_liquor" {
  name     = "rg-smart-liquor"
  location = var.location
}

resource "azurerm_virtual_network" "vnet" {
  name                = "vnet-smart-liquor"
  address_space       = ["10.0.0.0/16"]
  location            = azurerm_resource_group.smart_liquor.location
  resource_group_name = azurerm_resource_group.smart_liquor.name
}

resource "azurerm_subnet" "subnet" {
  name                 = "subnet-app"
  resource_group_name  = azurerm_resource_group.smart_liquor.name
  virtual_network_name = azurerm_virtual_network.vnet.name
  address_prefixes     = ["10.0.1.0/24"]
}

resource "azurerm_public_ip" "ip_publica" {
  name                = "ip-smart-liquor"
  location            = azurerm_resource_group.smart_liquor.location
  resource_group_name = azurerm_resource_group.smart_liquor.name
  allocation_method   = "Static"
  sku                 = "Standard"
}

resource "azurerm_network_security_group" "nsg" {
  name                = "nsg-smart-liquor"
  location            = azurerm_resource_group.smart_liquor.location
  resource_group_name = azurerm_resource_group.smart_liquor.name

  # Puerto SSH para administración
  security_rule {
    name                       = "SSH"
    priority                   = 1001
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "22"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }

  # Puerto 8000 para el dashboard Smart-Liquor
  security_rule {
    name                       = "APP"
    priority                   = 1002
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "8000"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }
}

resource "azurerm_network_interface" "nic" {
  name                = "nic-smart-liquor"
  location            = azurerm_resource_group.smart_liquor.location
  resource_group_name = azurerm_resource_group.smart_liquor.name

  ip_configuration {
    name                          = "config-interna"
    subnet_id                     = azurerm_subnet.subnet.id
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = azurerm_public_ip.ip_publica.id
  }
}

resource "azurerm_network_interface_security_group_association" "nic_nsg" {
  network_interface_id      = azurerm_network_interface.nic.id
  network_security_group_id = azurerm_network_security_group.nsg.id
}

resource "azurerm_linux_virtual_machine" "vm" {
  name                = "vm-smart-liquor"
  resource_group_name = azurerm_resource_group.smart_liquor.name
  location            = azurerm_resource_group.smart_liquor.location
  size                = var.vm_size
  admin_username      = var.admin_username

  network_interface_ids = [azurerm_network_interface.nic.id]

  admin_ssh_key {
    username   = var.admin_username
    public_key = file(var.ssh_public_key_path)
  }

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "Standard_LRS"  # HDD estándar, más barato
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "0001-com-ubuntu-server-jammy"
    sku       = "22_04-lts-gen2"
    version   = "latest"
  }

  # Instala Docker automáticamente al crear la VM
  custom_data = base64encode(<<-EOF
    #!/bin/bash
    apt-get update -y
    apt-get install -y docker.io docker-compose git
    systemctl enable docker
    systemctl start docker
    usermod -aG docker ${var.admin_username}
    echo "✅ Docker listo en la VM"
  EOF
  )
}
