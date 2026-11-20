# -*- coding: utf-8 -*-
"""
部署 FunctionGraph 函数到华为云
使用 IAM Token 认证
"""
import os
import zipfile
import base64
import json
from io import BytesIO
import requests
from datetime import datetime
import time

# 配置
AK = "YOUR_ACCESS_KEY"
SK = "YOUR_SECRET_KEY"
REGION = "cn-north-4"
PROJECT_ID = os.environ.get("HW_PROJECT_ID", "")  # 项目 ID 经环境变量传入，不硬编码

# 函数列表
FUNCTIONS = [
    {
        "name": "shopping-cart-auth",
        "handler": "auth_handler.handler",
        "description": "用户认证函数",
        "file": "auth_handler.py",
        "runtime": "Python3.9",
        "memory": 128,
        "timeout": 30
    },
    {
        "name": "shopping-cart-cart",
        "handler": "cart_handler.handler",
        "description": "购物车函数",
        "file": "cart_handler.py",
        "runtime": "Python3.9",
        "memory": 128,
        "timeout": 30
    },
    {
        "name": "shopping-cart-product",
        "handler": "product_handler.handler",
        "description": "商品函数",
        "file": "product_handler.py",
        "runtime": "Python3.9",
        "memory": 128,
        "timeout": 30
    },
    {
        "name": "shopping-cart-order",
        "handler": "order_handler.handler",
        "description": "订单函数",
        "file": "order_handler.py",
        "runtime": "Python3.9",
        "memory": 128,
        "timeout": 30
    },
]


def get_iam_token():
    """获取 IAM Token"""
    iam_url = "https://iam.cn-north-4.myhuaweicloud.com/v3/auth/tokens"

    body = {
        "auth": {
            "identity": {
                "methods": ["hw_aksk"],
                "hw_aksk": {
                    "access_key": AK,
                    "secret_key": SK
                }
            },
            "scope": {
                "project": {
                    "id": PROJECT_ID
                }
            }
        }
    }

    try:
        response = requests.post(iam_url, json=body, timeout=30)
        if response.status_code in [200, 201]:
            token = response.headers.get("X-Subject-Token")
            print(f"✅ 获取 IAM Token 成功")
            return token
        else:
            print(f"❌ 获取 IAM Token 失败: {response.status_code}")
            print(f"   {response.text[:200]}")
            return None
    except Exception as e:
        print(f"❌ 获取 IAM Token 失败: {e}")
        return None


def create_function(token, func_config):
    """创建函数"""
    func_name = func_config["name"]

    # 读取函数代码
    with open(func_config["file"], 'r', encoding='utf-8') as f:
        code = f.read()

    # 创建 zip
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(func_config["file"], code)
    zip_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

    # API 配置
    endpoint = f"functiongraph.{REGION}.myhuaweicloud.com"
    url = f"https://{endpoint}/v2/{PROJECT_ID}/fgs/function"

    headers = {
        "Content-Type": "application/json",
        "X-Auth-Token": token
    }

    # 请求体
    body = {
        "func_name": func_name,
        "description": func_config["description"],
        "handler": func_config["handler"],
        "runtime": func_config["runtime"],
        "memory_size": func_config["memory"],
        "timeout": func_config["timeout"],
        "code_type": "inline",
        "func_code": {
            "file": zip_base64
        }
    }

    try:
        response = requests.post(url, headers=headers, json=body, timeout=60)
        if response.status_code in [200, 201]:
            result = response.json()
            print(f"✅ 函数 {func_name} 创建成功")
            print(f"   URN: {result.get('func_urn', 'N/A')}")
            return result
        else:
            print(f"❌ 函数 {func_name} 创建失败: {response.status_code}")
            print(f"   {response.text[:300]}")
            return None
    except Exception as e:
        print(f"❌ 函数 {func_name} 创建失败: {e}")
        return None


def list_functions(token):
    """列出函数"""
    endpoint = f"functiongraph.{REGION}.myhuaweicloud.com"
    url = f"https://{endpoint}/v2/{PROJECT_ID}/fgs/function?limit=100"

    headers = {
        "X-Auth-Token": token
    }

    try:
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code == 200:
            result = response.json()
            functions = result.get("functions", [])
            print(f"\n已存在的函数 ({len(functions)} 个):")
            for func in functions:
                print(f"  - {func.get('func_name')} ({func.get('runtime')})")
        else:
            print(f"列出函数失败: {response.status_code}")
            print(f"   {response.text[:200]}")
    except Exception as e:
        print(f"列出函数失败: {e}")


def main():
    """主函数"""
    print("=" * 60)
    print("华为云 FunctionGraph 部署")
    print("=" * 60)
    print(f"Region: {REGION}")
    print(f"Project ID: {PROJECT_ID}")
    print(f"Functions: {len(FUNCTIONS)}")
    print("=" * 60)

    # 获取 Token
    token = get_iam_token()
    if not token:
        print("\n❌ 无法获取 IAM Token，请检查 AK/SK")
        return

    # 列出已存在的函数
    list_functions(token)

    print("\n开始部署函数...")

    for func_config in FUNCTIONS:
        create_function(token, func_config)

    print("\n" + "=" * 60)
    print("部署完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()
