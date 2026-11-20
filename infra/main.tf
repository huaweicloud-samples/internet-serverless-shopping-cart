# ============================================================================
# 华为云 购物车服务 Terraform 配置（简化版）
# ============================================================================

terraform {
  required_version = ">= 1.5"

  required_providers {
    huaweicloud = {
      source  = "huaweicloud/huaweicloud"
      version = "~> 1.70"
    }
  }
}

provider "huaweicloud" {
  region     = var.region
  access_key = "YOUR_ACCESS_KEY"
  secret_key = "YOUR_SECRET_KEY"
}

variable "region" {
  description = "华为云区域"
  type        = string
  default     = "cn-north-4"
}

variable "project_name" {
  description = "项目名称"
  type        = string
  default     = "shopping-cart-20260820"
}

variable "rds_password" {
  description = "RDS MySQL 密码"
  type        = string
  sensitive   = true
  default     = "ShoppingCart123!"
}

# ============================================================================
# VPC 网络
# ============================================================================

resource "huaweicloud_vpc" "main" {
  name                  = "${var.project_name}-vpc"
  cidr                  = "10.1.0.0/16"
  enterprise_project_id = "0"
}

resource "huaweicloud_vpc_subnet" "main" {
  name       = "${var.project_name}-subnet"
  vpc_id     = huaweicloud_vpc.main.id
  cidr       = "10.1.1.0/24"
  gateway_ip = "10.1.1.1"
}

resource "huaweicloud_networking_secgroup" "main" {
  name        = "${var.project_name}-sg"
  description = "Security group for shopping cart service"
}

resource "huaweicloud_networking_secgroup_rule" "allow_http" {
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 80
  port_range_max    = 80
  remote_ip_prefix  = "0.0.0.0/0"
  security_group_id = huaweicloud_networking_secgroup.main.id
}

resource "huaweicloud_networking_secgroup_rule" "allow_https" {
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 443
  port_range_max    = 443
  remote_ip_prefix  = "0.0.0.0/0"
  security_group_id = huaweicloud_networking_secgroup.main.id
}

resource "huaweicloud_networking_secgroup_rule" "allow_mysql" {
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 3306
  port_range_max    = 3306
  remote_ip_prefix  = "10.1.0.0/16"
  security_group_id = huaweicloud_networking_secgroup.main.id
}

# ============================================================================
# RDS MySQL
# ============================================================================

resource "huaweicloud_rds_instance" "mysql" {
  name   = "${var.project_name}-mysql"
  flavor = "rds.mysql.n1.large.2"
  volume {
    type = "CLOUDSSD"
    size = 20
  }
  db {
    type     = "MySQL"
    version  = "8.0"
    password = var.rds_password
    port     = 3306
  }
  vpc_id            = huaweicloud_vpc.main.id
  subnet_id         = huaweicloud_vpc_subnet.main.id
  security_group_id = huaweicloud_networking_secgroup.main.id
  availability_zone = ["${var.region}a"]

  timeouts {
    create = "30m"
  }
}

# ============================================================================
# OBS 存储
# ============================================================================

resource "huaweicloud_obs_bucket" "assets" {
  bucket        = "${var.project_name}-demo-assets"
  acl           = "public-read"
  storage_class = "STANDARD"
}

# ============================================================================
# 输出
# ============================================================================

output "vpc_id" {
  value = huaweicloud_vpc.main.id
}

output "subnet_id" {
  value = huaweicloud_vpc_subnet.main.id
}

output "security_group_id" {
  value = huaweicloud_networking_secgroup.main.id
}

output "obs_bucket" {
  value = huaweicloud_obs_bucket.assets.bucket
}


output "rds_endpoint" {
  value     = huaweicloud_rds_instance.mysql.private_ips[0]
  sensitive = true
}

output "rds_port" {
  value = 3306
}
