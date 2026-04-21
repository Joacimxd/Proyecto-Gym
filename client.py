"""
client.py — Gym Routine Schedule Client

• Beautiful NiceGUI web interface on port 8081
• Communicates with the Gym Server via TCP sockets (port 5050)
"""

import socket
import json

from nicegui import ui

# ──────────────────────────────────────────────────────────────────────
#   Socket helpers
# ──────────────────────────────────────────────────────────────────────
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 5050


def _socket_request(payload: dict) -> dict:
    """Send a JSON payload to the server and return the parsed response."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    try:
        sock.connect((SERVER_HOST, SERVER_PORT))
        sock.send(json.dumps(payload).encode("utf-8"))
        data = sock.recv(8192).decode("utf-8")
        return json.loads(data)
    finally:
        sock.close()


def fetch_machines() -> list:
    """Retrieve machine list from the server."""
    try:
        resp = _socket_request({"action": "get_machines"})
        if resp.get("status") == "success":
            return resp["machines"]
    except Exception:
        pass
    return []


def request_schedule(user_name: str, routine: list) -> dict:
    """Send a routine request and return the schedule response."""
    return _socket_request({"user": user_name, "routine": routine})


# ──────────────────────────────────────────────────────────────────────
#   Custom CSS
# ──────────────────────────────────────────────────────────────────────
CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');

:root {
    --accent-violet: #8b5cf6;
    --accent-cyan: #06b6d4;
    --bg-dark: #0a0a12;
    --bg-card: rgba(18, 18, 32, 0.85);
    --bg-card-hover: rgba(26, 26, 48, 0.95);
    --border-glow: rgba(139, 92, 246, 0.2);
    --text-primary: #e8e8f0;
    --text-secondary: #9ca3af;
    --success: #22c55e;
}

body, .q-page, .nicegui-content {
    font-family: 'Inter', sans-serif !important;
    background: var(--bg-dark) !important;
    color: var(--text-primary) !important;
}

.gradient-text {
    background: linear-gradient(135deg, var(--accent-violet), var(--accent-cyan)) !important;
    -webkit-background-clip: text !important;
    -webkit-text-fill-color: transparent !important;
    background-clip: text !important;
}

.hero-section {
    background: linear-gradient(160deg, rgba(139, 92, 246, 0.12) 0%, rgba(6, 182, 212, 0.08) 50%, rgba(139, 92, 246, 0.05) 100%) !important;
    border: 1px solid rgba(139, 92, 246, 0.15) !important;
    border-radius: 24px !important;
    padding: 3rem !important;
    position: relative;
    overflow: hidden;
}
.hero-section::before {
    content: '';
    position: absolute;
    top: -50%;
    right: -20%;
    width: 400px;
    height: 400px;
    background: radial-gradient(circle, rgba(139, 92, 246, 0.12) 0%, transparent 70%);
    border-radius: 50%;
}

.glass-card {
    background: var(--bg-card) !important;
    border: 1px solid var(--border-glow) !important;
    backdrop-filter: blur(16px) !important;
    border-radius: 16px !important;
    transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1) !important;
    cursor: pointer;
}
.glass-card:hover {
    background: var(--bg-card-hover) !important;
    border-color: rgba(139, 92, 246, 0.4) !important;
    box-shadow: 0 8px 32px rgba(139, 92, 246, 0.12) !important;
    transform: translateY(-3px) !important;
}

.machine-card-selected {
    background: rgba(139, 92, 246, 0.15) !important;
    border-color: var(--accent-violet) !important;
    box-shadow: 0 0 24px rgba(139, 92, 246, 0.2), inset 0 0 24px rgba(139, 92, 246, 0.05) !important;
}

.machine-icon-wrap {
    width: 56px;
    height: 56px;
    border-radius: 14px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.5rem;
    transition: all 0.3s ease;
}
.icon-default {
    background: rgba(139, 92, 246, 0.1);
    border: 1px solid rgba(139, 92, 246, 0.2);
}
.icon-selected {
    background: linear-gradient(135deg, var(--accent-violet), var(--accent-cyan));
    border: none;
    box-shadow: 0 4px 16px rgba(139, 92, 246, 0.35);
}

.chip-tag {
    background: rgba(139, 92, 246, 0.1) !important;
    border: 1px solid rgba(139, 92, 246, 0.2) !important;
    border-radius: 8px !important;
    padding: 2px 10px !important;
    font-size: 0.75rem !important;
    color: var(--accent-cyan) !important;
    font-weight: 500 !important;
}

.schedule-item {
    background: rgba(18, 18, 32, 0.6) !important;
    border: 1px solid rgba(139, 92, 246, 0.12) !important;
    border-radius: 14px !important;
    padding: 1.2rem 1.5rem !important;
    transition: all 0.3s ease !important;
}
.schedule-item:hover {
    border-color: rgba(6, 182, 212, 0.3) !important;
    background: rgba(22, 22, 40, 0.8) !important;
}

.time-badge {
    background: linear-gradient(135deg, rgba(139, 92, 246, 0.2), rgba(6, 182, 212, 0.2)) !important;
    border: 1px solid rgba(139, 92, 246, 0.25) !important;
    border-radius: 10px !important;
    padding: 6px 14px !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.9rem !important;
    font-weight: 600 !important;
    color: var(--accent-cyan) !important;
}

.submit-btn {
    background: linear-gradient(135deg, var(--accent-violet), #7c3aed) !important;
    border: none !important;
    border-radius: 14px !important;
    padding: 14px 40px !important;
    font-size: 1rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.03em !important;
    transition: all 0.3s ease !important;
    box-shadow: 0 4px 20px rgba(139, 92, 246, 0.3) !important;
}
.submit-btn:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 30px rgba(139, 92, 246, 0.45) !important;
}

.result-panel {
    background: linear-gradient(160deg, rgba(34, 197, 94, 0.06) 0%, rgba(6, 182, 212, 0.04) 100%) !important;
    border: 1px solid rgba(34, 197, 94, 0.15) !important;
    border-radius: 20px !important;
    padding: 2rem !important;
}

.timeline-line {
    width: 3px;
    background: linear-gradient(180deg, var(--accent-violet), var(--accent-cyan));
    border-radius: 2px;
    min-height: 40px;
}
.timeline-dot {
    width: 14px;
    height: 14px;
    border-radius: 50%;
    background: linear-gradient(135deg, var(--accent-violet), var(--accent-cyan));
    box-shadow: 0 0 10px rgba(139, 92, 246, 0.4);
    flex-shrink: 0;
}

.q-input .q-field__control {
    background: rgba(18, 18, 32, 0.9) !important;
    border: 1px solid var(--border-glow) !important;
    border-radius: 12px !important;
    color: var(--text-primary) !important;
}

.error-badge {
    background: rgba(239, 68, 68, 0.15) !important;
    border: 1px solid rgba(239, 68, 68, 0.3) !important;
    color: #f87171 !important;
    border-radius: 8px !important;
    padding: 4px 10px !important;
    font-size: 0.8rem !important;
}

.empty-state {
    color: var(--text-secondary);
    text-align: center;
    padding: 3rem;
}
</style>
"""

# Machine icons mapping
MACHINE_ICONS = {
    "Squat Machine": "🦵",
    "Pendulum Squat Machine": "🏋️",
    "Leg Curl": "💪",
    "Leg Extension": "🦿",
    "Hip Thrust": "🍑",
    "Smith Machine": "⚙️",
}

MACHINE_ICONS_MATERIAL = {
    "Squat Machine": "fitness_center",
    "Pendulum Squat Machine": "accessibility_new",
    "Leg Curl": "airline_seat_legroom_extra",
    "Leg Extension": "airline_seat_legroom_normal",
    "Hip Thrust": "self_improvement",
    "Smith Machine": "sports_gymnastics",
}


# ──────────────────────────────────────────────────────────────────────
#   NiceGUI Client UI
# ──────────────────────────────────────────────────────────────────────
@ui.page("/")
def client_page():
    ui.add_head_html(CUSTOM_CSS)
    ui.add_head_html(
        '<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">'
    )

    selected_machines: list[str] = []
    machine_cards: dict = {}

    # ── Container ──
    with ui.column().classes("w-full max-w-5xl mx-auto px-4 py-6 gap-6"):

        # ── Top bar ──
        with ui.row().classes("w-full items-center justify-between"):
            with ui.row().classes("items-center gap-3"):
                ui.label("🏋️‍♂️").classes("text-3xl")
                ui.label("GymFlow").classes("text-2xl font-black gradient-text")
            with ui.row().classes("items-center gap-2"):
                status_dot = ui.html('<span class="pulse-dot" style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#22c55e;animation:pulse 2s infinite"></span>', sanitize=False)
                status_label = ui.label("Connected").classes("text-sm text-green-400 font-medium")

        # ── Hero ──
        with ui.element("div").classes("hero-section"):
            ui.label("Build Your Workout").classes("text-3xl font-black mb-2")
            ui.label(
                "Select machines below to create your personalized gym routine. "
                "We'll generate an optimized schedule based on real-time availability."
            ).classes("text-gray-400 text-base max-w-2xl")

        # ── Name input ──
        with ui.card().classes("glass-card p-5"):
            ui.label("👤  Your Name").classes("text-sm font-semibold text-gray-300 mb-2")
            name_input = ui.input(
                placeholder="Enter your name…"
            ).classes("w-full").props('dark dense outlined')

        # ── Machine selection ──
        ui.label("📋  Select Your Machines").classes("text-lg font-bold mt-2")
        ui.label("Click the machines you want in your routine").classes("text-sm text-gray-500 -mt-4")

        machines_container = ui.row().classes("w-full gap-4 flex-wrap")
        schedule_result_container = ui.column().classes("w-full gap-4")

        # ── Selected summary (declared early so refresh can access it) ──
        with ui.row().classes("w-full justify-center"):
            selected_summary_label = ui.label("No machines selected").classes("text-sm text-gray-500")

        def toggle_machine(name: str):
            if name in selected_machines:
                selected_machines.remove(name)
            else:
                selected_machines.append(name)
            refresh_selection_ui()

        def refresh_selection_ui():
            for mname, card_el in machine_cards.items():
                if mname in selected_machines:
                    card_el.classes(add="machine-card-selected")
                else:
                    card_el.classes(remove="machine-card-selected")
            if selected_machines:
                selected_summary_label.set_text(f"Selected: {', '.join(selected_machines)}")
            else:
                selected_summary_label.set_text("No machines selected")

        def load_machines():
            machines_container.clear()
            machine_cards.clear()

            machines = fetch_machines()
            if not machines:
                with machines_container:
                    with ui.column().classes("empty-state w-full"):
                        ui.icon("cloud_off", size="3rem").classes("text-gray-600 mx-auto")
                        ui.label("Cannot connect to server").classes("text-lg font-semibold mt-2")
                        ui.label("Make sure server.py is running on port 5050").classes("text-gray-500 text-sm")
                        ui.button("Retry", on_click=load_machines).props("color=deep-purple-8 no-caps").classes("mt-3")
                status_label.set_text("Disconnected")
                status_label.classes(remove="text-green-400", add="text-red-400")
                return

            status_label.set_text("Connected")
            status_label.classes(remove="text-red-400", add="text-green-400")

            with machines_container:
                for m in machines:
                    mname = m["name"]
                    emoji = MACHINE_ICONS.get(mname, "💪")
                    mat_icon = MACHINE_ICONS_MATERIAL.get(mname, "fitness_center")

                    with ui.card().classes("glass-card p-5 flex-grow") as card:
                        card.on("click", lambda _, n=mname: toggle_machine(n))
                        machine_cards[mname] = card

                        with ui.row().classes("items-start gap-4"):
                            with ui.element("div").classes("machine-icon-wrap icon-default"):
                                ui.icon(mat_icon, size="1.6rem").classes("text-violet-400")

                            with ui.column().classes("gap-1 flex-grow"):
                                ui.label(mname).classes("font-bold text-base")
                                with ui.row().classes("gap-2 mt-1"):
                                    ui.html(
                                        f'<span class="chip-tag">⏱ {m["average_time"]} min</span>',
                                        sanitize=False,
                                    )
                                    ui.html(
                                        f'<span class="chip-tag">👥 {m["max_concurrent"]} slots</span>',
                                        sanitize=False,
                                    )

        # ── Submit button ──
        def submit_routine():
            schedule_result_container.clear()
            user = name_input.value.strip()
            if not user:
                ui.notify("Please enter your name", type="warning")
                return
            if not selected_machines:
                ui.notify("Select at least one machine", type="warning")
                return

            try:
                resp = request_schedule(user, selected_machines)
            except Exception as e:
                ui.notify(f"Connection error: {e}", type="negative")
                return

            if resp.get("status") != "success":
                ui.notify(f"Server error: {resp.get('message', 'unknown')}", type="negative")
                return

            schedule = resp["schedule"]

            with schedule_result_container:
                with ui.element("div").classes("result-panel"):
                    with ui.row().classes("items-center gap-3 mb-5"):
                        ui.icon("event_available", size="md").classes("text-green-400")
                        ui.label(f"Schedule for {user}").classes("text-xl font-bold")
                        ui.label(f"{len(schedule)} exercises").classes("text-sm text-gray-400 ml-auto")

                    # Timeline
                    total_min = 0
                    for i, item in enumerate(schedule):
                        with ui.row().classes("w-full items-start gap-4"):
                            # Timeline connector
                            with ui.column().classes("items-center gap-0 pt-1"):
                                ui.html('<div class="timeline-dot"></div>', sanitize=False)
                                if i < len(schedule) - 1:
                                    ui.html('<div class="timeline-line"></div>', sanitize=False)

                            # Card
                            with ui.element("div").classes("schedule-item flex-grow"):
                                if "error" in item:
                                    with ui.row().classes("items-center gap-3"):
                                        emoji = MACHINE_ICONS.get(item["machine"], "❓")
                                        ui.label(f"{emoji}  {item['machine']}").classes("font-semibold")
                                        ui.html(f'<span class="error-badge">⚠ {item["error"]}</span>', sanitize=False)
                                else:
                                    emoji = MACHINE_ICONS.get(item["machine"], "💪")
                                    with ui.row().classes("items-center justify-between w-full"):
                                        with ui.row().classes("items-center gap-3"):
                                            ui.label(f"{emoji}").classes("text-2xl")
                                            with ui.column().classes("gap-0"):
                                                ui.label(item["machine"]).classes("font-bold text-base")
                                                ui.label(f"{item['duration']} minutes").classes("text-gray-500 text-sm")
                                        with ui.row().classes("gap-2"):
                                            ui.html(f'<span class="time-badge">{item["start"]}</span>', sanitize=False)
                                            ui.label("→").classes("text-gray-500 self-center")
                                            ui.html(f'<span class="time-badge">{item["end"]}</span>', sanitize=False)
                                    total_min += item.get("duration", 0)

                    # Summary footer
                    with ui.element("div").classes("mt-5 pt-4").style("border-top: 1px solid rgba(139, 92, 246, 0.15)"):
                        with ui.row().classes("justify-between items-center"):
                            ui.label(f"Total workout time: {total_min} minutes").classes("font-semibold text-gray-300")
                            ui.button("🔄  New Routine", on_click=lambda: schedule_result_container.clear()).props(
                                "flat no-caps color=grey"
                            )

            ui.notify("Schedule generated! 🎉", type="positive")

        with ui.row().classes("w-full justify-center mt-2"):
            ui.button(
                "⚡  Generate Schedule",
                on_click=submit_routine,
            ).props("no-caps size=lg color=deep-purple-8").classes("submit-btn")

        # ── Load machines on page open ──
        load_machines()



# ──────────────────────────────────────────────────────────────────────
#   Main
# ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    ui.run(
        title="GymFlow — Build Your Workout",
        port=8081,
        dark=True,
        reload=False,
        show=False,
    )
