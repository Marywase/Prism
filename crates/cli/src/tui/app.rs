use std::{
    io::{self, IsTerminal},
    time::Duration,
};

use crossterm::{
    cursor::{Hide, Show},
    event::{self, Event, KeyCode, KeyEvent, KeyEventKind, KeyModifiers},
    execute,
    terminal::{disable_raw_mode, enable_raw_mode, EnterAlternateScreen, LeaveAlternateScreen},
};
use grat_core::types::{config::NetworkConfig, trace::ExecutionTrace};
use ratatui::{
    backend::CrosstermBackend,
    layout::{Constraint, Layout},
    style::{Color, Style},
    text::{Line, Span},
    widgets::Paragraph,
    Frame, Terminal,
};

use super::{
    state::{Panel, TuiState},
    widgets::timeline,
};

/// Restores the terminal on normal exit, I/O errors and panic unwinding.
struct TerminalGuard;

impl TerminalGuard {
    fn enter() -> io::Result<Self> {
        enable_raw_mode()?;
        execute!(io::stdout(), EnterAlternateScreen, Hide)?;
        Ok(Self)
    }
}

impl Drop for TerminalGuard {
    fn drop(&mut self) {
        let _ = disable_raw_mode();
        let _ = execute!(io::stdout(), LeaveAlternateScreen, Show);
    }
}

pub async fn launch(tx_hash: &str, network: &NetworkConfig) -> anyhow::Result<()> {
    anyhow::ensure!(
        io::stdin().is_terminal() && io::stdout().is_terminal(),
        "Interactive replay requires a terminal; use `grat trace <tx-hash>` for redirected output."
    );

    // The transaction is replayed before the terminal enters raw mode so that
    // replay failures keep the regular terminal output.
    let trace = grat_core::replay::replay_transaction(tx_hash, network).await?;

    let mut state = TuiState {
        tx_hash: tx_hash.to_string(),
        selected_panel: Panel::Timeline,
        scroll_offset: 0,
    };

    let _guard = TerminalGuard::enter()?;
    let mut terminal = Terminal::new(CrosstermBackend::new(io::stdout()))?;

    loop {
        terminal.draw(|frame| render(frame, &state, &trace))?;
        if event::poll(Duration::from_millis(100))? {
            if let Event::Key(key) = event::read()? {
                if handle_key(&mut state, key, &trace) {
                    break;
                }
            }
        }
    }

    Ok(())
}

/// Handles a key press and reports whether the debugger should exit.
fn handle_key(state: &mut TuiState, key: KeyEvent, trace: &ExecutionTrace) -> bool {
    if key.kind == KeyEventKind::Release {
        return false;
    }
    if key.code == KeyCode::Char('c') && key.modifiers.contains(KeyModifiers::CONTROL) {
        return true;
    }

    match key.code {
        KeyCode::Char('q') | KeyCode::Esc => true,
        KeyCode::Down | KeyCode::Char('j') => {
            move_focus(state, trace, 1);
            false
        }
        KeyCode::Up | KeyCode::Char('k') => {
            move_focus(state, trace, -1);
            false
        }
        _ => false,
    }
}

/// Moves the focused frame by `delta` positions inside the invocation timeline.
///
/// `TuiState::scroll_offset` holds the index of the focused frame.
fn move_focus(state: &mut TuiState, trace: &ExecutionTrace, delta: isize) {
    let frames = timeline::count(&trace.invocations);
    if frames == 0 {
        state.scroll_offset = 0;
        return;
    }

    let last = frames - 1;
    let current = state.scroll_offset.min(last);
    let next = if delta < 0 {
        current.saturating_sub(delta.unsigned_abs())
    } else {
        current.saturating_add(delta.unsigned_abs())
    };

    state.scroll_offset = next.min(last);
}

/// Draws the debugger screen.
fn render(frame: &mut Frame<'_>, state: &TuiState, trace: &ExecutionTrace) {
    let area = frame.area();
    let [header_area, body_area, footer_area] = Layout::vertical([
        Constraint::Length(1),
        Constraint::Min(0),
        Constraint::Length(1),
    ])
    .areas(area);

    frame.render_widget(header(state, trace), header_area);

    timeline::render_with_focus(
        frame,
        body_area,
        &trace.invocations,
        state.scroll_offset,
        matches!(state.selected_panel, Panel::Timeline),
    );

    frame.render_widget(footer(state, trace), footer_area);
}

/// Renders the transaction summary shown above the timeline.
fn header(state: &TuiState, trace: &ExecutionTrace) -> Paragraph<'static> {
    Paragraph::new(Line::from(vec![
        Span::styled("Replay ", Style::default().fg(Color::Cyan)),
        Span::raw(state.tx_hash.clone()),
        Span::raw(format!(
            "  ·  {}  ·  ledger {}",
            trace.network, trace.ledger_sequence
        )),
    ]))
}

/// Renders the timeline position and the available key bindings.
fn footer(state: &TuiState, trace: &ExecutionTrace) -> Paragraph<'static> {
    let frames = timeline::count(&trace.invocations);
    let position = if frames == 0 {
        0
    } else {
        state.scroll_offset.min(frames - 1) + 1
    };

    Paragraph::new(Line::from(vec![
        Span::raw(format!(" Frame {position}/{frames} ")),
        Span::styled("↑/↓ navigate", Style::default().fg(Color::DarkGray)),
        Span::raw("  "),
        Span::styled("q quit", Style::default().fg(Color::DarkGray)),
    ]))
}

#[cfg(test)]
mod tests {
    use super::*;
    use grat_core::types::trace::{
        ContractInvocation, HostFunctionCall, ResourceProfile, StateDiff, TraceId,
    };
    use ratatui::backend::TestBackend;

    fn invocation(function_name: &str) -> ContractInvocation {
        ContractInvocation {
            trace_id: TraceId::new(),
            contract_id: "CONTRACT_A".to_string(),
            function_name: function_name.to_string(),
            arguments: Vec::new(),
            return_value: None,
            host_calls: Vec::<HostFunctionCall>::new(),
            sub_invocations: Vec::new(),
            total_cpu_instructions: 0,
            total_memory_bytes: 0,
            is_error: false,
        }
    }

    fn trace(invocations: Vec<ContractInvocation>) -> ExecutionTrace {
        ExecutionTrace {
            tx_hash: "tx-hash".to_string(),
            ledger_sequence: 42,
            network: "testnet".to_string(),
            invocations,
            state_diff: StateDiff::default(),
            resource_profile: ResourceProfile::default(),
            diagnostic_events: Vec::new(),
        }
    }

    fn state() -> TuiState {
        TuiState {
            tx_hash: "tx-hash".to_string(),
            selected_panel: Panel::Timeline,
            scroll_offset: 0,
        }
    }

    fn press(state: &mut TuiState, key: KeyEvent, trace: &ExecutionTrace) -> bool {
        handle_key(state, key, trace)
    }

    #[test]
    fn quit_keys_leave_the_debugger() {
        let trace = trace(Vec::new());
        let mut state = state();

        assert!(press(
            &mut state,
            KeyEvent::new(KeyCode::Char('q'), KeyModifiers::NONE),
            &trace
        ));
        assert!(press(
            &mut state,
            KeyEvent::new(KeyCode::Esc, KeyModifiers::NONE),
            &trace
        ));
        assert!(press(
            &mut state,
            KeyEvent::new(KeyCode::Char('c'), KeyModifiers::CONTROL),
            &trace
        ));
    }

    #[test]
    fn navigation_moves_the_focused_frame() {
        let trace = trace(vec![invocation("transfer"), invocation("swap")]);
        let mut state = state();

        assert!(!press(
            &mut state,
            KeyEvent::new(KeyCode::Down, KeyModifiers::NONE),
            &trace
        ));
        assert_eq!(state.scroll_offset, 1);

        assert!(!press(
            &mut state,
            KeyEvent::new(KeyCode::Char('j'), KeyModifiers::NONE),
            &trace
        ));
        assert_eq!(state.scroll_offset, 1);

        assert!(!press(
            &mut state,
            KeyEvent::new(KeyCode::Up, KeyModifiers::NONE),
            &trace
        ));
        assert_eq!(state.scroll_offset, 0);
    }

    #[test]
    fn navigation_stays_inside_the_timeline() {
        let trace = trace(vec![invocation("transfer"), invocation("swap")]);
        let mut state = state();

        for _ in 0..5 {
            press(
                &mut state,
                KeyEvent::new(KeyCode::Up, KeyModifiers::NONE),
                &trace,
            );
        }
        assert_eq!(state.scroll_offset, 0);

        for _ in 0..5 {
            press(
                &mut state,
                KeyEvent::new(KeyCode::Down, KeyModifiers::NONE),
                &trace,
            );
        }
        assert_eq!(state.scroll_offset, 1);
    }

    #[test]
    fn an_empty_trace_keeps_the_focus_at_the_first_frame() {
        let trace = trace(Vec::new());
        let mut state = state();

        press(
            &mut state,
            KeyEvent::new(KeyCode::Down, KeyModifiers::NONE),
            &trace,
        );
        assert_eq!(state.scroll_offset, 0);
    }

    #[test]
    fn the_screen_shows_the_invocation_timeline() {
        let trace = trace(vec![invocation("transfer"), invocation("swap")]);
        let state = state();

        let mut terminal = Terminal::new(TestBackend::new(80, 20)).unwrap();
        terminal
            .draw(|frame| render(frame, &state, &trace))
            .unwrap();

        let text: String = terminal
            .backend()
            .buffer()
            .content
            .iter()
            .map(|cell| cell.symbol())
            .collect();

        assert!(text.contains("tx-hash"));
        assert!(text.contains("Timeline"));
        assert!(text.contains("transfer"));
        assert!(text.contains("swap"));
        assert!(text.contains("Frame 1/2"));
    }
}
