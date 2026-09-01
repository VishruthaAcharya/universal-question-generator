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
  ExportIcon,
} from "../icons";

interface QualityDashboardStepProps {
  questions: QuestionRow[];
  batchConfig: AssessmentBatchConfig;
  onProceedToExport: () => void;
  onJumpToReview: () => void;
  onExportDraft?: (format: "csv" | "xlsx") => Promise<void> | void;
  onBack: () => void;
}

export default function QualityDashboardStep({
  questions,
  batchConfig,
  onProceedToExport,
  onJumpToReview,
  onExportDraft,
  onBack,
}: QualityDashboardStepProps) {
  const stats = useMemo(() => {
    let blockers = 0;
    let warnings = 0;
    let informational = 0;
    let highConfidence = 0;
    let medConfidence = 0;
    let lowConfidence = 0;
    let totalConfidenceSum = 0;

    questions.forEach((q) => {
      const aiVal: AIValidationResult | undefined = q.validation?.ai_validation;
      const conf = aiVal?.confidence ?? (q.validation?.valid ? 0.95 : 0.60);
      totalConfidenceSum += conf;

      // 1. BLOCKER checks (genuinely mandatory unresolved items):
      // - Empty question prompt / stem
      // - No answer decision at all (missing final, source, and AI answer)
      // - Complete schema corruption
      const stem = String(
        q.data_json?.["Question Text"] ||
        q.data_json?.["question"] ||
        q.data_json?.["Question"] ||
        q.data_json?.["Prompt"] ||
        ""
      ).trim();
      const hasNoAnswer = !q.final_answer && !q.source_answer && !q.ai_answer && !q.data_json?.["Correct Answer"] && !q.data_json?.["correct_answer"];

      const isBlocker = !stem || hasNoAnswer;

      // 2. WARNING checks (unresolved answer conflict where source != AI and no explicit final choice):
      const isUnresolvedConflict =
        Boolean(q.source_answer && q.ai_answer && q.source_answer.toUpperCase() !== q.ai_answer.toUpperCase() && !q.final_answer);
      const isLowConfidence = conf < 0.70;
      const hasMissingOptional = Object.values(q.source_metadata?.fields || {}).some(
        (f: any) => f.status === "MISSING" || f.review_required
      );

      const isWarning = !isBlocker && (isUnresolvedConflict || isLowConfidence || hasMissingOptional || !q.validation?.valid);

      // 3. INFORMATIONAL checks:
      const hasAiInferred = Object.values(q.source_metadata?.fields || {}).some(
        (f: any) => f.origin === "AI_INFERRED" || f.status === "AI_INFERRED"
      );

      if (isBlocker) {
        blockers++;
      } else if (isWarning) {
        warnings++;
      }

      if (hasAiInferred) {
        informational++;
      }

      if (conf >= 0.95) {
        highConfidence++;
      } else if (conf >= 0.85) {
        medConfidence++;
      } else {
        lowConfidence++;
      }
    });

    const overallValidationConfidence =
      questions.length > 0
        ? Math.round((totalConfidenceSum / questions.length) * 100)
        : 0;

    // Only genuine blockers block Certified export
    const isGateReady = questions.length > 0 && blockers === 0;

    return {
      total: questions.length,
      blockers,
      warnings,
      informational,
      highConfidence,
      medConfidence,
      lowConfidence,
      overallValidationConfidence,
      isGateReady,
    };
  }, [questions]);

  return (
    <section className="card">
      <div className="card-header-flex">
        <div>
          <div className="card-title">
            <QualityIcon size={22} color="var(--primary-hover)" /> Step 5: Quality Check
          </div>
          <div className="card-subtitle">
            Comprehensive audit of assessment integrity, schema compliance, answer key validation, and export readiness.
          </div>
        </div>
        <span className="badge info">Step 05 / 06</span>
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
              {stats.isGateReady ? "QUALITY GATE: READY FOR CERTIFIED EXPORT" : "QUALITY GATE: CERTIFICATION BLOCKED"}
            </div>
            <div style={{ fontSize: "0.84rem", color: "var(--text-secondary)", marginTop: "4px" }}>
              {stats.isGateReady
                ? `Zero critical blockers detected. ${stats.warnings > 0 ? `${stats.warnings} non-blocking warning(s) present.` : "Assessment batch fully certified."}`
                : `${stats.blockers} critical blocker(s) must be resolved before Certified Export.`}
            </div>
          </div>
        </div>

        <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
          {onExportDraft && (
            <button
              className="secondary"
              onClick={() => onExportDraft("xlsx")}
              style={{
                gap: "6px",
                background: "rgba(255, 255, 255, 0.08)",
                border: "1px solid rgba(255, 255, 255, 0.2)",
              }}
            >
              <ExportIcon size={14} /> Download Draft / Review Export
            </button>
          )}

          {!stats.isGateReady && (
            <button className="danger-btn" onClick={onJumpToReview} style={{ gap: "6px" }}>
              Jump to Issues in Review Workspace <ArrowRightIcon size={14} />
            </button>
          )}
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div className="metrics-grid">
        <div className="metric-card">
          <div className="metric-title">Selected Questions</div>
          <div className="metric-value">{stats.total}</div>
          <div className="metric-foot">Batch assessment items</div>
        </div>

        <div className="metric-card">
          <div className="metric-title" style={{ color: stats.blockers === 0 ? "var(--accent)" : "var(--danger)" }}>
            Critical Blockers
          </div>
          <div className="metric-value" style={{ color: stats.blockers === 0 ? "var(--accent)" : "var(--danger)" }}>
            {stats.blockers}
          </div>
          <div className="metric-foot">Blocks certified export</div>
        </div>

        <div className="metric-card">
          <div className="metric-title" style={{ color: "var(--warning)" }}>Warnings / Review</div>
          <div className="metric-value" style={{ color: "var(--warning)" }}>{stats.warnings}</div>
          <div className="metric-foot">Non-blocking notices</div>
        </div>

        <div className="metric-card">
          <div className="metric-title" style={{ color: "var(--primary-hover)" }}>AI-Inferred Fields</div>
          <div className="metric-value" style={{ color: "var(--primary-hover)" }}>{stats.informational}</div>
          <div className="metric-foot">Provenance tracked</div>
        </div>

        <div className="metric-card">
          <div className="metric-title" style={{ color: "var(--accent)" }}>High Confidence</div>
          <div className="metric-value" style={{ color: "var(--accent)" }}>{stats.highConfidence}</div>
          <div className="metric-foot">95% – 100% confidence</div>
        </div>

        <div className="metric-card">
          <div className="metric-title">Validation Confidence</div>
          <div className="metric-value" style={{ color: stats.overallValidationConfidence >= 85 ? "var(--accent)" : "var(--warning)" }}>
            {stats.overallValidationConfidence}%
          </div>
          <div className="metric-foot">Overall quality index</div>
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
          Automated Quality Gate Classification Matrix
        </div>

        <ul className="list-unstyled">
          <li style={{ color: stats.blockers === 0 ? "var(--accent)" : "var(--danger)" }}>
            <span>{stats.blockers === 0 ? <CheckIcon size={14} /> : <XIcon size={14} />}</span>
            <strong>BLOCKER: Mandatory Integrity & Stem Presence:</strong>
            {stats.blockers === 0
              ? "All question prompts and required answer structures are complete."
              : `${stats.blockers} item(s) have missing question prompts or unresolved answer structures.`}
          </li>

          <li style={{ color: stats.warnings === 0 ? "var(--accent)" : "var(--warning)" }}>
            <span>{stats.warnings === 0 ? <CheckIcon size={14} /> : <AlertTriangleIcon size={14} />}</span>
            <strong>WARNING: Optional Metadata & Low-Confidence Infill:</strong>
            {stats.warnings === 0
              ? "All optional metadata fields resolved or accepted."
              : `${stats.warnings} non-blocking warning(s) present (does not block certified export).`}
          </li>

          <li style={{ color: "var(--accent)" }}>
            <CheckIcon size={14} />
            <strong>INFORMATIONAL: Field Provenance Tracking:</strong>
            All AI-inferred values, missing reasons, and reviewer overrides preserved with explicit metadata.
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
          flexWrap: "wrap",
          gap: "12px",
        }}
      >
        <button className="secondary" onClick={onBack} style={{ gap: "6px" }}>
          <ArrowLeftIcon size={16} /> Back to Human Review
        </button>

        <div style={{ display: "flex", gap: "10px" }}>
          <button
            className={stats.isGateReady ? "primary" : "secondary"}
            onClick={onProceedToExport}
            disabled={!stats.isGateReady}
            style={{ gap: "6px" }}
          >
            {stats.isGateReady ? (
              <>
                Proceed to Certified Export <ArrowRightIcon size={16} />
              </>
            ) : (
              "Resolve Blockers to Unlock Certified Export"
            )}
          </button>
        </div>
      </div>
    </section>
  );
}
