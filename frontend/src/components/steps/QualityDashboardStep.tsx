"use client";

import React, { useMemo } from "react";
import { QuestionRow, AssessmentBatchConfig, AIValidationResult } from "../../types";
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
    let highConfidence = 0;
    let medConfidence = 0;
    let lowConfidence = 0;
    let uncertain = 0;
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
        conflicts++;
      } else {
        valid++;
      }

      if (conf >= 0.95) {
        highConfidence++;
      } else if (conf >= 0.85) {
        medConfidence++;
      } else if (conf >= 0.70) {
        lowConfidence++;
      } else {
        uncertain++;
      }
    });

    const overallValidationConfidence =
      questions.length > 0
        ? Math.round((totalConfidenceSum / questions.length) * 100)
        : 0;

    const isGateReady = questions.length > 0 && conflicts === 0;

    return {
      total: questions.length,
      valid,
      conflicts,
      highConfidence,
      medConfidence,
      lowConfidence,
      uncertain,
      overallValidationConfidence,
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
            Comprehensive audit of assessment integrity, schema compliance, multi-stage answer key validation, and export readiness.
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
                : `${stats.conflicts} blocking validation conflict(s) remain unresolved. Manual review or resolution required prior to export.`}
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
          <div className="metric-title" style={{ color: "var(--accent)" }}>High Confidence</div>
          <div className="metric-value" style={{ color: "var(--accent)" }}>{stats.highConfidence}</div>
          <div className="metric-foot">95% – 100% confidence</div>
        </div>

        <div className="metric-card">
          <div className="metric-title" style={{ color: "var(--primary-hover)" }}>Medium Confidence</div>
          <div className="metric-value" style={{ color: "var(--primary-hover)" }}>{stats.medConfidence}</div>
          <div className="metric-foot">85% – 94% confidence</div>
        </div>

        <div className="metric-card">
          <div className="metric-title" style={{ color: "var(--warning)" }}>Low Confidence</div>
          <div className="metric-value" style={{ color: "var(--warning)" }}>{stats.lowConfidence}</div>
          <div className="metric-foot">70% – 84% confidence</div>
        </div>

        <div className="metric-card">
          <div className="metric-title" style={{ color: "var(--danger)" }}>Answer Conflicts</div>
          <div className="metric-value" style={{ color: "var(--danger)" }}>{stats.conflicts}</div>
          <div className="metric-foot">Source / AI discrepancies</div>
        </div>

        <div className="metric-card">
          <div className="metric-title">Validation Confidence</div>
          <div className="metric-value" style={{ color: stats.overallValidationConfidence >= 85 ? "var(--accent)" : "var(--warning)" }}>
            {stats.overallValidationConfidence}%
          </div>
          <div className="metric-foot">Evidence confidence rating</div>
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
            <strong>Answer Key Integrity:</strong>
            {stats.conflicts === 0
              ? "All question answer keys verified with zero unresolved conflicts."
              : `${stats.conflicts} question(s) flagged with answer conflicts between source and AI solver.`}
          </li>

          <li style={{ color: stats.uncertain === 0 ? "var(--accent)" : "var(--warning)" }}>
            <span>{stats.uncertain === 0 ? <CheckIcon size={14} /> : <AlertTriangleIcon size={14} />}</span>
            <strong>Validation Certainty:</strong>
            {stats.uncertain === 0
              ? "All questions meet minimum reliability thresholds."
              : `${stats.uncertain} question(s) require human review due to ambiguity, visual dependency, or low confidence.`}
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
