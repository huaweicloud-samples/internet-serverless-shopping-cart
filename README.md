# Serverless Shopping Cart Service

[中文版](./README.cn.md)

![License](https://img.shields.io/badge/License-MIT-green)
![Huawei Cloud](https://img.shields.io/badge/Huawei%20Cloud-Ready-blue)

## Overview

This project is a serverless shopping cart service built on Huawei Cloud using FunctionGraph, APIG, and RDS MySQL. The solution adopts an event-driven architecture, leveraging Huawei Cloud's serverless computing capabilities for elastic scaling, while achieving asynchronous processing and system decoupling through message queues.

### Core Features

This shopping cart service provides complete e-commerce shopping cart functionality, covering the entire lifecycle of user shopping:

1. **Anonymous Shopping Cart** - Unauthenticated users can create anonymous shopping carts. The system automatically generates a temporary cart ID and stores it in the database. Anonymous shopping carts support basic operations such as adding items, modifying quantities, and removing items, providing users with a smooth guest shopping experience. Anonymous shopping carts have a TTL (Time-To-Live) expiration mechanism and are automatically cleaned up after 7 days of inactivity, saving storage resources.

2. **User Shopping Cart** - Logged-in users have dedicated shopping carts bound to their accounts. Shopping cart data is permanently preserved without expiration. User shopping carts support features such as product favorites, quantity management, and real-time price synchronization, providing users with complete cart management capabilities.

3. **Cart Merge** - This is one of the core highlight features. When a user completes login from an anonymous state, the system automatically merges items from the anonymous cart into the user's cart. The merge logic intelligently handles duplicate items: identical products have quantities accumulated, while different products are retained. The merge process is handled asynchronously through DMS RabbitMQ, ensuring system stability under high concurrency scenarios.

4. **TTL Expiration Processing** - The system uses the delayed message function of the message queue to implement shopping cart item expiration processing. When items are about to expire, the system automatically sends notifications to remind users; if the user does not respond within the specified time, items are automatically removed from the cart. This mechanism helps e-commerce platforms clear items that have occupied inventory for long periods, improving inventory turnover efficiency.

5. **Checkout** - After completing shopping, users can submit items in the cart to create an order with one click. The checkout process automatically calculates total price, discounts, shipping costs, and other fees. After the order is created, inventory is automatically deducted. After successful order creation, the shopping cart is automatically cleared or retains user-selected items.

### Technical Highlights

- **Serverless Architecture**: Uses FunctionGraph for business logic, pay-per-use, no server management required
- **High Availability Design**: Multi-AZ deployment with automatic failover
- **Elastic Scaling**: Automatically scales based on request volume to handle burst traffic
- **Event-Driven**: Achieves asynchronous processing and system decoupling through DMS RabbitMQ
- **Data Persistence**: Uses RDS MySQL for shopping cart data storage, ensuring data reliability

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                  Huawei Cloud Shopping Cart                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│  │   APIG   │───▶│Function │───▶│ RDS MySQL │              │
│  │ Gateway │    │Graph    │    │  (Cart)  │              │
│  └──────────┘    └──────────┘    └──────────┘              │
│       │               │                                   │
│       │               ▼                                   │
│       │         ┌──────────┐                          │
│       │         │   DMS    │  (RabbitMQ)              │
│       │         │  Queue   │                          │
│       │         └──────────┘                          │
│       │               │                                   │
│       └───────────────┴─────────────────────────────────│
│                      │                                    │
│                      ▼                                    │
│              ┌──────────────┐                         │
│              │   Custom    │  (Auth Service)          │
│              │     JWT    │                         │
│              └──────────────┘                         │
└─────────────────────────────────────────────────────────────┘
```

## Cloud Services

| Service | Purpose |
|---------|---------|
| FunctionGraph | Serverless functions |
| APIG | API Gateway |
| RDS MySQL | Relational database |
| DMS RabbitMQ | Message Queue |
| OBS | Object Storage |
| VPC | Virtual Private Cloud |

## Prerequisites

- Huawei Cloud account
- AK/SK credentials
- cn-north-4 region

## Quick Start

```bash
# Configure credentials
export HW_ACCESS_KEY="your-access-key"
export HW_SECRET_KEY="your-secret-key"

# Initialize
cd infra
terraform init

# Preview resources
terraform plan

# Deploy all resources
terraform apply

# Get API URL
terraform output apig_url
```

## Deployment Content

| Resource | Count |
|----------|-------|
| VPC/Subnet/SG | 7 |
| RDS MySQL | 1 |
| DMS RabbitMQ | 4 |
| OBS | 2 |
| APIG | 5 |
| FunctionGraph | 4 |

## Usage

```bash
# Create cart
curl -X POST https://{apig-url}/carts

# Add item
curl -X POST https://{apig-url}/carts/{cart_id}/items \
  -H "Content-Type: application/json" \
  -d '{"product_id": "123", "quantity": 2}'

# Get cart
curl https://{apig-url}/carts/{cart_id}
```

## Cleanup

```bash
terraform destroy
```

## License

MIT License
