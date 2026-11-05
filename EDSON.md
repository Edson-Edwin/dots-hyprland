# Edson edition

This fork builds on end-4's Illogical Impulse shell and its Lua Hyprland configuration. The installer and upstream licenses are preserved. Fedora is the target for this edition.

## Install

Clone the fork with its pinned QML shapes library:

```sh
git clone --recurse-submodules https://github.com/Edson-Edwin/dots-hyprland.git
cd dots-hyprland
./setup install
```

If you already cloned, run `git submodule update --init --recursive` first. Review the interactive installer and keep its configuration backup if replacing an existing desktop. It syncs managed configuration directories. You don't need to reinstall to keep using an already customized desktop.

The Fedora dependency list includes PySide6 and requests for Voice & Chat, psutil for System Monitor, PipeWire utilities for recording, libsecret for key storage, and Plasma Workspace for KRunner. Outside Fedora, provide the equivalents for your distribution. The runner falls back to fuzzel when KRunner is unavailable.

## Use

| Shortcut | Action |
|---|---|
| Super+Alt+P | Fill the chosen external display when mirroring; press again to extend. |
| Super+B | Open System / Anime as a sliding left panel, even after detaching it. |
| Super+N | Open the right sidebar. Nearby Wi-Fi refreshes while the list is open. |
| Super+F6 | Choose a preset, restore the previous palette, or use wallpaper colors. |
| Ctrl+Super+T | Open the wallpaper picker. Thumbnail decoding is serialized, cached and cancellable. |
| Alt+Space | Open KRunner with KDE's own appearance. |
| Ctrl+Super+D | Start or stop dictation in the focused text field. |
| Ctrl+Super+A | Open the themed chat overlay. Enter sends; Shift+Enter adds a line. Use the pin to follow workspace changes. |

In **System**, view CPU, RAM, swap, disk and network graphs, processes, and local listening ports. Sampling stops when the panel is hidden. Linux can withhold another user's socket details; “Owner unavailable” means the unprivileged collector couldn't identify a process.

Use the **microphone in the top bar → Settings** to configure transcription and chat independently. Chat supports OpenAI-compatible, Gemini and Anthropic request formats; dictation supports OpenAI-compatible and Gemini transcription. Pick a supported format, base URL and model for each. Keys are entered locally and stored via Secret Service. Chat can only return text; it has no tools or command actions. Dictation sends recorded audio to the configured service. Supported Hyprland captures redact this overlay with a black rectangle.

The horizontal top bar uses one black background with no group pills. On an existing installation, enable **Borderless** and **Show background** in the bar settings to use this style.

## Dolphin format wheel

Alt+left-click one supported local file in Dolphin, or right-click it and select **Convert / PDF tools…**. Choose a wedge, review the proposed output, and select **Yes, create copy**. Escape cancels. A numbered name is used if the destination already exists. The original is kept. Dolphin may need a new window to discover a newly installed service menu.

PDF → editable DOCX or TXT extracts selectable text (not layout or OCR); PDF → PNG or JPEG renders the first page. Single-frame PNG, JPEG, WebP, BMP, GIF and TIFF images can be converted to PNG, JPEG, WebP or PDF. Unsupported targets aren't offered. The wheel is local and runs only when opened. It uses GTK 3, GTK Layer Shell, PyGObject, Cairo, Pillow, Python D-Bus, and Poppler utilities.

## Combine images, merge PDFs, and split pages

In Dolphin, select your JPGs, PNGs, PDFs, or a mix. Right-click the selection and choose **Convert / PDF tools…**. The input list shows the exact page order; use **Move up / Move down**, then **Review and create… → Yes**. Images each contribute one page; PDF pages stay as PDF content. The output is saved beside the first input in the list.

For one PDF, Alt+click it and choose **PAGES** on the wheel. Extract or reorder pages with `3,1-2`; omit a page to leave it out. Split into groups with `1-3;4-6`, export each page separately, or rotate all pages left or right. Split jobs create a numbered set inside a new folder. Existing files aren't replaced. Locked PDFs are unsupported. Combining/extracting copies pages, not document-level items such as signatures and bookmarks. Requires libqpdf (Fedora: `qpdf-libs`).

## Downloads organizer

Open **Super+N → Downloads**. **Organize now** moves loose regular files in your XDG Downloads directory into extension folders (for example, `pdf/`, `jpg/`, or `tar.gz/`). Files without an extension go into `No extension/`. Existing directories, hidden files, symlinks, and recognized partial downloads are left alone. A name collision gets a numbered suffix; nothing is overwritten.

Automatic sorting starts off. Choose **Hourly**, **Daily** (midnight), or **Weekly** (Monday at midnight), in local time. A user systemd timer runs the same organizer and skips files modified in the last two minutes. Choose **Off** to stop future runs. Turning a schedule off does not undo earlier moves. No Downloads contents or scheduling state are stored in the repo.

## Headset audio

Connected Bluetooth headsets are preferred for playback and, when supported, microphone input. WirePlumber switches to the call profile when an app uses the headset mic and back to stereo playback afterwards. Leave your calling app’s input and output on **System Default**. USB devices and analog jacks use WirePlumber’s normal device and jack detection. To release a previously pinned audio output and input, run `wpctl clear-default 0 && wpctl clear-default 1`. No audio server restart is needed for routine connections.

## Make it your desktop

- **Themes:** press Super+F6 to try a palette. Choose **Wallpaper colors** to follow your wallpaper again, or **Restore previous** to undo a change.
- **Shortcuts and layout:** put your own bindings in `~/.config/hypr/custom/keybinds.lua` and appearance overrides in `~/.config/hypr/custom/general.lua`. For example, to change window rounding, add `hl.config({ decoration = { rounding = 8 } })` to your custom general file, then run `hyprctl reload`.
- **Voice and chat:** each person supplies their own provider and API key through the microphone menu. Both features are optional.
- **Displays:** the presentation shortcut detects the connected outputs. Your monitor names and saved profiles stay local.

When sharing your own changes, stage the intended source files and review `git diff --cached`. Keep your local shell settings, keyring, clipboard database, display profiles, and diagnostic logs outside the repository.

## Where the changes live

- `dots/.config/hypr/hyprland/edson.lua`: edition shortcuts and capture rules.
- `dots/.config/hypr/hyprland/scripts/edson/`: theme presets, runner and Voice & Chat.
- `dots/.config/quickshell/ii/modules/ii/`: bar, sliding sidebars, Wi-Fi dialog and charts.
- `dots/.config/quickshell/ii/scripts/`: thumbnail worker, monitor sampler and terminal palette fixes.

From the repository root, the checks below cover process/port parsing, thumbnail limits and cancellation, theme changes, provider formats and offscreen chat interactions. They require the desktop Python dependencies, Pillow and ImageMagick; they make no provider requests.

```sh
for t in tests/edson/test_*.py; do /usr/bin/python3 "$t" || exit 1; done
```

Connecting an external display automatically starts presentation mirroring at its preferred resolution and refresh rate; no display dimensions need to be entered. At login, a single already-connected external display is detected too. The external image fills its screen without stretching. Use Super+Alt+P to return to your extended layout. The laptop can have bars if its aspect ratio differs. With several external outputs, select which one to fill. This shortcut makes session-only changes; it does not overwrite your saved extended layout.
