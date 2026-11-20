# 部署指南：购物车服务

## 前置条件

1. 华为云账号
2. AK/SK 凭证
3. Terraform >= 1.5
4. cn-north-4 区域

## 步骤 1：配置凭证

```bash
export HW_ACCESS_KEY="your-access-key"
export HW_SECRET_KEY="your-secret-key"
```

## 步骤 2：初始化

```bash
cd infra
terraform init
```

## 步骤 3：部署

```bash
terraform apply
```

### 结算方式

| 资源 | 规格 | 结算方式 |
|------|------|----------|
| APIG 专享版 | BASIC | 按小时 |
| FunctionGraph | 512MB | 按请求量 |
| RDS MySQL | 3节点 | 按小时 |
| DMS RabbitMQ | 单节点 | 按小时 |
| VPC | - | 不单独收费 |
| OBS | - | 不单独收费 |

## 步骤 4：验证

```bash
# 获取 API 地址
terraform output apig_url

# 测试创建购物车
curl -X POST https://{apig-url}/carts
```

## 步骤 5：清理

```bash
terraform destroy
```

## 手动创建资源

以下资源需要手动创建：

1. **FunctionGraph 函数**：
   - 创建购物车
   - 添加商品
   - 删除商品
   - 获取购物车
   - 合并购物车
   - 结账

2. **JWT 认证服务**：
   - 详细部署见 [auth-service-deployment.md](./auth-service-deployment.md)
   - 或使用 FunctionGraph + APIG 快速部署

3. **前端部署**：
   - 使用 SWR 镜像托管
   - 或 OBS 静态网站
