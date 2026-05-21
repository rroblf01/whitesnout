use pyo3::prelude::*;

fn mime_type(ext: &str) -> &'static str {
    match ext {
        ".html" => "text/html",
        ".css" => "text/css",
        ".js" => "application/javascript",
        ".json" => "application/json",
        ".svg" => "image/svg+xml",
        ".png" => "image/png",
        ".jpg" => "image/jpeg",
        ".jpeg" => "image/jpeg",
        ".gif" => "image/gif",
        ".webp" => "image/webp",
        ".ico" => "image/x-icon",
        ".woff2" => "font/woff2",
        ".woff" => "font/woff",
        ".ttf" => "font/ttf",
        ".otf" => "font/otf",
        ".eot" => "application/vnd.ms-fontobject",
        ".pdf" => "application/pdf",
        ".txt" => "text/plain",
        ".xml" => "application/xml",
        ".zip" => "application/zip",
        ".gz" => "application/gzip",
        ".br" => "application/brotli",
        ".map" => "application/json",
        ".wasm" => "application/wasm",
        ".mjs" => "application/javascript",
        ".cjs" => "application/javascript",
        _ => "application/octet-stream",
    }
}

#[pyfunction]
#[pyo3(signature = (path, charset = "utf-8"))]
pub fn guess_content_type(path: &str, charset: &str) -> String {
    let ext = std::path::Path::new(path)
        .extension()
        .and_then(|e| e.to_str())
        .map(|e| {
            let mut ext = String::with_capacity(e.len() + 1);
            ext.push('.');
            ext.push_str(&e.to_lowercase());
            ext
        })
        .unwrap_or_default();

    let mime = mime_type(&ext);
    if mime.starts_with("text/")
        || mime == "application/json"
        || mime == "application/javascript"
        || mime == "application/xml"
    {
        format!("{}; charset={}", mime, charset)
    } else {
        mime.to_string()
    }
}
