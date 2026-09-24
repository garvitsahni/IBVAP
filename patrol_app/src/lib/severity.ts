import type { Alert, ThreatLevel } from "../types/api";

export type Severity = "critical" | "high" | "medium" | "low";

export function severityOf(alert: Pick<Alert, "threat_level" | "threat_score">): Severity {
  const level: ThreatLevel | undefined =
    alert.threat_level ??
    (alert.threat_score >= 0.8
      ? "critical"
      : alert.threat_score >= 0.5
      ? "high"
      : alert.threat_score >= 0.3
      ? "medium"
      : "low");
  return level === "critical" || level === "high" || level === "medium" ? level : "low";
}
