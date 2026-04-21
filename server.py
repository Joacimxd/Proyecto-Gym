"""
server.py — Gym Routine Schedule Server

• TCP socket server on port 5050  (unchanged protocol)
• NiceGUI admin dashboard on port 8080
• Machine data stored in SQLite via db.py
"""

import socket
import threading
import json
from datetime import datetime, timedelta
from collections import deque

from nicegui import ui, app
import db

# ──────────────────────────────────────────────────────────────────────
#   Shared state
# ──────────────────────────────────────────────────────────────────────
schedule_lock = threading.Lock()
machine_availability = {}  # rebuilt from DB on each startup & refresh
server_stats = {
    "active_connections": 0,
    "total_schedules": 0,
    "start_time": None,
}
log_entries = deque(maxlen=200)  # ring buffer for recent log lines


def _add_log(msg):
    """Thread-safe log append."""
    ts = datetime.now().strftime("%H:%M:%S")
    log_entries.appendleft(f"[{ts}]  {msg}")


def rebuild_availability():
    """Re-read machines from DB and reset availability slots."""
    global machine_availability
    machines = db.get_machines_dict()
    with schedule_lock:
        machine_availability = {
            name: [datetime.now()] * info["max_concurrent"]
            for name, info in machines.items()
        }


# ──────────────────────────────────────────────────────────────────────
#   Scheduler  (same algorithm)
# ──────────────────────────────────────────────────────────────────────
def generate_schedule(user_name, routine):
    machines = db.get_machines_dict()
    with schedule_lock:
        user_schedule = []
        user_current_time = datetime.now()

        for requested_machine in routine:
            if requested_machine not in machines:
                user_schedule.append({
                    "machine": requested_machine,
                    "error": "Machine not found in gym.",
                })
                continue

            machine_info = machines[requested_machine]
            avg_time = machine_info["average_time"]

            # Ensure availability slot exists
            if requested_machine not in machine_availability:
                machine_availability[requested_machine] = (
                    [datetime.now()] * machine_info["max_concurrent"]
                )

            available_slots = machine_availability[requested_machine]
            earliest = min(available_slots)
            slot_index = available_slots.index(earliest)

            start_time = max(user_current_time, earliest)
            end_time = start_time + timedelta(minutes=avg_time)

            user_schedule.append({
                "machine": requested_machine,
                "start": start_time.strftime("%H:%M:%S"),
                "end": end_time.strftime("%H:%M:%S"),
                "duration": avg_time,
            })

            available_slots[slot_index] = end_time
            user_current_time = end_time

        return user_schedule


# ──────────────────────────────────────────────────────────────────────
#   Socket server  (same protocol — now with get_machines action)
# ──────────────────────────────────────────────────────────────────────
def handle_client(conn, addr):
    server_stats["active_connections"] += 1
    _add_log(f"Client {addr} connected.")
    try:
        data = conn.recv(4096).decode("utf-8")
        if not data:
            return

        request = json.loads(data)
        action = request.get("action")

        # ── New: return machine list ──
        if action == "get_machines":
            machines = db.get_all_machines()
            response = json.dumps({"status": "success", "machines": machines})
            conn.send(response.encode("utf-8"))
            _add_log(f"Sent machine list to {addr}")
            return

        # ── Existing: generate schedule ──
        user_name = request.get("user", "Unknown Client")
        routine = request.get("routine", [])

        _add_log(f"Routine from {user_name}: {routine}")

        schedule = generate_schedule(user_name, routine)
        server_stats["total_schedules"] += 1

        response = json.dumps({"status": "success", "schedule": schedule})
        conn.send(response.encode("utf-8"))
        _add_log(f"Sent schedule to {user_name} ({len(schedule)} items)")

    except Exception as e:
        _add_log(f"Error processing {addr}: {e}")
        try:
            error_response = json.dumps({"status": "error", "message": str(e)})
            conn.send(error_response.encode("utf-8"))
        except Exception:
            pass
    finally:
        server_stats["active_connections"] -= 1
        conn.close()


def start_socket_server():
    host = "127.0.0.1"
    port = 5050

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, port))
    server.listen()
    _add_log(f"🚀 Socket server listening on {host}:{port}")
    server_stats["start_time"] = datetime.now()

    while True:
        try:
            conn, addr = server.accept()
            threading.Thread(
                target=handle_client, args=(conn, addr), daemon=True
            ).start()
        except OSError:
            break


# ──────────────────────────────────────────────────────────────────────
#   NiceGUI Admin Dashboard
# ──────────────────────────────────────────────────────────────────────

# ── Custom CSS injected into the page ──
CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

:root {
    --accent-violet: #8b5cf6;
    --accent-cyan: #06b6d4;
    --bg-dark: #0f0f14;
    --bg-card: rgba(22, 22, 35, 0.85);
    --bg-card-hover: rgba(30, 30, 50, 0.95);
    --border-glow: rgba(139, 92, 246, 0.25);
    --text-primary: #e8e8f0;
    --text-secondary: #9ca3af;
}

body, .q-page, .nicegui-content {
    font-family: 'Inter', sans-serif !important;
    background: var(--bg-dark) !important;
    color: var(--text-primary) !important;
}

.glass-card {
    background: var(--bg-card) !important;
    border: 1px solid var(--border-glow) !important;
    backdrop-filter: blur(16px) !important;
    border-radius: 16px !important;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
}
.glass-card:hover {
    background: var(--bg-card-hover) !important;
    border-color: rgba(139, 92, 246, 0.45) !important;
    box-shadow: 0 8px 32px rgba(139, 92, 246, 0.15) !important;
}

.gradient-text {
    background: linear-gradient(135deg, var(--accent-violet), var(--accent-cyan)) !important;
    -webkit-background-clip: text !important;
    -webkit-text-fill-color: transparent !important;
    background-clip: text !important;
}

.stat-number {
    font-size: 2.8rem !important;
    font-weight: 800 !important;
    background: linear-gradient(135deg, var(--accent-violet), var(--accent-cyan)) !important;
    -webkit-background-clip: text !important;
    -webkit-text-fill-color: transparent !important;
    background-clip: text !important;
    line-height: 1.1 !important;
}

.stat-label {
    color: var(--text-secondary) !important;
    font-size: 0.85rem !important;
    font-weight: 500 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.08em !important;
}

.hero-banner {
    background: linear-gradient(135deg, rgba(139, 92, 246, 0.15), rgba(6, 182, 212, 0.10)) !important;
    border: 1px solid rgba(139, 92, 246, 0.2) !important;
    border-radius: 20px !important;
    padding: 2rem 2.5rem !important;
}

.log-container {
    background: rgba(10, 10, 18, 0.8) !important;
    border: 1px solid rgba(139, 92, 246, 0.15) !important;
    border-radius: 12px !important;
    font-family: 'JetBrains Mono', 'Fira Code', monospace !important;
    font-size: 0.82rem !important;
    max-height: 400px !important;
    overflow-y: auto !important;
    padding: 1rem !important;
}

.q-table {
    background: transparent !important;
}
.q-table thead tr th {
    color: var(--accent-cyan) !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    font-size: 0.75rem !important;
    letter-spacing: 0.06em !important;
    border-bottom: 1px solid var(--border-glow) !important;
}
.q-table tbody tr td {
    color: var(--text-primary) !important;
    border-bottom: 1px solid rgba(139, 92, 246, 0.08) !important;
}
.q-table tbody tr:hover td {
    background: rgba(139, 92, 246, 0.06) !important;
}

.q-btn {
    border-radius: 10px !important;
    font-weight: 600 !important;
    text-transform: none !important;
    letter-spacing: 0.02em !important;
}

.q-input .q-field__control, .q-select .q-field__control {
    background: rgba(22, 22, 35, 0.9) !important;
    border: 1px solid var(--border-glow) !important;
    border-radius: 10px !important;
    color: var(--text-primary) !important;
}

.q-dialog .q-card {
    background: #16162a !important;
    border: 1px solid var(--border-glow) !important;
    border-radius: 16px !important;
}

.pulse-dot {
    display: inline-block;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: #22c55e;
    animation: pulse 2s infinite;
}
@keyframes pulse {
    0%   { box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.5); }
    70%  { box-shadow: 0 0 0 8px rgba(34, 197, 94, 0); }
    100% { box-shadow: 0 0 0 0 rgba(34, 197, 94, 0); }
}
</style>
"""

# Machine icons mapping
MACHINE_ICONS = {
    "Squat Machine": "fitness_center",
    "Pendulum Squat Machine": "accessibility_new",
    "Leg Curl": "airline_seat_legroom_extra",
    "Leg Extension": "airline_seat_legroom_normal",
    "Hip Thrust": "self_improvement",
    "Smith Machine": "sports_gymnastics",
}


def get_icon(name):
    return MACHINE_ICONS.get(name, "fitness_center")


@ui.page("/")
def admin_dashboard():
    ui.add_head_html(CUSTOM_CSS)
    ui.add_head_html('<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">')

    # ── Top bar ──
    with ui.row().classes("w-full items-center justify-between px-6 py-4"):
        with ui.row().classes("items-center gap-3"):
            ui.icon("admin_panel_settings", size="sm").classes("text-violet-400")
            ui.label("Gym Admin").classes("text-xl font-bold gradient-text")
        with ui.row().classes("items-center gap-2"):
            ui.html('<span class="pulse-dot"></span>', sanitize=False)
            ui.label("Server Online").classes("text-sm text-green-400 font-medium")

    # ── Hero ──
    with ui.element("div").classes("hero-banner mx-6 mb-6"):
        with ui.row().classes("items-center justify-between"):
            with ui.column().classes("gap-1"):
                ui.label("🏋️  Server Control Panel").classes("text-2xl font-bold")
                ui.label("Manage gym machines, monitor connections, and view real-time logs.").classes("text-gray-400")
            ui.label("Socket :5050").classes("text-violet-400 font-mono text-sm bg-violet-950 px-3 py-1 rounded-lg border border-violet-800")

    # ── Stats row ──
    with ui.row().classes("w-full px-6 gap-4 mb-6"):
        stat_machines = ui.label("0")
        stat_connections = ui.label("0")
        stat_schedules = ui.label("0")
        stat_uptime = ui.label("—")

        # Rebuild with proper layout
        stat_machines.delete()
        stat_connections.delete()
        stat_schedules.delete()
        stat_uptime.delete()

    stats_row = ui.row().classes("w-full px-6 gap-4 mb-6")
    with stats_row:
        with ui.card().classes("glass-card flex-1 p-5"):
            stat_machines_label = ui.label("0").classes("stat-number")
            ui.label("Machines").classes("stat-label mt-1")
        with ui.card().classes("glass-card flex-1 p-5"):
            stat_connections_label = ui.label("0").classes("stat-number")
            ui.label("Active Connections").classes("stat-label mt-1")
        with ui.card().classes("glass-card flex-1 p-5"):
            stat_schedules_label = ui.label("0").classes("stat-number")
            ui.label("Schedules Generated").classes("stat-label mt-1")
        with ui.card().classes("glass-card flex-1 p-5"):
            stat_uptime_label = ui.label("—").classes("stat-number")
            ui.label("Uptime (min)").classes("stat-label mt-1")

    # ── Machine management ──
    with ui.card().classes("glass-card mx-6 mb-6 p-6"):
        with ui.row().classes("w-full items-center justify-between mb-4"):
            ui.label("🎛️  Machine Management").classes("text-lg font-bold")

            def open_add_dialog():
                with ui.dialog() as dlg, ui.card().classes("p-6 w-96"):
                    ui.label("Add New Machine").classes("text-lg font-bold gradient-text mb-4")
                    name_input = ui.input("Machine Name").classes("w-full mb-2")
                    time_input = ui.number("Average Time (min)", value=15, min=1).classes("w-full mb-2")
                    conc_input = ui.number("Max Concurrent", value=1, min=1).classes("w-full mb-4")

                    with ui.row().classes("w-full justify-end gap-2"):
                        ui.button("Cancel", on_click=dlg.close).props("flat color=grey")

                        def do_add():
                            result = db.add_machine(
                                name_input.value,
                                int(time_input.value),
                                int(conc_input.value),
                            )
                            if result:
                                rebuild_availability()
                                refresh_table()
                                ui.notify(f"Added '{name_input.value}'", type="positive")
                                _add_log(f"➕ Added machine: {name_input.value}")
                                dlg.close()
                            else:
                                ui.notify("Machine name already exists!", type="negative")

                        ui.button("Add Machine", on_click=do_add).props(
                            "color=deep-purple-8"
                        ).classes("px-6")
                dlg.open()

            ui.button("＋  Add Machine", on_click=open_add_dialog).props(
                "color=deep-purple-8 no-caps"
            ).classes("px-5")

        # Machine table
        machine_table_container = ui.column().classes("w-full")

    def refresh_table():
        machine_table_container.clear()
        machines = db.get_all_machines()
        stat_machines_label.set_text(str(len(machines)))

        with machine_table_container:
            columns = [
                {"name": "id", "label": "ID", "field": "id", "align": "left"},
                {"name": "name", "label": "Machine Name", "field": "name", "align": "left"},
                {"name": "average_time", "label": "Avg Time (min)", "field": "average_time", "align": "center"},
                {"name": "max_concurrent", "label": "Max Slots", "field": "max_concurrent", "align": "center"},
                {"name": "actions", "label": "Actions", "field": "actions", "align": "center"},
            ]
            rows = machines

            table = ui.table(
                columns=columns,
                rows=rows,
                row_key="id",
            ).classes("w-full")

            table.add_slot(
                "body-cell-actions",
                """
                <q-td :props="props">
                    <q-btn flat dense round icon="edit" color="cyan" size="sm"
                           @click="$parent.$emit('edit', props.row)" />
                    <q-btn flat dense round icon="delete" color="red-4" size="sm"
                           @click="$parent.$emit('delete', props.row)" />
                </q-td>
                """,
            )

            def handle_edit(e):
                row = e.args
                with ui.dialog() as dlg, ui.card().classes("p-6 w-96"):
                    ui.label("Edit Machine").classes("text-lg font-bold gradient-text mb-4")
                    n = ui.input("Machine Name", value=row["name"]).classes("w-full mb-2")
                    t = ui.number("Average Time (min)", value=row["average_time"], min=1).classes("w-full mb-2")
                    c = ui.number("Max Concurrent", value=row["max_concurrent"], min=1).classes("w-full mb-4")

                    with ui.row().classes("w-full justify-end gap-2"):
                        ui.button("Cancel", on_click=dlg.close).props("flat color=grey")

                        def do_update():
                            db.update_machine(
                                row["id"],
                                name=n.value,
                                average_time=int(t.value),
                                max_concurrent=int(c.value),
                            )
                            rebuild_availability()
                            refresh_table()
                            ui.notify(f"Updated '{n.value}'", type="positive")
                            _add_log(f"✏️  Updated machine: {n.value}")
                            dlg.close()

                        ui.button("Save", on_click=do_update).props("color=deep-purple-8").classes("px-6")
                dlg.open()

            def handle_delete(e):
                row = e.args
                with ui.dialog() as dlg, ui.card().classes("p-6 w-96"):
                    ui.label("Delete Machine?").classes("text-lg font-bold text-red-400 mb-2")
                    ui.label(f'Are you sure you want to delete "{row["name"]}"?').classes("text-gray-400 mb-4")
                    with ui.row().classes("w-full justify-end gap-2"):
                        ui.button("Cancel", on_click=dlg.close).props("flat color=grey")

                        def do_delete():
                            db.delete_machine(row["id"])
                            rebuild_availability()
                            refresh_table()
                            ui.notify(f"Deleted '{row['name']}'", type="warning")
                            _add_log(f"🗑️  Deleted machine: {row['name']}")
                            dlg.close()

                        ui.button("Delete", on_click=do_delete).props("color=red-8").classes("px-6")
                dlg.open()

            table.on("edit", handle_edit)
            table.on("delete", handle_delete)

    # ── Live logs ──
    with ui.card().classes("glass-card mx-6 mb-6 p-6"):
        ui.label("📜  Live Server Log").classes("text-lg font-bold mb-3")
        log_display = ui.html("", sanitize=False).classes("log-container w-full")

    # ── Timer to refresh stats & logs ──
    def tick():
        stat_connections_label.set_text(str(server_stats["active_connections"]))
        stat_schedules_label.set_text(str(server_stats["total_schedules"]))
        if server_stats["start_time"]:
            uptime_min = int((datetime.now() - server_stats["start_time"]).total_seconds() / 60)
            stat_uptime_label.set_text(str(uptime_min))
        # Refresh logs
        lines = list(log_entries)[:50]
        html_lines = "<br>".join(
            f'<span style="color:#9ca3af">{line}</span>' for line in lines
        )
        log_display.set_content(html_lines if html_lines else '<span style="color:#555">No log entries yet…</span>')

    ui.timer(1.5, tick)

    # Initial table load
    refresh_table()


# ──────────────────────────────────────────────────────────────────────
#   Main
# ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Initialize database
    db.init_db()
    rebuild_availability()

    # Start socket server in background thread
    socket_thread = threading.Thread(target=start_socket_server, daemon=True)
    socket_thread.start()

    _add_log("🏁 Server starting up…")

    # Start NiceGUI (blocking — serves admin dashboard)
    ui.run(
        title="Gym Admin Dashboard",
        port=8082,
        dark=True,
        reload=False,
        show=False,
    )
