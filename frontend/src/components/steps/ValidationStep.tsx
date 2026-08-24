"use client";

import React, { useState, useMemo } from "react";
import { QuestionRow } from "../../types";
import AlertPanel from "../AlertPanel";
import {
  ValidationIcon,
  CheckCircleIcon,
  AlertTriangleIcon,
  SparklesIcon,
  ArrowRightIcon,
  ArrowLeftIcon,
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
  const [selectedFilter, setSelectedFilter] = useState<"ALL" | "VALIDATED" | "CONFLICT" | "REVIEW_REQUIRED" | "INFERRED">("ALL");

  const answerCol = columns.find((c) => /answer|correct/i.test(c)) || "Correct Answer";

  const metrics = useMemo(() => {
    let validCount = 0;
    let conflictCount = 0;
    let reviewRequiredCount = 0;
    let inferredCount = 0;

    questions.forEach((q) => {
      if (q.validation.valid) {
        validCount++;
      } else {
        conflictCount++;
      }

      const rawAns = q.data_json[answerCol] || "";
      if (!rawAns.trim()) {
        reviewRequiredCount++;
      }

      const fields = q.source_metadata?.fields || {};
      if (Object.values(fields).some((f) => f.origin === "inferred")) {
        inferredCount++;
      }
    });

    const qualityPercentage = questions.length > 0
      ? Math.round((validCount / questions.length) * 100)
      : 0;

    return {
      total: questions.length,
      valid: validCount,
      conflicts: conflictCount,
      reviewRequired: reviewRequiredCount,
      inferred: inferredCount,
      qualityPercentage,
    };
  }, [questions, answerCol]);

  const filteredQuestions = useMemo(() => {
    return questions.filter((q) => {
      if (selectedFilter === "ALL") return true;
      if (selectedFilter === "VALIDATED") return q.validation.valid;
      if (selectedFilter === "CONFLICT") return !q.validation.valid;
      if (selectedFilter === "REVIEW_REQUIRED") return !(q.data_json[answerCol] || "").trim();
      if (selectedFilter === "INFERRED") {
        const fields = q.source_metadata?.fields || {};
        return Object.values(fields).some((f) => f.origin === "inferred");
      }
      return true;
    });
  }, [questions, selectedFilter, answerCol]);

  const getStatusBadge = (q: QuestionRow) => {
    if (!q.validation.valid) {
      return <span className="badge danger">Answer Conflict</span>;
    }
    const rawAns = q.data_json[answerCol] || "";
    if (!rawAns.trim()) {
      return <span className="badge warning">Review Required</span>;
    }
    const fields = q.source_metadata?.fields || {};
    const hasInferred = Object.values(fields).some((f) => f.origin === "inferred");
    if (hasInferred) {
      return (
        <span className="badge purple" style={{ display: "inline-flex", alignItems: "center", gap: "4px" }}>
          <SparklesIcon size={12} /> AI Inferred
        </span>
      );
    }
    return (
      <span className="badge success" style={{ display: "inline-flex", alignItems: "center", gap: "4px" }}>
        <CheckCircleIcon size={12} /> AI Validated
      </span>
    );
  };

  return (
    <section className="card">
      <div className="card-header-flex">
        <div>
          <div className="card-title">
            <ValidationIcon size={22} color="var(--primary-hover)" /> Step 5: Automated AI Validation & Parity Analysis
          </div>
          <div className="card-subtitle">
            Source answer extraction, parity check, and metadata confidence computed across all {questions.length} selected questions.
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
          <div className="metric-foot">Selected questions</div>
        </div>

        <div
          className={`metric-card ${selectedFilter === "VALIDATED" ? "active" : ""}`}
          onClick={() => setSelectedFilter("VALIDATED")}
          style={{ cursor: "pointer" }}
        >
          <div className="metric-title" style={{ color: "var(--accent)" }}>AI Validated</div>
          <div className="metric-value" style={{ color: "var(--accent)" }}>{metrics.valid}</div>
          <div className="metric-foot">Schema & parity passed</div>
        </div>

        <div
          className={`metric-card ${selectedFilter === "CONFLICT" ? "active" : ""}`}
          onClick={() => setSelectedFilter("CONFLICT")}
          style={{ cursor: "pointer" }}
        >
          <div className="metric-title" style={{ color: "var(--danger)" }}>Answer Conflicts</div>
          <div className="metric-value" style={{ color: "var(--danger)" }}>{metrics.conflicts}</div>
          <div className="metric-foot">Requires human review</div>
        </div>

        <div
          className={`metric-card ${selectedFilter === "INFERRED" ? "active" : ""}`}
          onClick={() => setSelectedFilter("INFERRED")}
          style={{ cursor: "pointer" }}
        >
          <div className="metric-title" style={{ color: "var(--purple)" }}>AI Inferred Fields</div>
          <div className="metric-value" style={{ color: "var(--purple)" }}>{metrics.inferred}</div>
          <div className="metric-foot">Traceable metadata</div>
        </div>

        <div className="metric-card">
          <div className="metric-title">Integrity Score</div>
          <div className="metric-value" style={{ color: metrics.qualityPercentage >= 80 ? "var(--accent)" : "var(--warning)" }}>
            {metrics.qualityPercentage}%
          </div>
          <div className="metric-foot">Compliance index</div>
        </div>
      </div>

      {metrics.conflicts > 0 && (
        <AlertPanel type="warning" style={{ marginBottom: "20px" }}>
          <strong>Answer Parity Notice:</strong> {metrics.conflicts} question(s) contain validation or answer key conflicts. Inspect and resolve them in the Human Review Workspace before export.
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
                <th style={{ width: "70px", textAlign: "center" }}>Row</th>
                <th style={{ width: "90px", textAlign: "center" }}>Source</th>
                <th style={{ width: "170px" }}>Validation Status</th>
                <th>Question Stem</th>
                <th style={{ width: "120px" }}>Answer Key</th>
                <th style={{ width: "240px" }}>Parity / Schema Diagnostics</th>
              </tr>
            </thead>
            <tbody>
              {filteredQuestions.map((q) => {
                const questionTextKey = columns.find(
                  (c) => /question|item_text|prompt/i.test(c)
                ) || columns[0] || "";
                
                const questionSnippet = q.data_json[questionTextKey] || "—";
                const ans = q.data_json[answerCol] || "MISSING";

                return (
                  <tr key={q.id}>
                    <td style={{ textAlign: "center", fontWeight: 700 }}>#{q.row_number}</td>
                    <td style={{ textAlign: "center", color: "var(--text-secondary)" }}>
                      {q.source_metadata?.source_page ? `p. ${q.source_metadata.source_page}` : "—"}
                    </td>
                    <td>{getStatusBadge(q)}</td>
                    <td style={{ maxWidth: "340px", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                      {questionSnippet}
                    </td>
                    <td>
                      <span className={`badge ${ans !== "MISSING" ? "success" : "danger"}`}>
                        {ans}
                      </span>
                    </td>
                    <td>
                      {!q.validation.valid ? (
                        <div style={{ color: "var(--danger)", fontSize: "0.78rem" }}>
                          {q.validation.errors.map((err, i) => (
                            <div key={i}>• {err}</div>
                          ))}
                        </div>
                      ) : (
                        <span style={{ color: "var(--accent)", fontSize: "0.78rem" }}>
                          ✓ Parity Verified
                        </span>
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
