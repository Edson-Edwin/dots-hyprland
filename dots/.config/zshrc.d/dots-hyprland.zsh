# Kitty reads its generated theme from kitty.conf and reloads on theme changes.
# Other compatible terminals may opt in explicitly to startup OSC colors.
if [[ -o interactive && -t 1 && ${II_TERMINAL_OSC_COLORS:-0} == 1 ]]; then
    if [[ -f ~/.local/state/quickshell/user/generated/terminal/sequences.txt ]]; then
        cat ~/.local/state/quickshell/user/generated/terminal/sequences.txt
    fi
fi
