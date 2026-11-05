// One bounded-lifetime /proc snapshot; no daemon or external crates.
use std::{
    fs,
    io::{self, Write},
    path::Path,
};

struct Stat<'a> {
    name: &'a [u8],
    state: &'a str,
    ticks: u64,
    start: u64,
    rss: u64,
}
fn stat(line: &[u8]) -> Option<Stat<'_>> {
    // comm can contain spaces, newlines and parentheses. Fields after it are ASCII.
    let begin = line.iter().position(|&c| c == b'(')? + 1;
    let end = line.iter().rposition(|&c| c == b')')?;
    let name = line.get(begin..end)?;
    let mut f = std::str::from_utf8(&line[end + 1..])
        .ok()?
        .split_ascii_whitespace();
    let state = f.next()?;
    let user: u64 = f.nth(10)?.parse().ok()?; // field 14: utime
    let system: u64 = f.next()?.parse().ok()?;
    let start = f.nth(6)?.parse().ok()?; // field 22: starttime
    let rss = f.nth(1)?.parse().ok()?; // field 24: resident pages
    Some(Stat {
        name,
        state,
        ticks: user.checked_add(system)?,
        start,
        rss,
    })
}
fn quote(s: &[u8]) -> String {
    let mut out = String::from("\"");
    for c in String::from_utf8_lossy(s).chars().take(80) {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            c if c.is_control() => out.push_str(&format!("\\u{:04x}", c as u32)),
            c => out.push(c),
        }
    }
    out.push('"');
    out
}
fn main() -> io::Result<()> {
    let mut out = io::BufWriter::new(io::stdout().lock());
    write!(out, "[")?;
    let mut first = true;
    for entry in fs::read_dir(Path::new("/proc"))?.flatten() {
        let Ok(pid) = entry.file_name().to_string_lossy().parse::<u32>() else {
            continue;
        };
        let Ok(line) = fs::read(entry.path().join("stat")) else {
            continue;
        };
        let Some(s) = stat(&line) else { continue };
        // Like psutil, expand a truncated comm when argv[0] agrees with the kernel name.
        let cmd = if s.name.len() >= 15 {
            fs::read(entry.path().join("cmdline")).unwrap_or_default()
        } else {
            Vec::new()
        };
        let base = cmd
            .split(|&b| b == 0)
            .next()
            .unwrap_or_default()
            .rsplit(|&b| b == b'/')
            .next()
            .unwrap_or_default();
        let name = if !s.name.is_empty() && base.starts_with(s.name) {
            base
        } else {
            s.name
        };
        if !first {
            write!(out, ",")?;
        }
        first = false;
        write!(
            out,
            "[{},{},{},{},{},{}]",
            pid,
            s.start,
            s.ticks,
            s.rss,
            quote(s.state.as_bytes()),
            quote(name)
        )?;
    }
    writeln!(out, "]")?;
    out.flush()
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn tricky_comm() {
        let s = stat(b"123 (hi)\nthere) S 1 2 3 4 5 6 7 8 9 10 14 15 16 17 18 19 20 21 22 23 24")
            .unwrap();
        assert_eq!((s.ticks, s.start, s.rss), (29, 22, 24));
        assert_eq!(s.name, b"hi)\nthere");
        assert_eq!(quote(b"x\n\"\\"), "\"x\\u000a\\\"\\\\\"");
        assert!(stat(b"1 (short) S 0").is_none());
    }
}
