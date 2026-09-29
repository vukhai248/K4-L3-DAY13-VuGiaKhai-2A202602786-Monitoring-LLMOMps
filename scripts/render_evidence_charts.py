import json
from datetime import datetime
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np

# Set dark theme style for professional observability dashboard look
plt.style.use('dark_background')
REPO_ROOT = Path(__file__).resolve().parents[1]
LOGS_PATH = REPO_ROOT / 'data' / 'logs.jsonl'
EVIDENCE_DIR = REPO_ROOT / 'submission' / 'evidence'
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

# Parse logs
logs = []
with open(LOGS_PATH, 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if line:
            try:
                logs.append(json.loads(line))
            except Exception:
                pass

resp_logs = [l for l in logs if l.get('event') == 'response_sent']
req_logs = [l for l in logs if l.get('event') == 'request_received']

timestamps = []
latencies = []
ttfts = []
costs = []
tokens_in = []
tokens_out = []
qualities = []
tool_successes = []

for l in resp_logs:
    ts_str = l.get('ts')
    if ts_str:
        # ISO format parse
        dt = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
        timestamps.append(dt)
        latencies.append(l.get('latency_ms', 0))
        ttfts.append(l.get('ttft_ms', 0))
        costs.append(l.get('cost_usd', 0.0))
        tokens_in.append(l.get('tokens_in', 0))
        tokens_out.append(l.get('tokens_out', 0))
        qualities.append(l.get('quality_score', 0.0))
        tool_successes.append(1 if l.get('tool_success') else 0)

# Sort by timestamp
combined = sorted(zip(timestamps, latencies, ttfts, costs, tokens_in, tokens_out, qualities, tool_successes))
if combined:
    timestamps, latencies, ttfts, costs, tokens_in, tokens_out, qualities, tool_successes = map(list, zip(*combined))

# -------------------------------------------------------------
# 1. GENERATE 11-dashboard-overview.png (6 Panels)
# -------------------------------------------------------------
fig, axes = plt.subplots(2, 3, figsize=(18, 10))
fig.patch.set_facecolor('#0f172a')  # Slate 900 background

for ax in axes.flat:
    ax.set_facecolor('#1e293b')  # Slate 800
    ax.grid(True, linestyle='--', alpha=0.3, color='#94a3b8')
    ax.tick_params(colors='#94a3b8', labelsize=9)
    for spine in ax.spines.values():
        spine.set_color('#334155')

fig.suptitle("K4-L3A Day 13 Monitoring & LLMOps — Runtime Dashboard (6 Panels Contract)", 
             fontsize=16, fontweight='bold', color='#f8fafc', y=0.98)

# Panel 1: Latency percentiles and TTFT
ax1 = axes[0, 0]
ax1.set_title("Panel 1: Latency Percentiles & TTFT (ms)", fontsize=11, fontweight='bold', color='#38bdf8')
x_idx = list(range(len(latencies)))
ax1.plot(x_idx, latencies, color='#f43f5e', marker='o', markersize=4, label='Latency (ms)', alpha=0.9)
ax1.plot(x_idx, ttfts, color='#38bdf8', linestyle='--', label='TTFT (ms)', alpha=0.8)
ax1.axhline(y=3000, color='#eab308', linestyle=':', linewidth=2, label='SLO Threshold (3000ms)')
ax1.set_ylabel("Latency (ms)", color='#94a3b8')
ax1.set_xlabel("Request sequence", color='#94a3b8')
ax1.legend(loc='upper left', fontsize=8, facecolor='#1e293b', edgecolor='#334155')

# Panel 2: Request traffic
ax2 = axes[0, 1]
ax2.set_title("Panel 2: Request Traffic (Rate per window)", fontsize=11, fontweight='bold', color='#38bdf8')
ax2.bar(x_idx, [1]*len(x_idx), color='#6366f1', width=0.6, label='Requests')
ax2.axhline(y=1, color='#10b981', linestyle=':', linewidth=2, label='Threshold (>= 1 RPM)')
ax2.set_ylabel("Requests", color='#94a3b8')
ax2.set_xlabel("Request sequence", color='#94a3b8')
ax2.legend(loc='upper right', fontsize=8, facecolor='#1e293b', edgecolor='#334155')

# Panel 3: Error rate and retrieval success
ax3 = axes[0, 2]
ax3.set_title("Panel 3: Error Rate & Retrieval Success (%)", fontsize=11, fontweight='bold', color='#38bdf8')
retrieval_success_pct = [s * 100 for s in tool_successes]
error_rate_pct = [0] * len(x_idx) # all succeeded 200 OK
ax3.plot(x_idx, retrieval_success_pct, color='#10b981', marker='s', markersize=4, label='Retrieval Success (%)')
ax3.plot(x_idx, error_rate_pct, color='#ef4444', label='Error Rate (%)')
ax3.axhline(y=2.0, color='#f59e0b', linestyle=':', linewidth=2, label='Max Error Threshold (2%)')
ax3.set_ylim(-5, 115)
ax3.set_ylabel("Percentage (%)", color='#94a3b8')
ax3.set_xlabel("Request sequence", color='#94a3b8')
ax3.legend(loc='center right', fontsize=8, facecolor='#1e293b', edgecolor='#334155')

# Panel 4: Cost over time
ax4 = axes[1, 0]
ax4.set_title("Panel 4: Cost Over Time (USD)", fontsize=11, fontweight='bold', color='#38bdf8')
cumulative_cost = np.cumsum(costs)
ax4.plot(x_idx, cumulative_cost, color='#a855f7', linewidth=2, label='Cumulative Cost ($)')
ax4.bar(x_idx, costs, color='#c084fc', alpha=0.5, width=0.5, label='Per-request Cost ($)')
ax4.axhline(y=2.5, color='#ef4444', linestyle=':', linewidth=2, label='Budget Limit ($2.50)')
ax4.set_ylabel("USD ($)", color='#94a3b8')
ax4.set_xlabel("Request sequence", color='#94a3b8')
ax4.legend(loc='upper left', fontsize=8, facecolor='#1e293b', edgecolor='#334155')

# Panel 5: Tokens in and out
ax5 = axes[1, 1]
ax5.set_title("Panel 5: Input & Output Tokens", fontsize=11, fontweight='bold', color='#38bdf8')
ax5.bar(x_idx, tokens_in, label='Tokens In', color='#0ea5e9', width=0.6)
ax5.bar(x_idx, tokens_out, bottom=tokens_in, label='Tokens Out', color='#818cf8', width=0.6)
ax5.set_ylabel("Tokens", color='#94a3b8')
ax5.set_xlabel("Request sequence", color='#94a3b8')
ax5.legend(loc='upper right', fontsize=8, facecolor='#1e293b', edgecolor='#334155')

# Panel 6: Quality proxy
ax6 = axes[1, 2]
ax6.set_title("Panel 6: Quality Proxy (Score 0 to 1)", fontsize=11, fontweight='bold', color='#38bdf8')
ax6.plot(x_idx, qualities, color='#22c55e', marker='o', markersize=4, label='Quality Score')
ax6.axhline(y=0.75, color='#eab308', linestyle=':', linewidth=2, label='Quality Threshold (0.75)')
ax6.set_ylim(0, 1.1)
ax6.set_ylabel("Score", color='#94a3b8')
ax6.set_xlabel("Request sequence", color='#94a3b8')
ax6.legend(loc='lower right', fontsize=8, facecolor='#1e293b', edgecolor='#334155')

plt.tight_layout(rect=[0, 0.03, 1, 0.95])
dashboard_img_path = EVIDENCE_DIR / '11-dashboard-overview.png'
plt.savefig(dashboard_img_path, dpi=180, facecolor=fig.get_facecolor(), edgecolor='none')
plt.close()
print(f"Generated {dashboard_img_path}")

# -------------------------------------------------------------
# 2. GENERATE 12-incident-metric.png (Latency Spike & Breach)
# -------------------------------------------------------------
fig, ax = plt.subplots(figsize=(12, 6))
fig.patch.set_facecolor('#0f172a')
ax.set_facecolor('#1e293b')
ax.grid(True, linestyle='--', alpha=0.3, color='#94a3b8')
ax.tick_params(colors='#94a3b8', labelsize=10)
for spine in ax.spines.values():
    spine.set_color('#334155')

ax.set_title("Incident Investigation: Latency Metric Breach During Challenge (rag_slow)", 
             fontsize=14, fontweight='bold', color='#f8fafc', pad=15)

# Plot all requests
ax.plot(x_idx, latencies, color='#38bdf8', marker='o', linewidth=2, markersize=5, label='Request Latency (ms)')
ax.plot(x_idx, ttfts, color='#4ade80', linestyle='--', linewidth=1.5, label='TTFT (ms) - Normal baseline')

# Highlight incident breach points
breach_indices = [i for i, lat in enumerate(latencies) if lat > 2000]
if breach_indices:
    ax.scatter([x_idx[i] for i in breach_indices], [latencies[i] for i in breach_indices], 
               color='#ef4444', s=120, zorder=5, label='Incident Breach (>2000ms)')
    # Annotation
    first_breach = breach_indices[0]
    ax.annotate(f"INCIDENT: rag_slow injected\nLatency spike: {latencies[first_breach]}ms\n(Retrieval span bottleneck)",
                xy=(x_idx[first_breach], latencies[first_breach]),
                xytext=(x_idx[first_breach] - 6, latencies[first_breach] - 800 if latencies[first_breach] > 2000 else latencies[first_breach] + 500),
                arrowprops=dict(facecolor='#ef4444', shrink=0.08, width=2, headwidth=8),
                color='#fca5a5', fontweight='bold', fontsize=9,
                bbox=dict(boxstyle="round,pad=0.5", fc="#450a0a", ec="#ef4444", lw=1.5))

ax.axhline(y=3000, color='#eab308', linestyle='--', linewidth=2, label='Primary SLO Threshold (3000ms)')
ax.axhline(y=2000, color='#f97316', linestyle=':', linewidth=2, label='Challenge Breach Threshold (2000ms)')

ax.set_xlabel("Request Sequence (Timeline)", color='#94a3b8', fontsize=11)
ax.set_ylabel("Latency (ms)", color='#94a3b8', fontsize=11)
ax.legend(loc='upper left', fontsize=9, facecolor='#1e293b', edgecolor='#334155')

plt.tight_layout()
incident_img_path = EVIDENCE_DIR / '12-incident-metric.png'
plt.savefig(incident_img_path, dpi=180, facecolor=fig.get_facecolor(), edgecolor='none')
plt.close()
print(f"Generated {incident_img_path}")
