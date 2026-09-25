"""Self-contained FastAPI service and monitoring demo.

Run with: uvicorn monitoring:app --reload
"""
from __future__ import annotations

import asyncio
import os
import platform
import time
from collections import Counter as RequestCounts, deque
from datetime import datetime, timezone
from threading import Lock
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
import psutil
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, make_asgi_app

app = FastAPI(
    title="API Monitoring Demo",
    description="Sample REST API with request metrics, alerts, and failure diagnostics.",
    version="1.0.0",
)

# Keep labels bounded: use the registered route template (for example, /users/{id})
# instead of arbitrary URL paths that may contain user supplied values.
METRICS = CollectorRegistry()
HTTP_REQUESTS = Counter(
    "api_http_requests_total", "HTTP requests handled by the API",
    ("method", "path", "status"), registry=METRICS,
)
HTTP_DURATION = Histogram(
    "api_http_request_duration_seconds", "HTTP request duration in seconds",
    ("method", "path"),
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
    registry=METRICS,
)
PROCESS_START = Gauge("api_process_start_time_seconds", "API process start time", registry=METRICS)
PROCESS_START.set(time.time())
CPU_PERCENT = Gauge("api_host_cpu_percent", "Host CPU utilization percent", registry=METRICS)
MEMORY_PERCENT = Gauge("api_host_memory_percent", "Host memory utilization percent", registry=METRICS)

_lock = Lock()
_started = time.time()
_requests: RequestCounts[tuple[str, str, int]] = RequestCounts()
_latencies: dict[str, deque[float]] = {}
_events: deque[dict[str, Any]] = deque(maxlen=100)
_rate_limit: deque[float] = deque()
ALERT_ERROR_PERCENT = float(os.getenv("ALERT_ERROR_PERCENT", "10"))
ALERT_LATENCY_MS = float(os.getenv("ALERT_LATENCY_MS", "1000"))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@app.middleware("http")
async def collect_metrics(request: Request, call_next):
    if request.url.path == "/metrics":
        return await call_next(request)
    started = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    except Exception as exc:
        with _lock:
            _events.append({"time": utc_now(), "type": "exception", "route": request.url.path,
                            "status": 500, "cause": f"{type(exc).__name__}: {exc}"})
        raise
    finally:
        elapsed = (time.perf_counter() - started) * 1000
        route = request.scope.get("route")
        route_path = getattr(route, "path", request.url.path)
        method = request.method
        with _lock:
            _requests[(method, route_path, status)] += 1
            _latencies.setdefault(route_path, deque(maxlen=500)).append(elapsed)
            if status >= 500:
                cause = "Simulated server failure" if route_path == "/simulate-error" else "Server returned an error"
                _events.append({"time": utc_now(), "type": "http_error", "route": route_path,
                                "status": status, "cause": cause})
        HTTP_REQUESTS.labels(method, route_path, str(status)).inc()
        HTTP_DURATION.labels(method, route_path).observe(time.perf_counter() - started)
        CPU_PERCENT.set(psutil.cpu_percent(interval=None))
        MEMORY_PERCENT.set(psutil.virtual_memory().percent)


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def dashboard():
    return DASHBOARD


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "Sample FastAPI", "timestamp": utc_now()}


@app.get("/users")
async def users():
    return {"users": [{"id": 1, "name": "Avery Chen"}, {"id": 2, "name": "Jordan Lee"}]}


@app.get("/products")
async def products():
    return {"products": [{"id": "p-101", "name": "Demo keyboard", "price": 79.99},
                         {"id": "p-102", "name": "Demo mouse", "price": 39.5}]}


@app.get("/simulate-error")
async def simulate_error():
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=500, content={"error": "SimulatedInternalError",
                                                  "message": "Intentional failure for alert testing.",
                                                  "timestamp": utc_now()})


@app.get("/simulate-timeout")
async def simulate_timeout(delay: float = 3):
    delay = max(0, min(delay, 30))
    await asyncio.sleep(delay)
    return {"status": "ok", "delayed_seconds": delay, "timestamp": utc_now()}


@app.get("/simulate-rate-limit")
async def simulate_rate_limit():
    from fastapi.responses import JSONResponse
    now = time.monotonic()
    with _lock:
        while _rate_limit and now - _rate_limit[0] > 60:
            _rate_limit.popleft()
        if len(_rate_limit) >= 5:
            retry = max(1, int(60 - (now - _rate_limit[0])))
            return JSONResponse(status_code=429, headers={"Retry-After": str(retry)},
                                content={"error": "TooManyRequests", "retry_after_seconds": retry})
        _rate_limit.append(now)
        remaining = 5 - len(_rate_limit)
    return {"status": "ok", "remaining_requests": remaining, "window_seconds": 60}


def snapshot() -> dict[str, Any]:
    with _lock:
        counts = _requests
        latencies = {route: list(values) for route, values in _latencies.items()}
        events = list(_events)
    total = sum(counts.values())
    errors = sum(count for (_, _, status), count in counts.items() if status >= 400)
    server_errors = sum(count for (_, _, status), count in counts.items() if status >= 500)
    all_latency = sorted(value for values in latencies.values() for value in values)
    p95 = all_latency[min(len(all_latency) - 1, int(len(all_latency) * .95))] if all_latency else 0
    by_route: dict[str, dict[str, Any]] = {}
    for (method, route, status), count in counts.items():
        item = by_route.setdefault(route, {"requests": 0, "errors": 0, "statuses": {}})
        item["requests"] += count
        item["errors"] += count if status >= 400 else 0
        item["statuses"][str(status)] = item["statuses"].get(str(status), 0) + count
    for route, item in by_route.items():
        values = sorted(latencies.get(route, []))
        item["avg_ms"] = round(sum(values) / len(values), 1) if values else 0
        item["p95_ms"] = round(values[min(len(values)-1, int(len(values)*.95))], 1) if values else 0
    alerts = []
    error_pct = errors / total * 100 if total else 0
    if error_pct >= ALERT_ERROR_PERCENT:
        alerts.append({"severity": "critical", "title": "Elevated error rate",
                       "detail": f"{error_pct:.1f}% of requests returned 4xx/5xx (threshold {ALERT_ERROR_PERCENT:g}%)."})
    if p95 >= ALERT_LATENCY_MS:
        alerts.append({"severity": "warning", "title": "High response latency",
                       "detail": f"Recent p95 latency is {p95:.0f} ms (threshold {ALERT_LATENCY_MS:g} ms)."})
    return {"status": "healthy" if not server_errors else "degraded", "uptime_seconds": int(time.time()-_started),
            "total_requests": total, "failed_requests": errors, "server_errors": server_errors,
            "error_percent": round(error_pct, 2), "avg_response_ms": round(sum(all_latency)/len(all_latency), 1) if all_latency else 0,
            "p95_response_ms": round(p95, 1), "routes": by_route, "alerts": alerts,
            "events": events[-20:], "timestamp": utc_now(),
            "server": {"hostname": platform.node(), "platform": platform.system(), "python": platform.python_version(),
                       "cpu_percent": psutil.cpu_percent(interval=None),
                       "memory_percent": psutil.virtual_memory().percent}}


@app.get("/api/monitoring/summary")
async def monitoring_summary():
    return snapshot()


app.mount("/metrics", make_asgi_app(registry=METRICS))


DASHBOARD = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>API Monitor</title><style>
:root{color-scheme:dark;--bg:#0b1020;--panel:#121a2d;--line:#26334c;--muted:#91a0ba;--text:#eef3ff;--green:#48d597;--red:#ff7185;--amber:#ffc66d;--blue:#7aa9ff}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(ellipse at 15% 0,#182647 0,transparent 40%),var(--bg);color:var(--text);font:14px/1.5 Inter,Segoe UI,Arial,sans-serif}main{max-width:1200px;margin:0 auto;padding:36px 24px 60px}.top{display:flex;align-items:center;justify-content:space-between;gap:20px;margin-bottom:28px}.eyebrow{color:var(--blue);font-size:11px;font-weight:800;letter-spacing:.17em;text-transform:uppercase}h1{font-size:29px;margin:4px 0}.sub,.muted{color:var(--muted)}.live{display:flex;align-items:center;gap:9px;color:var(--green);font-weight:700}.dot{width:8px;height:8px;border-radius:99px;background:currentColor;box-shadow:0 0 15px currentColor}.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:13px;margin-bottom:16px}.card,.panel{background:linear-gradient(145deg,rgba(20,30,51,.98),rgba(15,23,40,.98));border:1px solid var(--line);border-radius:13px}.card{padding:17px}.label{font-size:12px;color:var(--muted)}.value{font-size:27px;font-weight:750;margin-top:7px}.hint{font-size:11px;color:var(--muted)}.layout{display:grid;grid-template-columns:1.25fr .75fr;gap:15px}.panel{padding:18px;margin-bottom:15px}.panel h2{font-size:15px;margin:0 0 14px}.table{width:100%;border-collapse:collapse;text-align:left}.table th{color:var(--muted);font-size:11px;font-weight:600}.table th,.table td{border-bottom:1px solid #202b41;padding:10px 8px}.table tr:last-child td{border-bottom:0}code,.pill{font:12px ui-monospace,Consolas,monospace}.pill{border:1px solid var(--line);border-radius:6px;padding:3px 6px;color:#c8d5ee}.status{font-weight:750}.ok{color:var(--green)}.bad{color:var(--red)}.warn{color:var(--amber)}.alert{border:1px solid #653b43;background:#2a1b29;border-radius:9px;padding:12px;margin:8px 0}.alert.warnbox{border-color:#59482f;background:#28251e}.alert strong{display:block;margin-bottom:3px}.event{padding:11px 0;border-bottom:1px solid #202b41}.event:last-child{border-bottom:0}.event-title{display:flex;justify-content:space-between;gap:12px}.actions{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0}.actions a{color:#cfe0ff;text-decoration:none;border:1px solid #344563;padding:7px 10px;border-radius:7px;font-size:12px}.actions a:hover{background:#1d2a44}.foot{font-size:11px;color:var(--muted);margin-top:4px}.empty{color:var(--muted);padding:8px 0}@media(max-width:800px){.cards{grid-template-columns:repeat(2,1fr)}.layout{grid-template-columns:1fr}}@media(max-width:480px){main{padding:24px 14px}.top{align-items:flex-start;flex-direction:column}.cards{gap:8px}.value{font-size:23px}}
</style></head><body><main>
<div class="top"><div><div class="eyebrow">Operations / Service health</div><h1>API Monitoring</h1><div class="sub">Sample REST API · request health, latency, failures and alerts</div></div><div class="live"><span class="dot" id="dot"></span><span id="health">Connecting</span></div></div>
<section class="cards"><div class="card"><div class="label">Availability</div><div class="value" id="availability">—</div><div class="hint">Process health check</div></div><div class="card"><div class="label">Requests observed</div><div class="value" id="requests">—</div><div class="hint">Since this process started</div></div><div class="card"><div class="label">Error percentage</div><div class="value" id="errors">—</div><div class="hint">HTTP 4xx and 5xx responses</div></div><div class="card"><div class="label">Response time · p95</div><div class="value" id="latency">—</div><div class="hint">Recent request samples</div></div></section>
<div class="layout"><div><section class="panel"><h2>Endpoint performance</h2><table class="table"><thead><tr><th>ROUTE</th><th>REQUESTS</th><th>ERRORS</th><th>AVG / P95</th><th>HTTP STATUS</th></tr></thead><tbody id="routes"><tr><td colspan="5" class="empty">Waiting for requests…</td></tr></tbody></table></section><section class="panel"><h2>Try the API · create monitoring signals</h2><div class="actions"><a href="/health" target="_blank">Healthy check</a><a href="/users" target="_blank">Sample users</a><a href="/products" target="_blank">Sample products</a><a href="/simulate-timeout?delay=2" target="_blank">Slow response (2s)</a><a href="/simulate-error" target="_blank">Trigger HTTP 500</a><a href="/simulate-rate-limit" target="_blank">Rate limit (6× for 429)</a><a href="/metrics" target="_blank">Prometheus metrics</a><a href="/docs" target="_blank">API docs</a></div><div class="foot">Metrics and alerts update every 2 seconds. Rate limit allows 5 requests per minute.</div></section></div>
<div><section class="panel"><h2>Active alerts</h2><div id="alerts" class="empty">No active alerts</div></section><section class="panel"><h2>Recent failure events · root cause</h2><div id="events" class="empty">No failures recorded</div></section><section class="panel"><h2>Server health</h2><div id="server" class="muted">Loading…</div></section></div></div><div class="foot" id="updated">Connecting to monitoring API…</div></main>
<script>
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function refresh(){try{const r=await fetch('/api/monitoring/summary',{cache:'no-store'});if(!r.ok)throw Error('HTTP '+r.status);const d=await r.json();const up=d.status==='healthy';document.getElementById('health').textContent=up?'Operational':'Degraded';document.getElementById('health').className=up?'ok':'bad';document.getElementById('dot').style.color=up?'var(--green)':'var(--red)';document.getElementById('availability').textContent=up?'UP':'DEGRADED';document.getElementById('availability').className='value '+(up?'ok':'bad');document.getElementById('requests').textContent=d.total_requests.toLocaleString();document.getElementById('errors').textContent=d.error_percent+'%';document.getElementById('errors').className='value '+(d.error_percent?'warn':'ok');document.getElementById('latency').textContent=d.p95_response_ms+' ms';document.getElementById('server').innerHTML=`<div>Host <b>${esc(d.server.hostname)}</b></div><div>OS <b>${esc(d.server.platform)}</b> · Python <b>${esc(d.server.python)}</b></div><div>Process uptime <b>${Math.floor(d.uptime_seconds/60)}m ${d.uptime_seconds%60}s</b></div><div>CPU <b>${d.server.cpu_percent}%</b> · Memory <b>${d.server.memory_percent}%</b></div><div>Server errors <b class="${d.server_errors?'bad':'ok'}">${d.server_errors}</b></div>`;
const routes=Object.entries(d.routes);document.getElementById('routes').innerHTML=routes.length?routes.map(([path,x])=>`<tr><td><code>${esc(path)}</code></td><td>${x.requests}</td><td class="${x.errors?'bad':'ok'}">${x.errors}</td><td>${x.avg_ms} / ${x.p95_ms} ms</td><td>${Object.entries(x.statuses).map(([s,n])=>`<span class="pill">${s} × ${n}</span>`).join(' ')}</td></tr>`).join(''):'<tr><td colspan="5" class="empty">Waiting for requests…</td></tr>';
document.getElementById('alerts').innerHTML=d.alerts.length?d.alerts.map(a=>`<div class="alert ${a.severity==='warning'?'warnbox':''}"><strong class="${a.severity==='warning'?'warn':'bad'}">${esc(a.severity.toUpperCase())} · ${esc(a.title)}</strong><span>${esc(a.detail)}</span></div>`).join(''):'<div class="empty">No active alerts</div>';
document.getElementById('events').innerHTML=d.events.length?[...d.events].reverse().map(e=>`<div class="event"><div class="event-title"><b class="bad">HTTP ${e.status} · ${esc(e.route)}</b><span class="muted">${new Date(e.time).toLocaleTimeString()}</span></div><div class="muted">Cause: ${esc(e.cause)}</div><div class="muted">Check the endpoint behavior and downstream dependencies.</div></div>`).join(''):'<div class="empty">No failures recorded</div>';document.getElementById('updated').textContent='Last refreshed '+new Date(d.timestamp).toLocaleTimeString()+' · auto refresh 2s';}catch(e){document.getElementById('health').textContent='Unreachable';document.getElementById('health').className='bad';document.getElementById('dot').style.color='var(--red)';document.getElementById('availability').textContent='DOWN';document.getElementById('availability').className='value bad';document.getElementById('updated').textContent='Monitoring API unavailable: '+e.message}}
refresh();setInterval(refresh,2000);
</script></body></html>'''
