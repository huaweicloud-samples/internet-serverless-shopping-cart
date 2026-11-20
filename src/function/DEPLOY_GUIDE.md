# FunctionGraph 部署指南

## 方式一：控制台手动部署（推荐）

### 1. 登录华为云控制台
访问 https://console.huaweicloud.com/functiongraph/

### 2. 创建函数

点击"创建函数"，填写以下信息：

| 字段 | 值 |
|------|-----|
| 函数名称 | shopping-cart-auth |
| 运行时 | Python 3.9 |
| 处理程序 | auth_handler.handler |
| 内存 | 128 MB |
| 超时时间 | 30 秒 |

### 3. 上传代码

创建函数后，点击"上传代码"，选择以下文件：

| 函数 | 文件 | 说明 |
|------|------|------|
| shopping-cart-auth | auth_handler.py | 用户认证 |
| shopping-cart-cart | cart_handler.py | 购物车 |
| shopping-cart-product | product_handler.py | 商品 |
| shopping-cart-order | order_handler.py | 订单 |

### 4. 配置环境变量

在函数配置中添加：

```
MYSQL_HOST=your-rds-endpoint
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your-password
MYSQL_DATABASE=shopping_cart
JWT_SECRET=your-secret-key
```

### 5. 创建触发器（可选）

API 网关触发器配置：

| 字段 | 值 |
|------|-----|
| API 名称 | shopping-cart-api |
| 认证方式 | None / App |
| 方法 | ANY |
| 路径 | /* |

---

## 方式二：使用华为云 CLI

### 1. 安装 CLI

```bash
pip install huaweicloud-cli
```

### 2. 配置凭证

```bash
hwcloud config set --type AKSK --region cn-north-4 --ak YOUR_AK --sk YOUR_SK
```

### 3. 创建函数

```bash
hwcloud fgs function create \
  --name shopping-cart-auth \
  --runtime Python3.9 \
  --handler auth_handler.handler \
  --code ./auth_handler.py
```

---

## 方式三：使用 Terraform（未来支持）

当前 Terraform Provider 版本不支持 FunctionGraph 的部分参数，需要等待 Provider 更新。

---

## 依赖说明

FunctionGraph Python 3.9 运行时已内置以下库：
- Python 3.9 标准库
- pymysql
- cryptography
- PyJWT
- pika

如需额外依赖，可通过 Layer 上传。

---

## 验证部署

部署完成后，可通过以下命令测试：

```bash
# 测试认证函数
curl -X POST https://{apig-url}/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "test", "password": "test"}'
```
