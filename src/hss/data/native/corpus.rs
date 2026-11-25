use std::collections::HashMap;
use std::env;
use std::fs::File;
use std::io::{self, BufRead, BufReader, Write};

fn quoted(text: &str) -> String {
    let mut result = String::from("\"");
    for c in text.chars() {
        match c {
            '"' => result.push_str("\\\""),
            '\\' => result.push_str("\\\\"),
            '\n' => result.push_str("\\n"),
            '\r' => result.push_str("\\r"),
            '\t' => result.push_str("\\t"),
            c if c < ' ' => result.push_str(&format!("\\u{:04x}", c as u32)),
            c => result.push(c),
        }
    }
    result.push('"');
    result
}

fn run(args: &[String]) -> Result<(), Box<dyn std::error::Error>> {
    if args.len() == 2 && args[1] == "--version" {
        println!("hss-corpus");
        return Ok(());
    }
    if args.len() < 3 || !["profile", "concordance"].contains(&args[1].as_str()) {
        return Err("Usage: hss-corpus profile FILE | concordance FILE QUERY [CONTEXT]".into());
    }
    let query = args.get(3).map(String::as_str).unwrap_or("");
    if args[1] == "concordance" && query.is_empty() {
        return Err("Provide a nonempty query".into());
    }
    let context: usize = args.get(4).map(|x| x.parse()).transpose()?.unwrap_or(40);
    let mut input = BufReader::new(File::open(&args[2])?);
    let mut output = io::BufWriter::new(io::stdout().lock());
    let (mut lines, mut bytes, mut characters, mut tokens, mut matches) = (0, 0, 0, 0, 0);
    let mut frequencies: HashMap<String, usize> = HashMap::new();
    let mut line = String::new();
    loop {
        line.clear();
        let read = input.read_line(&mut line)?;
        if read == 0 { break; }
        lines += 1;
        let chars: Vec<char> = line.chars().collect();
        if args[1] == "profile" {
            for token in line.split_whitespace() {
                tokens += 1;
                *frequencies.entry(token.to_string()).or_insert(0) += 1;
            }
        } else {
            for (byte, found) in line.match_indices(query) {
                let start = line[..byte].chars().count();
                let end = start + found.chars().count();
                let left: String = chars[start.saturating_sub(context)..start].iter().collect();
                let right: String = chars[end..(end + context).min(chars.len())].iter().collect();
                writeln!(output, "{{\"kind\":\"match\",\"line\":{},\"start\":{},\"end\":{},\"byte_start\":{},\"byte_end\":{},\"match\":{},\"left\":{},\"right\":{}}}",
                    lines, characters + start, characters + end, bytes + byte,
                    bytes + byte + found.len(), quoted(found), quoted(&left), quoted(&right))?;
                matches += 1;
            }
        }
        bytes += read;
        characters += chars.len();
    }
    if args[1] == "profile" {
        let mut ranked: Vec<_> = frequencies.into_iter().collect();
        ranked.sort_by(|a,b| b.1.cmp(&a.1).then(a.0.cmp(&b.0)));
        let unique = ranked.len();
        let top = ranked.iter().take(30).map(|(text, count)|
            format!("{{\"token\":{},\"count\":{}}}", quoted(text), count)).collect::<Vec<_>>().join(",");
        writeln!(output,"{{\"bytes\":{},\"characters\":{},\"lines\":{},\"whitespace_tokens\":{},\"unique_tokens\":{},\"top_tokens\":[{}]}}",bytes,characters,lines,tokens,unique,top)?;
    } else {
        writeln!(output,"{{\"kind\":\"summary\",\"matches\":{},\"lines\":{},\"characters\":{},\"bytes\":{}}}", matches,lines,characters,bytes)?;
    }
    output.flush()?;
    Ok(())
}

fn main() {
    if let Err(error) = run(&env::args().collect::<Vec<_>>()) {
        eprintln!("{}", error);
        std::process::exit(1);
    }
}

#[cfg(test)]
mod tests {
    use super::quoted;
    #[test]
    fn json_preserves_unicode_and_escapes_controls() {
        assert_eq!(quoted("甲\n\"乙"), "\"甲\\n\\\"乙\"");
    }
}
