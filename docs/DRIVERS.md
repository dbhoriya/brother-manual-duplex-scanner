# Scanner and driver setup

## Understand the pieces

- **SANE backend/driver:** communicates with the scanner. Install it through your distribution or manufacturer.
- **Device ID:** identifies the scanner to SANE.
- **App profile:** supplies source, mode and resolution settings. It does not install or replace a driver.

## Brother printers

1. Identify the exact model; printer support does not imply scanner support.
2. Install its Linux scanner driver from [Brother support](https://support.brother.com/g/b/productsearch.aspx?c=us&lang=en), following Brother's instructions.
3. Connect the scanner and confirm it appears in `scanimage -L`.
4. In the app, open **Scanner**, choose the device and **Brother brscan**.
5. Read driver options and check the glass/feeder and color-mode selections.

The initial tested device is the Brother MFC-L2700DW with `brscan4`. Other Brother models may use different drivers and option names.

## Other SANE / AirScan scanners

Use **Standard SANE / AirScan**, then read the actual driver options. `Flatbed`, `ADF`, `Gray`, and `Color` are starting values, not universal names. Select the values your backend reports.

For compatible eSCL/WSD devices, see the [sane-airscan project](https://github.com/alexpevzner/sane-airscan). AirScan compatibility is device-specific and is not a claim that the MFC-L2700DW supports it.

## Manual device ID / custom backend

Paste an exact SANE ID in Scanner setup and choose **Custom backend**. Enter source and mode names, or read them from the driver. A manual ID cannot make an uninstalled backend work.

Supported DPI may be a comma-separated list. The app chooses the value closest to the requested preset. Leave it empty for a driver that accepts the requested resolution directly.

## Diagnostics

```bash
scanimage -L
scanimage -d 'YOUR_DEVICE_ID' --all-options
```

The second command reads options; it does not acquire an image. See the [official scanimage manual](https://www.sane-project.org/man/scanimage.1.html).

If discovery fails:

- Check power, cable/network, and the installed backend.
- Ensure another application is not occupying the scanner.
- Check device permissions using your distribution's scanner setup instructions.
- If `scanimage` is absent, install `sane-utils`.
- Review the setup dialog's diagnostic output; redact identifiers before posting it.

The app never runs privileged driver installers or downloads drivers automatically.


## Slowdown during a long batch

Use 100 DPI grayscale for the smallest acquisition workload. PDF compression only affects export; it cannot speed up the feeder motor. The app appends live thumbnails, limits its thumbnail cache, and batches project saves per collection cycle.

Each finished pass writes `scanner.log` and `timing.csv` alongside its raw pages. Timing is based on completed file modification times, excluding the first page; it includes scanning and transfer time, so it cannot alone identify a mechanical fault. Compare early and late intervals. If files arrive quickly but previews lag, investigate computer load. If file arrival and paper feeding both slow, investigate the scanner, connection and driver.

Brother documents a heat-related motor-save mode for [some ADS scanners](https://support.brother.com/g/b/faqend.aspx?c=sg&faqid=faq00003149_000&lang=en&prod=ads1100w_eu_as_cn). This does **not** establish that the MFC-L2700DW uses the same behavior. Let the machine rest and compare a subsequent pass; do not disable thermal protection.

For device I/O errors or a driver crash, stop the scan, retain completed pages, and reconnect/restart the scanner before continuing. USB device IDs can change after reconnecting: use **Scanner** to detect it again. Check `journalctl -k` locally for USB errors or `libsane-brother` crashes. Do not publish raw logs without removing serial numbers and personal paths. Check your model's [official Brother downloads](https://support.brother.com/) before changing drivers. The app cannot repair proprietary driver code or guarantee a hardware slowdown fix.
