param(
    [Parameter(Mandatory=$true)][ValidateSet('Prepare','Import','Install')][string]$Mode
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Security
$m2Dir = Join-Path $env:LOCALAPPDATA 'MOSA2-CodexChat'
$m2Name = 'MOSA2-Codex-Text-Transport'
$m2Identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$m2Sid = $m2Identity.User
$m2New = !(Test-Path -LiteralPath $m2Dir)
if ($m2New) {
    New-Item -ItemType Directory -Path $m2Dir | Out-Null
}
if ((Get-Item -LiteralPath $m2Dir).Attributes -band [IO.FileAttributes]::ReparsePoint) {
    throw 'The Codex transport directory must not be a reparse point.'
}
if ($m2New) {
    $m2Acl = New-Object Security.AccessControl.DirectorySecurity
    $m2Acl.SetOwner($m2Sid)
    $m2Acl.SetAccessRuleProtection($true, $false)
    $m2Rule = New-Object Security.AccessControl.FileSystemAccessRule(
        $m2Sid, 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow')
    $m2Acl.AddAccessRule($m2Rule)
    Set-Acl -LiteralPath $m2Dir -AclObject $m2Acl
} else {
    $m2Acl = Get-Acl -LiteralPath $m2Dir
    $m2Rules = @($m2Acl.GetAccessRules($true, $true, [Security.Principal.SecurityIdentifier]))
    if (!$m2Acl.AreAccessRulesProtected -or $m2Acl.GetOwner([Security.Principal.SecurityIdentifier]) -ne $m2Sid -or
        !$m2Rules.Count -or @($m2Rules | Where-Object IdentityReference -ne $m2Sid).Count) {
        throw 'The Codex transport directory must have a private ACL.'
    }
}
$m2KeyFile = Join-Path $m2Dir 'setup-key.dpapi'
$m2SecretFile = Join-Path $m2Dir 'worker.dpapi'
$m2Scope = [Security.Cryptography.DataProtectionScope]::CurrentUser
if ($Mode -eq 'Prepare') {
    if ((Test-Path -LiteralPath $m2KeyFile) -or (Test-Path -LiteralPath $m2SecretFile)) { throw 'Transport setup already exists.' }
    $m2Rsa = New-Object Security.Cryptography.RSACryptoServiceProvider(3072)
    $m2Rsa.PersistKeyInCsp = $false
    try {
        $m2Private = [Text.Encoding]::UTF8.GetBytes($m2Rsa.ToXmlString($true))
        [IO.File]::WriteAllBytes($m2KeyFile, [Security.Cryptography.ProtectedData]::Protect($m2Private, $null, $m2Scope))
        $m2Public = $m2Rsa.ExportParameters($false)
        @{n=[Convert]::ToBase64String($m2Public.Modulus); e=[Convert]::ToBase64String($m2Public.Exponent)} | ConvertTo-Json -Compress
    } finally { $m2Rsa.Dispose() }
} elseif ($Mode -eq 'Import') {
    if (Test-Path -LiteralPath $m2SecretFile) { throw 'Refusing to replace existing transport credentials.' }
    $m2Ciphertext = [Convert]::FromBase64String([Console]::ReadLine())
    $m2Rsa = New-Object Security.Cryptography.RSACryptoServiceProvider
    $m2Rsa.PersistKeyInCsp = $false
    try {
        $m2Private = [Security.Cryptography.ProtectedData]::Unprotect([IO.File]::ReadAllBytes($m2KeyFile), $null, $m2Scope)
        $m2Rsa.FromXmlString([Text.Encoding]::UTF8.GetString($m2Private))
        $m2Plain = $m2Rsa.Decrypt($m2Ciphertext, $true)
        $m2Config = [Text.Encoding]::UTF8.GetString($m2Plain) | ConvertFrom-Json
        if ($m2Config.token -cnotmatch '^[0-9a-f]{64}$' -or $m2Config.password -cnotmatch '^[!-~]{32,100}$') {
            throw 'Invalid encrypted worker credentials.'
        }
        [IO.File]::WriteAllBytes($m2SecretFile, [Security.Cryptography.ProtectedData]::Protect($m2Plain, $null, $m2Scope))
        Remove-Item -LiteralPath $m2KeyFile
        Write-Output 'DPAPI worker credentials saved.'
    } finally { $m2Rsa.Dispose() }
} else {
    if (!(Test-Path -LiteralPath $m2SecretFile)) { throw 'No private worker credentials.' }
    $m2Python = (Get-Command python.exe -CommandType Application).Source
    $m2Cli = (Get-Command codex.exe -CommandType Application).Source
    $m2Worker = Join-Path $m2Dir 'codex_chat_worker.py'
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'codex_chat_worker.py') -Destination $m2Worker
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'nova_chat_worker.py') -Destination $m2Dir
    [IO.File]::WriteAllText((Join-Path $m2Dir 'cli.txt'), $m2Cli)
    & $m2Python -E $m2Worker --verify-scope
    if ($LASTEXITCODE -ne 0) { throw 'The scoped worker access could not be verified.' }
    $m2Pythonw = Join-Path (Split-Path -Parent $m2Python) 'pythonw.exe'
    $m2Action = New-ScheduledTaskAction -Execute $m2Pythonw -Argument ('-E "' + $m2Worker + '"') -WorkingDirectory $m2Dir
    $m2Trigger = New-ScheduledTaskTrigger -AtLogOn -User $m2Identity.Name
    $m2Principal = New-ScheduledTaskPrincipal -UserId $m2Identity.Name -LogonType Interactive -RunLevel Limited
    $m2Settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) -Hidden -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
    Register-ScheduledTask -TaskName $m2Name -Action $m2Action -Trigger $m2Trigger -Principal $m2Principal -Settings $m2Settings -ErrorAction Stop | Out-Null
    Start-ScheduledTask -TaskName $m2Name
    Get-ScheduledTask -TaskName $m2Name | Select-Object TaskName,State
}

