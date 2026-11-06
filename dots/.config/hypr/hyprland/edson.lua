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

-- Use the connected display's advertised preferred mode for presentations.
-- Listen to physical hot-plug and login, not layout changes caused by our own rules.
local presentationCommand = "python3 ~/.config/hypr/hyprland/scripts/edson/mirror-fit.py --auto"
hl.on("monitor.added", function(m)
    local name = m.name
    if name and name:match("^[%w_.%-]+$") and not name:match("^eDP") and not name:match("^LVDS")
        and not name:match("^DSI") and not name:match("^HEADLESS") and not name:match("^FALLBACK") then
        hl.exec_cmd(presentationCommand .. " " .. name)
    end
end)
hl.on("hyprland.start", function() hl.exec_cmd(presentationCommand) end)
