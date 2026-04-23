"""Render heatmap dashboard HTML (framework-free)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any


def render_dashboard_html(payload: dict[str, Any], status_message: str = "") -> str:
    generated_at = datetime.now(timezone.utc).isoformat()
    data = {
        "generated_at": generated_at,
        "rows_loaded": payload.get("rows_loaded", 0),
        "tables": payload.get("tables", {}),
    }
    json_blob = json.dumps(data, ensure_ascii=False)
    safe_status = status_message.replace("<", "&lt;").replace(">", "&gt;")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta http-equiv="refresh" content="600" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>BTC 5m Heatmap Dashboard</title>
  <style>
    :root {{
      --bg: #0f172a; --panel: #111827; --panel2: #1f2937; --border: #334155;
      --text: #e5e7eb; --muted: #94a3b8;
      --very-weak: #4b1d1d; --weak: #5b3340; --mid: #3f3f46; --good: #1f4d3b; --strong: #14532d;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin:0; padding:24px; font-family: Arial, Helvetica, sans-serif; background:var(--bg); color:var(--text); }}
    .panel {{ background:var(--panel); border:1px solid var(--border); border-radius:14px; padding:16px; margin-bottom:18px; }}
    .meta {{ display:flex; flex-wrap:wrap; gap:14px; color:var(--muted); font-size:14px; }}
    table {{ width:100%; border-collapse:collapse; min-width:900px; }}
    th, td {{ border:1px solid var(--border); padding:10px; text-align:center; }}
    th {{ background:var(--panel2); font-size:13px; }}
    td {{ font-size:13px; line-height:1.35; }}
    .sub {{ display:block; margin-top:4px; font-size:11px; color:#cbd5e1; }}
    .rate-very-weak {{ background:var(--very-weak); }} .rate-weak {{ background:var(--weak); }}
    .rate-mid {{ background:var(--mid); }} .rate-good {{ background:var(--good); }} .rate-strong {{ background:var(--strong); }}
    .low-sample {{ outline:2px dashed #9ca3af; }} .missing {{ color:var(--muted); background:#0b1220; }}
    .very-low-sample {{ outline:2px solid #ef4444; }}
    .table-wrap {{ overflow-x:auto; }}
    .status {{ color:#fbbf24; margin-top:8px; }}
  </style>
</head>
<body>
  <div class="panel">
    <h1>BTC 5m Heatmap Dashboard</h1>
    <div class="meta">
      <div><strong>Rolling Window:</strong> last 200 log lines</div>
      <div><strong>Auto Refresh:</strong> every 10 minutes</div>
      <div><strong>Last Refresh:</strong> <span id="refreshTime">—</span></div>
      <div><strong>Rows Loaded:</strong> <span id="rowsLoaded">0</span></div>
    </div>
    <div id="statusMsg" class="status">{safe_status}</div>
  </div>
  <div id="app"></div>

  <script>
    const TIME_BUCKETS = [300,280,260,240,220,200,180,160,140,120,100,80,60,40,20,0];
    const PNL_BUCKETS = ["lt_neg_2","neg_2_to_neg_1","neg_1_to_neg_0_3","neg_0_3_to_0_3","pos_0_3_to_1","pos_1_to_2","gt_2"];
    const LIQ_BUCKETS = ["strong_minus","weak_minus","neutral","weak_plus","strong_plus"];
    const dashboardData = {json_blob};

    function rateClass(winRate) {{
      if (winRate == null) return "missing";
      if (winRate < 0.40) return "rate-very-weak";
      if (winRate < 0.50) return "rate-weak";
      if (winRate < 0.60) return "rate-mid";
      if (winRate < 0.70) return "rate-good";
      return "rate-strong";
    }}
    function fmtPct(value, digits=1) {{
      if (value == null || Number.isNaN(value)) return "—";
      return (value*100).toFixed(digits) + "%";
    }}
    function human(v) {{ return String(v).replaceAll("_", " "); }}

    function renderTable(bucketName, tableData) {{
      const section = document.createElement("section");
      section.className = "panel";
      section.innerHTML = `<h2>Liquidation Bucket: ${{human(bucketName)}}</h2>`;
      const wrap = document.createElement("div"); wrap.className = "table-wrap";
      const table = document.createElement("table");
      const thead = document.createElement("thead");
      const hr = document.createElement("tr");
      const corner = document.createElement("th"); corner.textContent = "Time Left \\ PnL Z-Bucket"; hr.appendChild(corner);
      for (const pnl of PNL_BUCKETS) {{ const th = document.createElement("th"); th.textContent = human(pnl); hr.appendChild(th); }}
      thead.appendChild(hr); table.appendChild(thead);
      const tbody = document.createElement("tbody");
      for (const t of TIME_BUCKETS) {{
        const tr = document.createElement("tr");
        const h = document.createElement("th"); h.textContent = String(t); tr.appendChild(h);
        for (const pnl of PNL_BUCKETS) {{
          const key = `${{t}}__${{pnl}}`;
          const cell = tableData?.[key] || null;
          const td = document.createElement("td");
          if (!cell) {{ td.className = "missing"; td.textContent = "—"; }}
          else {{
            td.className = rateClass(cell.win_rate);
            if ((cell.samples || 0) < 50) td.classList.add("low-sample");
            if ((cell.samples || 0) < 30) td.classList.add("very-low-sample");
            const main = document.createElement("div");
            main.textContent = `${{fmtPct(cell.win_rate)}} (${{cell.samples}})`;
            const sub = document.createElement("span"); sub.className = "sub";
            sub.textContent = `avg pnl: ${{fmtPct(cell.avg_final_pnl_pct)}}`;
            td.appendChild(main); td.appendChild(sub);
          }}
          tr.appendChild(td);
        }}
        tbody.appendChild(tr);
      }}
      table.appendChild(tbody); wrap.appendChild(table); section.appendChild(wrap); return section;
    }}

    function renderApp() {{
      document.getElementById("refreshTime").textContent = dashboardData.generated_at || "—";
      document.getElementById("rowsLoaded").textContent = String(dashboardData.rows_loaded || 0);
      const app = document.getElementById("app");
      app.innerHTML = "";
      const hasAny = LIQ_BUCKETS.some(b => dashboardData.tables?.[b] && Object.keys(dashboardData.tables[b]).length > 0);
      if (!hasAny) {{
        const div = document.createElement("div"); div.className = "panel";
        div.textContent = "No heatmap data available yet.";
        app.appendChild(div);
        return;
      }}
      for (const b of LIQ_BUCKETS) app.appendChild(renderTable(b, dashboardData.tables?.[b] || {{}}));
    }}
    renderApp();
  </script>
</body>
</html>
"""
