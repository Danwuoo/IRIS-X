$ErrorActionPreference = 'Continue'
Set-Content -Path 'C:\Users\wurre\Desktop\Vanta\docs\04_experiments\results\post_stage_1_larger_sample\20260528_163424\_logs\heartbeat.txt' -Value "started $(Get-Date -Format o)"
try {
  mix vanta.post_stage_1_larger_sample --out 'C:\Users\wurre\Desktop\Vanta\docs\04_experiments\results\post_stage_1_larger_sample\20260528_163424' > 'C:\Users\wurre\Desktop\Vanta\docs\04_experiments\results\post_stage_1_larger_sample\20260528_163424\_logs\stdout.log' 2> 'C:\Users\wurre\Desktop\Vanta\docs\04_experiments\results\post_stage_1_larger_sample\20260528_163424\_logs\stderr.log'
  $code = $LASTEXITCODE
  Set-Content -Path 'C:\Users\wurre\Desktop\Vanta\docs\04_experiments\results\post_stage_1_larger_sample\20260528_163424\_logs\exit_code.txt' -Value $code
  Add-Content -Path 'C:\Users\wurre\Desktop\Vanta\docs\04_experiments\results\post_stage_1_larger_sample\20260528_163424\_logs\heartbeat.txt' -Value "finished $(Get-Date -Format o) code=$code"
  exit $code
} catch {
  Add-Content -Path 'C:\Users\wurre\Desktop\Vanta\docs\04_experiments\results\post_stage_1_larger_sample\20260528_163424\_logs\stderr.log' -Value $_.Exception.ToString()
  Set-Content -Path 'C:\Users\wurre\Desktop\Vanta\docs\04_experiments\results\post_stage_1_larger_sample\20260528_163424\_logs\exit_code.txt' -Value 999
  Add-Content -Path 'C:\Users\wurre\Desktop\Vanta\docs\04_experiments\results\post_stage_1_larger_sample\20260528_163424\_logs\heartbeat.txt' -Value "exception $(Get-Date -Format o)"
  exit 999
}
