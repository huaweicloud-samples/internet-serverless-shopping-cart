# -*- coding: utf-8 -*-
"""
购物车服务 - 模型适配层
华为云服务适配

依赖: pip install pymysql cryptography
"""

import json
import time
import uuid
import os
from typing import List, Dict, Any, Optional
from contextlib import contextmanager

# RDS MySQL 连接配置
MYSQL_CONFIG = {
    "host": os.environ.get("MYSQL_HOST", "localhost"),
    "port": int(os.environ.get("MYSQL_PORT", 3306)),
    "user": os.environ.get("MYSQL_USER", "root"),
    "password": os.environ.get("MYSQL_PASSWORD", ""),
    "database": os.environ.get("MYSQL_DATABASE", "shopping_cart"),
    "charset": "utf8mb4",
}


class MySQLConnection:
    """MySQL 连接管理器"""

    _instance = None

    def __new__(cls, config: Dict = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._config = config or MYSQL_CONFIG
        return cls._instance

    @property
    def config(self) -> Dict:
        return self._config

    @contextmanager
    def get_connection(self):
        """获取数据库连接"""
        import pymysql
        conn = pymysql.connect(**self._config)
        try:
            yield conn
        finally:
            conn.close()

    def init_tables(self):
        """初始化数据库表"""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                # 用户表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        user_id VARCHAR(36) PRIMARY KEY,
                        username VARCHAR(255) UNIQUE NOT NULL,
                        password_hash VARCHAR(255) NOT NULL,
                        email VARCHAR(255),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                    )
                """)

                # 购物车表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS shopping_carts (
                        cart_id VARCHAR(36) PRIMARY KEY,
                        user_id VARCHAR(36),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        expires_at TIMESTAMP NULL,
                        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE SET NULL
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
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_cart_user ON shopping_carts(user_id)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_cart_items_cart ON cart_items(cart_id)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_cart_expires ON shopping_carts(expires_at)
                """)

                conn.commit()


# 全局 MySQL 连接
_mysql = MySQLConnection()


class AuthAdapter:
    """
    认证适配器 - 自建 JWT 认证
    自建 JWT 认证服务 + RDS MySQL
    """

    def __init__(self, jwt_secret: str = None, mysql_config: Dict = None):
        self.jwt_secret = jwt_secret or os.environ.get("JWT_SECRET", "your-secret-key-change-in-production")
        if mysql_config:
            global _mysql
            _mysql = MySQLConnection(mysql_config)

    def register(self, username: str, password: str, email: str = None) -> Dict:
        """用户注册"""
        import hashlib
        import pymysql

        user_id = str(uuid.uuid4())
        password_hash = hashlib.sha256(password.encode()).hexdigest()

        try:
            with _mysql.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "INSERT INTO users (user_id, username, password_hash, email) VALUES (%s, %s, %s, %s)",
                        (user_id, username, password_hash, email)
                    )
                    conn.commit()
            return {"user_id": user_id, "username": username, "status": "registered"}
        except pymysql.IntegrityError:
            return {"error": "Username already exists", "code": "DUPLICATE_USERNAME"}

    def login(self, username: str, password: str) -> Dict:
        """用户登录"""
        import hashlib
        import jwt as pyjwt

        password_hash = hashlib.sha256(password.encode()).hexdigest()

        with _mysql.get_connection() as conn:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute(
                    "SELECT user_id, username FROM users WHERE username = %s AND password_hash = %s",
                    (username, password_hash)
                )
                user = cursor.fetchone()

        if not user:
            return {"error": "Invalid credentials", "code": "INVALID_CREDENTIALS"}

        token = pyjwt.encode(
            {"sub": user["user_id"], "username": username, "exp": int(time.time()) + 3600 * 24 * 7},
            self.jwt_secret,
            algorithm="HS256"
        )
        return {
            "token": token,
            "expires_in": 604800,
            "user_id": user["user_id"],
            "username": username
        }

    def verify_token(self, token: str) -> Dict:
        """验证 Token"""
        try:
            import jwt as pyjwt
            payload = pyjwt.decode(token, self.jwt_secret, algorithms=["HS256"])
            return {"valid": True, "user_id": payload.get("sub"), "username": payload.get("username")}
        except:
            return {"valid": False}

    def get_user(self, user_id: str) -> Dict:
        """获取用户信息"""
        with _mysql.get_connection() as conn:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute(
                    "SELECT user_id, username, email, created_at FROM users WHERE user_id = %s",
                    (user_id,)
                )
                return cursor.fetchone() or {}


class ShoppingCartAdapter:
    """
    购物车适配器 - 关系型存储
    华为云 RDS MySQL 适配
    """

    def __init__(self, mysql_config: Dict = None):
        if mysql_config:
            global _mysql
            _mysql = MySQLConnection(mysql_config)

    def create_cart(self, user_id: str = None) -> Dict:
        """创建购物车"""
        cart_id = str(uuid.uuid4())
        expires_at = int(time.time()) + (86400 * 7)  # 7天过期

        with _mysql.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO shopping_carts (cart_id, user_id, expires_at) VALUES (%s, %s, FROM_UNIXTIME(%s))",
                    (cart_id, user_id, expires_at)
                )
                conn.commit()

        return {
            "cart_id": cart_id,
            "user_id": user_id,
            "items": [],
            "created_at": int(time.time()),
            "expires_at": expires_at
        }

    def add_item(self, cart_id: str, product_id: str, quantity: int = 1) -> Dict:
        """添加商品到购物车"""
        import pymysql

        # 检查商品是否已存在
        with _mysql.get_connection() as conn:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute(
                    "SELECT id, quantity FROM cart_items WHERE cart_id = %s AND product_id = %s",
                    (cart_id, product_id)
                )
                existing = cursor.fetchone()

                if existing:
                    # 更新数量
                    cursor.execute(
                        "UPDATE cart_items SET quantity = quantity + %s WHERE id = %s",
                        (quantity, existing["id"])
                    )
                else:
                    # 插入新商品
                    cursor.execute(
                        "INSERT INTO cart_items (cart_id, product_id, quantity) VALUES (%s, %s, %s)",
                        (cart_id, product_id, quantity)
                    )
                conn.commit()

        return self.get_cart(cart_id)

    def remove_item(self, cart_id: str, product_id: str) -> Dict:
        """移除购物车商品"""
        with _mysql.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM cart_items WHERE cart_id = %s AND product_id = %s",
                    (cart_id, product_id)
                )
                conn.commit()

        return {"cart_id": cart_id, "product_id": product_id, "removed": True}

    def get_cart(self, cart_id: str) -> Dict:
        """获取购物车"""
        import pymysql

        with _mysql.get_connection() as conn:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                # 获取购物车信息
                cursor.execute(
                    "SELECT cart_id, user_id, created_at, expires_at FROM shopping_carts WHERE cart_id = %s",
                    (cart_id,)
                )
                cart = cursor.fetchone()

                if not cart:
                    return {"cart_id": cart_id, "items": [], "error": "Cart not found"}

                # 检查过期
                if cart.get("expires_at"):
                    expires_ts = int(cart["expires_at"].timestamp()) if hasattr(cart["expires_at"], 'timestamp') else 0
                    if expires_ts < int(time.time()):
                        return {"cart_id": cart_id, "items": [], "error": "Cart expired"}

                # 获取商品列表
                cursor.execute(
                    "SELECT product_id, quantity, created_at FROM cart_items WHERE cart_id = %s",
                    (cart_id,)
                )
                items = cursor.fetchall()

                return {
                    "cart_id": cart["cart_id"],
                    "user_id": cart.get("user_id"),
                    "items": [
                        {
                            "product_id": item["product_id"],
                            "quantity": item["quantity"]
                        }
                        for item in items
                    ],
                    "created_at": int(cart["created_at"].timestamp()) if hasattr(cart["created_at"], 'timestamp') else 0
                }

    def merge_carts(self, anonymous_cart_id: str, user_cart_id: str) -> Dict:
        """合并购物车（登录时）"""
        import pymysql

        with _mysql.get_connection() as conn:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
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
                            (user_cart_id, item["product_id"], item["quantity"]))

                # 删除匿名购物车
                cursor.execute("DELETE FROM shopping_carts WHERE cart_id = %s", (anonymous_cart_id,))
                conn.commit()

        return {"merged_cart_id": user_cart_id, "source_cart_id": anonymous_cart_id}

    def clear_cart(self, cart_id: str) -> Dict:
        """清空购物车"""
        with _mysql.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM cart_items WHERE cart_id = %s", (cart_id,))
                conn.commit()
        return {"cart_id": cart_id, "cleared": True}


class QueueAdapter:
    """
    队列适配器 - 消息队列服务
    华为云 DMS RabbitMQ 适配
    """

    def __init__(self, endpoint: str = None):
        self.endpoint = endpoint or os.environ.get("RABBITMQ_ENDPOINT")

    def send_message(self, queue_name: str, message: Dict) -> Dict:
        """发送消息"""
        # TODO: 发送到 RabbitMQ
        # 可以使用 pika 库连接 RabbitMQ
        return {"message_id": str(uuid.uuid4()), "queue": queue_name}

    def receive_message(self, queue_name: str) -> Dict:
        """接收消息"""
        # TODO: 从 RabbitMQ 读取
        return {}


class ShoppingCartService:
    """
    购物车服务主类
    """

    def __init__(
        self,
        auth: AuthAdapter = None,
        cart: ShoppingCartAdapter = None,
        queue: QueueAdapter = None
    ):
        self.auth = auth or AuthAdapter()
        self.cart = cart or ShoppingCartAdapter()
        self.queue = queue or QueueAdapter()

    def initialize_database(self):
        """初始化数据库表"""
        _mysql.init_tables()

    def add_to_cart(self, cart_id: str, product_id: str, quantity: int = 1) -> Dict:
        """添加商品到购物车"""
        result = self.cart.add_item(cart_id, product_id, quantity)

        # 发送事件到队列
        self.queue.send_message("cart-events", {
            "event": "item_added",
            "cart_id": cart_id,
            "product_id": product_id,
            "timestamp": int(time.time())
        })

        return result

    def get_cart(self, cart_id: str) -> Dict:
        """获取购物车"""
        return self.cart.get_cart(cart_id)

    def checkout(self, cart_id: str) -> Dict:
        """结账"""
        cart = self.cart.get_cart(cart_id)

        if cart.get("items") is None:
            return {"error": cart.get("error", "Cart not found")}

        # 发送结账事件
        self.queue.send_message("order-events", {
            "event": "checkout",
            "cart_id": cart_id,
            "items": cart.get("items", []),
            "timestamp": int(time.time())
        })

        # 清空购物车
        self.cart.clear_cart(cart_id)

        return {"order_id": str(uuid.uuid4()), "status": "created"}


# 环境变量配置说明
ENV_CONFIG = """
# RDS MySQL 配置
export MYSQL_HOST="your-rds-endpoint.rds.cn-north-4.myhuaweicloud.com"
export MYSQL_PORT=3306
export MYSQL_USER="root"
export MYSQL_PASSWORD="your-password"
export MYSQL_DATABASE="shopping_cart"

# JWT 密钥
export JWT_SECRET="your-secret-key-change-in-production"

# RabbitMQ (可选)
export RABBITMQ_ENDPOINT="amqp://user:password@rabbitmq-host:5672"
"""

if __name__ == "__main__":
    service = ShoppingCartService()

    # 初始化数据库
    print("初始化数据库表...")
    service.initialize_database()

    # 创建购物车
    cart = service.cart.create_cart()
    print("购物车:", cart["cart_id"])

    # 添加商品
    service.add_to_cart(cart["cart_id"], "product-123", 2)

    # 获取购物车
    result = service.get_cart(cart["cart_id"])
    print("购物车内容:", result)
