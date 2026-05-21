use pyo3::prelude::*;

#[pyfunction]
pub fn parse_accept_encoding(header: &str) -> Vec<String> {
    let mut entries: Vec<(f64, String)> = Vec::new();

    for part in header.split(',') {
        let part = part.trim();
        if part.is_empty() {
            continue;
        }

        let mut q = 1.0;
        let token;

        if let Some(semicolon_pos) = part.find(';') {
            token = part[..semicolon_pos].trim().to_lowercase();
            let params = &part[semicolon_pos + 1..];
            for param in params.split(';') {
                let param = param.trim();
                if let Some(q_val) = param.strip_prefix("q=") {
                    if let Ok(v) = q_val.parse::<f64>() {
                        q = v;
                    }
                }
            }
        } else {
            token = part.to_lowercase();
        }

        entries.push((q, token));
    }

    entries.sort_by(|a, b| b.0.partial_cmp(&a.0).unwrap_or(std::cmp::Ordering::Equal));
    entries.into_iter().map(|(_, t)| t).collect()
}

#[pyfunction]
#[pyo3(signature = (file_path, accept_encoding, allow_brotli = true, allow_gzip = true))]
pub fn find_compressed(
    file_path: &str,
    accept_encoding: &str,
    allow_brotli: bool,
    allow_gzip: bool,
) -> Option<(String, String)> {
    let encodings = parse_accept_encoding(accept_encoding);

    for enc in &encodings {
        if enc == "br" && allow_brotli {
            let br_path = format!("{}.br", file_path);
            if std::path::Path::new(&br_path).exists() {
                return Some((br_path, "br".to_string()));
            }
        }
        if enc == "gzip" && allow_gzip {
            let gz_path = format!("{}.gz", file_path);
            if std::path::Path::new(&gz_path).exists() {
                return Some((gz_path, "gzip".to_string()));
            }
        }
    }

    None
}

#[pyfunction]
pub fn is_hashed_file(filename: &str, pattern: &str) -> bool {
    regex::Regex::new(pattern)
        .map_or(false, |re| re.is_match(filename))
}
