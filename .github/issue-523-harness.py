from pathlib import Path
import subprocess
import argparse
import os

parser = argparse.ArgumentParser()
parser.add_argument('--repo')
parser.add_argument('--notes')
parser.add_argument('--base-sha', default='37e3cee1ebe695a8dd09de5753918e433e9196a8')
args = parser.parse_args()
notes = Path(args.notes) if args.notes else Path(__file__).resolve().parent
repo = Path(args.repo) if args.repo else notes.parents[3] / 'projects/Toolbox-Lab/Prism/Marywase'
notes.mkdir(parents=True, exist_ok=True)
linux_repo = str(repo) if os.name != 'nt' else '/mnt/c/Users/HP/Documents/plinger-hunter/projects/Toolbox-Lab/Prism/Marywase'
linux_notes = str(notes) if os.name != 'nt' else '/mnt/c/Users/HP/Documents/plinger-hunter/work/Toolbox-Lab/Prism/523'
original = subprocess.check_output(['git', 'show', args.base_sha + ':crates/cli/src/tui/widgets/inspector.rs'], cwd=repo, text=True, encoding='utf-8')
current = (repo / 'crates/cli/src/tui/widgets/inspector.rs').read_text(encoding='utf-8')
def truncate_fn(text):
    start = text.index('fn truncate(')
    return text[start:text.index('\n}', start) + 2]
(notes / 'baseline-inspector-regression.rs').write_text(current.replace(truncate_fn(current), truncate_fn(original)), encoding='utf-8')
current_app = (repo / 'crates/cli/src/tui/app.rs').read_text(encoding='utf-8')
(notes / 'baseline-app-regression.rs').write_text(current_app.replace('Constraint::Length(7)', 'Constraint::Length(6)'), encoding='utf-8')

for baseline in [True, False]:
    name = 'baseline-harness' if baseline else 'harness'
    target = notes / name
    target.mkdir(exist_ok=True)
    (target / 'Cargo.toml').write_text('''[package]
name = "replay-validation"
version = "0.1.0"
edition = "2021"
[workspace]
[lib]
path = "lib.rs"
[[bin]]
name = "replay-validation"
path = "main.rs"
[dependencies]
ratatui = "0.29"
crossterm = "0.28"
anyhow = "1"
serde = { version = "1", features = ["derive"] }
serde_json = "1"
uuid = { version = "1.26.1", features = ["serde", "v4"] }
clap = { version = "4", features = ["derive"] }
tokio = { version = "1", features = ["macros", "rt-multi-thread"] }
''', encoding='utf-8')
    inspector = f'{linux_notes}/baseline-inspector-regression.rs' if baseline else f'{linux_repo}/crates/cli/src/tui/widgets/inspector.rs'
    app = f'{linux_notes}/baseline-app-regression.rs' if baseline else f'{linux_repo}/crates/cli/src/tui/app.rs'
    output_source = (repo / 'crates/cli/src/output/mod.rs').read_text(encoding='utf-8')
    output_type = output_source[output_source.index('#[derive(Debug, Clone, Copy'):output_source.index('pub type OutputMode')]
    lib = '''extern crate self as grat_core;
// Only unused authorization metadata and the network/replay boundary are
// substituted. Trace data types and all TUI/command implementation are real.
pub mod decode { pub mod auth { pub type AuthChain = serde_json::Value; } }
pub mod network { pub use crate::types::config::NetworkConfig; }
pub mod types {
    #[path = "REPO/crates/core/src/types/trace.rs"] pub mod trace;
    pub mod config { pub struct NetworkConfig; }
}
pub mod replay {
    pub async fn replay_transaction(_: &str, _: &crate::types::config::NetworkConfig) -> anyhow::Result<crate::types::trace::ExecutionTrace> {
        anyhow::ensure!(std::env::var_os("PRISM523_REPLAY_ERROR").is_none(), "fixture replay failure");
        use crate::types::trace::*;
        let unicode = std::env::var_os("PRISM523_UNICODE").is_some();
        let call = |name: &str| ContractInvocation {
            trace_id: TraceId::new(), contract_id: "CEXAMPLE".into(), function_name: name.into(),
            arguments: if unicode { vec!["é".repeat(50)] } else { vec!["amount=42".into()] },
            return_value: Some("ok".into()), host_calls: vec![], sub_invocations: vec![],
            total_cpu_instructions: 0, total_memory_bytes: 0, is_error: false,
        };
        let mut parent = call("parent"); parent.sub_invocations.push(call("child"));
        Ok(ExecutionTrace {
            tx_hash: "fixture-523".into(), network: "fixture".into(), ledger_sequence: 1,
            invocations: vec![parent, call("sibling")], state_diff: StateDiff::default(),
            resource_profile: ResourceProfile { total_cpu: 250, cpu_limit: 1000, total_memory: 500, memory_limit: 1000, ..ResourceProfile::default() },
            diagnostic_events: vec![], auth_chains: vec![],
        })
    }
}
pub mod output { OUTPUT }
pub mod commands { #[path = "REPO/crates/cli/src/commands/replay.rs"] pub mod replay; }
pub mod tui {
    #[path = "REPO/crates/cli/src/tui/state.rs"] pub mod state;
    pub mod widgets {
        #[path = "REPO/crates/cli/src/tui/widgets/controls.rs"] pub mod controls;
        #[path = "REPO/crates/cli/src/tui/widgets/timeline.rs"] pub mod timeline;
        #[path = "INSPECTOR"] pub mod inspector;
    }
    pub mod app {
        include!("APP_SOURCE");
        // Test instrumentation in the harness only: exercise the unchanged
        // private production guard on normal return, errors and unwinding.
        pub fn guard_probe(mode: &str) -> std::io::Result<()> {
            let _guard = TerminalGuard::enter()?;
            match mode {
                "panic" => panic!("terminal cleanup probe"),
                "error" => Err(std::io::Error::other("terminal cleanup probe")),
                _ => Ok(()),
            }
        }
    }
}
'''.replace('REPO', linux_repo).replace('INSPECTOR', inspector).replace('APP_SOURCE', app).replace('OUTPUT', output_type)
    (target / 'lib.rs').write_text(lib, encoding='utf-8')
    (target / 'main.rs').write_text('''use clap::{Parser, Subcommand};
#[derive(Parser)] struct Cli {
    #[command(subcommand)] command: Command,
    #[arg(long, global=true, default_value="human")] output: String,
    #[arg(long, global=true)] quiet: bool,
}
#[derive(Subcommand)] enum Command {
    Replay(replay_validation::commands::replay::ReplayArgs),
    Guard { mode: String },
}
#[tokio::main] async fn main() -> anyhow::Result<()> {
    let cli = Cli::parse();
    match cli.command {
        Command::Replay(args) => replay_validation::commands::replay::run(args, &replay_validation::types::config::NetworkConfig, &cli.output, &cli.quiet).await,
        Command::Guard { mode } => Ok(replay_validation::tui::app::guard_probe(&mode)?),
    }
}
''', encoding='utf-8')
print('Created baseline and current harnesses around actual source; network/auth metadata boundaries substituted.')
