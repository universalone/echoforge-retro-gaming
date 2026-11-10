# Game helper for EchoForge Retro Gaming (shared with EchoForge). Runs only while a game is open.
# Reads buttons: Xbox-style pads through XInput, PS4 and PS5 controllers straight from their HID reports (shared
# access, so the emulator still gets every button). It never talks to the network or changes settings.
# Prints:
#   "ready", "pads <n>"         started; number of controllers seen
#   "quit"                      Select + Start (Back + Start, Share/Create + Options) held for HoldMs
#   "menu"                      Select + Start tapped together (released before HoldMs): open the pause menu
#   "rect <pid> l t r b"        reply to "rect <pid>": where the game's window is on screen
#   "nav up|down|left|right|ok|back"   only while EchoForge's pause menu is open ("nav on")
# Reads commands from EchoForge, one per line:
#   "nav on" / "nav off"        menu navigation on or off
#   "suspend <pid>" / "resume <pid>"   pause or continue the game's process while the menu is open
#   "key <pid> <keys>"          bring the game's window forward and press keys there, e.g. "F2" or "Shift+F1"
#                               (quick save / load in emulators whose default keys EchoForge knows)
# Ends when EchoForge closes its input.
param([int]$HoldMs = 2000, [switch]$Trace)

Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Threading;
using Microsoft.Win32.SafeHandles;

public static class EfPadWatch {
  [StructLayout(LayoutKind.Sequential)] struct XState { public uint Packet; public ushort Buttons; public byte LT, RT; public short LX, LY, RX, RY; }
  [DllImport("xinput1_4.dll")] static extern uint XInputGetState(uint index, out XState state);
  [DllImport("xinput1_4.dll", EntryPoint = "#100")] static extern uint XInputGetStateEx(uint index, out XState state); // includes the Guide button

  [StructLayout(LayoutKind.Sequential)] struct HidAttr { public int Size; public ushort VendorID, ProductID, Version; }
  [StructLayout(LayoutKind.Sequential)] struct IfData { public int cbSize; public Guid Class; public int Flags; public IntPtr Reserved; }
  [DllImport("hid.dll")] static extern void HidD_GetHidGuid(out Guid g);
  [DllImport("hid.dll")] static extern bool HidD_GetAttributes(SafeFileHandle h, ref HidAttr a);
  [DllImport("setupapi.dll", CharSet = CharSet.Unicode)] static extern IntPtr SetupDiGetClassDevs(ref Guid g, IntPtr e, IntPtr w, int flags);
  [DllImport("setupapi.dll")] static extern bool SetupDiEnumDeviceInterfaces(IntPtr set, IntPtr info, ref Guid g, int i, ref IfData d);
  [DllImport("setupapi.dll", CharSet = CharSet.Unicode)] static extern bool SetupDiGetDeviceInterfaceDetail(IntPtr set, ref IfData d, IntPtr detail, int size, out int need, IntPtr info);
  [DllImport("setupapi.dll")] static extern bool SetupDiDestroyDeviceInfoList(IntPtr set);
  [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)] static extern SafeFileHandle CreateFile(string n, uint access, uint share, IntPtr sa, uint disp, uint flags, IntPtr t);

  [DllImport("kernel32.dll")] static extern IntPtr OpenProcess(uint access, bool inherit, int pid);
  [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr h);
  [DllImport("ntdll.dll")] static extern int NtSuspendProcess(IntPtr h);
  [DllImport("ntdll.dll")] static extern int NtResumeProcess(IntPtr h);

  delegate bool EnumProc(IntPtr hwnd, IntPtr l);
  [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc cb, IntPtr l);
  [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr hwnd, out int pid);
  [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr hwnd);
  [DllImport("user32.dll")] static extern IntPtr GetWindow(IntPtr hwnd, uint cmd);
  [DllImport("user32.dll")] static extern bool SetForegroundWindow(IntPtr hwnd);
  [DllImport("user32.dll")] static extern bool ShowWindow(IntPtr hwnd, int cmd);
  [DllImport("user32.dll")] static extern bool IsIconic(IntPtr hwnd);
  [StructLayout(LayoutKind.Sequential)] struct RECT { public int L, T, R, B; }
  [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr hwnd, out RECT r);
  [DllImport("user32.dll")] static extern void keybd_event(byte vk, byte scan, uint flags, UIntPtr extra);
  [DllImport("user32.dll")] static extern uint MapVirtualKey(uint code, uint type);

  // Button bits, the same for every controller.
  const int SELECT = 1, START = 2, HOME = 4, UP = 8, DOWN = 16, LEFT = 32, RIGHT = 64, OK = 128, BACK = 256;
  static readonly HashSet<string> open = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
  static readonly Dictionary<string, int> sony = new Dictionary<string, int>();
  static readonly object gate = new object();
  static volatile bool stop, nav, exOk = true;

  static void Say(string line) { lock (gate) { Console.WriteLine(line); Console.Out.Flush(); } }

  // Sony report layouts: index of the first button byte for each report type.
  static int Offset(byte id, bool dualsense, bool bt) {
    if (!dualsense) return id == 0x01 ? 5 : id == 0x11 ? 7 : -1;          // DualShock 4: USB / BT basic, BT full
    if (id == 0x31) return 9;                                               // DualSense BT full
    if (id == 0x01) return bt ? 5 : 8;                                      // DualSense BT basic / USB
    return -1;
  }
  // First byte: d-pad in the low 4 bits (0 up, 2 right, 4 down, 6 left, 8 none), Square 0x10, Cross 0x20, Circle 0x40.
  // Second: Share/Create 0x10, Options 0x20. Third: PS 0x01.
  static int SonyBits(byte[] b, int o) {
    int bits = 0, dp = b[o] & 0x0F;
    if (dp == 0 || dp == 1 || dp == 7) bits |= UP;
    if (dp == 3 || dp == 4 || dp == 5) bits |= DOWN;
    if (dp == 5 || dp == 6 || dp == 7) bits |= LEFT;
    if (dp == 1 || dp == 2 || dp == 3) bits |= RIGHT;
    if ((b[o] & 0x20) != 0) bits |= OK;
    if ((b[o] & 0x40) != 0) bits |= BACK;
    if ((b[o + 1] & 0x10) != 0) bits |= SELECT;
    if ((b[o + 1] & 0x20) != 0) bits |= START;
    if ((b[o + 2] & 0x01) != 0) bits |= HOME;
    return bits;
  }

  public static bool Trace;
  static void Read(string path, SafeFileHandle h, bool dualsense) {
    bool bt = path.IndexOf("00001124-", StringComparison.OrdinalIgnoreCase) >= 0;
    string lastSig = "";
    var buf = new byte[1024];
    try {
      using (var fs = new FileStream(h, FileAccess.Read, 1024, false)) {
        while (!stop) {
          int n = fs.Read(buf, 0, buf.Length);
          if (n <= 0) break;
          int o = Offset(buf[0], dualsense, bt);
          if (Trace) {
            string sig = buf[0].ToString("X2") + " o=" + o + " :" + (o >= 0 && o + 2 < n ? " " + buf[o].ToString("X2") + " " + buf[o + 1].ToString("X2") + " " + (buf[o + 2] & 3).ToString("X2") : "") + " n=" + n;
            if (sig != lastSig) { lastSig = sig; Say("trace " + sig); }
          }
          if (o < 0 || o + 2 >= n) continue;
          int bits = SonyBits(buf, o);
          lock (gate) sony[path] = bits;
        }
      }
    } catch { }
    lock (gate) { open.Remove(path); sony.Remove(path); }
  }

  static void FindSony() {
    Guid g; HidD_GetHidGuid(out g);
    IntPtr set = SetupDiGetClassDevs(ref g, IntPtr.Zero, IntPtr.Zero, 0x12); // present | device interface
    if (set == new IntPtr(-1)) return;
    try {
      for (int i = 0; ; i++) {
        var d = new IfData(); d.cbSize = Marshal.SizeOf(d);
        if (!SetupDiEnumDeviceInterfaces(set, IntPtr.Zero, ref g, i, ref d)) break;
        int need; SetupDiGetDeviceInterfaceDetail(set, ref d, IntPtr.Zero, 0, out need, IntPtr.Zero);
        IntPtr mem = Marshal.AllocHGlobal(need);
        string path;
        try {
          Marshal.WriteInt32(mem, IntPtr.Size == 8 ? 8 : 6);
          if (!SetupDiGetDeviceInterfaceDetail(set, ref d, mem, need, out need, IntPtr.Zero)) continue;
          path = Marshal.PtrToStringUni(new IntPtr(mem.ToInt64() + 4));
        } finally { Marshal.FreeHGlobal(mem); }
        if (path.IndexOf("054c", StringComparison.OrdinalIgnoreCase) < 0) continue;
        lock (gate) { if (open.Contains(path)) continue; }
        var h = CreateFile(path, 0x80000000, 3, IntPtr.Zero, 3, 0, IntPtr.Zero); // read, shared
        if (h.IsInvalid) continue;
        var a = new HidAttr(); a.Size = Marshal.SizeOf(a);
        if (!HidD_GetAttributes(h, ref a) || a.VendorID != 0x054C) { h.Dispose(); continue; }
        bool ds4 = a.ProductID == 0x05C4 || a.ProductID == 0x09CC || a.ProductID == 0x0BA0;
        bool dse = a.ProductID == 0x0CE6 || a.ProductID == 0x0DF2;
        if (!ds4 && !dse) { h.Dispose(); continue; }
        lock (gate) open.Add(path);
        string p = path; bool isDs = dse;
        var t = new Thread(() => Read(p, h, isDs)); t.IsBackground = true; t.Start();
      }
    } finally { SetupDiDestroyDeviceInfoList(set); }
  }

  static int XBits(ushort b) {
    int bits = 0;
    if ((b & 0x0020) != 0) bits |= SELECT; if ((b & 0x0010) != 0) bits |= START; if ((b & 0x0400) != 0) bits |= HOME;
    if ((b & 0x0001) != 0) bits |= UP; if ((b & 0x0002) != 0) bits |= DOWN; if ((b & 0x0004) != 0) bits |= LEFT; if ((b & 0x0008) != 0) bits |= RIGHT;
    if ((b & 0x1000) != 0) bits |= OK; if ((b & 0x2000) != 0) bits |= BACK;
    return bits;
  }

  // ---- commands from EchoForge ----
  static void Suspend(int pid, bool on) {
    IntPtr h = OpenProcess(0x0800, false, pid); // PROCESS_SUSPEND_RESUME
    if (h == IntPtr.Zero) { Say("error " + (on ? "suspend" : "resume")); return; }
    try { if (on) NtSuspendProcess(h); else NtResumeProcess(h); } finally { CloseHandle(h); }
    Say((on ? "suspended " : "resumed ") + pid);
  }
  static IntPtr MainWindow(int pid) {
    IntPtr found = IntPtr.Zero;
    EnumWindows((w, l) => { int p; GetWindowThreadProcessId(w, out p); if (p == pid && IsWindowVisible(w) && GetWindow(w, 4) == IntPtr.Zero) { found = w; return false; } return true; }, IntPtr.Zero);
    return found;
  }
  static void Front(int pid) {
    IntPtr w = MainWindow(pid); if (w == IntPtr.Zero) return;
    if (IsIconic(w)) ShowWindow(w, 9);
    keybd_event(0x12, 0, 0, UIntPtr.Zero); keybd_event(0x12, 0, 2, UIntPtr.Zero); // Windows lets a window come forward after a key press
    SetForegroundWindow(w);
  }
  static readonly Dictionary<string, byte> VK = new Dictionary<string, byte>(StringComparer.OrdinalIgnoreCase) {
    { "F1", 0x70 }, { "F2", 0x71 }, { "F3", 0x72 }, { "F4", 0x73 }, { "F5", 0x74 }, { "F6", 0x75 }, { "F7", 0x76 }, { "F8", 0x77 }, { "F9", 0x78 }, { "F10", 0x79 }, { "F11", 0x7A }, { "F12", 0x7B },
    { "Shift", 0x10 }, { "Ctrl", 0x11 }, { "Alt", 0x12 } };
  static void Keys(int pid, string spec) {
    var parts = spec.Split('+'); var down = new List<byte>();
    foreach (var p in parts) { byte v; if (!VK.TryGetValue(p.Trim(), out v)) { Say("error key"); return; } down.Add(v); }
    Front(pid); Thread.Sleep(250);
    foreach (var v in down) keybd_event(v, (byte)MapVirtualKey(v, 0), 0, UIntPtr.Zero);
    Thread.Sleep(80);
    for (int i = down.Count - 1; i >= 0; i--) keybd_event(down[i], (byte)MapVirtualKey(down[i], 0), 2, UIntPtr.Zero);
    Say("keys " + spec);
  }
  static void Command(string line) {
    var a = line.Trim().Split(new[] { ' ' }, 3); int pid = 0;
    if (a.Length >= 2 && a[0] == "nav") { nav = a[1] == "on"; return; }
    if (a.Length >= 2) int.TryParse(a[1], out pid);
    if (pid <= 0) return;
    if (a[0] == "suspend") Suspend(pid, true);
    else if (a[0] == "resume") Suspend(pid, false);
    else if (a[0] == "front") Front(pid);
    else if (a[0] == "rect") { IntPtr w = MainWindow(pid); RECT r; if (w != IntPtr.Zero && GetWindowRect(w, out r)) Say("rect " + pid + " " + r.L + " " + r.T + " " + r.R + " " + r.B); else Say("rect " + pid + " none"); }
    else if (a[0] == "key" && a.Length == 3) Keys(pid, a[2]);
  }

  public static void Run(int holdMs) {
    var input = new Thread(() => { try { string l; while ((l = Console.In.ReadLine()) != null) { try { Command(l); } catch { } } } catch { } stop = true; });
    input.IsBackground = true; input.Start();
    FindSony();
    int lastPads = -1, prev = 0; DateTime since = DateTime.MaxValue, nextScan = DateTime.Now.AddSeconds(5); bool fired = false;
    Say("ready");
    while (!stop) {
      int bits = 0, pads = 0;
      for (uint i = 0; i < 4; i++) {
        XState s; uint r;
        if (exOk) { try { r = XInputGetStateEx(i, out s); } catch { exOk = false; r = XInputGetState(i, out s); } } else r = XInputGetState(i, out s);
        if (r == 0) { pads++; bits |= XBits(s.Buttons); }
      }
      lock (gate) { pads += open.Count; foreach (var v in sony.Values) bits |= v; }
      if (pads != lastPads) { lastPads = pads; Say("pads " + pads); }
      int pressed = bits & ~prev; prev = bits;
      // Quit: Select + Start held.
      bool held = (bits & (SELECT | START)) == (SELECT | START);
      // Select + Start: a quick tap opens the menu, holding for holdMs quits. (PS / Guide aren't used: RPCS3 and the
      // Xbox Game Bar already open their own menus on them.)
      if (!held) {
        if (since != DateTime.MaxValue && !fired && !nav && (DateTime.Now - since).TotalMilliseconds >= 40) Say("menu");
        since = DateTime.MaxValue; fired = false;
      }
      else if (since == DateTime.MaxValue) since = DateTime.Now;
      else if (!fired && (DateTime.Now - since).TotalMilliseconds >= holdMs) { fired = true; Say("quit"); }
      if (nav) {
        if ((pressed & UP) != 0) Say("nav up"); if ((pressed & DOWN) != 0) Say("nav down");
        if ((pressed & LEFT) != 0) Say("nav left"); if ((pressed & RIGHT) != 0) Say("nav right");
        if ((pressed & OK) != 0) Say("nav ok"); if ((pressed & BACK) != 0) Say("nav back");
      }
      if (DateTime.Now >= nextScan) { nextScan = DateTime.Now.AddSeconds(5); try { FindSony(); } catch { } }
      Thread.Sleep(30);
    }
  }
}
'@

[EfPadWatch]::Trace = [bool]$Trace
[EfPadWatch]::Run($HoldMs)
