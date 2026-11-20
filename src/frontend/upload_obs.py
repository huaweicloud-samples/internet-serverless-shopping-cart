# -*- coding: utf-8 -*-
"""
上传静态文件到 OBS
"""
import base64
import hashlib
import hmac
import time
from datetime import datetime
import requests

# 配置
AK = "YOUR_ACCESS_KEY"
SK = "YOUR_SECRET_KEY"
REGION = "cn-north-4"
BUCKET = "shopping-cart-20260820-demo-assets"
FILE_PATH = "index.html"
OBS_ENDPOINT = f"https://obs.{REGION}.myhuaweicloud.com"

def create_signature(method, bucket, object_key, headers, SK):
    """创建 OBS 签名"""
    # 简化签名计算
    string_to_sign = f"{method}\n\n\n{headers.get('date', '')}\n/{bucket}/{object_key}"
    signature = base64.b64encode(
        hmac.new(SK.encode(), string_to_sign.encode(), hashlib.sha1).digest()
    ).decode()
    return signature

def upload_file_to_obs(file_path, bucket, object_key):
    """上传文件到 OBS"""
    with open(file_path, 'rb') as f:
        content = f.read()

    # 生成日期
    date = datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')
    host = f"{bucket}.obs.{REGION}.myhuaweicloud.com"
    url = f"https://{host}/{object_key}"

    # 签名
    string_to_sign = f"PUT\n\ntext/html\n{date}\n/{bucket}/{object_key}"
    signature = base64.b64encode(
        hmac.new(SK.encode(), string_to_sign.encode(), hashlib.sha1).digest()
    ).decode()

    headers = {
        'Content-Type': 'text/html',
        'Date': date,
        'Host': host,
        'Authorization': f'OBS {AK}:{signature}'
    }

    response = requests.put(url, data=content, headers=headers)
    return response

if __name__ == "__main__":
    print(f"上传文件到 OBS...")
    print(f"Bucket: {BUCKET}")
    print(f"File: {FILE_PATH}")

    # 上传 index.html
    response = upload_file_to_obs(FILE_PATH, BUCKET, FILE_PATH)
    print(f"上传状态: {response.status_code}")

    if response.status_code in [200, 201]:
        print(f"✅ 上传成功!")
        print(f"访问地址: https://{BUCKET}.obs.{REGION}.myhuaweicloud.com/{FILE_PATH}")
    else:
        print(f"❌ 上传失败: {response.text}")
