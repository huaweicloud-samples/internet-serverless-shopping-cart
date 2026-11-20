# 上传文件到 OBS
$AK = "YOUR_ACCESS_KEY"
$SK = "YOUR_SECRET_KEY"
$Region = "cn-north-4"
$Bucket = "shopping-cart-20260820-demo-assets"
$FilePath = "index.html"
$ObjectKey = "index.html"

# 读取文件内容
$Content = Get-Content -Path $FilePath -Raw -Encoding UTF8

# 生成日期
$Date = (Get-Date).ToUniversalTime().ToString("ddd, dd MMM yyyy HH:mm:ss GMT")
$Host = "$Bucket.obs.$Region.myhuaweicloud.com"
$Url = "https://$Host/$ObjectKey"

# 计算签名
$StringToSign = "PUT`n`ntext/html`n$Date`n/$Bucket/$ObjectKey"
$Signature = [Convert]::ToBase64String((New-Object System.Security.Cryptography.HMACSHA1).ComputeHash([System.Text.Encoding]::UTF8.GetBytes($SK + $StringToSign)))

# 发送请求
$Headers = @{
    "Content-Type" = "text/html"
    "Date" = $Date
    "Host" = $Host
    "Authorization" = "OBS $AK`:$Signature"
}

Write-Host "上传文件到 OBS..."
Write-Host "Bucket: $Bucket"
Write-Host "URL: $Url"

try {
    $Response = Invoke-RestMethod -Uri $Url -Method Put -Body $Content -Headers $Headers -ContentType "text/html" -TimeoutSec 30
    Write-Host "✅ 上传成功!"
    Write-Host "访问地址: https://$Bucket.obs.$Region.myhuaweicloud.com/$ObjectKey"
} catch {
    Write-Host "❌ 上传失败: $_"
    Write-Host $_.Exception.Response
}
