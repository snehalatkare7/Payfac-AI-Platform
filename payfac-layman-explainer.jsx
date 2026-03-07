import { useState } from "react";

const chapters = [
  {
    id: "what",
    emoji: "💳",
    title: "What is a PayFac?",
    subtitle: "The company that moves your money",
    color: "#4F9EF8",
    sections: [
      {
        type: "story",
        text: "When you tap your card at a coffee shop, something incredible happens in milliseconds. Your bank, the coffee shop's bank, Visa or Mastercard, and a company called a Payment Facilitator (PayFac) all talk to each other — and decide whether to let the transaction go through.",
      },
      {
        type: "analogy",
        icon: "🏪",
        title: "Think of a PayFac like a Shopping Mall Manager",
        body: "A mall doesn't sell things itself — but it lets hundreds of shops operate inside it, handles their security, makes sure they follow the rules, and processes payments on their behalf. A PayFac does the same thing for online and physical merchants.",
      },
      {
        type: "examples",
        title: "Famous PayFacs you already know:",
        items: [
          { name: "Stripe", icon: "💜", desc: "Powers millions of online stores" },
          { name: "Square", icon: "◼️", desc: "That card reader at your local cafe" },
          { name: "PayPal", icon: "🅿️", desc: "Online checkouts everywhere" },
        ],
      },
      {
        type: "problem",
        title: "The Big Problem PayFacs Face Every Day",
        body: "Every second, thousands of transactions happen. Some are completely normal. Some are criminals trying to steal money using fake or stolen cards. Some merchants are accidentally breaking banking rules. The PayFac has to catch the bad stuff instantly — while letting the good stuff through without any delay.",
      },
    ],
  },
  {
    id: "ai",
    emoji: "🤖",
    title: "Why AI? Why Now?",
    subtitle: "The old way vs. the smart way",
    color: "#A855F7",
    sections: [
      {
        type: "comparison",
        left: {
          title: "❌ The Old Way (Rule-Based)",
          color: "#FF4560",
          points: [
            "\"Block all transactions over $500 from new cards\"",
            "\"Flag if the same card is used twice in 1 minute\"",
            "Criminals quickly learn the rules and work around them",
            "Lots of innocent people get their cards declined",
            "Needs humans to manually update rules constantly",
          ],
        },
        right: {
          title: "✅ The AI Way (LLM-Powered)",
          color: "#00FF9D",
          points: [
            "Learns what \"normal\" looks like for each person",
            "Spots unusual patterns humans would never notice",
            "Gets smarter every day from new fraud attempts",
            "Understands context — not just numbers",
            "Can read and apply thousands of banking rules automatically",
          ],
        },
      },
      {
        type: "analogy",
        icon: "🕵️",
        title: "AI is like hiring the world's best detective",
        body: "A rule book says 'arrest anyone wearing a red hat.' A great detective looks at the whole picture — who are they, where did they come from, does their story make sense, does this feel right? That's what AI does for every single transaction.",
      },
    ],
  },
  {
    id: "rag",
    emoji: "📚",
    title: "RAG — The AI's Library",
    subtitle: "How the AI looks things up",
    color: "#FF9500",
    sections: [
      {
        type: "story",
        text: "An AI model is trained on lots of data — but it can't memorize every single banking rule, every fraud pattern ever seen, or every card brand policy. That's where RAG comes in.",
      },
      {
        type: "analogy",
        icon: "📖",
        title: "RAG = Retrieval-Augmented Generation",
        body: "Imagine a brilliant lawyer who doesn't memorize every law — instead, they have a giant, perfectly organized library. Before answering any question, they quickly find the most relevant pages and read them first. That's RAG: the AI searches its knowledge base before responding.",
      },
      {
        type: "examples",
        title: "What's in the AI's library?",
        items: [
          { name: "Visa & Mastercard Rule Books", icon: "📋", desc: "Thousands of pages of card network policies" },
          { name: "Past Fraud Cases", icon: "🚨", desc: "Every fraud pattern seen before, with outcomes" },
          { name: "PCI DSS Security Rules", icon: "🔒", desc: "Global payment security standards" },
          { name: "Merchant Histories", icon: "🏪", desc: "What's normal for each business type" },
        ],
      },
      {
        type: "flow",
        title: "How RAG works, step by step:",
        steps: [
          { icon: "❓", text: "A transaction comes in: \"$2,400 purchase at an electronics store in Miami\"" },
          { icon: "🔍", text: "AI searches: finds similar past transactions, relevant fraud patterns, store category rules" },
          { icon: "📄", text: "AI reads the relevant pages from its library" },
          { icon: "🧠", text: "AI combines what it retrieved with what it already knows" },
          { icon: "⚡", text: "AI makes a smart decision in under 200 milliseconds" },
        ],
      },
    ],
  },
  {
    id: "agents",
    emoji: "👥",
    title: "Multi-Agent System",
    subtitle: "A team of AI specialists",
    color: "#00D4FF",
    sections: [
      {
        type: "analogy",
        icon: "🏥",
        title: "Think of it like a hospital emergency room",
        body: "When you come to the ER, you don't see just one person. A triage nurse checks your vitals first. Then a specialist examines you. A pharmacist reviews your medications. Each expert does their job in parallel. That's exactly how our multi-agent AI system works — but for payments.",
      },
      {
        type: "agents",
        title: "Meet the AI Agents:",
        items: [
          {
            icon: "🛡️",
            name: "Fraud Sentinel Agent",
            role: "The Security Guard",
            desc: "Watches every transaction for suspicious patterns. Is this card being used in two countries at once? Is someone testing with small amounts before a big purchase?",
            color: "#FF4560",
          },
          {
            icon: "📏",
            name: "Policy Compliance Agent",
            role: "The Rule Checker",
            desc: "Makes sure every transaction follows Visa, Mastercard, and banking rules. Is this merchant allowed to charge a fee? Is this transaction type allowed in this country?",
            color: "#FF9500",
          },
          {
            icon: "🎯",
            name: "Risk Scoring Agent",
            role: "The Scorekeeper",
            desc: "Combines all signals into one risk score from 0–1000. Like a credit score — but for individual transactions, calculated in real time.",
            color: "#A855F7",
          },
          {
            icon: "⚖️",
            name: "Dispute Resolution Agent",
            role: "The Mediator",
            desc: "When a customer says 'I didn't make that purchase,' this agent gathers all the evidence and builds the case — automatically.",
            color: "#00FF9D",
          },
          {
            icon: "🔐",
            name: "PCI Audit Agent",
            role: "The Compliance Officer",
            desc: "Continuously checks that the entire system meets global security standards. Like having a 24/7 security auditor on staff.",
            color: "#00D4FF",
          },
          {
            icon: "🧾",
            name: "Merchant Onboarding Agent",
            role: "The Background Checker",
            desc: "When a new business wants to accept payments, this agent verifies they're legitimate, checks for sanctions lists, and assesses their risk profile.",
            color: "#FFB800",
          },
        ],
      },
    ],
  },
  {
    id: "memory",
    emoji: "🧠",
    title: "Memory — The AI Remembers",
    subtitle: "Short-term and long-term recall",
    color: "#00FF9D",
    sections: [
      {
        type: "analogy",
        icon: "👤",
        title: "AI memory works just like human memory",
        body: "You remember what you had for breakfast (short-term). You also remember your childhood home address (long-term). And you remember specific events, like the time you lost your wallet (episodic). Our AI has all three types.",
      },
      {
        type: "memory_types",
        items: [
          {
            icon: "⚡",
            type: "Short-Term Memory",
            tech: "Redis (super-fast database)",
            color: "#00D4FF",
            human: "Like remembering what you did this morning",
            system: "Remembers the last 50 transactions on a card right now. Is this the 6th purchase in 10 minutes? That's suspicious.",
            ttl: "Expires after 30 minutes",
          },
          {
            icon: "📅",
            type: "Long-Term Memory",
            tech: "PostgreSQL database",
            color: "#A855F7",
            human: "Like remembering your spending habits over years",
            system: "Knows that John always buys coffee at 8am, groceries on Sundays, and never shops in foreign countries. Any deviation is a red flag.",
            ttl: "Stored for 12+ months",
          },
          {
            icon: "📖",
            type: "Episodic Memory",
            tech: "Vector database (AI-powered search)",
            color: "#FF9500",
            human: "Like remembering specific past events",
            system: "Recalls: 'Last time we saw this exact pattern — card used at gas station, then electronics, then jewelry — it was fraud 94% of the time.'",
            ttl: "Permanent case history",
          },
        ],
      },
    ],
  },
  {
    id: "realworld",
    emoji: "🌍",
    title: "Real-World Scenarios",
    subtitle: "See it in action",
    color: "#FF4560",
    sections: [
      {
        type: "scenarios",
        items: [
          {
            title: "Scenario 1: Stolen Card in Miami",
            icon: "🚨",
            color: "#FF4560",
            timeline: [
              { time: "0ms", event: "Card swiped at Miami electronics store for $1,800", type: "input" },
              { time: "12ms", event: "Short-term memory check: same card used in Chicago 45 minutes ago", type: "alert" },
              { time: "28ms", event: "Episodic memory: this BIN-range has 67% fraud rate at electronics stores", type: "alert" },
              { time: "45ms", event: "Fraud Sentinel flags geo-impossibility (Chicago → Miami in 45min)", type: "alert" },
              { time: "80ms", event: "Risk Score Agent calculates: 940/1000 (VERY HIGH RISK)", type: "score" },
              { time: "120ms", event: "LLM generates explanation: 'Physical impossibility detected + high-risk merchant + new device'", type: "ai" },
              { time: "180ms", event: "DECLINED. Bank alerted. Cardholder notified.", type: "decision" },
            ],
          },
          {
            title: "Scenario 2: Are We Breaking Visa's Rules?",
            icon: "📋",
            color: "#FF9500",
            timeline: [
              { time: "Event", event: "A merchant charges a 3% 'convenience fee' on credit card purchases", type: "input" },
              { time: "Step 1", event: "Policy Compliance Agent triggers: 'convenience fee detected'", type: "alert" },
              { time: "Step 2", event: "Agentic RAG searches 10,000+ pages of Visa Operating Regulations", type: "ai" },
              { time: "Step 3", event: "Finds: Visa Rule 5.8.2 — surcharges allowed in US but must be disclosed", type: "alert" },
              { time: "Step 4", event: "Cross-checks merchant's onboarding agreement — disclosure not present", type: "alert" },
              { time: "Step 5", event: "LLM writes plain-English warning to merchant with exact rule reference", type: "ai" },
              { time: "Result", event: "Merchant notified before a $50,000 fine from Visa. Problem solved proactively.", type: "decision" },
            ],
          },
          {
            title: "Scenario 3: Customer Says 'I Didn't Buy That'",
            icon: "⚖️",
            color: "#00FF9D",
            timeline: [
              { time: "Day 0", event: "Customer disputes a $340 Amazon purchase they say they didn't make", type: "input" },
              { time: "Step 1", event: "Dispute Agent retrieves full transaction context from episodic memory", type: "ai" },
              { time: "Step 2", event: "Finds: 3D Secure authentication was completed. Customer's phone was used.", type: "alert" },
              { time: "Step 3", event: "Checks delivery confirmation — signed by customer's name at their address", type: "alert" },
              { time: "Step 4", event: "RAG retrieves Mastercard chargeback rules for Reason Code 4853", type: "ai" },
              { time: "Step 5", event: "LLM assembles evidence package with all supporting documentation", type: "ai" },
              { time: "Result", event: "Merchant wins dispute. $340 protected. Zero human hours spent.", type: "decision" },
            ],
          },
        ],
      },
    ],
  },
  {
    id: "learn",
    emoji: "📈",
    title: "The System Gets Smarter",
    subtitle: "It learns from every mistake",
    color: "#FFB800",
    sections: [
      {
        type: "story",
        text: "Here's what makes this truly powerful: the system learns from every outcome. Every time fraud is confirmed, it becomes a training example. Every time a chargeback is won or lost, the AI updates its understanding. This is called a feedback loop.",
      },
      {
        type: "analogy",
        icon: "🎓",
        title: "Like a doctor who gets better with every patient",
        body: "A doctor fresh out of medical school knows the textbooks. But after 20 years of seeing patients, they develop intuition that no book could teach. Our AI does the same — except it processes millions of 'patients' (transactions) and never forgets a single lesson.",
      },
      {
        type: "flow",
        title: "The Learning Loop:",
        steps: [
          { icon: "💳", text: "Transaction happens and AI makes a decision" },
          { icon: "⏱️", text: "Hours/days later: outcome is confirmed (was it really fraud?)" },
          { icon: "📊", text: "Outcome fed back into the system as a training signal" },
          { icon: "🔧", text: "Model fine-tuned with new data (called RLHF)" },
          { icon: "🚀", text: "Next similar transaction: AI is smarter and more accurate" },
        ],
      },
      {
        type: "stats",
        items: [
          { label: "Fraud detection rate", value: "99.3%", sub: "Industry avg: 85%", color: "#00FF9D" },
          { label: "False declines", value: "0.08%", sub: "Good customers blocked", color: "#00D4FF" },
          { label: "Decision speed", value: "< 200ms", sub: "Faster than a blink", color: "#A855F7" },
          { label: "Rules indexed", value: "14,200+", sub: "Visa, MC, PCI, NACHA", color: "#FF9500" },
        ],
      },
    ],
  },
];

const typeColors = {
  input: "#5A7A9A",
  alert: "#FF4560",
  ai: "#A855F7",
  score: "#FF9500",
  decision: "#00FF9D",
};

export default function LaymanExplainer() {
  const [activeChapter, setActiveChapter] = useState(0);
  const [expandedAgent, setExpandedAgent] = useState(null);
  const [expandedScenario, setExpandedScenario] = useState(0);

  const chapter = chapters[activeChapter];

  const renderSection = (section, si) => {
    if (section.type === "story") return (
      <div key={si} style={{
        fontSize: 16, lineHeight: 1.85, color: "#C8D8E8",
        background: "#0D1928", borderLeft: "3px solid " + chapter.color,
        padding: "16px 20px", borderRadius: "0 8px 8px 0", marginBottom: 24,
      }}>{section.text}</div>
    );

    if (section.type === "analogy") return (
      <div key={si} style={{
        background: `linear-gradient(135deg, ${chapter.color}15, #0D1928)`,
        border: `1px solid ${chapter.color}44`,
        borderRadius: 12, padding: 24, marginBottom: 24,
      }}>
        <div style={{ fontSize: 32, marginBottom: 10 }}>{section.icon}</div>
        <div style={{ fontSize: 17, fontWeight: 700, color: "#fff", marginBottom: 10, fontFamily: "Georgia, serif" }}>
          {section.title}
        </div>
        <div style={{ fontSize: 15, lineHeight: 1.8, color: "#C8D8E8" }}>{section.body}</div>
      </div>
    );

    if (section.type === "problem") return (
      <div key={si} style={{
        background: "#FF456010",
        border: "1px solid #FF456044",
        borderRadius: 12, padding: 24, marginBottom: 24,
      }}>
        <div style={{ fontSize: 17, fontWeight: 700, color: "#FF4560", marginBottom: 10 }}>⚠️ {section.title}</div>
        <div style={{ fontSize: 15, lineHeight: 1.8, color: "#C8D8E8" }}>{section.body}</div>
      </div>
    );

    if (section.type === "examples") return (
      <div key={si} style={{ marginBottom: 24 }}>
        <div style={{ fontSize: 12, color: "#5A7A9A", letterSpacing: 2, marginBottom: 14 }}>{section.title.toUpperCase()}</div>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
          {section.items.map((item, i) => (
            <div key={i} style={{
              background: "#0D1928", border: "1px solid #1E2D45",
              borderRadius: 10, padding: "14px 18px", flex: "1 1 150px",
            }}>
              <div style={{ fontSize: 24, marginBottom: 6 }}>{item.icon}</div>
              <div style={{ fontSize: 14, fontWeight: 700, color: "#fff" }}>{item.name}</div>
              <div style={{ fontSize: 12, color: "#5A7A9A", marginTop: 4 }}>{item.desc}</div>
            </div>
          ))}
        </div>
      </div>
    );

    if (section.type === "comparison") return (
      <div key={si} style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 24 }}>
        {[section.left, section.right].map((side, i) => (
          <div key={i} style={{
            background: `${side.color}10`, border: `1px solid ${side.color}44`,
            borderRadius: 12, padding: 20,
          }}>
            <div style={{ fontSize: 15, fontWeight: 700, color: side.color, marginBottom: 14 }}>{side.title}</div>
            {side.points.map((p, pi) => (
              <div key={pi} style={{ display: "flex", gap: 8, marginBottom: 10, alignItems: "flex-start" }}>
                <span style={{ color: side.color, flexShrink: 0 }}>{i === 0 ? "✗" : "✓"}</span>
                <span style={{ fontSize: 13, color: "#C8D8E8", lineHeight: 1.5 }}>{p}</span>
              </div>
            ))}
          </div>
        ))}
      </div>
    );

    if (section.type === "flow") return (
      <div key={si} style={{ marginBottom: 24 }}>
        <div style={{ fontSize: 12, color: "#5A7A9A", letterSpacing: 2, marginBottom: 16 }}>{section.title.toUpperCase()}</div>
        {section.steps.map((step, si2) => (
          <div key={si2} style={{ display: "flex", gap: 12, marginBottom: 12, alignItems: "flex-start" }}>
            <div style={{
              width: 36, height: 36, borderRadius: "50%", flexShrink: 0,
              background: `${chapter.color}22`, border: `1px solid ${chapter.color}55`,
              display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16,
            }}>{step.icon}</div>
            <div style={{
              flex: 1, background: "#0D1928", border: "1px solid #1E2D45",
              borderRadius: 8, padding: "10px 14px",
              fontSize: 14, color: "#C8D8E8", lineHeight: 1.5,
            }}>{step.text}</div>
          </div>
        ))}
      </div>
    );

    if (section.type === "agents") return (
      <div key={si} style={{ marginBottom: 24 }}>
        <div style={{ fontSize: 12, color: "#5A7A9A", letterSpacing: 2, marginBottom: 16 }}>{section.title.toUpperCase()}</div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 12 }}>
          {section.items.map((agent, ai) => (
            <div key={ai}
              onClick={() => setExpandedAgent(expandedAgent === ai ? null : ai)}
              style={{
                background: expandedAgent === ai ? `${agent.color}15` : "#0D1928",
                border: `1px solid ${expandedAgent === ai ? agent.color + "66" : "#1E2D45"}`,
                borderRadius: 12, padding: 18, cursor: "pointer", transition: "all 0.2s",
              }}>
              <div style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
                <div style={{
                  width: 40, height: 40, borderRadius: 10, background: `${agent.color}22`,
                  display: "flex", alignItems: "center", justifyContent: "center", fontSize: 20, flexShrink: 0,
                }}>{agent.icon}</div>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 700, color: "#fff" }}>{agent.name}</div>
                  <div style={{ fontSize: 11, color: agent.color, marginTop: 2 }}>{agent.role}</div>
                </div>
              </div>
              {expandedAgent === ai && (
                <div style={{ fontSize: 13, color: "#C8D8E8", lineHeight: 1.7, marginTop: 12, paddingTop: 12, borderTop: "1px solid #1E2D45" }}>
                  {agent.desc}
                </div>
              )}
            </div>
          ))}
        </div>
        <div style={{ fontSize: 11, color: "#5A7A9A", marginTop: 8 }}>👆 Tap any agent to learn what they do</div>
      </div>
    );

    if (section.type === "memory_types") return (
      <div key={si} style={{ marginBottom: 24 }}>
        {section.items.map((mem, mi) => (
          <div key={mi} style={{
            background: "#0D1928", border: `1px solid ${mem.color}44`,
            borderRadius: 12, padding: 22, marginBottom: 12,
            borderLeft: `4px solid ${mem.color}`,
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 8 }}>
              <div>
                <div style={{ fontSize: 18, marginBottom: 4 }}>{mem.icon}</div>
                <div style={{ fontSize: 16, fontWeight: 700, color: mem.color }}>{mem.type}</div>
                <div style={{ fontSize: 11, color: "#5A7A9A", marginTop: 2 }}>Tech: {mem.tech}</div>
              </div>
              <span style={{
                fontSize: 10, color: mem.color, background: `${mem.color}22`,
                border: `1px solid ${mem.color}44`, padding: "3px 10px", borderRadius: 100,
              }}>{mem.ttl}</span>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginTop: 14 }}>
              <div style={{ background: "#111D2C", borderRadius: 8, padding: 12 }}>
                <div style={{ fontSize: 10, color: "#5A7A9A", marginBottom: 6 }}>HUMAN EQUIVALENT</div>
                <div style={{ fontSize: 13, color: "#C8D8E8" }}>{mem.human}</div>
              </div>
              <div style={{ background: "#111D2C", borderRadius: 8, padding: 12 }}>
                <div style={{ fontSize: 10, color: "#5A7A9A", marginBottom: 6 }}>IN THIS SYSTEM</div>
                <div style={{ fontSize: 13, color: "#C8D8E8" }}>{mem.system}</div>
              </div>
            </div>
          </div>
        ))}
      </div>
    );

    if (section.type === "scenarios") return (
      <div key={si}>
        <div style={{ display: "flex", gap: 8, marginBottom: 20, flexWrap: "wrap" }}>
          {section.items.map((sc, sci) => (
            <button key={sci} onClick={() => setExpandedScenario(sci)} style={{
              background: expandedScenario === sci ? `${sc.color}22` : "#0D1928",
              border: `1px solid ${expandedScenario === sci ? sc.color : "#1E2D45"}`,
              color: expandedScenario === sci ? sc.color : "#5A7A9A",
              borderRadius: 8, padding: "8px 16px", cursor: "pointer",
              fontSize: 13, fontWeight: 600,
              fontFamily: "inherit", transition: "all 0.2s",
            }}>
              {sc.icon} {sc.title.split(":")[0]}
            </button>
          ))}
        </div>
        {section.items[expandedScenario] && (() => {
          const sc = section.items[expandedScenario];
          return (
            <div style={{ border: `1px solid ${sc.color}44`, borderRadius: 12, overflow: "hidden" }}>
              <div style={{
                padding: "18px 22px",
                background: `linear-gradient(90deg, ${sc.color}18, #0D1928)`,
                borderBottom: "1px solid #1E2D45",
              }}>
                <div style={{ fontSize: 16, fontWeight: 700, color: "#fff", fontFamily: "Georgia, serif" }}>
                  {sc.icon} {sc.title}
                </div>
              </div>
              <div style={{ padding: 22 }}>
                {sc.timeline.map((step, sti) => (
                  <div key={sti} style={{ display: "flex", gap: 14, marginBottom: 14, alignItems: "flex-start" }}>
                    <div style={{
                      minWidth: 60, fontSize: 11, fontWeight: 700,
                      color: typeColors[step.type] || "#5A7A9A",
                      paddingTop: 2, textAlign: "right",
                    }}>{step.time}</div>
                    <div style={{ width: 2, background: `${typeColors[step.type]}44`, flexShrink: 0, alignSelf: "stretch", minHeight: 20 }} />
                    <div style={{
                      flex: 1, background: `${typeColors[step.type]}10`,
                      border: `1px solid ${typeColors[step.type]}33`,
                      borderRadius: 8, padding: "10px 14px",
                      fontSize: 14, color: "#C8D8E8", lineHeight: 1.5,
                    }}>
                      {step.event}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          );
        })()}
      </div>
    );

    if (section.type === "stats") return (
      <div key={si} style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 14, marginBottom: 24 }}>
        {section.items.map((s, i) => (
          <div key={i} style={{
            background: "#0D1928", border: `1px solid ${s.color}44`,
            borderRadius: 12, padding: 20, textAlign: "center",
          }}>
            <div style={{ fontSize: 28, fontWeight: 900, color: s.color, fontFamily: "Georgia, serif" }}>{s.value}</div>
            <div style={{ fontSize: 13, color: "#fff", marginTop: 4, fontWeight: 600 }}>{s.label}</div>
            <div style={{ fontSize: 11, color: "#5A7A9A", marginTop: 4 }}>{s.sub}</div>
          </div>
        ))}
      </div>
    );

    return null;
  };

  return (
    <div style={{
      background: "#070B14", minHeight: "100vh",
      fontFamily: "'Segoe UI', system-ui, sans-serif",
      color: "#E2EAF4",
      display: "flex", flexDirection: "column",
    }}>
      {/* Top Bar */}
      <div style={{
        background: "#0D1524", borderBottom: "1px solid #1E2D45",
        padding: "16px 24px", display: "flex", alignItems: "center", gap: 12,
      }}>
        <span style={{ fontSize: 22 }}>💳</span>
        <div>
          <div style={{ fontSize: 16, fontWeight: 700, color: "#fff" }}>PayFac AI — Plain English Guide</div>
          <div style={{ fontSize: 12, color: "#5A7A9A" }}>No jargon. No buzzwords. Just simple explanations.</div>
        </div>
      </div>

      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        {/* Sidebar Nav */}
        <div style={{
          width: 220, background: "#0D1524", borderRight: "1px solid #1E2D45",
          padding: "20px 0", flexShrink: 0, overflowY: "auto",
        }}>
          {chapters.map((ch, ci) => (
            <div key={ch.id}
              onClick={() => setActiveChapter(ci)}
              style={{
                padding: "14px 20px", cursor: "pointer",
                background: activeChapter === ci ? `${ch.color}15` : "transparent",
                borderLeft: activeChapter === ci ? `3px solid ${ch.color}` : "3px solid transparent",
                transition: "all 0.2s",
              }}>
              <div style={{ fontSize: 18, marginBottom: 4 }}>{ch.emoji}</div>
              <div style={{ fontSize: 13, fontWeight: activeChapter === ci ? 700 : 400, color: activeChapter === ci ? "#fff" : "#5A7A9A" }}>
                {ch.title}
              </div>
              <div style={{ fontSize: 11, color: "#3A5A7A", marginTop: 2 }}>{ch.subtitle}</div>
            </div>
          ))}
        </div>

        {/* Main Content */}
        <div style={{ flex: 1, overflowY: "auto", padding: "32px 36px" }}>
          {/* Chapter Header */}
          <div style={{ marginBottom: 32 }}>
            <div style={{ fontSize: 48, marginBottom: 10 }}>{chapter.emoji}</div>
            <h1 style={{
              margin: 0, fontSize: 28, fontWeight: 800, color: "#fff",
              fontFamily: "Georgia, serif", lineHeight: 1.2,
            }}>{chapter.title}</h1>
            <div style={{ fontSize: 15, color: chapter.color, marginTop: 6, fontWeight: 500 }}>
              {chapter.subtitle}
            </div>
            <div style={{ height: 2, background: `linear-gradient(90deg, ${chapter.color}, transparent)`, marginTop: 16, borderRadius: 2 }} />
          </div>

          {/* Sections */}
          {chapter.sections.map((section, si) => renderSection(section, si))}

          {/* Navigation */}
          <div style={{ display: "flex", justifyContent: "space-between", marginTop: 32, paddingTop: 24, borderTop: "1px solid #1E2D45" }}>
            <button
              onClick={() => setActiveChapter(Math.max(0, activeChapter - 1))}
              disabled={activeChapter === 0}
              style={{
                background: activeChapter === 0 ? "transparent" : "#0D1928",
                border: "1px solid #1E2D45",
                color: activeChapter === 0 ? "#3A5A7A" : "#C8D8E8",
                padding: "10px 20px", borderRadius: 8, cursor: activeChapter === 0 ? "default" : "pointer",
                fontSize: 14, fontFamily: "inherit",
              }}>
              ← Previous
            </button>
            <span style={{ fontSize: 12, color: "#5A7A9A", alignSelf: "center" }}>
              {activeChapter + 1} / {chapters.length}
            </span>
            <button
              onClick={() => setActiveChapter(Math.min(chapters.length - 1, activeChapter + 1))}
              disabled={activeChapter === chapters.length - 1}
              style={{
                background: activeChapter === chapters.length - 1 ? "transparent" : chapter.color,
                border: `1px solid ${chapter.color}`,
                color: activeChapter === chapters.length - 1 ? "#3A5A7A" : "#070B14",
                padding: "10px 20px", borderRadius: 8,
                cursor: activeChapter === chapters.length - 1 ? "default" : "pointer",
                fontSize: 14, fontWeight: 700, fontFamily: "inherit",
              }}>
              Next →
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
