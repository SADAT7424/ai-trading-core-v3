import type { TradeEvaluationResponse } from "@/lib/api";
import styles from "./RiskCard.module.css";

const KILL_SWITCH_CLASS: Record<TradeEvaluationResponse["kill_switch_state"], string> = {
  NORMAL: styles.killNormal!,
  ALERT: styles.killAlert!,
  SAFE_MODE: styles.killDanger!,
  EMERGENCY_STOP: styles.killDanger!,
};

export function RiskCard({ data }: { data: TradeEvaluationResponse }) {
  const noSetup = data.direction === "NONE";

  return (
    <div className={styles.card}>
      <div className={styles.headerRow}>
        <h3 className={styles.title}>Risk check</h3>
        <span className={`${styles.killBadge} ${KILL_SWITCH_CLASS[data.kill_switch_state]}`}>
          {data.kill_switch_state.replace("_", " ").toLowerCase()}
        </span>
      </div>

      {noSetup ? (
        <p className={styles.emptyState}>No setup to evaluate right now.</p>
      ) : (
        <>
          <div className={styles.decisionRow}>
            <span className={`${styles.decisionBadge} ${data.approved ? styles.approved : styles.rejected}`}>
              {data.approved ? "Approved" : "Rejected"}
            </span>
            <span className={styles.priceInfo}>
              Entry {data.entry_price.toFixed(2)} · Stop {data.stop_price?.toFixed(2)}
            </span>
          </div>

          {data.reasons.length > 0 && (
            <ul className={styles.reasonList}>
              {data.reasons.map((reason) => (
                <li key={reason} className={styles.reasonItem}>
                  {reason.replaceAll("_", " ").toLowerCase()}
                </li>
              ))}
            </ul>
          )}

          {data.position && (
            <dl className={styles.statGrid}>
              <div className={styles.statRow}>
                <dt>Position size</dt>
                <dd>{data.position.units.toFixed(4)} oz</dd>
              </div>
              <div className={styles.statRow}>
                <dt>Risk</dt>
                <dd>
                  ${data.position.risk_amount.toFixed(2)} ({data.position.risk_pct.toFixed(2)}%)
                </dd>
              </div>
              <div className={styles.statRow}>
                <dt>Exposure</dt>
                <dd>{data.position.exposure_pct.toFixed(1)}% of account</dd>
              </div>
            </dl>
          )}

          {data.notes.length > 0 && (
            <p className={styles.notes}>{data.notes.join(" ")}</p>
          )}
        </>
      )}
    </div>
  );
}

export function RiskCardEmptyState() {
  return (
    <div className={styles.card}>
      <div className={styles.headerRow}>
        <h3 className={styles.title}>Risk check</h3>
      </div>
      <p className={styles.emptyState}>Needs an opportunity to evaluate.</p>
    </div>
  );
}
