"""Local Windows OCR transport. Images/text travel through pipes, never files."""

from __future__ import annotations

import base64
import json
import math
import os
from pathlib import Path
from statistics import median
import sys


MAX_OCR_DIMENSION = 2400
OCR_TIMEOUT_MS = 30_000

# Only this static script goes in the process command line. Document pixels are
# JSON on stdin; neither recognized text nor provider exceptions are logged.
_WINDOWS_OCR_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Console]::InputEncoding = [Text.Encoding]::UTF8
[Console]::OutputEncoding = New-Object Text.UTF8Encoding($false)
$bitmap = $null
try {
    Add-Type -AssemblyName System.Runtime.WindowsRuntime
    [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType=WindowsRuntime] | Out-Null
    [Windows.Graphics.Imaging.SoftwareBitmap, Windows.Foundation, ContentType=WindowsRuntime] | Out-Null
    [Windows.Graphics.Imaging.BitmapPixelFormat, Windows.Foundation, ContentType=WindowsRuntime] | Out-Null
    [Windows.Graphics.Imaging.BitmapAlphaMode, Windows.Foundation, ContentType=WindowsRuntime] | Out-Null
    [Windows.Globalization.Language, Windows.Globalization, ContentType=WindowsRuntime] | Out-Null
    [Windows.Media.Ocr.OcrResult, Windows.Foundation, ContentType=WindowsRuntime] | Out-Null
    $request = [Console]::In.ReadToEnd() | ConvertFrom-Json
    $width = [int]$request.width
    $height = [int]$request.height
    $maximum = [Math]::Min(2400, [Windows.Media.Ocr.OcrEngine]::MaxImageDimension)
    if ($width -lt 1 -or $height -lt 1 -or $width -gt $maximum -or $height -gt $maximum) {
        throw 'invalid_dimensions'
    }
    $language = New-Object Windows.Globalization.Language([string]$request.language)
    $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($language)
    if ($null -eq $engine) {
        [Console]::Out.Write('{"ok":false,"error":"language_unavailable"}')
        exit 2
    }
    $pixels = [Convert]::FromBase64String([string]$request.pixels)
    if ($pixels.Length -ne ($width * $height * 4)) { throw 'invalid_pixels' }
    $buffer = [System.Runtime.InteropServices.WindowsRuntime.WindowsRuntimeBufferExtensions]::AsBuffer($pixels)
    $bitmap = [Windows.Graphics.Imaging.SoftwareBitmap]::CreateCopyFromBuffer(
        $buffer, [Windows.Graphics.Imaging.BitmapPixelFormat]::Bgra8,
        $width, $height, [Windows.Graphics.Imaging.BitmapAlphaMode]::Ignore)
    $asTask = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
        $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and
        $_.GetGenericArguments().Length -eq 1 -and $_.GetParameters().Length -eq 1 -and
        $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
    } | Select-Object -First 1
    $task = $asTask.MakeGenericMethod([Windows.Media.Ocr.OcrResult]).Invoke(
        $null, @($engine.RecognizeAsync($bitmap)))
    $task.Wait()
    $text = ($task.Result.Lines | ForEach-Object { $_.Text }) -join "`n"
    $words = @(foreach ($line in $task.Result.Lines) {
        foreach ($word in $line.Words) {
            $rect = $word.BoundingRect
            @{text=$word.Text; x=$rect.X; y=$rect.Y; width=$rect.Width; height=$rect.Height}
        }
    })
    [Console]::Out.Write((@{ok=$true; text=$text; words=$words} | ConvertTo-Json -Compress -Depth 4))
} catch {
    [Console]::Out.Write('{"ok":false,"error":"ocr_failed"}')
    exit 1
} finally {
    if ($null -ne $bitmap) { $bitmap.Dispose() }
}
"""


class ScanOcrError(ValueError):
    pass


def ocr_process_command() -> tuple[str, list[str]]:
    if sys.platform != "win32":
        raise ScanOcrError("Local OCR requires Windows 10 or later.")
    executable = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    if not executable.is_file():
        raise ScanOcrError("Windows PowerShell is unavailable. Local OCR could not start.")
    script = base64.b64encode(_WINDOWS_OCR_SCRIPT.encode("utf-16-le")).decode("ascii")
    return str(executable), ["-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-EncodedCommand", script]


def encode_ocr_request(pixels: bytes, width: int, height: int, language: str) -> bytes:
    if not (1 <= width <= MAX_OCR_DIMENSION and 1 <= height <= MAX_OCR_DIMENSION):
        raise ScanOcrError("Selected image is too large for local OCR.")
    if len(pixels) != width * height * 4 or language not in {"ko", "en-US"}:
        raise ScanOcrError("Selected image or OCR language is invalid.")
    return json.dumps({
        "width": width, "height": height, "language": language,
        "pixels": base64.b64encode(pixels).decode("ascii"),
    }, separators=(",", ":")).encode("utf-8")


def parse_ocr_response(output: bytes) -> str:
    try:
        result = json.loads(output.decode("utf-8-sig"))
    except (UnicodeError, ValueError):
        raise ScanOcrError("Local OCR returned an unreadable result. Try a smaller area.") from None
    if not isinstance(result, dict) or result.get("ok") is not True:
        if isinstance(result, dict) and result.get("error") == "language_unavailable":
            raise ScanOcrError("OCR language is not installed. Add it in Windows language settings or choose another language.")
        raise ScanOcrError("Local OCR failed. Try a smaller area or another language.")
    text = result.get("text")
    if not isinstance(text, str):
        raise ScanOcrError("Local OCR returned an invalid text result.")
    if result.get("words"):
        return _text_in_reading_rows(result["words"])
    return text.strip()


def _text_in_reading_rows(words: object) -> str:
    """Keep neighboring table columns on the same visual row; never repair values."""
    if not isinstance(words, list) or len(words) > 10000:
        raise ScanOcrError("Local OCR returned invalid word positions.")
    parsed = []
    for word in words:
        try:
            text = word["text"]
            x, y, width, height = (float(word[key]) for key in ("x", "y", "width", "height"))
            valid = all(math.isfinite(value) and abs(value) < 100000 for value in (x, y, width, height))
        except (KeyError, TypeError, ValueError):
            raise ScanOcrError("Local OCR returned invalid word positions.") from None
        if not isinstance(text, str) or not valid or width <= 0 or height <= 0:
            raise ScanOcrError("Local OCR returned invalid word positions.")
        if text.strip():
            parsed.append((y + height / 2, x, width, height, text.strip()))
    if not parsed:
        return ""
    tolerance = median(word[3] for word in parsed) * 0.55
    rows: list[list[tuple]] = []
    for word in sorted(parsed):
        if not rows or abs(word[0] - median(item[0] for item in rows[-1])) > tolerance:
            rows.append([])
        rows[-1].append(word)
    output = []
    for row in rows:
        previous = None
        parts = []
        for word in sorted(row, key=lambda item: item[1]):
            if previous is not None:
                gap = word[1] - (previous[1] + previous[2])
                parts.append("  " if gap > median((word[3], previous[3])) * 1.5 else " ")
            parts.append(word[4])
            previous = word
        output.append("".join(parts))
    return "\n".join(output)
