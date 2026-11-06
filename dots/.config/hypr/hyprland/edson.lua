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
