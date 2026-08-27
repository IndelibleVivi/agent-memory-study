# Current-main native build receipt

Status: `exact_source_compile_failure`

## Source

- Repository: `voxmastery/FluctlightDB`
- Exact commit: `d867f3cdbcffcefe4e14473333a78ce33a06ae47`
- Checkout state: clean `main...origin/main`
- Native/SDK release line: `0.5.10`
- `crates/fluctlightdb/src/brain.rs` SHA-256: `5f16e2eaacf294ea12b574672b034cd31a8b5ea2030aa10e34a05a6a07a20163`

## Build environment

- macOS arm64
- CPython 3.13.3
- Rust 1.98.0 (`88d9e12ae`, 2026-08-18)
- Cargo 1.98.0 (`797e8a9bc`, 2026-08-05)
- maturin 1.15.0
- release profile, pyo3 abi3-py39, deployment target macOS 11.0

## Exact failure

`maturin build --release --manifest-path crates/fluctlight-py/Cargo.toml` reached
`fluctlightdb-native v0.5.10` and returned Rust `E0425`:

```text
error[E0425]: cannot find function `sync_once` in crate `fluctlightdb`
   --> crates/fluctlight-py/src/lib.rs:726:27
    |
726 |             fluctlightdb::sync_once(std::path::Path::new(primary), std::path::Path::new(replica))
    |                           ^^^^^^^^^ not found in `fluctlightdb`
```

No current-main wheel, import, official benchmark output, or independent treatment
output was produced. Official descendant
`f5d51e247b544503f8f47960b9dc6ecd43c2f464` explicitly repairs the missing
crate-root export and is tested separately as `repair-descendant`; it is not
represented as current-main runtime evidence.
