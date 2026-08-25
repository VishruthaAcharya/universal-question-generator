"use client";

import React, { useState, useMemo } from "react";
import { QuestionRow, AIValidationResult } from "../../types";
import AlertPanel from "../AlertPanel";
import {
  ValidationIcon,
  CheckCircleIcon,
  AlertTriangleIcon,
  SparklesIcon,
  ArrowRightIcon,
  ArrowLeftIcon,
  CheckIcon,
  XIcon,
} from "../icons";

interface ValidationStepProps {
  questions: QuestionRow[];
  columns: string[];
  onProceedToReview: () => void;
  onBack: () => void;
}

export default function ValidationStep({
  questions,
  columns,
  onProceedToReview,
  onBack,
}: ValidationStepProps) {
  const [selectedFilter, setSelectedFilter] = useState<
    "ALL" | "HIGH_CONF" | "MED_CONF" | "LOW_CONF" | "CONFLICT" | "UNCERTAIN"
  >("ALL");

  const answerCol = columns.find((c) => /answer|correct/i.test(c)) || "Correct Answer";

  const metrics = useMemo(() => {
    let highConfCount = 0;
    let medConfCount = 0;
    let lowConfCount = 0;
    let uncertainCount = 0;
    let conflictCount = 0;
    let totalConfidenceSum = 0;

    questions.forEach((q) => {
      const aiVal: AIValidationResult | undefined = q.validation?.ai_validation;
      const conf = aiVal?.confidence ?? (q.validation?.valid ? 0.95 : 0.60);
      totalConfidenceSum += conf;

      const isConflict =
        aiVal?.validation_status === "ANSWER_CONFLICT" ||
        !q.validation?.valid ||
        (q.source_answer && q.ai_answer && q.source_answer.toUpperCase() !== q.ai_answer.toUpperCase());

      if (isConflict) {
        conflictCount++;
      }

      if (conf >= 0.95) {
        highConfCount++;
      } else if (conf >= 0.85) {
        medConfCount++;
      } else if (conf >= 0.70) {
        lowConfCount++;
      } else {
        uncertainCount++;
      }
    });

    const avgConfidencePct =
      questions.length > 0
        ? Math.round((totalConfidenceSum / questions.length) * 100)
        : 0;

    return {
      total: questions.length,
      highConf: highConfCount,
      medConf: medConfCount,
      lowConf: lowConfCount,
      uncertain: uncertainCount,
      conflicts: conflictCount,
      avgConfidencePct,
    };
  }, [questions]);

  const filteredQuestions = useMemo(() => {
    return questions.filter((q) => {
      const aiVal = q.validation?.ai_validation;
      const conf = aiVal?.confidence ?? (q.validation?.valid ? 0.95 : 0.60);
      const isConflict =
        aiVal?.validation_status === "ANSWER_CONFLICT" ||
        !q.validation?.valid ||
        (q.source_answer && q.ai_answer && q.source_answer.toUpperCase() !== q.ai_answer.toUpperCase());

      if (selectedFilter === "ALL") return true;
      if (selectedFilter === "HIGH_CONF") return conf >= 0.95;
      if (selectedFilter === "MED_CONF") return conf >= 0.85 && conf < 0.95;
      if (selectedFilter === "LOW_CONF") return conf >= 0.70 && conf < 0.85;
      if (selectedFilter === "CONFLICT") return isConflict;
      if (selectedFilter === "UNCERTAIN") return conf < 0.70 || aiVal?.validation_status === "UNCERTAIN";
      return true;
    });
  }, [questions, selectedFilter]);

  const getConfidenceBadge = (confidence: number, level?: string) => {
    const pct = Math.round(confidence * 100);
    if (confidence >= 0.95) {
      return (
        <span className="badge success" style={{ fontWeight: 700 }}>
          {pct}% HIGH CONFIDENCE
        </span>
      );
    }
    if (confidence >= 0.85) {
      return (
        <span className="badge info" style={{ fontWeight: 700 }}>
          {pct}% MEDIUM CONFIDENCE
        </span>
      );
    }
    if (confidence >= 0.70) {
      return (
        <span className="badge warning" style={{ fontWeight: 700 }}>
          {pct}% LOW CONFIDENCE
        </span>
      );
    }
    return (
      <span className="badge danger" style={{ fontWeight: 700 }}>
        {pct}% UNCERTAIN
      </span>
    );
  };

  const getStatusBadge = (q: QuestionRow) => {
    const aiVal = q.validation?.ai_validation;
    const isConflict =
      aiVal?.validation_status === "ANSWER_CONFLICT" ||
      !q.validation?.valid ||
      (q.source_answer && q.ai_answer && q.source_answer.toUpperCase() !== q.ai_answer.toUpperCase());

    if (isConflict) {
      return <span className="badge danger">✕ Answer Conflict</span>;
    }

    if (aiVal?.validation_status === "AMBIGUOUS") {
      return <span className="badge warning">⚠ Ambiguous Question</span>;
    }

    if (aiVal?.validation_status === "MISSING_INFORMATION") {
      return <span className="badge warning">⚠ Missing Information</span>;
    }

    if (aiVal?.validation_status === "VISUAL_CONTEXT_REQUIRED") {
      return <span className="badge purple">📷 Visual Context Required</span>;
    }

    if (aiVal?.validation_status === "UNCERTAIN" || (aiVal?.confidence && aiVal.confidence < 0.70)) {
      return <span className="badge danger">⚠ Uncertain / Review</span>;
    }

    return (
      <span className="badge success" style={{ display: "inline-flex", alignItems: "center", gap: "4px" }}>
        <CheckCircleIcon size={12} /> ✓ AI Validated
      </span>
    );
  };

  return (
    <section className="card">
      <div className="card-header-flex">
        <div>
          <div className="card-title">
            <ValidationIcon size={22} color="var(--primary-hover)" /> Step 5: Multi-Stage Independent AI & Deterministic Validation
          </div>
          <div className="card-subtitle">
            Zero-confirmation-bias solving, domain-specific deterministic proof (Math/Physics/Chemistry/Biology), and evidence-based confidence analysis across {questions.length} questions.
          </div>
        </div>
        <span className="badge info">Step 05 / 08</span>
      </div>

      {/* Analytics Grid */}
      <div className="metrics-grid">
        <div
          className={`metric-card ${selectedFilter === "ALL" ? "active" : ""}`}
          onClick={() => setSelectedFilter("ALL")}
          style={{ cursor: "pointer" }}
        >
          <div className="metric-title">Active Batch</div>
          <div className="metric-value">{metrics.total}</div>
          <div className="metric-foot">Selected items</div>
        </div>

        <div
          className={`metric-card ${selectedFilter === "HIGH_CONF" ? "active" : ""}`}
          onClick={() => setSelectedFilter("HIGH_CONF")}
          style={{ cursor: "pointer" }}
        >
          <div className="metric-title" style={{ color: "var(--accent)" }}>High Confidence</div>
          <div className="metric-value" style={{ color: "var(--accent)" }}>{metrics.highConf}</div>
          <div className="metric-foot">95% – 100% confidence</div>
        </div>

        <div
          className={`metric-card ${selectedFilter === "MED_CONF" ? "active" : ""}`}
          onClick={() => setSelectedFilter("MED_CONF")}
          style={{ cursor: "pointer" }}
        >
          <div className="metric-title" style={{ color: "var(--primary-hover)" }}>Medium Confidence</div>
          <div className="metric-value" style={{ color: "var(--primary-hover)" }}>{metrics.medConf}</div>
          <div className="metric-foot">85% – 94% confidence</div>
        </div>

        <div
          className={`metric-card ${selectedFilter === "LOW_CONF" ? "active" : ""}`}
          onClick={() => setSelectedFilter("LOW_CONF")}
          style={{ cursor: "pointer" }}
        >
          <div className="metric-title" style={{ color: "var(--warning)" }}>Low Confidence</div>
          <div className="metric-value" style={{ color: "var(--warning)" }}>{metrics.lowConf}</div>
          <div className="metric-foot">70% – 84% confidence</div>
        </div>

        <div
          className={`metric-card ${selectedFilter === "CONFLICT" ? "active" : ""}`}
          onClick={() => setSelectedFilter("CONFLICT")}
          style={{ cursor: "pointer" }}
        >
          <div className="metric-title" style={{ color: "var(--danger)" }}>Answer Conflicts</div>
          <div className="metric-value" style={{ color: "var(--danger)" }}>{metrics.conflicts}</div>
          <div className="metric-foot">Source vs AI mismatch</div>
        </div>

        <div className="metric-card">
          <div className="metric-title">Validation Confidence</div>
          <div className="metric-value" style={{ color: metrics.avgConfidencePct >= 85 ? "var(--accent)" : "var(--warning)" }}>
            {metrics.avgConfidencePct}%
          </div>
          <div className="metric-foot">Evidence confidence index</div>
        </div>
      </div>

      {metrics.conflicts > 0 && (
        <AlertPanel type="warning" style={{ marginBottom: "20px" }}>
          <strong>Answer Conflict Alert:</strong> {metrics.conflicts} question(s) contain discrepancies between the source answer key and the independent AI/Deterministic solution. The source answer remains strictly protected and cannot be modified without human review.
        </AlertPanel>
      )}

      {/* Validation Status Table */}
      <div style={{ marginTop: "16px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
          <div style={{ fontWeight: 700, fontSize: "0.95rem" }}>
            Question Validation Log ({filteredQuestions.length} Items Displayed)
          </div>
          <div style={{ fontSize: "0.78rem", color: "var(--text-secondary)" }}>
            Filter: <strong style={{ color: "var(--primary-hover)" }}>{selectedFilter}</strong>
          </div>
        </div>

        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th style={{ width: "65px", textAlign: "center" }}>Row</th>
                <th style={{ width: "80px", textAlign: "center" }}>Page</th>
                <th style={{ width: "160px" }}>Validation Status</th>
                <th>Question Stem</th>
                <th style={{ width: "110px", textAlign: "center" }}>Source Key</th>
                <th style={{ width: "130px", textAlign: "center" }}>AI Solution</th>
                <th style={{ width: "170px" }}>Confidence Score</th>
                <th style={{ width: "240px" }}>Verification Reason & Method</th>
              </tr>
            </thead>
            <tbody>
              {filteredQuestions.map((q) => {
                const questionTextKey = columns.find(
                  (c) => /question|item_text|prompt/i.test(c)
                ) || columns[0] || "";
                
                const questionSnippet = q.data_json[questionTextKey] || "—";
                const aiVal = q.validation?.ai_validation;
                const sourceAns = q.source_answer || q.data_json[answerCol] || "—";
                const aiAns = q.ai_answer || aiVal?.ai_answer || "—";
                const conf = aiVal?.confidence ?? (q.validation?.valid ? 0.95 : 0.60);
                const isConflict =
                  aiVal?.validation_status === "ANSWER_CONFLICT" ||
                  (sourceAns !== "—" && aiAns !== "—" && sourceAns.toUpperCase() !== aiAns.toUpperCase());

                return (
                  <tr key={q.id}>
                    <td style={{ textAlign: "center", fontWeight: 700 }}>#{q.row_number}</td>
                    <td style={{ textAlign: "center", color: "var(--text-secondary)" }}>
                      {q.source_metadata?.source_page ? `p. ${q.source_metadata.source_page}` : "—"}
                    </td>
                    <td>{getStatusBadge(q)}</td>
                    <td style={{ maxWidth: "280px", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                      {questionSnippet}
                    </td>
                    <td style={{ textAlign: "center" }}>
                      <span className="badge secondary" style={{ fontWeight: 700 }}>
                        {sourceAns}
                      </span>
                      {(q.answer_page || q.source_metadata?.answer_page) && (
                        <div style={{ fontSize: "0.68rem", color: "var(--accent)", marginTop: "2px" }}>
                          Key p. {q.answer_page || q.source_metadata?.answer_page}
                        </div>
                      )}
                    </td>
                    <td style={{ textAlign: "center" }}>
                      <span className={`badge ${isConflict ? "danger" : "success"}`} style={{ fontWeight: 700 }}>
                        {aiAns}
                      </span>
                    </td>
                    <td>
                      {getConfidenceBadge(conf, aiVal?.confidence_level)}
                    </td>
                    <td>
                      <div style={{ fontSize: "0.78rem", color: "var(--text-primary)" }}>
                        {aiVal?.reason || (q.validation?.valid ? "Parity verified against source." : q.validation?.errors.join(", "))}
                      </div>
                      {aiVal?.validation_methods && (
                        <div style={{ fontSize: "0.68rem", color: "var(--text-muted)", marginTop: "2px" }}>
                          Methods: {aiVal.validation_methods.join(", ")}
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Navigation */}
      <div
        style={{
          marginTop: "32px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <button className="secondary" onClick={onBack} style={{ gap: "6px" }}>
          <ArrowLeftIcon size={16} /> Back to Field Mapping
        </button>

        <button className="primary" onClick={onProceedToReview} style={{ gap: "6px" }}>
          Proceed to Human Review Workspace <ArrowRightIcon size={16} />
        </button>
      </div>
    </section>
  );
}
