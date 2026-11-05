-- Edson edition shortcuts. Feature scripts live with the managed Hyprland files.
local scripts = "~/.config/hypr/hyprland/scripts/edson/"
hl.bind("ALT + SPACE", hl.dsp.exec_cmd(scripts .. "ii-runner.sh"), { description = "KRunner search" })
hl.bind("SUPER + F6", hl.dsp.exec_cmd("python3 " .. scripts .. "ii-themes.py"), { description = "Choose desktop theme" })
hl.bind("CTRL + SUPER + D", hl.dsp.exec_cmd(scripts .. "ii-voice-ai.sh dictate"), { description = "Start or stop dictation" })
hl.bind("CTRL + SUPER + A", hl.dsp.exec_cmd(scripts .. "ii-voice-ai.sh chat"), { description = "Open AI chat" })

-- The app manages whether to keep a pinned conversation across workspace changes.
hl.window_rule({
    match = { class = "^(ii-voice-ai)$" },
    float = true, center = true, pin = true, decorate = false, border_size = 0,
    no_shadow = true, no_blur = false, dim_around = false, no_screen_share = true,
})

hl.bind("SUPER + ALT + P", hl.dsp.exec_cmd("python3 ~/.config/hypr/hyprland/scripts/edson/mirror-fit.py"), { description = "Mirror full-screen to external display or extend" })

-- Connecting a monitor extends the desktop. Only the shortcut above enters presentation mode.

-- Capture the modified click only while Dolphin is active. A normal left
-- click would collapse a group before Dolphin could pass it to the action.
local formatClick
local function updateFormatClick(w)
    if w and w.class == "org.kde.dolphin" then
        if not formatClick then
            formatClick = hl.bind("ALT + mouse:272", hl.dsp.exec_cmd("/usr/bin/python3 ~/.config/hypr/hyprland/scripts/edson/format-wheel/gesture.py"),
                {release = true, description = "Dolphin: actions for clicked file or selection"})
        end
    elseif formatClick then
        formatClick:unbind()
        formatClick = nil
    end
end
hl.on("window.active", updateFormatClick)
updateFormatClick(hl.get_active_window())
hl.bind("SUPER + ALT + Escape", hl.dsp.exec_cmd("~/.local/bin/ii-desktop-recovery"), {description = "Desktop recovery"})
