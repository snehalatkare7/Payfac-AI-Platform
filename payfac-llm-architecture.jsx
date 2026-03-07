import { useState } from "react";

const palette = {
  bg: "#070B14",
  surface: "#0D1524",
  card: "#111927",
  border: "#1E2D45",
  accent: "#00D4FF",
  accentGlow: "#00A8CC",
  green: "#00FF9D",
  amber: "#FFB800",
  red: "#FF4560",
  purple: "#A855F7",
  text: "#E2EAF4",
  muted: "#5A7A9A",
};

const layers = [
  {
    id: "ingestion",
    label: "01 — DATA INGESTION & STREAMING",
    color: palette.accent,
    icon: "⚡",
    nodes: [
      { name: "Kafka Streams", sub: "Real-time txn events @ 50k TPS", tag: "STREAM" },
      { name: "Webhook Gateway", sub: "Card network callbacks (Visa/MC)", tag: "EVENT" },
      { name: "Batch ETL", sub: "Historical fraud patterns, chargeback logs", tag: "BATCH" },
      { name: "PCI DSS Vault", sub: "Tokenized PAN/CVV, HSM encrypted", tag: "SECURE" },
    ],
  },
  {
    id: "rag",
    label: "02 — RAG KNOWLEDGE LAYER",
    color: palette.purple,
    icon: "🧠",
    nodes: [
      { name: "Vector Store", sub: "pgvector — fraud embeddings, policy docs", tag: "DENSE" },
      { name: "Graph RAG", sub: "Merchant → BIN → Issuer relationships", tag: "GRAPH" },
      { name: "Agentic RAG", sub: "Self-query, re-rank, multi-hop retrieval", tag: "AGENT" },
      { name: "Policy Corpus", sub: "Visa/MC rules, PCI DSS v4.0, NACHA", tag: "DOCS" },
    ],
  },
  {
    id: "memory",
    label: "03 — MEMORY ARCHITECTURE",
    color: palette.green,
    icon: "💾",
    nodes: [
      { name: "Short-Term (Redis)", sub: "Session context, last 50 txns per card", tag: "HOT" },
      { name: "Long-Term (Postgres)", sub: "Merchant behavioral baselines, 12-mo history", tag: "WARM" },
      { name: "Episodic Memory", sub: "Past fraud incidents & resolution outcomes", tag: "CASE" },
      { name: "Semantic Cache", sub: "Cached policy lookups, rule explanations", tag: "CACHE" },
    ],
  },
  {
    id: "agents",
    label: "04 — MULTI-AGENT ORCHESTRATION",
    color: palette.amber,
    icon: "🤖",
    nodes: [
      { name: "Fraud Sentinel Agent", sub: "Velocity checks, geo-anomaly, device fingerprint", tag: "DETECT" },
      { name: "Policy Compliance Agent", sub: "Card brand rules, MCC validation, limits", tag: "COMPLY" },
      { name: "Risk Scoring Agent", sub: "Real-time composite risk score 0–1000", tag: "SCORE" },
      { name: "Dispute Resolution Agent", sub: "Chargeback triage, evidence gathering", tag: "RESOLVE" },
      { name: "PCI Audit Agent", sub: "Continuous DSS compliance checking", tag: "AUDIT" },
      { name: "Merchant Onboarding Agent", sub: "KYB, underwriting, risk classification", tag: "KYB" },
    ],
  },
  {
    id: "llm",
    label: "05 — LLM SERVER LAYER",
    color: "#FF6B6B",
    icon: "🔮",
    nodes: [
      { name: "vLLM / TGI Server", sub: "Mistral-7B fine-tuned on fraud patterns", tag: "INFERENCE" },
      { name: "Tool-Use Router", sub: "Function calling → DB, APIs, rules engine", tag: "TOOLS" },
      { name: "Structured Output", sub: "JSON schema enforcement for decisions", tag: "OUTPUT" },
      { name: "Fallback Chain", sub: "GPT-4o for complex edge cases", tag: "FALLBACK" },
    ],
  },
  {
    id: "actions",
    label: "06 — DECISIONING & ACTIONS",
    color: palette.red,
    icon: "⚖️",
    nodes: [
      { name: "Approve / Decline", sub: "<200ms auth response to acquirer", tag: "DECISION" },
      { name: "Step-Up Auth", sub: "Trigger 3DS2, biometric challenge", tag: "STEP-UP" },
      { name: "Alert & SIEM", sub: "Splunk, PagerDuty — SAR filing triggers", tag: "ALERT" },
      { name: "Model Feedback Loop", sub: "Confirmed fraud → RLHF fine-tune pipeline", tag: "LEARN" },
    ],
  },
];

const useCases = [
  {
    id: "uc1",
    title: "Real-Time Transaction Fraud Detection",
    severity: "CRITICAL",
    color: palette.red,
    latency: "< 180ms",
    agents: ["Fraud Sentinel", "Risk Scoring", "Memory"],
    description:
      "On every authorization request, the Fraud Sentinel Agent performs multi-dimensional analysis: velocity checks against short-term Redis memory (5 txns in 60s on same BIN?), geolocation anomaly detection (card used in NYC and Lagos within 2hrs?), device fingerprint comparison from episodic memory, and merchant MCC risk profiling from Graph RAG. The LLM generates a human-readable risk narrative with confidence score.",
    signals: ["Velocity > 3x baseline", "Geo-distance > 500mi in < 1hr", "New device + high-value", "CVV mismatch pattern"],
    rag: "Retrieves similar historical fraud cases via vector similarity on txn embeddings. Graph RAG traverses BIN → issuer → past fraud rates.",
  },
  {
    id: "uc2",
    title: "Card Brand Policy Compliance (Visa / Mastercard)",
    severity: "HIGH",
    color: palette.amber,
    latency: "< 500ms",
    agents: ["Policy Compliance", "Agentic RAG"],
    description:
      "The Policy Compliance Agent uses Agentic RAG with multi-hop retrieval to answer: 'Does this merchant MCC 5812 (restaurants) exceed Visa's interchange cap for this BIN range?' It indexes all Visa Core Rules, Mastercard Transaction Processing Rules as chunked embeddings. Self-querying reformulates ambiguous questions into precise policy lookups.",
    signals: ["MCC category mismatch", "Interchange rate breach", "Surcharge rule violation", "Recurring billing flag missing"],
    rag: "Dense retrieval on 10,000+ pages of card brand operating regulations. Re-ranking by recency (rule updated Q1 2025?).",
  },
  {
    id: "uc3",
    title: "PCI DSS v4.0 Continuous Compliance",
    severity: "HIGH",
    color: palette.purple,
    latency: "Async",
    agents: ["PCI Audit Agent", "Policy Compliance"],
    description:
      "The PCI Audit Agent continuously monitors the cardholder data environment. It uses long-term memory of past audit findings, retrieves PCI DSS requirement text via RAG, and generates Requirement-by-Requirement compliance narratives. When a new vulnerability is detected (e.g., TLS 1.1 still enabled), it auto-creates a remediation plan with evidence collection tasks.",
    signals: ["Unencrypted PAN in logs", "Missing tokenization", "Weak TLS/cipher", "Access control gap"],
    rag: "Full PCI DSS v4.0 standard indexed. SAQ type determination from merchant profile. Compensating control retrieval.",
  },
  {
    id: "uc4",
    title: "Chargeback & Dispute Resolution",
    severity: "MEDIUM",
    color: palette.green,
    latency: "< 2s",
    agents: ["Dispute Resolution", "Episodic Memory", "Agentic RAG"],
    description:
      "When a dispute arrives (Reason Code 10.4 – Card Absent), the agent retrieves the original transaction context from episodic memory, pulls relevant Visa/MC dispute resolution rules via RAG, analyzes available evidence (3DS data, device fingerprint, delivery confirmation), and generates a structured rebuttal package with supporting documentation highlights.",
    signals: ["Chargeback reason code", "Time elapsed since txn", "3DS authentication present", "Delivery proof available"],
    rag: "Retrieves past winning/losing dispute cases with same reason code. Card brand representment guidelines.",
  },
  {
    id: "uc5",
    title: "Merchant Risk & KYB Underwriting",
    severity: "MEDIUM",
    color: palette.accent,
    latency: "< 30s",
    agents: ["Merchant Onboarding", "Risk Scoring", "Graph RAG"],
    description:
      "During merchant onboarding, the system orchestrates 8 parallel sub-agents: business verification, OFAC/sanctions check, MCC risk classification, processing history analysis (via Graph RAG linking to similar merchants), chargeback rate prediction using long-term memory of merchant cohort data, and underwriting decision generation with plain-English risk narrative.",
    signals: ["High-risk MCC (crypto, gambling)", "Short business history", "Adverse media hits", "Processing volume vs. revenue mismatch"],
    rag: "Similar merchant risk profiles. Industry default rates. Regulatory prohibited business lists.",
  },
];

const architectureFlows = [
  { from: "ingestion", to: "rag", label: "Embed & Index" },
  { from: "ingestion", to: "memory", label: "Store Context" },
  { from: "rag", to: "agents", label: "Retrieved Context" },
  { from: "memory", to: "agents", label: "Historical State" },
  { from: "agents", to: "llm", label: "LLM Requests" },
  { from: "llm", to: "actions", label: "Decisions" },
  { from: "actions", to: "memory", label: "Feedback Loop" },
];

export default function PayFacLLM() {
  const [activeTab, setActiveTab] = useState("architecture");
  const [selectedUC, setSelectedUC] = useState(null);
  const [expandedLayer, setExpandedLayer] = useState(null);

  return (
    <div style={{
      background: palette.bg,
      minHeight: "100vh",
      fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
      color: palette.text,
      padding: "0",
    }}>
      {/* Header */}
      <div style={{
        borderBottom: `1px solid ${palette.border}`,
        padding: "24px 40px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        background: `linear-gradient(90deg, ${palette.surface} 0%, ${palette.bg} 100%)`,
        position: "sticky",
        top: 0,
        zIndex: 100,
      }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div style={{
              width: 10, height: 10, borderRadius: "50%",
              background: palette.green,
              boxShadow: `0 0 8px ${palette.green}`,
              animation: "pulse 2s infinite",
            }} />
            <span style={{ fontSize: 11, color: palette.green, letterSpacing: 3, fontWeight: 700 }}>
              SYSTEM ONLINE — PAYFAC AI ENGINE v2.4
            </span>
          </div>
          <h1 style={{
            margin: "6px 0 0",
            fontSize: 22,
            fontWeight: 800,
            letterSpacing: -0.5,
            color: "#fff",
            fontFamily: "Georgia, serif",
          }}>
            LLM-Powered Payment Facilitation Platform
          </h1>
          <p style={{ margin: "2px 0 0", fontSize: 12, color: palette.muted }}>
            Agentic RAG · Multi-Agent Orchestration · Real-Time Fraud Intelligence
          </p>
        </div>
        <div style={{ display: "flex", gap: 16, alignItems: "center" }}>
          {["architecture", "use-cases"].map(tab => (
            <button key={tab} onClick={() => setActiveTab(tab)} style={{
              background: activeTab === tab ? palette.accent : "transparent",
              color: activeTab === tab ? palette.bg : palette.muted,
              border: `1px solid ${activeTab === tab ? palette.accent : palette.border}`,
              padding: "8px 18px",
              borderRadius: 4,
              cursor: "pointer",
              fontSize: 11,
              fontFamily: "inherit",
              letterSpacing: 1.5,
              fontWeight: 700,
              transition: "all 0.2s",
            }}>
              {tab === "architecture" ? "ARCHITECTURE" : "USE CASES"}
            </button>
          ))}
        </div>
      </div>

      <style>{`
        @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.3} }
        @keyframes scan { 0%{transform:translateY(-100%)} 100%{transform:translateY(100vh)} }
        .node-card:hover { transform: translateY(-2px); box-shadow: 0 8px 32px rgba(0,212,255,0.15) !important; }
        .uc-card:hover { border-color: rgba(0,212,255,0.4) !important; }
      `}</style>

      {activeTab === "architecture" && (
        <div style={{ padding: "32px 40px" }}>
          {/* Flow Diagram Header */}
          <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 32 }}>
            <div style={{ flex: 1, height: 1, background: `linear-gradient(90deg, transparent, ${palette.border})` }} />
            <span style={{ fontSize: 11, color: palette.muted, letterSpacing: 2 }}>
              END-TO-END SYSTEM ARCHITECTURE
            </span>
            <div style={{ flex: 1, height: 1, background: `linear-gradient(90deg, ${palette.border}, transparent)` }} />
          </div>

          {/* Data Flow Badges */}
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 32, justifyContent: "center" }}>
            {architectureFlows.map((f, i) => (
              <div key={i} style={{
                border: `1px solid ${palette.border}`,
                borderRadius: 100,
                padding: "4px 12px",
                fontSize: 10,
                color: palette.muted,
                background: palette.surface,
              }}>
                <span style={{ color: palette.accent }}>{f.from}</span>
                <span style={{ margin: "0 6px" }}>→</span>
                <span style={{ color: palette.green }}>{f.to}</span>
                <span style={{ marginLeft: 6, color: palette.muted }}>{f.label}</span>
              </div>
            ))}
          </div>

          {/* Layer Stack */}
          <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
            {layers.map((layer, li) => (
              <div key={layer.id} style={{
                border: `1px solid ${expandedLayer === layer.id ? layer.color + "66" : palette.border}`,
                borderRadius: 8,
                overflow: "hidden",
                transition: "all 0.3s",
              }}>
                {/* Layer Header */}
                <div
                  onClick={() => setExpandedLayer(expandedLayer === layer.id ? null : layer.id)}
                  style={{
                    display: "flex", alignItems: "center", gap: 16,
                    padding: "16px 24px",
                    background: expandedLayer === layer.id
                      ? `linear-gradient(90deg, ${layer.color}22, ${palette.surface})`
                      : palette.surface,
                    cursor: "pointer",
                    borderBottom: expandedLayer === layer.id ? `1px solid ${palette.border}` : "none",
                  }}
                >
                  <div style={{
                    width: 36, height: 36, borderRadius: 8,
                    background: `${layer.color}22`,
                    border: `1px solid ${layer.color}44`,
                    display: "flex", alignItems: "center", justifyContent: "center",
                    fontSize: 18,
                  }}>{layer.icon}</div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 13, fontWeight: 700, color: layer.color, letterSpacing: 1 }}>
                      {layer.label}
                    </div>
                    <div style={{ fontSize: 11, color: palette.muted, marginTop: 2 }}>
                      {layer.nodes.length} components · click to expand
                    </div>
                  </div>
                  <div style={{
                    width: 20, height: 20,
                    display: "flex", alignItems: "center", justifyContent: "center",
                    color: palette.muted, fontSize: 14,
                    transform: expandedLayer === layer.id ? "rotate(180deg)" : "none",
                    transition: "transform 0.3s",
                  }}>▼</div>
                </div>

                {/* Layer Nodes */}
                {expandedLayer === layer.id && (
                  <div style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))",
                    gap: 16, padding: 24,
                    background: palette.card,
                  }}>
                    {layer.nodes.map((node, ni) => (
                      <div key={ni} className="node-card" style={{
                        border: `1px solid ${palette.border}`,
                        borderRadius: 8, padding: "16px 18px",
                        background: palette.surface,
                        cursor: "default",
                        transition: "all 0.2s",
                        position: "relative",
                        overflow: "hidden",
                      }}>
                        <div style={{
                          position: "absolute", top: 0, left: 0, right: 0,
                          height: 2, background: layer.color,
                          opacity: 0.6,
                        }} />
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                          <div style={{ fontSize: 13, fontWeight: 700, color: "#fff", lineHeight: 1.3 }}>
                            {node.name}
                          </div>
                          <span style={{
                            fontSize: 9, fontWeight: 700, letterSpacing: 1,
                            color: layer.color, background: `${layer.color}22`,
                            border: `1px solid ${layer.color}44`,
                            padding: "2px 7px", borderRadius: 4, whiteSpace: "nowrap",
                            marginLeft: 8,
                          }}>{node.tag}</span>
                        </div>
                        <div style={{ fontSize: 11, color: palette.muted, marginTop: 6, lineHeight: 1.5 }}>
                          {node.sub}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Bottom Stats */}
          <div style={{
            display: "grid", gridTemplateColumns: "repeat(4, 1fr)",
            gap: 16, marginTop: 32,
          }}>
            {[
              { label: "AUTH LATENCY P99", value: "< 200ms", color: palette.green },
              { label: "FRAUD DETECTION RATE", value: "99.3%", color: palette.accent },
              { label: "FALSE POSITIVE RATE", value: "0.08%", color: palette.amber },
              { label: "POLICY RULES INDEXED", value: "14,200+", color: palette.purple },
            ].map((s, i) => (
              <div key={i} style={{
                border: `1px solid ${palette.border}`, borderRadius: 8,
                padding: "18px 20px", background: palette.surface,
                textAlign: "center",
              }}>
                <div style={{ fontSize: 24, fontWeight: 900, color: s.color, fontFamily: "Georgia, serif" }}>
                  {s.value}
                </div>
                <div style={{ fontSize: 10, color: palette.muted, marginTop: 4, letterSpacing: 1.5 }}>
                  {s.label}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {activeTab === "use-cases" && (
        <div style={{ padding: "32px 40px" }}>
          <div style={{ display: "flex", gap: 24 }}>
            {/* UC List */}
            <div style={{ width: 300, flexShrink: 0 }}>
              <div style={{ fontSize: 10, color: palette.muted, letterSpacing: 2, marginBottom: 16 }}>
                REGISTERED USE CASES ({useCases.length})
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {useCases.map(uc => (
                  <div
                    key={uc.id}
                    className="uc-card"
                    onClick={() => setSelectedUC(uc)}
                    style={{
                      border: `1px solid ${selectedUC?.id === uc.id ? uc.color + "66" : palette.border}`,
                      borderRadius: 8, padding: "14px 16px",
                      background: selectedUC?.id === uc.id ? `${uc.color}11` : palette.surface,
                      cursor: "pointer", transition: "all 0.2s",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                      <div style={{ fontSize: 12, fontWeight: 700, color: "#fff", lineHeight: 1.4, flex: 1 }}>
                        {uc.title}
                      </div>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 8 }}>
                      <span style={{
                        fontSize: 9, fontWeight: 700, letterSpacing: 1,
                        color: uc.color, background: `${uc.color}22`,
                        border: `1px solid ${uc.color}44`,
                        padding: "2px 8px", borderRadius: 4,
                      }}>{uc.severity}</span>
                      <span style={{ fontSize: 10, color: palette.muted }}>{uc.latency}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* UC Detail */}
            <div style={{ flex: 1 }}>
              {!selectedUC ? (
                <div style={{
                  height: "100%", display: "flex", alignItems: "center", justifyContent: "center",
                  flexDirection: "column", gap: 12,
                  border: `1px dashed ${palette.border}`, borderRadius: 12,
                  color: palette.muted, minHeight: 400,
                }}>
                  <div style={{ fontSize: 32 }}>🔍</div>
                  <div style={{ fontSize: 13 }}>Select a use case to explore</div>
                </div>
              ) : (
                <div style={{
                  border: `1px solid ${selectedUC.color}44`,
                  borderRadius: 12, overflow: "hidden",
                  background: palette.card,
                }}>
                  {/* UC Header */}
                  <div style={{
                    padding: "24px 28px",
                    background: `linear-gradient(135deg, ${selectedUC.color}18, ${palette.surface})`,
                    borderBottom: `1px solid ${palette.border}`,
                  }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                      <h2 style={{ margin: 0, fontSize: 20, color: "#fff", fontFamily: "Georgia, serif" }}>
                        {selectedUC.title}
                      </h2>
                      <div style={{ textAlign: "right" }}>
                        <div style={{ fontSize: 11, color: palette.muted }}>TARGET LATENCY</div>
                        <div style={{ fontSize: 20, color: selectedUC.color, fontWeight: 900 }}>
                          {selectedUC.latency}
                        </div>
                      </div>
                    </div>

                    {/* Agents */}
                    <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 16 }}>
                      <span style={{ fontSize: 10, color: palette.muted, alignSelf: "center" }}>AGENTS:</span>
                      {selectedUC.agents.map((a, i) => (
                        <span key={i} style={{
                          fontSize: 10, fontWeight: 700, letterSpacing: 0.5,
                          color: selectedUC.color,
                          background: `${selectedUC.color}22`,
                          border: `1px solid ${selectedUC.color}44`,
                          padding: "3px 10px", borderRadius: 100,
                        }}>{a}</span>
                      ))}
                    </div>
                  </div>

                  <div style={{ padding: 28 }}>
                    {/* Description */}
                    <div style={{ marginBottom: 24 }}>
                      <div style={{ fontSize: 10, color: palette.muted, letterSpacing: 2, marginBottom: 10 }}>
                        HOW IT WORKS
                      </div>
                      <p style={{ fontSize: 13, color: palette.text, lineHeight: 1.8, margin: 0 }}>
                        {selectedUC.description}
                      </p>
                    </div>

                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
                      {/* Signals */}
                      <div style={{
                        border: `1px solid ${palette.border}`, borderRadius: 8, padding: 18,
                        background: palette.surface,
                      }}>
                        <div style={{ fontSize: 10, color: palette.muted, letterSpacing: 2, marginBottom: 12 }}>
                          KEY DETECTION SIGNALS
                        </div>
                        {selectedUC.signals.map((s, i) => (
                          <div key={i} style={{
                            display: "flex", alignItems: "flex-start", gap: 10, marginBottom: 10,
                          }}>
                            <div style={{
                              width: 6, height: 6, borderRadius: "50%",
                              background: selectedUC.color, marginTop: 5, flexShrink: 0,
                            }} />
                            <span style={{ fontSize: 12, color: palette.text }}>{s}</span>
                          </div>
                        ))}
                      </div>

                      {/* RAG */}
                      <div style={{
                        border: `1px solid ${palette.border}`, borderRadius: 8, padding: 18,
                        background: palette.surface,
                      }}>
                        <div style={{ fontSize: 10, color: palette.muted, letterSpacing: 2, marginBottom: 12 }}>
                          RAG RETRIEVAL STRATEGY
                        </div>
                        <p style={{ fontSize: 12, color: palette.text, lineHeight: 1.7, margin: 0 }}>
                          {selectedUC.rag}
                        </p>

                        {/* LLM Flow */}
                        <div style={{ marginTop: 16, paddingTop: 16, borderTop: `1px solid ${palette.border}` }}>
                          <div style={{ fontSize: 10, color: palette.muted, letterSpacing: 2, marginBottom: 10 }}>
                            LLM PIPELINE
                          </div>
                          <div style={{ display: "flex", alignItems: "center", gap: 4, flexWrap: "wrap" }}>
                            {["Embed Query", "→", "Retrieve", "→", "Re-rank", "→", "Augment Prompt", "→", "Generate", "→", "Structure Output"].map((step, i) => (
                              <span key={i} style={{
                                fontSize: 10,
                                color: step === "→" ? palette.muted : palette.accent,
                                fontWeight: step === "→" ? 400 : 600,
                              }}>{step}</span>
                            ))}
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Memory Usage */}
                    <div style={{
                      marginTop: 20,
                      border: `1px solid ${palette.border}`, borderRadius: 8, padding: 18,
                      background: palette.surface,
                      display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16,
                    }}>
                      <div>
                        <div style={{ fontSize: 10, color: palette.muted, letterSpacing: 2, marginBottom: 6 }}>SHORT-TERM MEMORY</div>
                        <div style={{ fontSize: 12, color: palette.green }}>Redis · TTL 30min</div>
                        <div style={{ fontSize: 11, color: palette.muted, marginTop: 2 }}>Active session context</div>
                      </div>
                      <div>
                        <div style={{ fontSize: 10, color: palette.muted, letterSpacing: 2, marginBottom: 6 }}>LONG-TERM MEMORY</div>
                        <div style={{ fontSize: 12, color: palette.purple }}>Postgres · 12mo history</div>
                        <div style={{ fontSize: 11, color: palette.muted, marginTop: 2 }}>Behavioral baselines</div>
                      </div>
                      <div>
                        <div style={{ fontSize: 10, color: palette.muted, letterSpacing: 2, marginBottom: 6 }}>EPISODIC MEMORY</div>
                        <div style={{ fontSize: 12, color: palette.amber }}>Vector DB · Case-based</div>
                        <div style={{ fontSize: 11, color: palette.muted, marginTop: 2 }}>Past fraud outcomes</div>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Bottom Architecture Summary */}
          <div style={{
            marginTop: 32,
            border: `1px solid ${palette.border}`, borderRadius: 12, padding: 28,
            background: palette.surface,
          }}>
            <div style={{ fontSize: 10, color: palette.muted, letterSpacing: 2, marginBottom: 20 }}>
              ADVANCED LLM CONCEPTS IN USE
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: 12 }}>
              {[
                { concept: "Agentic RAG", detail: "Self-querying, multi-hop, re-ranking retrievers", color: palette.purple },
                { concept: "Multi-Agent", detail: "6 specialized agents with tool-use + handoffs", color: palette.amber },
                { concept: "Short-Term Memory", detail: "Redis session cache, sliding window context", color: palette.green },
                { concept: "Long-Term Memory", detail: "Postgres behavioral baselines, trend detection", color: palette.accent },
                { concept: "Episodic Memory", detail: "Vector-indexed case history for few-shot learning", color: palette.red },
                { concept: "Structured Output", detail: "JSON schema enforcement for all decisions", color: palette.muted },
                { concept: "RLHF Feedback Loop", detail: "Confirmed fraud → fine-tune signal pipeline", color: palette.purple },
                { concept: "Graph RAG", detail: "BIN/Issuer/Merchant relationship traversal", color: palette.amber },
                { concept: "vLLM Server", detail: "Self-hosted inference, fine-tuned fraud model", color: palette.green },
                { concept: "Tool-Use / Functions", detail: "Rules engine, DB queries, external APIs", color: palette.accent },
                { concept: "Semantic Cache", detail: "Policy lookup deduplication, latency reduction", color: "#FF6B6B" },
                { concept: "Agentic Server", detail: "LangGraph / CrewAI multi-agent orchestration", color: palette.text },
              ].map((c, i) => (
                <div key={i} style={{
                  borderLeft: `3px solid ${c.color}`,
                  paddingLeft: 12, paddingTop: 4, paddingBottom: 4,
                }}>
                  <div style={{ fontSize: 12, fontWeight: 700, color: c.color }}>{c.concept}</div>
                  <div style={{ fontSize: 10, color: palette.muted, marginTop: 2, lineHeight: 1.4 }}>{c.detail}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
