import pathlib

repo = pathlib.Path.cwd()
root = pathlib.Path('/tmp/issue-484-harness')
root.mkdir(exist_ok=True)
(root/'Cargo.toml').write_text('''[package]
name = "controls-validation"
version = "0.1.0"
edition = "2021"
[workspace]
[lib]
path = "lib.rs"
[dependencies]
ratatui = "0.29"
crossterm = "0.28"
anyhow = "1"
serde = { version = "1", features = ["derive"] }
uuid = { version = "1.26.1", features = ["serde", "v4"] }
''')
# Reuse the actual trace types and all actual TUI source files. Only the network
# boundary is a stub, so this validates UI code, not full CLI/replay integration.
(root/'lib.rs').write_text(f'''extern crate self as grat_core;
pub mod types {{
    #[path = "{repo}/crates/core/src/types/trace.rs"]
    pub mod trace;
    pub mod config {{ pub struct NetworkConfig; }}
}}
pub mod replay {{
    pub async fn replay_transaction(_: &str, _: &crate::types::config::NetworkConfig) -> anyhow::Result<crate::types::trace::ExecutionTrace> {{
        anyhow::bail!("Network replay is not exercised by this isolated UI harness")
    }}
}}
#[path = "{repo}/crates/cli/src/tui/mod.rs"]
pub mod tui;
''')
