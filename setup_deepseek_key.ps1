$key = Read-Host "Paste your DeepSeek API key" -AsSecureString
$plain = [Runtime.InteropServices.Marshal]::PtrToStringUni(
    [Runtime.InteropServices.Marshal]::SecureStringToBSTR($key)
)

if ([string]::IsNullOrWhiteSpace($plain)) {
    Write-Host "No key entered. Nothing changed."
    exit 1
}

[Environment]::SetEnvironmentVariable("DEEPSEEK_API_KEY", $plain, "User")
$env:DEEPSEEK_API_KEY = $plain

Write-Host "DeepSeek API key saved to your Windows user environment."
Write-Host "Close and reopen PowerShell, then run: .\run_fu2609_check.cmd"
