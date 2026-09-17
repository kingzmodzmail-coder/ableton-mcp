$ErrorActionPreference = 'Stop'
# Set default audio device via PolicyConfig (works on Win10/11)
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
namespace Audio {
  [Guid("f8679f50-850a-41cf-9c72-430f290290c8"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
  interface IPolicyConfig {
    void Unused1(); void Unused2(); void Unused3(); void Unused4(); void Unused5(); void Unused6(); void Unused7(); void Unused8(); void Unused9(); void Unused10();
    [PreserveSig] int SetDefaultEndpoint([MarshalAs(UnmanagedType.LPWStr)] string deviceId, int role);
  }
  [ComImport, Guid("870af99c-171d-4f9e-af0d-e63df40c2bc9")]
  class PolicyConfigClient {}
  public static class Default {
    public static int Set(string id) {
      var p = (new PolicyConfigClient() as IPolicyConfig);
      int r0 = p.SetDefaultEndpoint(id, 0); // console
      int r1 = p.SetDefaultEndpoint(id, 1); // multimedia
      int r2 = p.SetDefaultEndpoint(id, 2); // communications
      return r0 | r1 | r2;
    }
  }
}
"@
$id = "{ece442eb-9611-4ef9-846e-5192a416cf98}"
$code = [Audio.Default]::Set($id)
Write-Host "SetDefaultEndpoint result=$code for Realtek HD Audio 2nd output $id"
# Verify active defaults from registry DeviceState=1
Get-ChildItem "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio\Render" | ForEach-Object {
  $p = Join-Path $_.PSPath "Properties"
  try {
    $name = (Get-ItemProperty $p)."{a45c254e-df1c-4efd-8020-67d146a850e0},2"
    $state = (Get-ItemProperty $_.PSPath).DeviceState
    if ($state -eq 1) { Write-Host "ACTIVE: $name $($_.PSChildName)" }
  } catch {}
}
