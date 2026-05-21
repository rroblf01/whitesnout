mod cache;
mod file_handler;
mod utils;

use pyo3::prelude::*;

#[pymodule]
fn _rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<cache::LRUCache>()?;
    m.add_function(wrap_pyfunction!(utils::guess_content_type, m)?)?;
    m.add_function(wrap_pyfunction!(file_handler::parse_accept_encoding, m)?)?;
    m.add_function(wrap_pyfunction!(file_handler::find_compressed, m)?)?;
    m.add_function(wrap_pyfunction!(file_handler::is_hashed_file, m)?)?;
    Ok(())
}
