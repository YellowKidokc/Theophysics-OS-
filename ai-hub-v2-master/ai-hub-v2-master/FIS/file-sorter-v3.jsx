import { useState, useEffect, useCallback, useRef } from "react";

const API = "http://127.0.0.1:8450";

const DOMAIN_COLORS = {
  THEOPHYSICS: { bg: "#1a1a2e", fg: "#e8d5b7", border: "#c9a96e" },
  DEVELOPMENT: { bg: "#0d1b2a", fg: "#a8d8ea", border: "#5fa8d3" },
  DATA_TRADING: { bg: "#1b2d1b", fg: "#b8e6b8", border: "#6db86d" },
  BUSINESS: { bg: "#2d1b2d", fg: "#e6b8e6", border: "#b86db8" },
  AI_ML: { bg: "#1b1b2d", fg: "#b8b8e6", border: "#6d6db8" },
  INFRASTRUCTURE: { bg: "#2d2d1b", fg: "#e6e6b8", border: "#b8b86d" },
  MEDIA: { bg: "#2d1b1b", fg: "#e6b8b8", border: "#b86d6d" },
  DOCUMENTS: { bg: "#1b2d2d", fg: "#b8e6e6", border: "#6db8b8" },
  IMAGES: { bg: "#2d261b", fg: "#e6dab8", border: "#b8a86d" },
  PERSONAL: { bg: "#261b2d", fg: "#dab8e6", border: "#a86db8" },
  UNCATEGORIZED: { bg: "#1a1a1a", fg: "#999", border: "#555" },
};

const SOURCE_LABELS = { yake: "Keywords", deberta: "DeBERTa", ollama: "Ollama", markov: "Learned" };

const formatSize = (b) => {
  if (b < 1024) return b + " B";
  if (b < 1048576) return (b / 1024).toFixed(1) + " KB";
  return (b / 1048576).toFixed(1) + " MB";
};

function DomainBadge({ domain, small, onClick }) {
  const c = DOMAIN_COLORS[domain] || DOMAIN_COLORS.UNCATEGORIZED;
  return (
    <span
      onClick={onClick}
      style={{
        display: "inline-block",
        padding: small ? "1px 6px" : "2px 8px",
        borderRadius: 3,
        fontSize: small ? 10 : 11,
        fontWeight: 600,
        letterSpacing: 0.5,
        background: c.bg,
        color: c.fg,
        border: `1px solid ${c.border}`,
        cursor: onClick ? "pointer" : "default",
        transition: "opacity 0.15s",
      }}
    >
      {domain}
    </span>
  );
}

function ConfBar({ value, source }) {
  const color = value >= 70 ? "#4a9" : value >= 40 ? "#da5" : "#d55";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <div style={{ width: 60, height: 6, background: "#222", borderRadius: 3, overflow: "hidden" }}>
        <div style={{ width: `${Math.min(value, 100)}%`, height: "100%", background: color, borderRadius: 3, transition: "width 0.3s" }} />
      </div>
      <span style={{ fontSize: 11, color: "#888", minWidth: 30 }}>{value}%</span>
      {source && source !== "yake" && (
        <span style={{ fontSize: 9, color: "#666", background: "#1a1a1a", padding: "1px 4px", borderRadius: 2 }}>
          {SOURCE_LABELS[source] || source}
        </span>
      )}
    </div>
  );
}

function StatsPanel({ stats, onClose }) {
  if (!stats) return null;
  const acc = stats.accuracy || 0;
  const accColor = acc >= 90 ? "#4a9" : acc >= 75 ? "#da5" : "#d55";
  return (
    <div style={{ background: "#111", border: "1px solid #333", borderRadius: 6, padding: 16, marginBottom: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <span style={{ fontSize: 13, fontWeight: 700, color: "#ccc", letterSpacing: 1 }}>PREFERENCE ENGINE</span>
        <span onClick={onClose} style={{ cursor: "pointer", color: "#666", fontSize: 18 }}>×</span>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 12 }}>
        {[
          { label: "Decisions", val: stats.total_decisions },
          { label: "Accuracy", val: `${acc}%`, color: accColor },
          { label: "Auto-approve", val: `≥${stats.auto_approve_threshold}%` },
          { label: "Keywords", val: stats.unique_keywords_learned },
        ].map((s) => (
          <div key={s.label} style={{ textAlign: "center" }}>
            <div style={{ fontSize: 20, fontWeight: 700, color: s.color || "#eee", fontVariantNumeric: "tabular-nums" }}>{s.val}</div>
            <div style={{ fontSize: 10, color: "#666", marginTop: 2 }}>{s.label}</div>
          </div>
        ))}
      </div>
      {stats.top_corrections?.length > 0 && (
        <div style={{ borderTop: "1px solid #222", paddingTop: 8, marginTop: 4 }}>
          <div style={{ fontSize: 10, color: "#666", marginBottom: 4 }}>TOP CORRECTIONS</div>
          {stats.top_corrections.map((c, i) => (
            <div key={i} style={{ fontSize: 11, color: "#999", display: "flex", gap: 4, alignItems: "center" }}>
              <DomainBadge domain={c.from} small /> <span style={{ color: "#555" }}>→</span> <DomainBadge domain={c.to} small />
              <span style={{ color: "#555", marginLeft: "auto" }}>{c.count}×</span>
            </div>
          ))}
        </div>
      )}
      <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
        <div style={{ fontSize: 10, color: "#555" }}>
          ✓ {stats.approvals || 0} approved · ✎ {stats.overrides || 0} overridden · ✗ {stats.rejects || 0} rejected
        </div>
      </div>
    </div>
  );
}

export default function FileSorterV3() {
  const [scanPath, setScanPath] = useState("");
  const [files, setFiles] = useState([]);
  const [selected, setSelected] = useState(new Set());
  const [domainFilter, setDomainFilter] = useState(null);
  const [sortBy, setSortBy] = useState("confidence");
  const [threshold, setThreshold] = useState(30);
  const [stats, setStats] = useState(null);
  const [showStats, setShowStats] = useState(false);
  const [loading, setLoading] = useState(false);
  const [apiOk, setApiOk] = useState(null);
  const [msg, setMsg] = useState("");
  const [overrideFile, setOverrideFile] = useState(null);

  useEffect(() => {
    fetch(`${API}/api/stats`).then((r) => r.json()).then((d) => { setApiOk(true); setStats(d); }).catch(() => setApiOk(false));
  }, []);

  const flash = (m) => { setMsg(m); setTimeout(() => setMsg(""), 3000); };

  const doScan = async () => {
    if (!scanPath.trim()) return;
    setLoading(true); setFiles([]); setSelected(new Set());
    try {
      const r = await fetch(`${API}/api/scan?path=${encodeURIComponent(scanPath)}&top=true`);
      const d = await r.json();
      if (d.error) { flash(`Error: ${d.error}`); setLoading(false); return; }
      setFiles(d.files.map((f, i) => ({ ...f, id: i, status: f.auto_approve ? "auto" : "pending" })));
      flash(`Scanned ${d.total} files`);
    } catch (e) { flash("API unreachable — run: python api_server.py"); }
    setLoading(false);
  };

  const toggleSelect = (id) => setSelected((prev) => { const n = new Set(prev); n.has(id) ? n.delete(id) : n.add(id); return n; });
  const selectAll = () => setSelected(new Set(files.map((f) => f.id)));
  const selectNone = () => setSelected(new Set());
  const selectInvert = () => setSelected(new Set(files.filter((f) => !selected.has(f.id)).map((f) => f.id)));
  const selectBelow = () => setSelected(new Set(files.filter((f) => f.confidence < threshold).map((f) => f.id)));

  const submitDecisions = async (action, overrideDomain) => {
    const targets = files.filter((f) => selected.has(f.id));
    if (!targets.length) return;
    const decisions = targets.map((f) => ({
      filename: f.filename, ext: f.ext, keywords: f.keywords || [],
      proposed_domain: f.domain,
      final_domain: overrideDomain || f.domain,
      confidence: f.confidence,
      action: overrideDomain && overrideDomain !== f.domain ? "override" : action,
      source: f.source || "yake",
    }));
    try {
      const r = await fetch(`${API}/api/decide`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decisions }),
      });
      const d = await r.json();
      setFiles((prev) => prev.map((f) => {
        if (!selected.has(f.id)) return f;
        return { ...f, status: action === "reject" ? "rejected" : "approved", domain: overrideDomain || f.domain };
      }));
      setSelected(new Set());
      setStats((prev) => ({ ...prev, total_decisions: d.total_decisions, accuracy: d.accuracy, auto_approve_threshold: d.auto_approve_threshold }));
      flash(`${action === "reject" ? "Rejected" : "Recorded"} ${d.recorded} decisions — accuracy: ${d.accuracy}%`);
    } catch (e) { flash("API error — check server"); }
  };

  const runNLP = async () => {
    const targets = files.filter((f) => selected.has(f.id));
    if (!targets.length) return;
    setLoading(true); flash(`Running NLP on ${targets.length} files...`);
    try {
      const r = await fetch(`${API}/api/nlp-classify`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ files: targets.map((f) => f.filepath) }),
      });
      const d = await r.json();
      if (d.results) {
        setFiles((prev) => prev.map((f) => {
          const match = d.results.find((nr) => nr.filepath === f.filepath);
          if (!match) return f;
          return { ...f, domain: match.domain, confidence: match.confidence, source: match.source, nlp_summary: match.nlp_summary };
        }));
        flash(`NLP classified ${d.results.length} files`);
      }
    } catch (e) { flash("NLP failed — check models on X:\\Models"); }
    setLoading(false);
  };

  const domains = [...new Set(files.map((f) => f.domain))].sort();
  const visible = files
    .filter((f) => !domainFilter || f.domain === domainFilter)
    .sort((a, b) => {
      if (sortBy === "confidence") return a.confidence - b.confidence;
      if (sortBy === "name") return a.filename.localeCompare(b.filename);
      if (sortBy === "size") return b.size - a.size;
      if (sortBy === "domain") return a.domain.localeCompare(b.domain);
      return 0;
    });
  const pendingCount = files.filter((f) => f.status === "pending" || f.status === "auto").length;
  const approvedCount = files.filter((f) => f.status === "approved").length;

  return (
    <div style={{ fontFamily: "'SF Mono', 'Fira Code', 'Cascadia Code', monospace", background: "#0a0a0a", color: "#ccc", minHeight: "100vh", padding: "16px 20px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <div>
          <span style={{ fontSize: 16, fontWeight: 700, color: "#eee", letterSpacing: 1 }}>FILE SORTER</span>
          <span style={{ fontSize: 11, color: "#555", marginLeft: 8 }}>v3 — closed loop</span>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: apiOk === true ? "#4a9" : apiOk === false ? "#d55" : "#555" }} />
          <span style={{ fontSize: 10, color: "#666" }}>{apiOk === true ? "API connected" : apiOk === false ? "API offline" : "checking..."}</span>
          <button onClick={() => { setShowStats(!showStats); if (!showStats) fetch(`${API}/api/stats`).then(r => r.json()).then(setStats).catch(() => {}); }}
            style={{ background: "#1a1a1a", border: "1px solid #333", color: "#888", padding: "3px 10px", borderRadius: 3, cursor: "pointer", fontSize: 11 }}>
            {showStats ? "Hide" : "Engine"} Stats
          </button>
        </div>
      </div>

      {showStats && <StatsPanel stats={stats} onClose={() => setShowStats(false)} />}

      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <input value={scanPath} onChange={(e) => setScanPath(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && doScan()}
          placeholder="C:\Users\lowes\Desktop"
          style={{ flex: 1, background: "#111", border: "1px solid #333", borderRadius: 3, padding: "6px 10px", color: "#eee", fontSize: 12, fontFamily: "inherit" }} />
        <button onClick={doScan} disabled={loading}
          style={{ background: "#1a2a1a", border: "1px solid #3a5a3a", color: "#8c8", padding: "6px 16px", borderRadius: 3, cursor: loading ? "wait" : "pointer", fontSize: 12, fontWeight: 600 }}>
          {loading ? "Scanning..." : "Scan"}
        </button>
      </div>

      {msg && <div style={{ background: "#1a1a2e", border: "1px solid #333", borderRadius: 3, padding: "6px 12px", marginBottom: 10, fontSize: 11, color: "#aac" }}>{msg}</div>}

      {files.length > 0 && (
        <>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 10, alignItems: "center" }}>
            <span style={{ fontSize: 10, color: "#555", marginRight: 4 }}>FILTER:</span>
            <span onClick={() => setDomainFilter(null)}
              style={{ fontSize: 10, padding: "2px 8px", borderRadius: 3, cursor: "pointer", background: !domainFilter ? "#333" : "#111", color: !domainFilter ? "#eee" : "#666", border: "1px solid #333" }}>
              ALL ({files.length})
            </span>
            {domains.map((d) => {
              const count = files.filter((f) => f.domain === d).length;
              return (
                <span key={d} onClick={() => setDomainFilter(domainFilter === d ? null : d)} style={{ cursor: "pointer", opacity: domainFilter && domainFilter !== d ? 0.4 : 1 }}>
                  <DomainBadge domain={d} small /> <span style={{ fontSize: 9, color: "#555" }}>{count}</span>
                </span>
              );
            })}
          </div>

          <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 10, flexWrap: "wrap" }}>
            <div style={{ display: "flex", gap: 4 }}>
              {[{ label: "All", fn: selectAll }, { label: "None", fn: selectNone }, { label: "Invert", fn: selectInvert }].map((b) => (
                <button key={b.label} onClick={b.fn}
                  style={{ background: "#111", border: "1px solid #333", color: "#888", padding: "2px 8px", borderRadius: 3, cursor: "pointer", fontSize: 10 }}>
                  {b.label}
                </button>
              ))}
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 4, borderLeft: "1px solid #222", paddingLeft: 8 }}>
              <span style={{ fontSize: 10, color: "#555" }}>Threshold:</span>
              <input type="range" min={0} max={100} value={threshold} onChange={(e) => setThreshold(+e.target.value)} style={{ width: 80, accentColor: "#da5" }} />
              <span style={{ fontSize: 11, color: "#da5", fontWeight: 600, minWidth: 28 }}>{threshold}%</span>
              <button onClick={selectBelow}
                style={{ background: "#2a1a1a", border: "1px solid #5a3a3a", color: "#d88", padding: "2px 8px", borderRadius: 3, cursor: "pointer", fontSize: 10 }}>
                Below {threshold}%
              </button>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 4, borderLeft: "1px solid #222", paddingLeft: 8 }}>
              <span style={{ fontSize: 10, color: "#555" }}>Sort:</span>
              {["confidence", "name", "size", "domain"].map((s) => (
                <button key={s} onClick={() => setSortBy(s)}
                  style={{ background: sortBy === s ? "#222" : "#111", border: "1px solid #333", color: sortBy === s ? "#eee" : "#666", padding: "2px 6px", borderRadius: 3, cursor: "pointer", fontSize: 10 }}>
                  {s}
                </button>
              ))}
            </div>
            {selected.size > 0 && (
              <span style={{ fontSize: 11, color: "#aac", fontWeight: 600, borderLeft: "1px solid #222", paddingLeft: 8 }}>
                {selected.size} selected
              </span>
            )}
          </div>

          {selected.size > 0 && (
            <div style={{ display: "flex", gap: 6, marginBottom: 10, padding: "8px 12px", background: "#111", border: "1px solid #333", borderRadius: 4 }}>
              <button onClick={() => submitDecisions("approve")}
                style={{ background: "#1a2a1a", border: "1px solid #3a5a3a", color: "#8c8", padding: "4px 14px", borderRadius: 3, cursor: "pointer", fontSize: 11, fontWeight: 600 }}>
                ✓ Approve ({selected.size})
              </button>
              <button onClick={() => submitDecisions("reject")}
                style={{ background: "#2a1a1a", border: "1px solid #5a3a3a", color: "#d88", padding: "4px 14px", borderRadius: 3, cursor: "pointer", fontSize: 11, fontWeight: 600 }}>
                ✗ Reject ({selected.size})
              </button>
              <button onClick={runNLP} disabled={loading}
                style={{ background: "#1a1a2a", border: "1px solid #3a3a5a", color: "#88c", padding: "4px 14px", borderRadius: 3, cursor: "pointer", fontSize: 11, fontWeight: 600 }}>
                🧠 NLP Classify
              </button>
              <div style={{ position: "relative", marginLeft: "auto" }}>
                <button onClick={() => setOverrideFile(overrideFile ? null : "batch")}
                  style={{ background: "#2a2a1a", border: "1px solid #5a5a3a", color: "#cc8", padding: "4px 14px", borderRadius: 3, cursor: "pointer", fontSize: 11, fontWeight: 600 }}>
                  ✎ Override →
                </button>
                {overrideFile === "batch" && (
                  <div style={{ position: "absolute", top: "100%", right: 0, marginTop: 4, background: "#111", border: "1px solid #333", borderRadius: 4, padding: 4, zIndex: 10, display: "flex", flexDirection: "column", gap: 2, minWidth: 140 }}>
                    {Object.keys(DOMAIN_COLORS).filter((d) => d !== "UNCATEGORIZED").map((d) => (
                      <div key={d} onClick={() => { submitDecisions("override", d); setOverrideFile(null); }}
                        style={{ cursor: "pointer", padding: "3px 8px", borderRadius: 3 }}>
                        <DomainBadge domain={d} small />
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
            <div style={{ flex: 1, height: 4, background: "#222", borderRadius: 2, overflow: "hidden" }}>
              <div style={{ width: `${(approvedCount / Math.max(files.length, 1)) * 100}%`, height: "100%", background: "#4a9", borderRadius: 2, transition: "width 0.3s" }} />
            </div>
            <span style={{ fontSize: 10, color: "#555" }}>
              {approvedCount}/{files.length} decided · {pendingCount} pending
            </span>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 1 }}>
            {visible.map((f) => {
              const isSel = selected.has(f.id);
              const statusColor = f.status === "approved" ? "#1a2a1a" : f.status === "rejected" ? "#2a1a1a" : f.status === "auto" ? "#1a1a2a" : "transparent";
              return (
                <div key={f.id} onClick={() => toggleSelect(f.id)}
                  style={{
                    display: "grid", gridTemplateColumns: "24px 1fr 120px 80px 70px",
                    alignItems: "center", gap: 8, padding: "6px 10px",
                    background: isSel ? "#1a1a2e" : statusColor,
                    border: isSel ? "1px solid #3a3a6a" : "1px solid transparent",
                    borderRadius: 3, cursor: "pointer", transition: "background 0.1s",
                  }}>
                  <div style={{ width: 14, height: 14, border: `1px solid ${isSel ? "#6a6aaa" : "#333"}`, borderRadius: 2, background: isSel ? "#3a3a6a" : "transparent", display: "flex", alignItems: "center", justifyContent: "center" }}>
                    {isSel && <span style={{ color: "#aac", fontSize: 10 }}>✓</span>}
                  </div>
                  <div style={{ overflow: "hidden" }}>
                    <div style={{ fontSize: 12, color: "#ddd", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{f.filename}</div>
                    {f.keywords?.length > 0 && (
                      <div style={{ fontSize: 9, color: "#555", marginTop: 1 }}>
                        {f.keywords.slice(0, 3).join(" · ")}
                        {f.markov && f.markov.domain !== f.domain && (
                          <span style={{ color: "#da5", marginLeft: 6 }}>markov→{f.markov.domain} ({f.markov.confidence}%)</span>
                        )}
                      </div>
                    )}
                  </div>
                  <DomainBadge domain={f.domain} />
                  <ConfBar value={f.confidence} source={f.source} />
                  <span style={{ fontSize: 10, color: "#555", textAlign: "right" }}>{formatSize(f.size)}</span>
                </div>
              );
            })}
          </div>

          {visible.length === 0 && (
            <div style={{ textAlign: "center", padding: 40, color: "#444", fontSize: 12 }}>No files match the current filter.</div>
          )}
        </>
      )}

      {files.length === 0 && !loading && (
        <div style={{ textAlign: "center", padding: "60px 20px", color: "#444" }}>
          <div style={{ fontSize: 14, marginBottom: 8 }}>Enter a path and hit Scan</div>
          <div style={{ fontSize: 11, color: "#333" }}>
            Start the API first: <span style={{ color: "#666", fontFamily: "inherit" }}>python api_server.py</span>
          </div>
          <div style={{ fontSize: 11, color: "#333", marginTop: 12 }}>
            Every approve/reject/override trains the Markov chain.<br />
            The more you decide, the faster it gets, until it's automatic.
          </div>
        </div>
      )}
    </div>
  );
}
