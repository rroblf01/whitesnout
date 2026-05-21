use pyo3::prelude::*;

#[pyfunction]
pub fn compute_etag(size: i64, mtime_ns: i64) -> String {
    format!("\"{:x}-{:x}\"", mtime_ns, size)
}

#[pyfunction]
pub fn format_last_modified(mtime_ns: i64) -> String {
    let secs = mtime_ns / 1_000_000_000;
    let dt = chrono::DateTime::from_timestamp(secs, 0)
        .unwrap_or(chrono::DateTime::UNIX_EPOCH);
    dt.format("%a, %d %b %Y %H:%M:%S GMT").to_string()
}

#[pyfunction]
pub fn build_cache_control(is_hashed: bool, max_age: u64, immutable_max_age: u64) -> String {
    if is_hashed {
        format!("public, immutable, max-age={}", immutable_max_age)
    } else {
        format!("public, max-age={}", max_age)
    }
}

#[pyfunction]
#[pyo3(signature = (enabled = true))]
pub fn security_headers(enabled: bool) -> Vec<(String, String)> {
    if !enabled {
        return vec![];
    }
    vec![
        ("x-content-type-options".to_string(), "nosniff".to_string()),
        ("x-frame-options".to_string(), "DENY".to_string()),
    ]
}

#[pyfunction]
pub fn build_headers(
    content_type: &str,
    content_length: i64,
    extra: Vec<(String, String)>,
) -> Vec<(String, String)> {
    let mut headers = vec![
        ("content-type".to_string(), content_type.to_string()),
        ("content-length".to_string(), content_length.to_string()),
    ];
    headers.extend(extra);
    headers
}

#[pyfunction]
pub fn parse_range(range_header: &str, file_size: i64) -> Option<(i64, i64)> {
    if !range_header.starts_with("bytes=") {
        return None;
    }
    let range_val = range_header[6..].trim();
    if !range_val.contains('-') {
        return None;
    }
    let mut parts = range_val.splitn(2, '-');
    let start_str = parts.next()?;
    let end_str = parts.next()?;

    if start_str.is_empty() {
        let n: i64 = end_str.parse().ok()?;
        if n <= 0 {
            return None;
        }
        return Some((file_size - n, file_size - 1));
    }

    let start: i64 = start_str.parse().ok()?;
    let end: i64 = if end_str.is_empty() {
        file_size - 1
    } else {
        end_str.parse().ok()?
    };

    if start < 0 || start >= file_size || end < start {
        return None;
    }
    Some((start, end.min(file_size - 1)))
}

#[pyfunction]
pub fn build_content_range(start: i64, end: i64, total: i64) -> String {
    format!("bytes {}-{}/{}", start, end, total)
}

#[pyfunction]
#[pyo3(signature = (if_none_match=None, if_modified_since=None, etag="", last_modified=""))]
pub fn check_304(
    if_none_match: Option<&str>,
    if_modified_since: Option<&str>,
    etag: &str,
    last_modified: &str,
) -> bool {
    if let Some(etag_match) = if_none_match {
        let em = etag_match.trim();
        if em == "*" {
            return true;
        }
        if em.trim_matches('"') == etag.trim_matches('"') {
            return true;
        }
    }

    if let Some(modified_since) = if_modified_since {
        if let (Ok(since), Ok(lm)) = (
            chrono::DateTime::parse_from_rfc2822(modified_since.trim()),
            chrono::DateTime::parse_from_rfc2822(last_modified.trim()),
        ) {
            if lm <= since {
                return true;
            }
        }
    }

    false
}

#[pyfunction]
#[pyo3(signature = (
    content_type, content_length,
    etag, last_modified, cache_control,
    content_encoding=None, security_enabled=true, cors_enabled=false,
    range_header=None, file_size=0,
))]
pub fn build_all_headers(
    content_type: &str,
    content_length: i64,
    etag: &str,
    last_modified: &str,
    cache_control: &str,
    content_encoding: Option<&str>,
    security_enabled: bool,
    cors_enabled: bool,
    range_header: Option<&str>,
    file_size: i64,
) -> (Vec<(Vec<u8>, Vec<u8>)>, u16, i64, Option<(i64, i64)>) {
    let mut headers: Vec<(Vec<u8>, Vec<u8>)> = Vec::with_capacity(8);

    headers.push((b"content-type".to_vec(), content_type.as_bytes().to_vec()));
    headers.push((b"content-length".to_vec(), content_length.to_string().into_bytes()));
    headers.push((b"etag".to_vec(), etag.as_bytes().to_vec()));
    headers.push((b"last-modified".to_vec(), last_modified.as_bytes().to_vec()));
    headers.push((b"cache-control".to_vec(), cache_control.as_bytes().to_vec()));

    if security_enabled {
        headers.push((b"x-content-type-options".to_vec(), b"nosniff".to_vec()));
        headers.push((b"x-frame-options".to_vec(), b"DENY".to_vec()));
    }

    if cors_enabled {
        headers.push((b"access-control-allow-origin".to_vec(), b"*".to_vec()));
    }

    if let Some(ce) = content_encoding {
        headers.push((b"content-encoding".to_vec(), ce.as_bytes().to_vec()));
    }

    let mut status: u16 = 200;
    let mut final_length = content_length;
    let mut range_spec: Option<(i64, i64)> = None;

    if let Some(rh) = range_header {
        let parsed = parse_range_inner(rh, file_size);
        if let Some((start, end)) = parsed {
            status = 206;
            final_length = end - start + 1;
            headers.push((
                b"content-range".to_vec(),
                format!("bytes {}-{}/{}", start, end, file_size).into_bytes(),
            ));
            range_spec = Some((start, end));
        }
    }

    (headers, status, final_length, range_spec)
}

fn parse_range_inner(range_header: &str, file_size: i64) -> Option<(i64, i64)> {
    if !range_header.starts_with("bytes=") {
        return None;
    }
    let range_val = range_header[6..].trim();
    if !range_val.contains('-') {
        return None;
    }
    let mut parts = range_val.splitn(2, '-');
    let start_str = parts.next()?;
    let end_str = parts.next()?;

    if start_str.is_empty() {
        let n: i64 = end_str.parse().ok()?;
        if n <= 0 {
            return None;
        }
        return Some((file_size - n, file_size - 1));
    }

    let start: i64 = start_str.parse().ok()?;
    let end: i64 = if end_str.is_empty() {
        file_size - 1
    } else {
        end_str.parse().ok()?
    };

    if start < 0 || start >= file_size || end < start {
        return None;
    }
    Some((start, end.min(file_size - 1)))
}
