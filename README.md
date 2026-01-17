[Generic_Proxifier_Template.xml](https://github.com/user-attachments/files/24685793/Generic_Proxifier_Template.xml)# pySOCKS5-iOS
**Bypass carrier-induced hotspot throttling with a working, persistent SOCKS5 proxy on iOS 26.3 (iPhone 16)**

`pySOCKS5` turns an iPhone into a long-running SOCKS5 gateway suitable for hotspot tunneling and full system traffic routing on connected clients. Under the documented baseline configuration, it remains active for hours with the display asleep and no user interaction.

This repository documents a configuration that works *today*.

---

## Table of Contents

- [Guaranteed Working Configuration](#guaranteed-working-configuration)
- [What This Is](#what-this-is)
- [What This Is Not](#what-this-is-not)
- [Quick Start (iOS)](#quick-start-ios)
- [Network Configuration](#network-configuration)
- [Windows Client Setup](#windows-client-setup)
- [Monitoring & Health Checks](#monitoring--health-checks)
- [Performance Characteristics](#performance-characteristics)
- [Security Notes](#security-notes)
- [Known Limitations](#known-limitations)
- [License](#license)
- [Technical Deep Dive](#technical-deep-dive-how-this-works-on-ios-26x)

---

## Guaranteed Working Configuration

This project is **guaranteed to work** on the following setup, because it was designed, tested, and validated exclusively on it:

- **Device:** iPhone 16 (base model)
- **Carrier:** T-Mobile (US)
- **OS:** iOS 26.3 *(build 23D5103d)*
- **Runtime:** Pythonista 3
- **Interpreter:** Python 3.10 (Pythonista default)
- **Network Mode:** iOS Personal Hotspot

The closer your environment is to this baseline, the higher the likelihood of success.

No guarantees are made for:
- Other iPhone models
- Other carriers
- Other iOS builds
- Sideloaded Python runtimes
- Jailbroken environments

---

## What This Is

- A standards-compliant **SOCKS5 server**
- Runs entirely inside **Pythonista 3**
- Requires **no jailbreak**
- Requires **no sideloading**
- Requires **no private entitlements**
- Persists with the screen locked
- Designed specifically for hotspot tunneling
- Tuned for low latency and high throughput

This is not a proof-of-concept. It has been run continuously for hours on the baseline device.

---

## What This Is Not

- Not a VPN
- Not a kernel exploit
- Not power-efficient
- Not guaranteed to survive future iOS releases
- Not hardened for hostile or public exposure

---

## Quick Start (iOS)

1. Install **Pythonista 3** from the App Store  
2. Import `pySOCKS5.py`  
3. Run the script  
4. Lock the screen  
5. Leave it alone  

On first run, the script automatically:
- Generates a silent WAV file
- Starts the audio keep-alive loop
- Binds the SOCKS5 server
- Registers lock-screen media controls
- Begins logging

No further interaction is required.

---

## Network Configuration

### Defaults

- **SOCKS5 Port:** `9999`
- **Bind Address:** `0.0.0.0`
- **Hotspot Gateway:** `172.20.10.1`
- **Authentication:** None

Clients should connect to:


---

## Windows Client Setup

### Proxifier (Recommended)

Proxifier is the preferred Windows client because it allows:

- Forced DNS resolution through SOCKS
- Prevention of direct-connect fallback
- Full system traffic capture
- Deterministic routing under throttled hotspots

```
<?xml version="1.0" encoding="UTF-8"?>
<ProxifierProfile version="4.11">

  <!-- ===================================================== -->
  <!-- Proxy Definitions                                    -->
  <!-- ===================================================== -->
  <ProxyServers>
    <ProxyServer id="1">
      <Address>172.20.10.1</Address>
      <Port>9999</Port>
      <Protocol>SOCKS5</Protocol>

      <!-- Authentication intentionally disabled -->
      <Authentication enabled="false" />

      <!-- Critical for throttled hotspots -->
      <ResolveThroughProxy enabled="true" />

      <Description>
        iPhone SOCKS5 Proxy (Pythonista / iOS Hotspot)
      </Description>
    </ProxyServer>
  </ProxyServers>

  <!-- ===================================================== -->
  <!-- Global Options                                       -->
  <!-- ===================================================== -->
  <Options>

    <!-- Force DNS through SOCKS to avoid throttling/leaks -->
    <NameResolution>
      <ResolveHostnamesThroughProxy enabled="true" />
    </NameResolution>

    <!-- Prevent Windows fallback to direct connections -->
    <LeakPreventionMode enabled="true" />

    <!-- Conservative timeouts for cellular backhaul -->
    <ConnectionTimeout>10</ConnectionTimeout>
    <HandshakeTimeout>10</HandshakeTimeout>

    <!-- UDP kept disabled by default for stability -->
    <UdpSupport enabled="false" />

  </Options>

  <!-- ===================================================== -->
  <!-- Proxification Rules                                  -->
  <!-- ===================================================== -->
  <Rules>

    <!-- ------------------------------------------------- -->
    <!-- Direct Access: iPhone Hotspot Gateway             -->
    <!-- Prevents routing loops                            -->
    <!-- ------------------------------------------------- -->
    <Rule enabled="true">
      <Name>DIRECT - iOS Hotspot Gateway</Name>
      <Applications>Any</Applications>
      <Targets>
        <Target type="IP">172.20.10.1</Target>
      </Targets>
      <Action type="Direct" />
    </Rule>

    <!-- ------------------------------------------------- -->
    <!-- Proxy: DNS Traffic                                -->
    <!-- Explicit rule for clarity/debugging               -->
    <!-- ------------------------------------------------- -->
    <Rule enabled="true">
      <Name>PROXY - DNS via SOCKS</Name>
      <Applications>Any</Applications>
      <Targets>
        <Target type="Port">53</Target>
      </Targets>
      <Action type="Proxy">
        <ProxyRef id="1" />
      </Action>
    </Rule>

    <!-- ------------------------------------------------- -->
    <!-- Proxy: System Services (Truncated)                -->
    <!-- Real profile contained more entries               -->
    <!-- ------------------------------------------------- -->
    <Rule enabled="true">
      <Name>PROXY - System Services</Name>
      <Applications>
        <Application>svchost.exe</Application>
        <Application>System</Application>
        <Application>lsass.exe</Application>
        <!-- additional services omitted -->
      </Applications>
      <Targets>
        <Target type="Hostname">*.microsoft.com</Target>
        <Target type="Hostname">*.windowsupdate.com</Target>
        <Target type="Hostname">*.msftconnecttest.com</Target>
        <!-- additional domains omitted -->
      </Targets>
      <Action type="Proxy">
        <ProxyRef id="1" />
      </Action>
    </Rule>

    <!-- ------------------------------------------------- -->
    <!-- Proxy: Common Applications (Truncated)            -->
    <!-- ------------------------------------------------- -->
    <Rule enabled="true">
      <Name>PROXY - User Applications</Name>
      <Applications>
        <Application>chrome.exe</Application>
        <Application>firefox.exe</Application>
        <Application>edge.exe</Application>
        <Application>steam.exe</Application>
        <!-- list intentionally truncated -->
      </Applications>
      <Targets>Any</Targets>
      <Action type="Proxy">
        <ProxyRef id="1" />
      </Action>
    </Rule>

    <!-- ------------------------------------------------- -->
    <!-- Default Rule: Tunnel Everything                   -->
    <!-- Required once hotspot throttling applies          -->
    <!-- ------------------------------------------------- -->
    <Rule enabled="true">
      <Name>PROXY - Default (Tunnel All)</Name>
      <Applications>Any</Applications>
      <Targets>Any</Targets>
      <Action type="Proxy">
        <ProxyRef id="1" />
      </Action>
    </Rule>

  </Rules>

</ProxifierProfile>
```


This configuration is designed for situations where:
- Hotspot data caps are exceeded
- Direct connections are throttled or deprioritized
- Split tunneling causes inconsistent performance

### Alternatives

- **SStap** (functional, less granular)
- Any SOCKS5-capable application or wrapper

---

## Monitoring & Health Checks

An optional PowerShell script (`iOS_Host_Heartbeat.ps1`) can be used on Windows to monitor:

- Reachability of the iPhone hotspot gateway
- Availability of the SOCKS5 proxy port

This allows quick differentiation between:
- Hotspot drop
- Proxy crash
- iOS suspension event

No administrator privileges are required.

---

## Performance Characteristics

- TCP_NODELAY enabled (low latency)
- Enlarged socket buffers (1 MB)
- Async I/O via `asyncio`
- IPv4, domain, and optional IPv6 support

Battery drain is expected and significant. This is the tradeoff for persistence.

---

## Security Notes

This proxy is **open by default**.

Do not expose it beyond your hotspot unless you fully understand the implications.  
No authentication, access control, or traffic filtering is provided.

You are responsible for:
- Network exposure
- Traffic routing
- Legal compliance

---

## Known Limitations

- Audio interruptions break persistence
- iOS updates may invalidate this approach entirely
- No UDP ASSOCIATE support
- No authentication
- No hardening for untrusted networks

---

## License

MIT License.

Use it, modify it, break it, ship it.

---

# Technical Deep Dive: How This Works on iOS 26.x

> **Recommended file split:**  
> Move everything below this heading into `DEEP_DIVE.md`

---

## The Core Problem: iOS Suspends Background Code

iOS aggressively suspends background execution:

- Interpreters are deprioritized
- Network daemons are considered abusive
- Idle background tasks are frozen within seconds

A normal Python SOCKS server will:
- Start successfully
- Lose the screen
- Be suspended by the kernel
- Drop all sockets

This behavior is expected.

---

## The Key Insight: Media Playback Is Privileged

iOS still grants elevated execution priority to apps that:

- Actively play audio
- Expose lock-screen media controls
- Maintain Now Playing metadata

These apps are expected to function with the screen off and remain responsive.

This execution class has remained reliable across many iOS releases, including 26.x.

---

## Why Pythonista Is Critical

Pythonista exposes enough of the Objective-C runtime to:

- Create and activate `AVAudioSession`
- Instantiate `AVAudioPlayer`
- Register `MPRemoteCommandCenter` handlers
- Publish `MPNowPlayingInfoCenter` metadata

At that point, iOS no longer treats the process as “a Python script”.

It treats it as an active media application.

---

## Persistence Architecture

pySOCKS5 relies on three coordinated subsystems:

 <img width="1536" height="1024" alt="pySOCKS5_Architecture" src="https://github.com/user-attachments/assets/f3d8bf91-af28-4cfd-8306-a583aeaff1cb" />

1. **Audio Keep-Alive**
2. **Lock-Screen Media Integration**
3. **Async SOCKS5 Network Server**

All three are required for
long-term stability.

---

## Audio Keep-Alive

- A silent WAV file is generated locally
- Playback loops indefinitely
- Volume is set near zero (but not zero)
- Audio buffers remain active

Paused or muted playback is insufficient; continuous audio buffers are required.

---

## Lock-Screen Media Integration

Audio alone is often insufficient on newer iOS builds.

The script also:
- Registers command handlers with `MPRemoteCommandCenter`
- Enables lock-screen controls
- Publishes Now Playing metadata

This reinforces classification as interactive media and reduces suspension pressure.

---

## Async SOCKS5 Server

Once persistence is established, the proxy itself is conventional:

- Fully async (`asyncio`)
- Per-socket tuning
- Optional IPv6 support
- Large buffers for throughput
- Clean restart logic

The novelty lies in the execution environment, not the proxy.

---

## Why This Works on iOS 26.3

Validated on:
- iPhone 16 (base model)
- T-Mobile (US)
- iOS 26.3 (23D5103d)
- Pythonista 3 / Python 3.10

At this version:
- Media playback still grants execution priority
- Lock-screen registration remains effective
- Audio sessions are not aggressively reaped
- Pythonista’s Objective-C bridge remains intact

No claims are made beyond this configuration.

---

## Why Hotspot Tunneling Fits This Model

Personal Hotspot provides:
- Predictable gateway (`172.20.10.1`)
- NAT isolation
- Clean routing boundaries
- No inbound exposure

When hotspot throttling occurs:
- Direct traffic is penalized
- Forcing all traffic through one persistent tunnel performs better
- Split routing becomes harmful

---

## Failure Modes

This approach can fail if:
- Audio playback is interrupted
- Another app seizes audio focus
- Apple revokes media execution privileges
- Pythonista removes Objective-C access
- Silent playback is reclassified as abuse

These are policy risks, not bugs.

---

## Why This Is Not an Exploit

This approach:
- Uses documented APIs
- Respects sandbox boundaries
- Does not elevate privileges
- Does not patch memory
- Does not escape entitlements

It relies on policy composition, not vulnerability.

Apple can close this window at any time.

---

## Final Perspective

This repository documents a narrow window where:
- iOS still trusts media playback
- Pythonista still exposes native APIs
- Hotspot routing behaves predictably

None of that is guaranteed forever.

Use it while it exists.
