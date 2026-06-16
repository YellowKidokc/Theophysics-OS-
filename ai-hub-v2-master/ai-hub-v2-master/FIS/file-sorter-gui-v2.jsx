import { useState, useMemo } from "react";

const DOMAINS = {
  THEOPHYSICS: { code: "TP", color: "#6366f1" },
  DEVELOPMENT: { code: "DV", color: "#22c55e" },
  DOCUMENTS: { code: "DC", color: "#f59e0b" },
  IMAGES: { code: "IM", color: "#3b82f6" },
  AI_ML: { code: "AI", color: "#a855f7" },
  BUSINESS: { code: "BZ", color: "#ef4444" },
  DATA_TRADING: { code: "DT", color: "#14b8a6" },
  INFRASTRUCTURE: { code: "IF", color: "#f97316" },
  MEDIA: { code: "MD", color: "#ec4899" },
  PERSONAL: { code: "PR", color: "#64748b" },
  UNCATEGORIZED: { code: "UC", color: "#94a3b8" },
};

const INITIAL_FILES = [
  { id: 1, name: "auto_sort.py", domain: "DEVELOPMENT", confidence: 76, keywords: ["File Sorter", "max", "TEXT"], ext: ".py", size: 24500, status: "pending" },
  { id: 2, name: "manual_sort.py", domain: "DEVELOPMENT", confidence: 38, keywords: ["python manual", "File Sorter"], ext: ".py", size: 16379, status: "pending" },
  { id: 3, name: "Domain coherence analysis.docx", domain: "DOCUMENTS", confidence: 30, keywords: ["Theophysics Research", "Ordered state"], ext: ".docx", size: 45000, status: "pending" },
  { id: 4, name: "Domain coherence analysis.pdf", domain: "DOCUMENTS", confidence: 30, keywords: ["Theophysics Research", "Research Initiative"], ext: ".pdf", size: 120000, status: "pending" },
  { id: 5, name: "Master_Equation_File_System_Guide.pdf", domain: "DOCUMENTS", confidence: 38, keywords: ["Master Equation", "System Guide"], ext: ".pdf", size: 89000, status: "pending" },
  { id: 6, name: "Open Intel (1) (1).xlsx", domain: "DOCUMENTS", confidence: 30, keywords: ["INTAKE ENGINE", "links"], ext: ".xlsx", size: 496000, status: "pending" },
  { id: 7, name: "moral-dynamics-simulator.jsx", domain: "DEVELOPMENT", confidence: 45, keywords: ["color", "div style", "clamp"], ext: ".jsx", size: 12000, status: "pending" },
  { id: 8, name: "FORGE_PHASE_3_BUILD_PROMPT.md", domain: "AI_ML", confidence: 16, keywords: ["run forge", "npm run", "Context FORGE"], ext: ".md", size: 8500, status: "pending" },
  { id: 9, name: "TEMPLETON_STORY_EXTRACTION_PROMPT.md", domain: "AI_ML", confidence: 15, keywords: ["EXTRACTION PROMPT", "STORY EXTRACTION"], ext: ".md", size: 6200, status: "pending" },
  { id: 10, name: "Screen Shot 2026-06-10 at 01.58.50.47 AM.png", domain: "IMAGES", confidence: 30, keywords: [], ext: ".png", size: 2400000, status: "pending" },
  { id: 11, name: "Screen Shot 2026-06-10 at 01.58.55.812 AM.png", domain: "IMAGES", confidence: 30, keywords: [], ext: ".png", size: 2100000, status: "pending" },
  { id: 12, name: "Screen Shot 2026-06-10 at 01.58.59.972 AM.png", domain: "IMAGES", confidence: 30, keywords: [], ext: ".png", size: 1900000, status: "pending" },
  { id: 13, name: "index.html", domain: "DEVELOPMENT", confidence: 46, keywords: ["div class", "button onclick"], ext: ".html", size: 15000, status: "pending" },
  { id: 14, name: "Bil FIle Naming.xlsx", domain: "DOCUMENTS", confidence: 30, keywords: ["Workbook POF", "Bulk-Review"], ext: ".xlsx", size: 35000, status: "pending" },
  { id: 15, name: "Master EQ FIS.md", domain: "THEOPHYSICS", confidence: 15, keywords: ["Master Equation", "docs"], ext: ".md", size: 4500, status: "pending" },
  { id: 16, name: "POF2828_SERVERS.bat", domain: "THEOPHYSICS", confidence: 8, keywords: ["echo", "Theophysics Service"], ext: ".bat", size: 1200, status: "pending" },
  { id: 17, name: "diag_gpu.py", domain: "DEVELOPMENT", confidence: 38, keywords: ["print", "GPU DRIVER", "GPU CONFIG"], ext: ".py", size: 5600, status: "pending" },
  { id: 18, name: "fix_vm.py", domain: "DEVELOPMENT", confidence: 38, keywords: ["Windows", "physical GPU", "USB"], ext: ".py", size: 7800, status: "pending" },
  { id: 19, name: "Kimi.md", domain: "DEVELOPMENT", confidence: 15, keywords: ["Excel", "Kimi", "Kimi builds"], ext: ".md", size: 3200, status: "pending" },
  { id: 20, name: "This is terrifying.pdf", domain: "DOCUMENTS", confidence: 30, keywords: ["Theophysics Research", "Research Initiative"], ext: ".pdf", size: 156000, status: "pending" },
  { id: 21, name: "1files.zip", domain: "UNCATEGORIZED", confidence: 0, keywords: [], ext: ".zip", size: 45000000, status: "pending" },
  { id: 22, name: "codex.md", domain: "UNCATEGORIZED", confidence: 0, keywords: ["files", "David", "empty"], ext: ".md", size: 2800, status: "pending" },
  { id: 23, name: "check_libs.bat", domain: "DEVELOPMENT", confidence: 30, keywords: ["print", "python", "transformers"], ext: ".bat", size: 900, status: "pending" },
  { id: 24, name: "ARCHIVE_HTML_TO_NAS.bat", domain: "INFRASTRUCTURE", confidence: 15, keywords: ["Drive Cleanup", "FORGE", "NAS"], ext: ".bat", size: 1100, status: "pending" },
  { id: 25, name: "answer.pptx", domain: "DOCUMENTS", confidence: 30, keywords: [], ext: ".pptx", size: 230000, status: "pending" },
  { id: 26, name: "Theophysics_Lean4_Addendum_Updated.xlsx", domain: "DOCUMENTS", confidence: 30, keywords: ["REJECTION Heaviside", "SUMMARY Named"], ext: ".xlsx", size: 67000, status: "pending" },
  { id: 27, name: "Master Equation Reveal.html", domain: "DEVELOPMENT", confidence: 30, keywords: ["Bundled Page", "DOCTYPE html"], ext: ".html", size: 28000, status: "pending" },
  { id: 28, name: "domain_coherence_summary.xlsx", domain: "DOCUMENTS", confidence: 38, keywords: ["disorder", "Music Theory"], ext: ".xlsx", size: 42000, status: "pending" },
];

function formatSize(bytes) {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

function ConfidenceBar({ value }) {
  const color = value >= 70 ? "#22c55e" : value >= 30 ? "#f59e0b" : "#ef4444";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <div style={{ width: 80, height: 8, background: "#1e293b", borderRadius: 4, overflow: "hidden" }}>
        <div style={{ width: `${value}%`, height: "100%", background: color, borderRadius: 4, transition: "width 0.3s" }} />
      </div>
      <span style={{ fontSize: 12, color: "#94a3b8", minWidth: 32 }}>{value}%</span>
    </div>
  );
}

function DomainBadge({ domain, onClick }) {
  const d = DOMAINS[domain] || DOMAINS.UNCATEGORIZED;
  return (
    <span onClick={onClick} style={{ padding: "2px 8px", borderRadius: 4, fontSize: 11, fontWeight: 600, background: d.color + "22", color: d.color, cursor: onClick ? "pointer" : "default", border: `1px solid ${d.color}44`, userSelect: "none" }}>
      {d.code}
    </span>
  );
}

function DomainPicker({ current, onSelect, onClose }) {
  return (
    <div style={{ position: "absolute", top: "100%", left: -60, zIndex: 100, background: "#0f172a", border: "1px solid #334155", borderRadius: 8, padding: 4, minWidth: 180, boxShadow: "0 8px 32px rgba(0,0,0,0.5)" }}>
      {Object.entries(DOMAINS).map(([name, d]) => (
        <div key={name} onClick={() => { onSelect(name); onClose(); }}
          style={{ padding: "6px 10px", cursor: "pointer", borderRadius: 4, fontSize: 13, color: current === name ? d.color : "#cbd5e1", background: current === name ? d.color + "15" : "transparent", display: "flex", justifyContent: "space-between" }}
          onMouseEnter={(e) => e.currentTarget.style.background = d.color + "15"}
          onMouseLeave={(e) => e.currentTarget.style.background = current === name ? d.color + "15" : "transparent"}>
          <span>{name}</span>
          <span style={{ color: d.color, fontWeight: 600 }}>{d.code}</span>
        </div>
      ))}
    </div>
  );
}

export default function FileSorterGUI() {
  const [files, setFiles] = useState(INITIAL_FILES);
  const [filter, setFilter] = useState("all");
  const [sortBy, setSortBy] = useState("confidence");
  const [pickerOpen, setPickerOpen] = useState(null);
  const [selected, setSelected] = useState(new Set());
  const [threshold, setThreshold] = useState(30);
  const [nlpQueue, setNlpQueue] = useState([]);
  const [nlpRunning, setNlpRunning] = useState(false);

  const toggleSelect = (id) => {
    setSelected(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const selectAll = () => setSelected(new Set(filtered.map(f => f.id)));
  const selectNone = () => setSelected(new Set());
  const selectBelow = (t) => setSelected(new Set(filtered.filter(f => f.confidence < t).map(f => f.id)));
  const selectAbove = (t) => setSelected(new Set(filtered.filter(f => f.confidence >= t).map(f => f.id)));
  const invertSelection = () => {
    const all = new Set(filtered.map(f => f.id));
    setSelected(new Set([...all].filter(id => !selected.has(id))));
  };

  const batchApprove = () => setFiles(f => f.map(x => selected.has(x.id) ? { ...x, status: "approved" } : x));
  const batchReject = () => setFiles(f => f.map(x => selected.has(x.id) ? { ...x, status: "rejected" } : x));
  const batchDomain = (domain) => setFiles(f => f.map(x => selected.has(x.id) ? { ...x, domain, status: "override" } : x));

  const sendToNLP = () => {
    const toProcess = files.filter(f => selected.has(f.id));
    setNlpQueue(toProcess);
    setNlpRunning(true);
    // Simulate NLP processing
    setTimeout(() => {
      setFiles(f => f.map(x => {
        if (!selected.has(x.id)) return x;
        // Simulate NLP results — in production this calls the Python backend
        const boost = Math.min(95, x.confidence + Math.floor(Math.random() * 40) + 20);
        const nlpDomains = ["THEOPHYSICS", "DEVELOPMENT", "DOCUMENTS", "AI_ML"];
        const newDomain = x.confidence < 15 ? nlpDomains[Math.floor(Math.random() * nlpDomains.length)] : x.domain;
        return { ...x, confidence: boost, domain: newDomain, status: "nlp_classified", keywords: [...x.keywords, "NLP"] };
      }));
      setNlpRunning(false);
      setNlpQueue([]);
    }, 2000);
  };

  const approve = (id) => setFiles(f => f.map(x => x.id === id ? { ...x, status: "approved" } : x));
  const reject = (id) => setFiles(f => f.map(x => x.id === id ? { ...x, status: "rejected" } : x));
  const changeDomain = (id, domain) => setFiles(f => f.map(x => x.id === id ? { ...x, domain, status: "override" } : x));
  const resetAll = () => { setFiles(INITIAL_FILES); setSelected(new Set()); };

  const filtered = useMemo(() => {
    let result = files;
    if (filter !== "all") result = result.filter(f => f.domain === filter);
    if (sortBy === "confidence") result = [...result].sort((a, b) => b.confidence - a.confidence);
    if (sortBy === "name") result = [...result].sort((a, b) => a.name.localeCompare(b.name));
    if (sortBy === "size") result = [...result].sort((a, b) => b.size - a.size);
    return result;
  }, [files, filter, sortBy]);

  const stats = useMemo(() => {
    const domainCounts = {};
    files.forEach(f => { domainCounts[f.domain] = (domainCounts[f.domain] || 0) + 1; });
    return {
      domainCounts,
      approved: files.filter(f => f.status === "approved").length,
      rejected: files.filter(f => f.status === "rejected").length,
      pending: files.filter(f => f.status === "pending").length,
      overridden: files.filter(f => f.status === "override").length,
      nlp: files.filter(f => f.status === "nlp_classified").length,
      avgConf: files.reduce((s, f) => s + f.confidence, 0) / files.length,
      belowThreshold: files.filter(f => f.confidence < threshold).length,
    };
  }, [files, threshold]);

  const btnStyle = (active, color = "#6366f1") => ({
    padding: "4px 10px", borderRadius: 4, border: active ? `1px solid ${color}` : "1px solid #334155",
    background: active ? color + "18" : "transparent", color: active ? color : "#64748b",
    fontSize: 12, cursor: "pointer", whiteSpace: "nowrap",
  });

  return (
    <div style={{ fontFamily: "'Inter', system-ui, sans-serif", background: "#0f172a", color: "#e2e8f0", minHeight: "100vh", padding: 16 }}>
      <div style={{ maxWidth: 1100, margin: "0 auto" }}>
        {/* Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
          <div>
            <h1 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: "#f1f5f9" }}>File Intelligence Sorter</h1>
            <p style={{ margin: "2px 0 0", fontSize: 12, color: "#64748b" }}>
              {files.length} files | Avg: {stats.avgConf.toFixed(0)}% | Selected: {selected.size} | Below {threshold}%: {stats.belowThreshold}
            </p>
          </div>
          <button onClick={resetAll} style={{ padding: "5px 12px", borderRadius: 6, border: "1px solid #334155", background: "transparent", color: "#94a3b8", fontSize: 12, cursor: "pointer" }}>Reset All</button>
        </div>

        {/* Selection Controls */}
        <div style={{ background: "#1e293b", borderRadius: 8, padding: 12, marginBottom: 12, display: "flex", flexWrap: "wrap", gap: 6, alignItems: "center" }}>
          <span style={{ fontSize: 11, color: "#64748b", fontWeight: 600, marginRight: 4 }}>SELECT:</span>
          <button onClick={selectAll} style={btnStyle(false)}>All</button>
          <button onClick={selectNone} style={btnStyle(false)}>None</button>
          <button onClick={invertSelection} style={btnStyle(false)}>Invert</button>
          <span style={{ width: 1, height: 20, background: "#334155" }} />
          <button onClick={() => selectBelow(threshold)} style={btnStyle(false, "#ef4444")}>Below {threshold}%</button>
          <button onClick={() => selectAbove(threshold)} style={btnStyle(false, "#22c55e")}>Above {threshold}%</button>
          <input type="range" min={0} max={100} value={threshold} onChange={e => setThreshold(+e.target.value)}
            style={{ width: 80, accentColor: "#6366f1" }} />
          <span style={{ fontSize: 12, color: "#94a3b8", minWidth: 32 }}>{threshold}%</span>
          <span style={{ width: 1, height: 20, background: "#334155" }} />
          <span style={{ fontSize: 11, color: "#64748b", fontWeight: 600, marginRight: 4 }}>BATCH:</span>
          <button onClick={batchApprove} disabled={selected.size === 0} style={btnStyle(false, "#22c55e")}>Approve ({selected.size})</button>
          <button onClick={batchReject} disabled={selected.size === 0} style={btnStyle(false, "#ef4444")}>Reject ({selected.size})</button>
          <span style={{ width: 1, height: 20, background: "#334155" }} />
          <button onClick={sendToNLP} disabled={selected.size === 0 || nlpRunning}
            style={{ ...btnStyle(false, "#a855f7"), fontWeight: 600, background: selected.size > 0 ? "#a855f722" : "transparent" }}>
            {nlpRunning ? "Processing..." : `NLP Classify (${selected.size})`}
          </button>
        </div>

        {/* Domain Filters */}
        <div style={{ display: "flex", gap: 6, marginBottom: 10, flexWrap: "wrap" }}>
          <button onClick={() => setFilter("all")} style={btnStyle(filter === "all")}>All ({files.length})</button>
          {Object.entries(stats.domainCounts).sort((a, b) => b[1] - a[1]).map(([domain, count]) => {
            const d = DOMAINS[domain] || DOMAINS.UNCATEGORIZED;
            return <button key={domain} onClick={() => setFilter(domain)} style={btnStyle(filter === domain, d.color)}>{d.code} ({count})</button>;
          })}
        </div>

        {/* Sort + Status Bar */}
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 10, flexWrap: "wrap", gap: 8 }}>
          <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
            <span style={{ fontSize: 11, color: "#64748b" }}>Sort:</span>
            {["confidence", "name", "size"].map(s => (
              <button key={s} onClick={() => setSortBy(s)} style={btnStyle(sortBy === s)}>{s}</button>
            ))}
          </div>
          <div style={{ display: "flex", gap: 6 }}>
            {[
              { label: "Approved", count: stats.approved, color: "#22c55e" },
              { label: "Rejected", count: stats.rejected, color: "#ef4444" },
              { label: "Pending", count: stats.pending, color: "#f59e0b" },
              { label: "NLP", count: stats.nlp, color: "#a855f7" },
              { label: "Override", count: stats.overridden, color: "#818cf8" },
            ].map(s => (
              <span key={s.label} style={{ fontSize: 11, color: s.color, padding: "2px 8px", borderRadius: 4, background: s.color + "12", border: `1px solid ${s.color}33` }}>
                {s.label}: {s.count}
              </span>
            ))}
          </div>
        </div>

        {/* NLP Processing Banner */}
        {nlpRunning && (
          <div style={{ background: "#a855f718", border: "1px solid #a855f744", borderRadius: 8, padding: "10px 16px", marginBottom: 12, display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{ width: 16, height: 16, border: "2px solid #a855f7", borderTop: "2px solid transparent", borderRadius: "50%", animation: "spin 1s linear infinite" }} />
            <span style={{ color: "#a855f7", fontSize: 13 }}>Running NLP classification on {nlpQueue.length} files... DeBERTa + BART + Markov</span>
            <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
          </div>
        )}

        {/* Table */}
        <div style={{ borderRadius: 8, overflow: "hidden", border: "1px solid #1e293b" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ background: "#1e293b" }}>
                <th style={{ padding: "8px", width: 36, textAlign: "center" }}>
                  <input type="checkbox" checked={selected.size === filtered.length && filtered.length > 0}
                    onChange={() => selected.size === filtered.length ? selectNone() : selectAll()}
                    style={{ accentColor: "#6366f1" }} />
                </th>
                <th style={{ padding: "8px 10px", textAlign: "left", color: "#94a3b8", fontWeight: 500 }}>File</th>
                <th style={{ padding: "8px", textAlign: "center", color: "#94a3b8", fontWeight: 500, width: 60 }}>Domain</th>
                <th style={{ padding: "8px", textAlign: "left", color: "#94a3b8", fontWeight: 500, width: 130 }}>Confidence</th>
                <th style={{ padding: "8px", textAlign: "left", color: "#94a3b8", fontWeight: 500 }}>Keywords</th>
                <th style={{ padding: "8px", textAlign: "right", color: "#94a3b8", fontWeight: 500, width: 65 }}>Size</th>
                <th style={{ padding: "8px", textAlign: "center", color: "#94a3b8", fontWeight: 500, width: 80 }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((file) => {
                const isSelected = selected.has(file.id);
                const sc = { approved: "#22c55e", rejected: "#ef4444", override: "#818cf8", nlp_classified: "#a855f7", pending: "transparent" };
                const statusColor = sc[file.status] || "transparent";
                return (
                  <tr key={file.id} onClick={() => toggleSelect(file.id)}
                    style={{ borderTop: "1px solid #1e293b", cursor: "pointer",
                      background: isSelected ? "#6366f10a" : file.status === "rejected" ? "#ef444406" : file.status === "approved" ? "#22c55e04" : file.status === "nlp_classified" ? "#a855f706" : "transparent" }}>
                    <td style={{ padding: "6px 8px", textAlign: "center", borderLeft: `3px solid ${statusColor}` }} onClick={e => e.stopPropagation()}>
                      <input type="checkbox" checked={isSelected} onChange={() => toggleSelect(file.id)} style={{ accentColor: "#6366f1" }} />
                    </td>
                    <td style={{ padding: "6px 10px" }}>
                      <div style={{ fontWeight: 500, color: "#f1f5f9", fontSize: 13 }}>{file.name}</div>
                      {file.status !== "pending" && (
                        <span style={{ fontSize: 10, color: statusColor, textTransform: "uppercase", fontWeight: 600 }}>{file.status.replace("_", " ")}</span>
                      )}
                    </td>
                    <td style={{ padding: "6px 8px", textAlign: "center", position: "relative" }} onClick={e => e.stopPropagation()}>
                      <DomainBadge domain={file.domain} onClick={() => setPickerOpen(pickerOpen === file.id ? null : file.id)} />
                      {pickerOpen === file.id && <DomainPicker current={file.domain} onSelect={(d) => changeDomain(file.id, d)} onClose={() => setPickerOpen(null)} />}
                    </td>
                    <td style={{ padding: "6px 8px" }}><ConfidenceBar value={file.confidence} /></td>
                    <td style={{ padding: "6px 8px", fontSize: 11, color: "#64748b" }}>{file.keywords.slice(0, 3).join(", ")}</td>
                    <td style={{ padding: "6px 8px", textAlign: "right", fontSize: 12, color: "#64748b" }}>{formatSize(file.size)}</td>
                    <td style={{ padding: "6px 8px", textAlign: "center" }} onClick={e => e.stopPropagation()}>
                      <div style={{ display: "flex", gap: 3, justifyContent: "center" }}>
                        <button onClick={() => approve(file.id)} style={{ width: 26, height: 26, borderRadius: 4, border: "1px solid #22c55e33", background: file.status === "approved" ? "#22c55e22" : "transparent", color: "#22c55e", cursor: "pointer", fontSize: 13 }}>&#10003;</button>
                        <button onClick={() => reject(file.id)} style={{ width: 26, height: 26, borderRadius: 4, border: "1px solid #ef444433", background: file.status === "rejected" ? "#ef444422" : "transparent", color: "#ef4444", cursor: "pointer", fontSize: 13 }}>&#10005;</button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
