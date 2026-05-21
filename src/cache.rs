use lru::LruCache;
use pyo3::prelude::*;
use std::num::NonZeroUsize;

#[pyclass]
pub struct LRUCache {
    cache: LruCache<String, PyObject>,
}

#[pymethods]
impl LRUCache {
    #[new]
    #[pyo3(signature = (maxsize=None))]
    pub fn new(maxsize: Option<usize>) -> Self {
        let capacity = maxsize.unwrap_or(100).max(1);
        LRUCache {
            cache: LruCache::new(NonZeroUsize::new(capacity).unwrap()),
        }
    }

    pub fn get(&mut self, py: Python<'_>, key: &str) -> Option<PyObject> {
        self.cache.get(key).map(|obj| obj.clone_ref(py))
    }

    pub fn put(&mut self, key: &str, value: PyObject) {
        self.cache.put(key.to_string(), value);
    }

    pub fn clear(&mut self) {
        self.cache.clear();
    }
}

#[pyclass]
pub struct StatCache {
    cache: LruCache<String, (i64, i64)>,
}

#[pymethods]
impl StatCache {
    #[new]
    #[pyo3(signature = (maxsize=None))]
    pub fn new(maxsize: Option<usize>) -> Self {
        let capacity = maxsize.unwrap_or(100).max(1);
        StatCache {
            cache: LruCache::new(NonZeroUsize::new(capacity).unwrap()),
        }
    }

    pub fn get(&mut self, key: &str) -> Option<(i64, i64)> {
        self.cache.get(key).copied()
    }

    pub fn put(&mut self, key: &str, size: i64, mtime_ns: i64) {
        self.cache.put(key.to_string(), (size, mtime_ns));
    }

    pub fn clear(&mut self) {
        self.cache.clear();
    }
}
