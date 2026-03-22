# Define the folder to search and the output file
$FolderPath = "D:\GPT\ai-student-companion\v3"
$OutputFile = "D:\GPT\ai-student-companion\AllFileContents.txt"


# Clear the output file if it already exists
if (Test-Path $OutputFile) {
    Clear-Content -Path $OutputFile
}

# Define folders and files to exclude (whole subtrees)
$ExcludedFolders = @("node_modules", "models", "data", "__pycache__", ".git", "knowledge_base")
$ExcludedFiles   = @(".gitignore")
$ExcludedExtensions = @(".svg", ".ico", ".png", ".jpg")

# Counters and tracking
$ProcessedCount = 0
$SkippedCount   = 0
$ImageCount     = 0
$IncludedFiles  = @()

# Get all files recursively
Get-ChildItem -Path $FolderPath -Recurse -File | ForEach-Object {
    $FilePath = $_.FullName

    # Skip if path contains any excluded folder (anywhere in the path)
    $skipFolder = $false
    foreach ($folder in $ExcludedFolders) {
        if ($FilePath -like "*\$folder\*") {
            $skipFolder = $true
            break
        }
    }

    # Skip if filename is in excluded list
    $skipFile = $ExcludedFiles -contains $_.Name

    # Skip if extension is in excluded list
    $skipExtension = $ExcludedExtensions -contains $_.Extension.ToLower()

    if ($skipFolder -or $skipFile) {
        Write-Host "Skipping: $FilePath"
        $SkippedCount++
        return
    }

    if ($skipExtension) {
        Write-Host "Image file found (skipped content): $FilePath"
        Add-Content -Path $OutputFile -Value "===== $FilePath ====="
        Add-Content -Path $OutputFile -Value "[Image file skipped]"
        Add-Content -Path $OutputFile -Value "`n"
        $ImageCount++
        $IncludedFiles += $FilePath
        return
    }

    # Show progress in console
    Write-Host "Processing: $FilePath"
    $ProcessedCount++
    $IncludedFiles += $FilePath

    # Write file path header to output file
    Add-Content -Path $OutputFile -Value "===== $FilePath ====="

    try {
        # Read and append file contents
        $Content = Get-Content -Path $FilePath -ErrorAction Stop
        Add-Content -Path $OutputFile -Value $Content
    } catch {
        Add-Content -Path $OutputFile -Value "Error reading file: $($_.Exception.Message)"
    }

    # Add a blank line for readability
    Add-Content -Path $OutputFile -Value "`n"
}

# Print summary at the end
Write-Host "`nSummary:"
Write-Host "Processed files: $ProcessedCount"
Write-Host "Skipped folders/files: $SkippedCount"
Write-Host "Image files logged (content skipped): $ImageCount"

# Print folder structure of included files
Write-Host "`nIncluded Files (Folder Structure):"
$IncludedFiles | Sort-Object | ForEach-Object {
    Write-Host $_
}