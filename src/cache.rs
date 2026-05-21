use pyo3::prelude::*;
use std::collections::HashMap;

#[pyclass]
pub struct LRUCache {
    capacity: usize,
    keys: Vec<u64>,
    map: HashMap<u64, PyObject>,
    next_id: u64,
    key_map: HashMap<u64, String>,
}

#[pymethods]
impl LRUCache {
    #[new]
    #[pyo3(signature = (maxsize=None))]
    pub fn new(maxsize: Option<usize>) -> Self {
        LRUCache {
            capacity: maxsize.unwrap_or(100).max(1),
            keys: Vec::new(),
            map: HashMap::new(),
            next_id: 0,
            key_map: HashMap::new(),
        }
    }

    pub fn get(&mut self, py: Python<'_>, key: &str) -> Option<PyObject> {
        let id = self.key_id(key)?;
        self.touch(id);
        self.map.get(&id).map(|obj| obj.clone_ref(py))
    }

    pub fn put(&mut self, key: &str, value: PyObject) {
        let id = match self.key_map.iter().find(|(_, v)| v.as_str() == key) {
            Some((k, _)) => *k,
            None => {
                let new_id = self.next_id;
                self.next_id += 1;
                self.key_map.insert(new_id, key.to_string());
                new_id
            }
        };

        if !self.map.contains_key(&id) {
            self.keys.push(id);
        }

        self.map.insert(id, value);
        self.touch(id);

        while self.keys.len() > self.capacity {
            if let Some(&evict) = self.keys.first() {
                self.keys.remove(0);
                self.map.remove(&evict);
                self.key_map.remove(&evict);
            }
        }
    }

    pub fn clear(&mut self) {
        self.keys.clear();
        self.map.clear();
        self.key_map.clear();
    }
}

impl LRUCache {
    fn key_id(&self, key: &str) -> Option<u64> {
        self.key_map
            .iter()
            .find(|(_, v)| v.as_str() == key)
            .map(|(k, _)| *k)
    }

    fn touch(&mut self, id: u64) {
        if let Some(pos) = self.keys.iter().position(|x| *x == id) {
            self.keys.remove(pos);
            self.keys.push(id);
        }
    }
}
