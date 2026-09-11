import type { PositionResponse } from "@/lib/api";
import styles from "./PositionsCard.module.css";

export function PositionsCard({ positions }: { positions: PositionResponse[] }) {
  return (
    <div className={styles.card}>
      <div className={styles.headerRow}>
        <h3 className={styles.title}>Open positions</h3>
        <span className={styles.count}>{positions.length}</span>
      </div>

      {positions.length === 0 ? (
        <p className={styles.emptyState}>No open positions right now.</p>
      ) : (
        <ul className={styles.positionList}>
          {positions.map((position) => (
            <li key={position.id} className={styles.positionRow}>
              <div className={styles.mainRow}>
                <span className={styles.direction}>{position.direction}</span>
                <span className={styles.entryPrice}>@ {position.entry_price.toFixed(2)}</span>
                {position.entry_quality_grade && (
                  <span className={styles.gradeBadge}>Grade {position.entry_quality_grade}</span>
                )}
              </div>
              <div className={styles.levelsRow}>
                <span className={styles.stopLevel}>Stop {position.current_stop_price.toFixed(2)}</span>
                <span className={styles.targetLevel}>Target {position.target_price.toFixed(2)}</span>
              </div>
              <p className={styles.thesis}>{position.entry_thesis}</p>
              <span className={styles.openedAt}>
                Opened{" "}
                {new Date(position.opened_at).toLocaleString("en-US", {
                  month: "short",
                  day: "numeric",
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
