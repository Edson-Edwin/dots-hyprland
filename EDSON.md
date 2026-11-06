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
