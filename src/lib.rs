mod cache;
mod file_handler;
mod response;
mod utils;

use pyo3::prelude::*;

#[pymodule]
fn _rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<cache::LRUCache>()?;
    m.add_class::<cache::StatCache>()?;
    m.add_function(wrap_pyfunction!(utils::guess_content_type, m)?)?;
    m.add_function(wrap_pyfunction!(file_handler::parse_accept_encoding, m)?)?;
    m.add_function(wrap_pyfunction!(file_handler::find_compressed, m)?)?;
    m.add_function(wrap_pyfunction!(file_handler::is_hashed_file, m)?)?;
    m.add_function(wrap_pyfunction!(response::compute_etag, m)?)?;
    m.add_function(wrap_pyfunction!(response::format_last_modified, m)?)?;
    m.add_function(wrap_pyfunction!(response::build_cache_control, m)?)?;
    m.add_function(wrap_pyfunction!(response::security_headers, m)?)?;
    m.add_function(wrap_pyfunction!(response::build_headers, m)?)?;
    m.add_function(wrap_pyfunction!(response::parse_range, m)?)?;
    m.add_function(wrap_pyfunction!(response::build_content_range, m)?)?;
    m.add_function(wrap_pyfunction!(response::check_304, m)?)?;
    m.add_function(wrap_pyfunction!(response::build_all_headers, m)?)?;
    m.add_function(wrap_pyfunction!(response::build_full_response, m)?)?;
    Ok(())
}
