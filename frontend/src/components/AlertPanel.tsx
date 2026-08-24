"use client";

import React from "react";

interface AlertPanelProps {
  type: "success" | "danger" | "warning" | "info";
  children: React.ReactNode;
  style?: React.CSSProperties;
  className?: string;
}

export default function AlertPanel({ type, children, style, className = "" }: AlertPanelProps) {
  return (
    <div className={`alert-panel ${type} ${className}`} style={style}>
      {children}
    </div>
  );
}
