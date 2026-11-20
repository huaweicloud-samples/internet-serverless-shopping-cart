# 认证服务部署指南

本文档说明如何在华为云上部署自建 JWT 认证服务。

## 概述

认证服务基于 FunctionGraph + RDS MySQL 实现，提供以下功能：

| 功能 | 说明 |
|------|------|
| 用户注册 | `/auth/register` - 创建新用户 |
| 用户登录 | `/auth/login` - 登录并获取 JWT |
| Token 验证 | `/auth/verify` - 验证 JWT 有效性 |
| Token 刷新 | `/auth/refresh` - 刷新过期 Token |

## 前置条件

1. **RDS MySQL 实例**：已创建 RDS MySQL 集群
2. **VPC 网络**：FunctionGraph 与 RDS MySQL 在同一 VPC 内
3. **依赖包**：
   - `PyJWT>=2.8.0`
   - `pymongo>=4.0`

---

## 步骤 1：创建用户表

连接到 RDS MySQL 并创建用户表：

```python
from pymongo import MongoClient

# 连接 RDS MySQL
client = MongoClient(
    "geminidb-endpoint:8635",
    username="root",
    password="your-password"
)
db = client["shopping_cart"]

# 创建用户集合（表）
db.users.create_index("username", unique=True)
```

或在 RDS MySQL 控制台执行：

```javascript
db.createCollection("users", {
  "indexes": [
    {
      "key": {"username": 1},
      "unique": true
    }
  ]
})
```

---

## 步骤 2：创建 FunctionGraph 函数

### 2.1 创建函数

1. 登录华为云控制台 → FunctionGraph
2. 创建函数：
   - **函数名称**：`shopping-cart-auth`
   - **运行时**：Python 3.9
   - **入口函数**：`auth_handler.handler`
   - **超时时间**：30 秒

### 2.2 配置环境变量

| 变量名 | 说明 | 示例值 |
|--------|------|--------|
| `GEMINIDB_ENDPOINT` | RDS MySQL 连接地址 | `geminidb-xxx.huaweicloud.com:8635` |
| `GEMINIDB_USER` | 数据库用户名 | `root` |
| `GEMINIDB_PASSWORD` | 数据库密码 | `YourPassword123!` |
| `GEMINIDB_DATABASE` | 数据库名称 | `shopping_cart` |
| `JWT_SECRET` | JWT 密钥 | `your-secret-key-change-in-production` |

### 2.3 配置 VPC

在函数配置中添加 VPC：

- **VPC**：选择与 RDS MySQL 相同的 VPC
- **Subnet**：选择可访问 RDS MySQL 的子网

### 2.4 上传依赖

创建 `requirements.txt`：

```
PyJWT>=2.8.0
pymongo>=4.0
```

在函数代码中上传 `auth_handler.py` 和依赖包。

---

## 步骤 3：配置 APIG

### 3.1 创建 API

1. 登录华为云控制台 → APIG
2. 选择 API 网关实例
3. 创建 API：

| 配置项 | 值 |
|--------|-----|
| API 名称 | `auth-service` |
| API 分组 | 选择已有分组或创建新分组 |
| 安全性 | 需要认证 |

### 3.2 配置后端

| 配置项 | 值 |
|--------|-----|
| 后端类型 | FunctionGraph |
| 函数 | `shopping-cart-auth` |
| 请求方法 | 与前端匹配 |

### 3.3 定义路由

创建以下后端路径：

| 前端路径 | 后端路径 | 方法 |
|----------|----------|------|
| `/auth/register` | `/auth/register` | POST |
| `/auth/login` | `/auth/login` | POST |
| `/auth/verify` | `/auth/verify` | GET |
| `/auth/refresh` | `/auth/refresh` | POST |

---

## 步骤 4：配置前端认证

### 4.1 APIG 自定义认证（可选）

在 APIG 中配置"前端认证"：

1. 进入 API → 认证管理
2. 选择"自定义认证"
3. 选择认证函数：`shopping-cart-auth`
4. 配置认证路径：`/auth/verify`

### 4.2 前端集成

```javascript
// 登录
async function login(username, password) {
  const response = await fetch('https://your-apig-url/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password })
  });
  const data = await response.json();
  localStorage.setItem('token', data.token);
  return data;
}

// 发送请求时携带 Token
async function fetchWithAuth(url, options = {}) {
  const token = localStorage.getItem('token');
  return fetch(url, {
    ...options,
    headers: {
      ...options.headers,
      'Authorization': `Bearer ${token}`
    }
  });
}
```

---

## 步骤 5：测试

### 5.1 注册用户

```bash
curl -X POST https://your-apig-url/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"password123","email":"test@example.com"}'
```

响应：
```json
{
  "message": "User registered successfully",
  "user_id": "uuid-xxxx-xxxx",
  "username": "testuser"
}
```

### 5.2 用户登录

```bash
curl -X POST https://your-apig-url/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"password123"}'
```

响应：
```json
{
  "token": "<demo-token-redacted>",
  "token_type": "Bearer",
  "expires_in": 604800,
  "user_id": "uuid-xxxx-xxxx",
  "username": "testuser"
}
```

### 5.3 验证 Token

```bash
curl -X GET https://your-apig-url/auth/verify \
  -H "Authorization: Bearer <demo-token-redacted>"
```

响应：
```json
{
  "valid": true,
  "user_id": "uuid-xxxx-xxxx",
  "username": "testuser"
}
```

---

## 步骤 6：Terraform 部署（可选）

如需通过 Terraform 自动化部署：

```hcl
# FunctionGraph 函数
resource "huaweicloud_fgs_function" "auth" {
  name        = "shopping-cart-auth"
  runtime     = "Python3.9"
  handler     = "auth_handler.handler"
  memory_size = 128
  timeout     = 30
  code_type   = "inline"
  code_url    = "obs://your-bucket/auth_function.zip"

  environment {
    variables = {
      GEMINIDB_ENDPOINT = var.geminidb_endpoint
      GEMINIDB_PASSWORD  = var.geminidb_password
      JWT_SECRET         = var.jwt_secret
    }
  }
}

# APIG 后端配置（略）
```

---

## 安全建议

1. **JWT 密钥**：使用强随机字符串，定期轮换
2. **HTTPS**：确保所有 API 使用 HTTPS
3. **密码存储**：使用 bcrypt 或 argon2 替代 SHA256
4. **Token 有效期**：生产环境建议 1-24 小时
5. **IP 白名单**：配置 APIG 访问控制
6. **日志审计**：启用 FunctionGraph 日志，记录登录尝试

---

## 故障排查

| 问题 | 可能原因 | 解决方案 |
|------|----------|----------|
| 登录失败 | RDS MySQL 连接失败 | 检查 VPC 配置和安全组规则 |
| Token 验证失败 | JWT 密钥不匹配 | 确保所有环境使用相同 JWT_SECRET |
| 函数超时 | RDS MySQL 响应慢 | 检查网络延迟，增加函数超时时间 |
| 400 错误 | 请求体格式错误 | 检查 Content-Type 和 JSON 格式 |
