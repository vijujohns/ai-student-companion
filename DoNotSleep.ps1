Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

public class SleepControl {
    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern uint SetThreadExecutionState(uint esFlags);
}
"@

# Define flags as unsigned values (use decimal for the high bit)
$ES_CONTINUOUS      = [uint32]2147483648
$ES_SYSTEM_REQUIRED = [uint32]1

# Prevent system sleep, allow display to turn off
[SleepControl]::SetThreadExecutionState($ES_CONTINUOUS -bor $ES_SYSTEM_REQUIRED)

Write-Host "✅ Preventing system from sleeping. Display may still turn off per power plan."
Write-Host "Press Enter to stop and restore normal sleep behavior."

try {
    # Wait for the user to press Enter; this will also wake the display when you press it
    [void](Read-Host)
}
finally {
    # Restore normal behavior when the script ends
    [SleepControl]::SetThreadExecutionState($ES_CONTINUOUS)
    Write-Host "System sleep behavior restored."
}