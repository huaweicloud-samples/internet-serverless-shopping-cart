# -*- coding: utf-8 -*-
"""
购物车服务 - 订单函数 (FunctionGraph)
依赖: pip install pymysql cryptography pika
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
            # 订单表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    order_id VARCHAR(36) PRIMARY KEY,
                    user_id VARCHAR(36),
                    cart_id VARCHAR(36),
                    total_amount DECIMAL(10, 2) NOT NULL,
                    status VARCHAR(50) NOT NULL DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
            """)
            # 订单商品表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS order_items (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    order_id VARCHAR(36) NOT NULL,
                    product_id VARCHAR(255) NOT NULL,
                    product_name VARCHAR(255),
                    price DECIMAL(10, 2) NOT NULL,
                    quantity INT NOT NULL,
                    FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE
                )
            """)
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


def get_cart_items(cart_id: str) -> list:
    """获取购物车商品"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT ci.product_id, ci.quantity, p.name, p.price FROM cart_items ci LEFT JOIN products p ON ci.product_id = p.product_id WHERE ci.cart_id = %s",
                (cart_id,)
            )
            return cursor.fetchall()
    finally:
        conn.close()


def create_order_handler(event: Dict) -> Dict:
    """创建订单 POST /orders"""
    import pymysql

    try:
        body = json.loads(event.get("body", "{}"))
        cart_id = body.get("cart_id")
        user_id = body.get("user_id")

        if not cart_id:
            return {"statusCode": 400, "body": json.dumps({"error": "cart_id required"})}

        # 获取购物车商品
        cart_items = get_cart_items(cart_id)
        if not cart_items:
            return {"statusCode": 400, "body": json.dumps({"error": "Cart is empty"})}

        # 计算总价
        total_amount = sum(float(item.get("price", 0)) * item["quantity"] for item in cart_items)

        order_id = str(uuid.uuid4())

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                # 创建订单
                cursor.execute(
                    "INSERT INTO orders (order_id, user_id, cart_id, total_amount, status) VALUES (%s, %s, %s, %s, %s)",
                    (order_id, user_id, cart_id, total_amount, "created")
                )

                # 创建订单商品
                for item in cart_items:
                    cursor.execute(
                        "INSERT INTO order_items (order_id, product_id, product_name, price, quantity) VALUES (%s, %s, %s, %s, %s)",
                        (order_id, item["product_id"], item.get("name", "Unknown"), item.get("price", 0), item["quantity"])
                    )

                # 清空购物车
                cursor.execute("DELETE FROM cart_items WHERE cart_id = %s", (cart_id,))
                cursor.execute("DELETE FROM shopping_carts WHERE cart_id = %s", (cart_id,))

                conn.commit()
        finally:
            conn.close()

        # 发送订单事件
        send_rabbitmq_message("order-events", {
            "event": "order_created",
            "order_id": order_id,
            "user_id": user_id,
            "total_amount": total_amount,
            "timestamp": int(time.time())
        })

        return {
            "statusCode": 201,
            "body": json.dumps({
                "order_id": order_id,
                "total_amount": total_amount,
                "status": "created",
                "created_at": int(time.time())
            })
        }

    except Exception as e:
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}


def get_order_handler(event: Dict) -> Dict:
    """获取订单 GET /orders/{order_id}"""
    import pymysql

    try:
        order_id = event.get("pathParameters", {}).get("order_id")
        if not order_id:
            return {"statusCode": 400, "body": json.dumps({"error": "order_id required"})}

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                # 获取订单
                cursor.execute(
                    "SELECT order_id, user_id, cart_id, total_amount, status, created_at FROM orders WHERE order_id = %s",
                    (order_id,)
                )
                order = cursor.fetchone()

                if not order:
                    return {"statusCode": 404, "body": json.dumps({"error": "Order not found"})}

                # 获取订单商品
                cursor.execute(
                    "SELECT product_id, product_name, price, quantity FROM order_items WHERE order_id = %s",
                    (order_id,)
                )
                items = cursor.fetchall()

                return {
                    "statusCode": 200,
                    "body": json.dumps({
                        "order_id": order["order_id"],
                        "user_id": order.get("user_id"),
                        "total_amount": float(order["total_amount"]),
                        "status": order["status"],
                        "items": [
                            {
                                "product_id": item["product_id"],
                                "product_name": item["product_name"],
                                "price": float(item["price"]),
                                "quantity": item["quantity"]
                            }
                            for item in items
                        ],
                        "created_at": int(order["created_at"].timestamp()) if hasattr(order["created_at"], 'timestamp') else 0
                    })
                }
        finally:
            conn.close()

    except Exception as e:
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}


def list_orders_handler(event: Dict) -> Dict:
    """获取用户订单列表 GET /orders"""
    import pymysql

    try:
        user_id = event.get("queryStringParameters", {}).get("user_id")
        if not user_id:
            return {"statusCode": 400, "body": json.dumps({"error": "user_id required"})}

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT order_id, user_id, total_amount, status, created_at FROM orders WHERE user_id = %s ORDER BY created_at DESC",
                    (user_id,)
                )
                orders = cursor.fetchall()

                return {
                    "statusCode": 200,
                    "body": json.dumps({
                        "orders": [
                            {
                                "order_id": o["order_id"],
                                "total_amount": float(o["total_amount"]),
                                "status": o["status"],
                                "created_at": int(o["created_at"].timestamp()) if hasattr(o["created_at"], "timestamp") else 0
                            }
                            for o in orders
                        ],
                        "total": len(orders)
                    })
                }
        finally:
            conn.close()

    except Exception as e:
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}


def handler(event: Dict, context: Dict) -> Dict:
    """FunctionGraph 入口函数"""
    path = event.get("path", "")
    http_method = event.get("httpMethod", "GET")

    if path == "/orders" and http_method == "POST":
        return create_order_handler(event)
    elif path == "/orders" and http_method == "GET":
        return list_orders_handler(event)
    elif path.startswith("/orders/") and http_method == "GET":
        return get_order_handler(event)
    else:
        return {"statusCode": 404, "body": json.dumps({"error": "Not found"})}


if __name__ == "__main__":
    print("初始化数据库...")
    init_db()
    print("测试获取订单列表...")
    result = handler({"path": "/orders", "httpMethod": "GET", "queryStringParameters": {"user_id": "test"}}, {})
    print(result)
