# -*- coding: utf-8 -*-
"""
购物车服务 - 认证函数 (FunctionGraph)
自建 JWT 认证服务
依赖: pip install pymysql cryptography PyJWT
"""

import json
import time
import uuid
import hashlib
import os
from typing import Dict, Any, Optional

# RDS MySQL 连接配置
MYSQL_HOST = os.environ.get("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.environ.get("MYSQL_PORT", 3306))
MYSQL_USER = os.environ.get("MYSQL_USER", "root")
MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.environ.get("MYSQL_DATABASE", "shopping_cart")

# JWT 配置
JWT_SECRET = os.environ.get("JWT_SECRET", "your-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
TOKEN_EXPIRE_SECONDS = 7 * 24 * 3600  # 7 天


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
            conn.commit()
    finally:
        conn.close()


def hash_password(password: str) -> str:
    """密码哈希 - 使用 SHA256 + salt"""
    salt = "shopping_cart_salt"  # 生产环境应使用随机 salt
    return hashlib.sha256(f"{salt}{password}".encode()).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    """验证密码"""
    return hash_password(password) == password_hash


def generate_token(user_id: str, username: str) -> str:
    """生成 JWT Token"""
    import jwt as pyjwt
    payload = {
        "sub": user_id,
        "username": username,
        "iat": int(time.time()),
        "exp": int(time.time()) + TOKEN_EXPIRE_SECONDS
    }
    token = pyjwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token


def verify_token(token: str) -> Optional[Dict]:
    """验证 JWT Token"""
    import jwt as pyjwt
    try:
        payload = pyjwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return {
            "valid": True,
            "user_id": payload.get("sub"),
            "username": payload.get("username")
        }
    except pyjwt.ExpiredSignatureError:
        return {"valid": False, "error": "Token expired"}
    except pyjwt.InvalidTokenError:
        return {"valid": False, "error": "Invalid token"}


def register_handler(event: Dict) -> Dict:
    """
    用户注册处理函数
    POST /auth/register
    Body: {"username": "xxx", "password": "xxx", "email": "xxx"}
    """
    import pymysql

    try:
        body = json.loads(event.get("body", "{}"))
        username = body.get("username")
        password = body.get("password")
        email = body.get("email", "")

        if not username or not password:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Username and password required"})
            }

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                # 检查用户是否已存在
                cursor.execute("SELECT user_id FROM users WHERE username = %s", (username,))
                if cursor.fetchone():
                    return {
                        "statusCode": 409,
                        "body": json.dumps({"error": "Username already exists"})
                    }

                # 创建新用户
                user_id = str(uuid.uuid4())
                user_doc = {
                    "user_id": user_id,
                    "username": username,
                    "password_hash": hash_password(password),
                    "email": email,
                }
                cursor.execute(
                    "INSERT INTO users (user_id, username, password_hash, email) VALUES (%s, %s, %s, %s)",
                    (user_doc["user_id"], user_doc["username"], user_doc["password_hash"], user_doc["email"])
                )
                conn.commit()
        finally:
            conn.close()

        return {
            "statusCode": 201,
            "body": json.dumps({
                "message": "User registered successfully",
                "user_id": user_id,
                "username": username
            })
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }


def login_handler(event: Dict) -> Dict:
    """
    用户登录处理函数
    POST /auth/login
    Body: {"username": "xxx", "password": "xxx"}
    """
    import pymysql

    try:
        body = json.loads(event.get("body", "{}"))
        username = body.get("username")
        password = body.get("password")

        if not username or not password:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Username and password required"})
            }

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                # 查找用户
                cursor.execute(
                    "SELECT user_id, username FROM users WHERE username = %s AND password_hash = %s",
                    (username, hash_password(password))
                )
                user = cursor.fetchone()

                if not user:
                    return {
                        "statusCode": 401,
                        "body": json.dumps({"error": "Invalid credentials"})
                    }

                # 生成 Token
                token = generate_token(user["user_id"], user["username"])

                return {
                    "statusCode": 200,
                    "body": json.dumps({
                        "token": token,
                        "token_type": "Bearer",
                        "expires_in": TOKEN_EXPIRE_SECONDS,
                        "user_id": user["user_id"],
                        "username": user["username"]
                    })
                }
        finally:
            conn.close()

    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }


def verify_handler(event: Dict) -> Dict:
    """
    Token 验证处理函数
    GET /auth/verify
    Headers: Authorization: Bearer <token>
    """
    try:
        # 从 Header 获取 Token
        auth_header = event.get("headers", {}).get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return {
                "statusCode": 401,
                "body": json.dumps({"error": "Missing or invalid Authorization header"})
            }

        token = auth_header[7:]  # 移除 "Bearer " 前缀

        # 验证 Token
        result = verify_token(token)
        if not result.get("valid"):
            return {
                "statusCode": 401,
                "body": json.dumps({"error": result.get("error", "Invalid token")})
            }

        return {
            "statusCode": 200,
            "body": json.dumps({
                "valid": True,
                "user_id": result.get("user_id"),
                "username": result.get("username")
            })
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }


def refresh_handler(event: Dict) -> Dict:
    """
    Token 刷新处理函数
    POST /auth/refresh
    Headers: Authorization: Bearer <token>
    """
    try:
        auth_header = event.get("headers", {}).get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return {
                "statusCode": 401,
                "body": json.dumps({"error": "Missing or invalid Authorization header"})
            }

        old_token = auth_header[7:]

        # 验证旧 Token
        result = verify_token(old_token)
        if not result.get("valid"):
            return {
                "statusCode": 401,
                "body": json.dumps({"error": result.get("error", "Invalid token")})
            }

        # 生成新 Token
        new_token = generate_token(
            result.get("user_id"),
            result.get("username")
        )

        return {
            "statusCode": 200,
            "body": json.dumps({
                "token": new_token,
                "token_type": "Bearer",
                "expires_in": TOKEN_EXPIRE_SECONDS
            })
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }


def handler(event: Dict, context: Dict) -> Dict:
    """
    FunctionGraph 入口函数
    根据请求路径分发到不同的处理函数
    """
    path = event.get("path", "")
    http_method = event.get("httpMethod", "GET")

    # 路由分发
    if path == "/auth/register" and http_method == "POST":
        return register_handler(event)
    elif path == "/auth/login" and http_method == "POST":
        return login_handler(event)
    elif path == "/auth/verify" and http_method == "GET":
        return verify_handler(event)
    elif path == "/auth/refresh" and http_method == "POST":
        return refresh_handler(event)
    else:
        return {
            "statusCode": 404,
            "body": json.dumps({"error": "Not found"})
        }


# 本地测试用
if __name__ == "__main__":
    # 初始化数据库
    print("初始化数据库...")
    init_db()

    # 测试注册
    test_event = {
        "path": "/auth/register",
        "httpMethod": "POST",
        "body": json.dumps({
            "username": "testuser",
            "password": "password123",
            "email": "test@example.com"
        })
    }
    print("Register test:", handler(test_event, {}))

    # 测试登录
    test_event = {
        "path": "/auth/login",
        "httpMethod": "POST",
        "body": json.dumps({
            "username": "testuser",
            "password": "password123"
        })
    }
    result = handler(test_event, {})
    print("Login test:", result)

    # 解析 token
    if result.get("statusCode") == 200:
        body = json.loads(result["body"])
        token = body.get("token")

        # 测试验证
        verify_event = {
            "path": "/auth/verify",
            "httpMethod": "GET",
            "headers": {"Authorization": f"Bearer {token}"}
        }
        print("Verify test:", handler(verify_event, {}))
