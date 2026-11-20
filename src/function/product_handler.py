# -*- coding: utf-8 -*-
"""
购物车服务 - 商品函数 (FunctionGraph)
依赖: pip install pymysql cryptography
"""

import json
import time
import uuid
import os
from typing import Dict, Any

# RDS MySQL 连接配置
MYSQL_HOST = os.environ.get("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.environ.get("MYSQL_PORT", 3306))
MYSQL_USER = os.environ.get("MYSQL_USER", "root")
MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.environ.get("MYSQL_DATABASE", "shopping_cart")


def get_db_connection():
    """获取数据库连接"""
    import pymysql
    return pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=(MYSQL_PASSWORD),
        database=MYSQL_DATABASE,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor
    )


def init_db():
    """初始化数据库表"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 商品表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    product_id VARCHAR(36) PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    description TEXT,
                    price DECIMAL(10, 2) NOT NULL,
                    stock INT NOT NULL DEFAULT 0,
                    category VARCHAR(100),
                    image_url VARCHAR(500),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
    finally:
        conn.close()


# 示例商品数据
SAMPLE_PRODUCTS = [
    {"product_id": "prod-001", "name": "iPhone 15 Pro", "description": "Apple iPhone 15 Pro 256GB", "price": 8999.00, "stock": 100, "category": "Electronics"},
    {"product_id": "prod-002", "name": "MacBook Pro 14", "description": "Apple MacBook Pro 14 inch M3", "price": 16999.00, "stock": 50, "category": "Electronics"},
    {"product_id": "prod-003", "name": "AirPods Pro", "description": "Apple AirPods Pro 2nd Gen", "price": 1899.00, "stock": 200, "category": "Audio"},
    {"product_id": "prod-004", "name": "iPad Air", "description": "Apple iPad Air 10.9 inch", "price": 4599.00, "stock": 80, "category": "Electronics"},
    {"product_id": "prod-005", "name": "Apple Watch", "description": "Apple Watch Series 9", "price": 2999.00, "stock": 150, "category": "Wearables"},
]


def list_products_handler(event: Dict) -> Dict:
    """获取商品列表 GET /products"""
    import pymysql

    try:
        category = event.get("queryStringParameters", {}).get("category")

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                if category:
                    cursor.execute(
                        "SELECT product_id, name, description, price, stock, category, image_url FROM products WHERE category = %s",
                        (category,)
                    )
                else:
                    cursor.execute(
                        "SELECT product_id, name, description, price, stock, category, image_url FROM products"
                    )
                products = cursor.fetchall()

                # 如果没有商品，返回示例数据
                if not products:
                    return {
                        "statusCode": 200,
                        "body": json.dumps({
                            "products": SAMPLE_PRODUCTS,
                            "total": len(SAMPLE_PRODUCTS)
                        })
                    }

                return {
                    "statusCode": 200,
                    "body": json.dumps({
                        "products": [
                            {
                                "product_id": p["product_id"],
                                "name": p["name"],
                                "description": p["description"],
                                "price": float(p["price"]),
                                "stock": p["stock"],
                                "category": p["category"],
                                "image_url": p.get("image_url")
                            }
                            for p in products
                        ],
                        "total": len(products)
                    })
                }
        finally:
            conn.close()

    except Exception as e:
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}


def get_product_handler(event: Dict) -> Dict:
    """获取单个商品 GET /products/{product_id}"""
    import pymysql

    try:
        product_id = event.get("pathParameters", {}).get("product_id")
        if not product_id:
            return {"statusCode": 400, "body": json.dumps({"error": "product_id required"})}

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT product_id, name, description, price, stock, category, image_url FROM products WHERE product_id = %s",
                    (product_id,)
                )
                product = cursor.fetchone()

                if not product:
                    # 返回示例商品
                    for p in SAMPLE_PRODUCTS:
                        if p["product_id"] == product_id:
                            return {
                                "statusCode": 200,
                                "body": json.dumps(p)
                            }
                    return {"statusCode": 404, "body": json.dumps({"error": "Product not found"})}

                return {
                    "statusCode": 200,
                    "body": json.dumps({
                        "product_id": product["product_id"],
                        "name": product["name"],
                        "description": product["description"],
                        "price": float(product["price"]),
                        "stock": product["stock"],
                        "category": product["category"],
                        "image_url": product.get("image_url")
                    })
                }
        finally:
            conn.close()

    except Exception as e:
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}


def create_product_handler(event: Dict) -> Dict:
    """创建商品 POST /products"""
    import pymysql

    try:
        body = json.loads(event.get("body", "{}"))
        product_id = body.get("product_id") or str(uuid.uuid4())

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO products (product_id, name, description, price, stock, category, image_url) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (product_id, body.get("name"), body.get("description"), body.get("price"), body.get("stock", 0), body.get("category"), body.get("image_url"))
                )
                conn.commit()
        finally:
            conn.close()

        return {
            "statusCode": 201,
            "body": json.dumps({"message": "Product created", "product_id": product_id})
        }

    except Exception as e:
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}


def handler(event: Dict, context: Dict) -> Dict:
    """FunctionGraph 入口函数"""
    path = event.get("path", "")
    http_method = event.get("httpMethod", "GET")

    if path == "/products" and http_method == "GET":
        return list_products_handler(event)
    elif path == "/products" and http_method == "POST":
        return create_product_handler(event)
    elif path.startswith("/products/") and http_method == "GET":
        return get_product_handler(event)
    else:
        return {"statusCode": 404, "body": json.dumps({"error": "Not found"})}


if __name__ == "__main__":
    print("测试获取商品列表...")
    result = handler({"path": "/products", "httpMethod": "GET", "queryStringParameters": {}}, {})
    print(result)
