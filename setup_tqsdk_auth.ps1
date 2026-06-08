$ErrorActionPreference = "Stop"
$OutputEncoding = [Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "配置 TqSdk / 快期行情账户"
Write-Host "账号和密码只会保存到当前项目目录的 tqsdk_auth.json。"
Write-Host ""

$user = Read-Host "请输入快期/TqSdk 账号"
if ([string]::IsNullOrWhiteSpace($user)) {
    Write-Host "未输入账号，已取消。"
    exit 1
}

$securePassword = Read-Host "请输入密码（输入时不显示）" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
try {
    $password = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
}

if ([string]::IsNullOrWhiteSpace($password)) {
    Write-Host "未输入密码，已取消。"
    exit 1
}

$payload = [ordered]@{
    user = $user.Trim()
    password = $password
    created_at = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
}

$path = Join-Path $PSScriptRoot "tqsdk_auth.json"
$payload | ConvertTo-Json | Set-Content -LiteralPath $path -Encoding UTF8

Write-Host ""
Write-Host "已保存到: $path"
Write-Host "请重新启动 run_fu2609_dashboard.cmd，或让我帮你重启当前服务。"
