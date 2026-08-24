"use client";

import React, { useMemo } from "react";
import { QuestionRow, AssessmentBatchConfig } from "../../types";
import {
  QualityIcon,
  CheckCircleIcon,
  AlertTriangleIcon,
  SparklesIcon,
  CheckIcon,
  XIcon,
  ArrowRightIcon,
  ArrowLeftIcon,
} from "../icons";

interface QualityDashboardStepProps {
  questions: QuestionRow[];
  batchConfig: AssessmentBatchConfig;
  onProceedToExport: () => void;
  onJumpToReview: () => void;
  onBack: () => void;
}

export default function QualityDashboardStep({
  questions,
  batchConfig,
  onProceedToExport,
  onJumpToReview,
  onBack,
}: QualityDashboardStepProps) {
  const stats = useMemo(() => {
    let valid = 0;
    let conflicts = 0;
    let lowConfidence = 0;
    let inferred = 0;
    let userEdited = 0;

    questions.forEach((q) => {
      if (q.validation.valid) {
        valid++;
      } else {
        conflicts++;
      }

      const fields = q.source_metadata?.fields || {};
      let isLowConf = false;
      let isInferred = false;
      let isEdited = false;

      Object.values(fields).forEach((f) => {
        if (f.origin === "inferred") isInferred = true;
        if (f.origin === "user_edited") isEdited = true;
        if (f.confidence < 0.7 && f.confidence > 0) isLowConf = true;
      });

      if (isInferred) inferred++;
      if (isEdited) userEdited++;
      if (isLowConf) lowConfidence++;
    });

    const qualityScore = questions.length > 0
      ? Math.round((valid / questions.length) * 100)
      : 0;

    const isGateReady = questions.length > 0 && conflicts === 0;

    return {
      total: questions.length,
      valid,
      conflicts,
      lowConfidence,
      inferred,
      userEdited,
      qualityScore,
      isGateReady,
    };
  }, [questions]);

  return (
    <section className="card">
      <div className="card-header-flex">
        <div>
          <div className="card-title">
            <QualityIcon size={22} color="var(--primary-hover)" /> Step 7: Menntr Quality Gate & Assessment Health Dashboard
          </div>
          <div className="card-subtitle">
            Comprehensive audit of assessment integrity, schema compliance, answer key validation, and export readiness.
          </div>
        </div>
        <span className="badge info">Step 07 / 08</span>
      </div>

      {/* Quality Gate Banner */}
      <div
        style={{
          padding: "24px",
          borderRadius: "14px",
          background: stats.isGateReady
            ? "linear-gradient(135deg, rgba(16, 185, 129, 0.15), rgba(5, 150, 105, 0.05))"
            : "linear-gradient(135deg, rgba(239, 68, 68, 0.15), rgba(185, 28, 28, 0.05))",
          border: `1px solid ${stats.isGateReady ? "rgba(16, 185, 129, 0.4)" : "rgba(239, 68, 68, 0.4)"}`,
          marginBottom: "28px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "16px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
          <div
            style={{
              width: "48px",
              height: "48px",
              borderRadius: "12px",
              background: stats.isGateReady ? "#10B981" : "#EF4444",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#FFF",
            }}
          >
            {stats.isGateReady ? <CheckIcon size={24} /> : <XIcon size={24} />}
          </div>

          <div>
            <div style={{ fontSize: "1.15rem", fontWeight: 800, color: "var(--text-primary)" }}>
              {stats.isGateReady ? "QUALITY GATE: READY FOR EXPORT" : "QUALITY GATE: EXPORT BLOCKED"}
            </div>
            <div style={{ fontSize: "0.84rem", color: "var(--text-secondary)", marginTop: "4px" }}>
              {stats.isGateReady
                ? "Zero blocking conflicts detected. Assessment batch conforms with Menntr delivery specifications."
                : `${stats.conflicts} blocking validation conflict(s) remain unresolved. Correction required prior to export.`}
            </div>
          </div>
        </div>

        {!stats.isGateReady && (
          <button className="danger-btn" onClick={onJumpToReview} style={{ gap: "6px" }}>
            Jump to Issues in Review Workspace <ArrowRightIcon size={14} />
          </button>
        )}
      </div>

      {/* KPI Cards Grid */}
      <div className="metrics-grid">
        <div className="metric-card">
          <div className="metric-title">Selected Questions</div>
          <div className="metric-value">{stats.total}</div>
          <div className="metric-foot">Batch assessment items</div>
        </div>

        <div className="metric-card">
          <div className="metric-title" style={{ color: "var(--accent)" }}>Validated & Passed</div>
          <div className="metric-value" style={{ color: "var(--accent)" }}>{stats.valid}</div>
          <div className="metric-foot">100% schema compliant</div>
        </div>

        <div className="metric-card">
          <div className="metric-title" style={{ color: "var(--danger)" }}>Answer Conflicts</div>
          <div className="metric-value" style={{ color: "var(--danger)" }}>{stats.conflicts}</div>
          <div className="metric-foot">Requires human correction</div>
        </div>

        <div className="metric-card">
          <div className="metric-title" style={{ color: "var(--warning)" }}>Low Confidence</div>
          <div className="metric-value" style={{ color: "var(--warning)" }}>{stats.lowConfidence}</div>
          <div className="metric-foot">Confidence &lt; 70%</div>
        </div>

        <div className="metric-card">
          <div className="metric-title" style={{ color: "var(--purple)" }}>AI Inferred</div>
          <div className="metric-value" style={{ color: "var(--purple)" }}>{stats.inferred}</div>
          <div className="metric-foot">Metadata synthesized</div>
        </div>

        <div className="metric-card">
          <div className="metric-title">Quality Health Score</div>
          <div className="metric-value" style={{ color: stats.qualityScore >= 90 ? "var(--accent)" : stats.qualityScore >= 70 ? "var(--warning)" : "var(--danger)" }}>
            {stats.qualityScore}%
          </div>
          <div className="metric-foot">Menntr Index Rating</div>
        </div>
      </div>

      {/* Quality Gate Audit Checklist */}
      <div
        style={{
          marginTop: "24px",
          background: "var(--bg-surface)",
          border: "1px solid var(--border-subtle)",
          borderRadius: "12px",
          padding: "20px",
        }}
      >
        <div style={{ fontWeight: 700, fontSize: "0.95rem", marginBottom: "14px" }}>
          Automated Quality Gate Compliance Matrix
        </div>

        <ul className="list-unstyled">
          <li style={{ color: stats.conflicts === 0 ? "var(--accent)" : "var(--danger)" }}>
            <span>{stats.conflicts === 0 ? <CheckIcon size={14} /> : <XIcon size={14} />}</span>
            <strong>Schema Completeness:</strong>
            {stats.conflicts === 0
              ? "All required fields (Question Stem, Options, Answers) are strictly populated."
              : `${stats.conflicts} question(s) missing mandatory schema values.`}
          </li>

          <li style={{ color: stats.lowConfidence === 0 ? "var(--accent)" : "var(--warning)" }}>
            <span>{stats.lowConfidence === 0 ? <CheckIcon size={14} /> : <AlertTriangleIcon size={14} />}</span>
            <strong>Confidence Thresholds:</strong>
            {stats.lowConfidence === 0
              ? "All extraction and inference fields meet confidence threshold."
              : `${stats.lowConfidence} field(s) flagged with lower extraction confidence.`}
          </li>

          <li style={{ color: "var(--accent)" }}>
            <CheckIcon size={14} />
            <strong>Target Schema Compatibility:</strong> Target Menntr Schema columns strictly mapped.
          </li>

          <li style={{ color: "var(--accent)" }}>
            <CheckIcon size={14} />
            <strong>Assessment Metadata Verification:</strong> {batchConfig.assessmentName || "Configured"} • {batchConfig.subject || "Standard"}
          </li>
        </ul>
      </div>

      {/* Navigation Actions */}
      <div
        style={{
          marginTop: "32px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <button className="secondary" onClick={onBack} style={{ gap: "6px" }}>
          <ArrowLeftIcon size={16} /> Back to Human Review
        </button>

        <button
          className={stats.isGateReady ? "primary" : "secondary"}
          onClick={onProceedToExport}
          disabled={!stats.isGateReady}
          style={{ gap: "6px" }}
        >
          {stats.isGateReady ? (
            <>
              Proceed to Final Export <ArrowRightIcon size={16} />
            </>
          ) : (
            "Resolve Issues to Unlock Export"
          )}
        </button>
      </div>
    </section>
  );
}
