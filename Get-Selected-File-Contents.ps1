# Define the folder to search and the output file
$FolderPath  = "D:\GPT\ai-student-companion\v3"
$OutputFile  = "D:\GPT\ai-student-companion\SelectedFileContents.txt"

# Clear the output file if it already exists
if (Test-Path $OutputFile) {
    Clear-Content -Path $OutputFile
}

# List of target filenames (without path)
$TargetFiles = @("routes.py","websocket.py","rag.py","llm.py","faiss_store.py",
"cache.py","history.py","auth.py","translation.py","ingestion.py")   # <-- replace with your list

# Counters
$ProcessedCount = 0
$SkippedCount   = 0
$IncludedFiles  = @()

# Get all files recursively
Get-ChildItem -Path $FolderPath -Recurse -File | ForEach-Object {
    $FilePath = $_.FullName
    $FileName = $_.Name

    # Check if this file is in the target list
    if ($TargetFiles -contains $FileName) {
        Write-Host "Processing: $FilePath"
        $ProcessedCount++
        $IncludedFiles += $FilePath

        # Write header
        Add-Content -Path $OutputFile -Value "Contents of file : $FilePath"

        try {
            # Read and append file contents
            $Content = Get-Content -Path $FilePath -ErrorAction Stop
            Add-Content -Path $OutputFile -Value $Content
        } catch {
            Add-Content -Path $OutputFile -Value "Error reading file: $($_.Exception.Message)"
        }

        # Write footer
        Add-Content -Path $OutputFile -Value "Contents of file ended"
        Add-Content -Path $OutputFile -Value "`n"
    } else {
        $SkippedCount++
    }
}

# Print summary
Write-Host "`nSummary:"
Write-Host "Processed files: $ProcessedCount"
Write-Host "Skipped files: $SkippedCount"

# Print included files
Write-Host "`nIncluded Files:"
$IncludedFiles | Sort-Object | ForEach-Object { Write-Host $_ }