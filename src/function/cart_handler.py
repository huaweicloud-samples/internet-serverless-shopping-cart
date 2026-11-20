# -*- coding: utf-8 -*-
"""
购物车服务 - 购物车函数 (FunctionGraph)
依赖: pip install pymysql cryptography PyJWT pika
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

# RabbitMQ 配置
RABBITMQ_ENDPOINT = os.environ.get("RABBITMQ_ENDPOINT", "")


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
            # 购物车表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS shopping_carts (
                    cart_id VARCHAR(36) PRIMARY KEY,
                    user_id VARCHAR(36),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NULL
                )
            """)
            # 购物车商品表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cart_items (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    cart_id VARCHAR(36) NOT NULL,
                    product_id VARCHAR(255) NOT NULL,
                    quantity INT NOT NULL DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (cart_id) REFERENCES shopping_carts(cart_id) ON DELETE CASCADE
                )
            """)
            # 索引
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cart_user ON shopping_carts(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cart_items_cart ON cart_items(cart_id)")
            conn.commit()
    finally:
        conn.close()


def send_rabbitmq_message(queue: str, message: Dict):
    """发送消息到 RabbitMQ"""
    if not RABBITMQ_ENDPOINT:
        return
    try:
        import pika
        params = pika.URLParameters(RABBITMQ_ENDPOINT)
        connection = pika.BlockingConnection(params)
        channel = connection.channel()
        channel.queue_declare(queue=queue, durable=True)
        channel.basic_publish(
            exchange='',
            routing_key=queue,
            body=json.dumps(message),
            properties=pika.BasicProperties(delivery_mode=2)
        )
        connection.close()
    except Exception as e:
        print(f"RabbitMQ send error: {e}")


def create_cart_handler(event: Dict) -> Dict:
    """创建购物车 POST /carts"""
    import pymysql

    try:
        body = json.loads(event.get("body", "{}"))
        user_id = body.get("user_id")  # 可选，登录用户

        cart_id = str(uuid.uuid4())
        expires_at = int(time.time()) + (86400 * 7)  # 7天过期

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO shopping_carts (cart_id, user_id, expires_at) VALUES (%s, %s, FROM_UNIXTIME(%s))",
                    (cart_id, user_id, expires_at)
                )
                conn.commit()
        finally:
            conn.close()

        return {
            "statusCode": 201,
            "body": json.dumps({
                "cart_id": cart_id,
                "user_id": user_id,
                "items": [],
                "expires_at": expires_at
            })
        }

    except Exception as e:
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}


def get_cart_handler(event: Dict) -> Dict:
    """获取购物车 GET /carts/{cart_id}"""
    import pymysql

    try:
        cart_id = event.get("pathParameters", {}).get("cart_id")
        if not cart_id:
            return {"statusCode": 400, "body": json.dumps({"error": "cart_id required"})}

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                # 获取购物车
                cursor.execute(
                    "SELECT cart_id, user_id, created_at, expires_at FROM shopping_carts WHERE cart_id = %s",
                    (cart_id,)
                )
                cart = cursor.fetchone()

                if not cart:
                    return {"statusCode": 404, "body": json.dumps({"error": "Cart not found"})}

                # 检查过期
                if cart.get("expires_at"):
                    expires_ts = int(cart["expires_at"].timestamp()) if hasattr(cart["expires_at"], 'timestamp') else 0
                    if expires_ts < int(time.time()):
                        return {"statusCode": 410, "body": json.dumps({"error": "Cart expired"})}

                # 获取商品
                cursor.execute(
                    "SELECT product_id, quantity FROM cart_items WHERE cart_id = %s",
                    (cart_id,)
                )
                items = cursor.fetchall()

                return {
                    "statusCode": 200,
                    "body": json.dumps({
                        "cart_id": cart["cart_id"],
                        "user_id": cart.get("user_id"),
                        "items": [{"product_id": item["product_id"], "quantity": item["quantity"]} for item in items],
                        "created_at": int(cart["created_at"].timestamp()) if hasattr(cart["created_at"], 'timestamp') else 0
                    })
                }
        finally:
            conn.close()

    except Exception as e:
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}


def add_item_handler(event: Dict) -> Dict:
    """添加商品 POST /carts/{cart_id}/items"""
    import pymysql

    try:
        cart_id = event.get("pathParameters", {}).get("cart_id")
        if not cart_id:
            return {"statusCode": 400, "body": json.dumps({"error": "cart_id required"})}

        body = json.loads(event.get("body", "{}"))
        product_id = body.get("product_id")
        quantity = int(body.get("quantity", 1))

        if not product_id:
            return {"statusCode": 400, "body": json.dumps({"error": "product_id required"})}

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                # 检查商品是否已存在
                cursor.execute(
                    "SELECT id, quantity FROM cart_items WHERE cart_id = %s AND product_id = %s",
                    (cart_id, product_id)
                )
                existing = cursor.fetchone()

                if existing:
                    cursor.execute(
                        "UPDATE cart_items SET quantity = quantity + %s WHERE id = %s",
                        (quantity, existing["id"])
                    )
                else:
                    cursor.execute(
                        "INSERT INTO cart_items (cart_id, product_id, quantity) VALUES (%s, %s, %s)",
                        (cart_id, product_id, quantity)
                    )
                conn.commit()
        finally:
            conn.close()

        # 发送事件到 RabbitMQ
        send_rabbitmq_message("cart-events", {
            "event": "item_added",
            "cart_id": cart_id,
            "product_id": product_id,
            "quantity": quantity,
            "timestamp": int(time.time())
        })

        return {
            "statusCode": 200,
            "body": json.dumps({"message": "Item added", "cart_id": cart_id, "product_id": product_id})
        }

    except Exception as e:
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}


def remove_item_handler(event: Dict) -> Dict:
    """删除商品 DELETE /carts/{cart_id}/items/{product_id}"""
    import pymysql

    try:
        cart_id = event.get("pathParameters", {}).get("cart_id")
        product_id = event.get("pathParameters", {}).get("product_id")

        if not cart_id or not product_id:
            return {"statusCode": 400, "body": json.dumps({"error": "cart_id and product_id required"})}

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM cart_items WHERE cart_id = %s AND product_id = %s",
                    (cart_id, product_id)
                )
                conn.commit()
        finally:
            conn.close()

        return {
            "statusCode": 200,
            "body": json.dumps({"message": "Item removed", "cart_id": cart_id, "product_id": product_id})
        }

    except Exception as e:
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}


def merge_carts_handler(event: Dict) -> Dict:
    """合并购物车 POST /carts/merge"""
    import pymysql

    try:
        body = json.loads(event.get("body", "{}"))
        anonymous_cart_id = body.get("anonymous_cart_id")
        user_cart_id = body.get("user_cart_id")

        if not anonymous_cart_id or not user_cart_id:
            return {"statusCode": 400, "body": json.dumps({"error": "cart_ids required"})}

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                # 获取匿名购物车的商品
                cursor.execute(
                    "SELECT product_id, quantity FROM cart_items WHERE cart_id = %s",
                    (anonymous_cart_id,)
                )
                anonymous_items = cursor.fetchall()

                for item in anonymous_items:
                    # 检查用户购物车是否已有该商品
                    cursor.execute(
                        "SELECT id, quantity FROM cart_items WHERE cart_id = %s AND product_id = %s",
                        (user_cart_id, item["product_id"])
                    )
                    existing = cursor.fetchone()

                    if existing:
                        cursor.execute(
                            "UPDATE cart_items SET quantity = quantity + %s WHERE id = %s",
                            (item["quantity"], existing["id"])
                        )
                    else:
                        cursor.execute(
                            "INSERT INTO cart_items (cart_id, product_id, quantity) VALUES (%s, %s, %s)",
                            (user_cart_id, item["product_id"], item["quantity"])
                        )

                # 删除匿名购物车
                cursor.execute("DELETE FROM shopping_carts WHERE cart_id = %s", (anonymous_cart_id,))
                conn.commit()
        finally:
            conn.close()

        # 发送合并事件
        send_rabbitmq_message("cart-merge", {
            "event": "carts_merged",
            "source_cart_id": anonymous_cart_id,
            "target_cart_id": user_cart_id,
            "timestamp": int(time.time())
        })

        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Carts merged",
                "source_cart_id": anonymous_cart_id,
                "target_cart_id": user_cart_id
            })
        }

    except Exception as e:
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}


def handler(event: Dict, context: Dict) -> Dict:
    """FunctionGraph 入口函数"""
    path = event.get("path", "")
    http_method = event.get("httpMethod", "GET")

    # 路由分发
    if path == "/carts" and http_method == "POST":
        return create_cart_handler(event)
    elif path == "/carts" and http_method == "GET":
        return create_cart_handler(event)  # 简化：创建购物车
    elif path.startswith("/carts/") and path.endswith("/items") and http_method == "POST":
        return add_item_handler(event)
    elif "/carts/" in path and "/items/" in path and http_method == "DELETE":
        return remove_item_handler(event)
    elif path == "/carts/merge" and http_method == "POST":
        return merge_carts_handler(event)
    elif path.startswith("/carts/") and http_method == "GET":
        return get_cart_handler(event)
    else:
        return {"statusCode": 404, "body": json.dumps({"error": "Not found"})}


if __name__ == "__main__":
    print("初始化数据库...")
    init_db()
    print("测试创建购物车...")
    result = handler({"path": "/carts", "httpMethod": "POST", "body": "{}"}, {})
    print(result)
