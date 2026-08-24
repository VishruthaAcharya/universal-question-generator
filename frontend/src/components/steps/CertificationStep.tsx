"use client";

import React from "react";
import { QuestionRow, AssessmentBatchConfig } from "../../types";

interface CertificationStepProps {
  questions: QuestionRow[];
  batchConfig: AssessmentBatchConfig;
  templateName: string;
  sourceFilename: string;
  isCertified: boolean;
  onCertify: () => void;
  onProceedToExport: () => void;
  onBack: () => void;
}

export default function CertificationStep({
  questions,
  batchConfig,
  templateName,
  sourceFilename,
  isCertified,
  onCertify,
  onProceedToExport,
  onBack,
}: CertificationStepProps) {
  const validCount = questions.filter((q) => q.validation.valid).length;
  const invalidCount = questions.length - validCount;
  const qualityScore = questions.length > 0
    ? Math.round((validCount / questions.length) * 100)
    : 0;

  const isEligible = questions.length > 0 && invalidCount === 0;

  return (
    <section className="card">
      <div className="card-header-flex">
        <div>
          <div className="card-title">
            <span>🏅</span> Step 8: Assessment Batch Certification & Compliance
          </div>
          <div className="card-subtitle">
            Official quality assurance sign-off and Menntr Content Factory certification certificate.
          </div>
        </div>
        <span className="badge info">Step 08 / 09</span>
      </div>

      {/* Certification Status Box */}
      <div
        style={{
          background: isCertified
            ? "radial-gradient(ellipse at center, rgba(16, 185, 129, 0.15), rgba(11, 15, 25, 0.8))"
            : "rgba(17, 24, 39, 0.5)",
          border: `2px solid ${isCertified ? "var(--accent)" : "var(--border-medium)"}`,
          borderRadius: "16px",
          padding: "36px 24px",
          textAlign: "center",
          marginBottom: "28px",
          position: "relative",
          overflow: "hidden",
        }}
      >
        <div style={{ fontSize: "3.5rem", marginBottom: "12px" }}>
          {isCertified ? "🎖️" : "📋"}
        </div>

        <div
          style={{
            display: "inline-block",
            padding: "6px 18px",
            borderRadius: "999px",
            fontWeight: 800,
            fontSize: "0.85rem",
            letterSpacing: "0.08em",
            textTransform: "uppercase",
            background: isCertified ? "rgba(16, 185, 129, 0.2)" : "rgba(239, 68, 68, 0.15)",
            border: `1px solid ${isCertified ? "var(--accent)" : "var(--danger)"}`,
            color: isCertified ? "#6EE7B7" : "#FCA5A5",
            marginBottom: "16px",
          }}
        >
          {isCertified ? "MENNTR CERTIFIED ASSESSMENT" : isEligible ? "READY FOR CERTIFICATION SIGN-OFF" : "CERTIFICATION BLOCKED"}
        </div>

        <h2 style={{ fontSize: "1.6rem", fontWeight: 800, color: "var(--text-primary)", marginBottom: "8px" }}>
          {batchConfig.assessmentName || "Menntr Assessment Batch"}
        </h2>

        <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem", maxWidth: "600px", margin: "0 auto 24px auto" }}>
          {isCertified
            ? "This assessment batch has met all Menntr quality, schema conformance, answer parity, and editorial standards for production delivery."
            : "Review batch metrics below. Sign-off with the digital certification seal to authorize export."}
        </p>

        {/* Audit Details Grid */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
            gap: "14px",
            maxWidth: "800px",
            margin: "0 auto 28px auto",
            textAlign: "left",
          }}
        >
          <div style={{ background: "rgba(0,0,0,0.3)", padding: "12px 16px", borderRadius: "8px" }}>
            <div style={{ fontSize: "0.7rem", color: "var(--text-secondary)", textTransform: "uppercase" }}>Batch Question Count</div>
            <div style={{ fontSize: "1.15rem", fontWeight: 700, color: "var(--text-primary)", marginTop: "2px" }}>
              {questions.length} Items
            </div>
          </div>

          <div style={{ background: "rgba(0,0,0,0.3)", padding: "12px 16px", borderRadius: "8px" }}>
            <div style={{ fontSize: "0.7rem", color: "var(--text-secondary)", textTransform: "uppercase" }}>Validation Integrity</div>
            <div style={{ fontSize: "1.15rem", fontWeight: 700, color: "var(--accent)", marginTop: "2px" }}>
              {validCount} / {questions.length} (100%)
            </div>
          </div>

          <div style={{ background: "rgba(0,0,0,0.3)", padding: "12px 16px", borderRadius: "8px" }}>
            <div style={{ fontSize: "0.7rem", color: "var(--text-secondary)", textTransform: "uppercase" }}>Quality Rating</div>
            <div style={{ fontSize: "1.15rem", fontWeight: 700, color: "#93C5FD", marginTop: "2px" }}>
              {qualityScore}% Index
            </div>
          </div>

          <div style={{ background: "rgba(0,0,0,0.3)", padding: "12px 16px", borderRadius: "8px" }}>
            <div style={{ fontSize: "0.7rem", color: "var(--text-secondary)", textTransform: "uppercase" }}>Target Schema</div>
            <div style={{ fontSize: "1.15rem", fontWeight: 700, color: "var(--text-primary)", marginTop: "2px", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
              {templateName || "Menntr Schema"}
            </div>
          </div>
        </div>

        {/* Certify Action Button */}
        {!isCertified ? (
          <button
            className="accent"
            onClick={onCertify}
            disabled={!isEligible}
            style={{ padding: "14px 32px", fontSize: "1rem" }}
          >
            🏅 Authorize & Certify Assessment Batch
          </button>
        ) : (
          <div style={{ display: "inline-flex", alignItems: "center", gap: "8px", color: "var(--accent)", fontWeight: 700 }}>
            <span>✓</span> Digitally Certified by Menntr Quality Engine
          </div>
        )}
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
        <button className="secondary" onClick={onBack}>
          ← Back to Quality Dashboard
        </button>

        <button
          className="primary"
          onClick={onProceedToExport}
          disabled={!isCertified}
        >
          Proceed to Final Export & Publishing →
        </button>
      </div>
    </section>
  );
}
