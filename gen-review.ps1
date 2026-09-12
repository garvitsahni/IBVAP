param([string]$Base, [string]$Head, [string]$OutFile)
$log = git log --oneline "$Base..$Head"
$stat = git diff --stat $Base $Head
$diff = git diff -U10 $Base $Head
$sb = New-Object System.Text.StringBuilder
[void]$sb.AppendLine("# Review Package - Task 1")
[void]$sb.AppendLine("")
[void]$sb.AppendLine("## Commits")
[void]$sb.AppendLine($log)
[void]$sb.AppendLine("")
[void]$sb.AppendLine("## Stats")
[void]$sb.AppendLine($stat)
[void]$sb.AppendLine("")
[void]$sb.AppendLine("## Full Diff")
[void]$sb.AppendLine("```diff")
[void]$sb.AppendLine($diff)
[void]$sb.AppendLine("```")
$reviewContent = $sb.ToString()
$reviewContent | Out-File -FilePath $OutFile -Encoding utf8
Write-Output "wrote $OutFile"
