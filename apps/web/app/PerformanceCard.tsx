import type { PerformanceSummaryResponse } from "@/lib/api";
import styles from "./PerformanceCard.module.css";

export function PerformanceCard({ data }: { data: PerformanceSummaryResponse }) {
  if (data.total_trades === 0) {
    return (
      <div className={styles.card}>
        <div className={styles.headerRow}>
          <h3 className={styles.title}>Performance</h3>
        </div>
        <p className={styles.emptyState}>
          No closed trades yet — this fills in automatically as positions close.
        </p>
      </div>
    );
  }

  const pnlPositive = data.total_realized_pnl >= 0;

  return (
    <div className={styles.card}>
      <div className={styles.headerRow}>
        <h3 className={styles.title}>Performance</h3>
        <span className={`${styles.pnlBadge} ${pnlPositive ? styles.pnlPositive : styles.pnlNegative}`}>
          {pnlPositive ? "+" : ""}
          {data.total_realized_pnl.toFixed(2)}
        </span>
      </div>

      <dl className={styles.statGrid}>
        <div className={styles.statRow}>
          <dt>Trades</dt>
          <dd>{data.total_trades}</dd>
        </div>
        <div className={styles.statRow}>
          <dt>Win rate</dt>
          <dd>{data.win_rate_pct.toFixed(1)}%</dd>
        </div>
        <div className={styles.statRow}>
          <dt>Wins / Losses</dt>
          <dd>
            {data.wins} / {data.losses}
          </dd>
        </div>
        <div className={styles.statRow}>
          <dt>Avg win / loss</dt>
          <dd>
            {data.average_win.toFixed(2)} / {data.average_loss.toFixed(2)}
          </dd>
        </div>
        <div className={styles.statRow}>
          <dt>Profit factor</dt>
          <dd>{data.profit_factor !== null ? data.profit_factor.toFixed(2) : "—"}</dd>
        </div>
        <div className={styles.statRow}>
          <dt>Expectancy / trade</dt>
          <dd>{data.expectancy.toFixed(2)}</dd>
        </div>
      </dl>
    </div>
  );
}
