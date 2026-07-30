[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ImagePath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

Add-Type -AssemblyName System.Runtime.WindowsRuntime

function Wait-WindowsRuntimeOperation {
    param(
        [Parameter(Mandatory = $true)]
        $Operation,
        [Parameter(Mandatory = $true)]
        [Type]$ResultType
    )

    $method = ([System.WindowsRuntimeSystemExtensions].GetMethods() |
        Where-Object {
            $_.Name -eq "AsTask" -and
            $_.IsGenericMethod -and
            $_.GetParameters().Count -eq 1
        } |
        Select-Object -First 1).MakeGenericMethod($ResultType)
    $task = $method.Invoke($null, @($Operation))
    $task.Wait()
    return $task.Result
}

$resolved = [System.IO.Path]::GetFullPath($ImagePath)
$storageFileType = [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime]
$randomAccessStreamType = [Windows.Storage.Streams.IRandomAccessStream, Windows.Storage.Streams, ContentType = WindowsRuntime]
$bitmapDecoderType = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType = WindowsRuntime]
$softwareBitmapType = [Windows.Graphics.Imaging.SoftwareBitmap, Windows.Graphics.Imaging, ContentType = WindowsRuntime]
$ocrEngineType = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
$ocrResultType = [Windows.Media.Ocr.OcrResult, Windows.Foundation, ContentType = WindowsRuntime]

$file = Wait-WindowsRuntimeOperation ($storageFileType::GetFileFromPathAsync($resolved)) $storageFileType
$stream = Wait-WindowsRuntimeOperation ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) $randomAccessStreamType
try {
    $decoder = Wait-WindowsRuntimeOperation ($bitmapDecoderType::CreateAsync($stream)) $bitmapDecoderType
    $bitmap = Wait-WindowsRuntimeOperation ($decoder.GetSoftwareBitmapAsync()) $softwareBitmapType
    $engine = $ocrEngineType::TryCreateFromUserProfileLanguages()
    if ($null -eq $engine) {
        throw "Windows OCR has no recognizer for the current user languages."
    }
    $result = Wait-WindowsRuntimeOperation ($engine.RecognizeAsync($bitmap)) $ocrResultType
    [pscustomobject]@{
        text = $result.Text
        lines = @($result.Lines | ForEach-Object { $_.Text })
    } | ConvertTo-Json -Compress -Depth 3
}
finally {
    $stream.Dispose()
}
