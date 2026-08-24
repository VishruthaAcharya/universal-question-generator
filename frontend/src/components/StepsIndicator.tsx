"use client";

export type StepKey = "template" | "source" | "compatibility" | "review" | "export";

export interface StepItem {
  key: StepKey;
  label: string;
}

interface StepsIndicatorProps {
  currentStep: StepKey;
  steps: StepItem[];
}

export default function StepsIndicator({ currentStep, steps }: StepsIndicatorProps) {
  const activeIndex = steps.findIndex((s) => s.key === currentStep);

  return (
    <div className="steps-indicator">
      {steps.map((s, idx) => {
        const isCompleted = activeIndex > idx;
        const isActive = currentStep === s.key;
        return (
          <div
            key={s.key}
            className={`step-node ${isActive ? "active" : ""} ${isCompleted ? "completed" : ""}`}
          >
            <div className="step-number">{isCompleted ? "✓" : idx + 1}</div>
            <span className="step-label">{s.label}</span>
          </div>
        );
      })}
    </div>
  );
}
