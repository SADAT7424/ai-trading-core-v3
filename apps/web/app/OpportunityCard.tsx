import type { OpportunityResponse } from "@/lib/api";
import styles from "./OpportunityCard.module.css";

const CLASSIFICATION_COPY: Record<OpportunityResponse["classification"], string> = {
  MACRO_ALIGNED_LONG: "Macro-aligned long",
  MACRO_ALIGNED_SHORT: "Macro-aligned short",
  COUNTER_MACRO_LONG: "Counter-macro long",
  COUNTER_MACRO_SHORT: "Counter-macro short",
  MACRO_NEUTRAL: "Macro-neutral",
};

const QUALITY_CLASS: Record<NonNullable<OpportunityResponse["score"]>["quality"], string> = {
  A: styles.qualityA!,
  B: styles.qualityB!,
  C: styles.qualityC!,
  D: styles.qualityD!,
};

const DIRECTION_CLASS: Record<OpportunityResponse["setup"]["direction"], string> = {
  LONG: styles.directionLong!,
  SHORT: styles.directionShort!,
  NONE: styles.directionNone!,
};

export function OpportunityCard({ data }: { data: OpportunityResponse }) {
  const asOfLabel = new Date(data.as_of).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });

  const noSetup = data.setup.direction === "NONE";

  return (
    <div className={styles.card}>
      <div className={styles.headerRow}>
        <h3 className={styles.title}>Active opportunity</h3>
        {data.score && (
          <span className={`${styles.qualityBadge} ${QUALITY_CLASS[data.score.quality]}`}>
            Grade {data.score.quality}
          </span>
        )}
      </div>
      <p className={styles.asOf}>
        {data.symbol} · {data.interval} · as of {asOfLabel}
      </p>

      {noSetup ? (
        <p className={styles.emptyState}>
          No trend-pullback setup right now — price is too far from the fast moving
          average, or momentum has turned against the trend. This is the strategy
          correctly staying out, not an error.
        </p>
      ) : (
        <>
          <div className={styles.directionRow}>
            <span className={`${styles.directionBadge} ${DIRECTION_CLASS[data.setup.direction]}`}>
              {data.setup.direction}
            </span>
            <span className={styles.classification}>
              {CLASSIFICATION_COPY[data.classification]}
            </span>
          </div>

          {data.score && (
            <dl className={styles.statGrid}>
              <div className={styles.statRow}>
                <dt>Technical score</dt>
                <dd>{data.score.technical_score.toFixed(0)}</dd>
              </div>
              <div className={styles.statRow}>
                <dt>Macro alignment</dt>
                <dd>{data.score.macro_alignment_score.toFixed(0)}</dd>
              </div>
              <div className={styles.statRow}>
                <dt>Overall score</dt>
                <dd>{data.score.overall_score.toFixed(0)}</dd>
              </div>
              <div className={styles.statRow}>
                <dt>Distance to fast SMA</dt>
                <dd>{data.setup.distance_to_fast_sma_pct.toFixed(2)}%</dd>
              </div>
            </dl>
          )}
        </>
      )}
    </div>
  );
}

export function OpportunityEmptyState({ symbol }: { symbol: string }) {
  return (
    <div className={styles.card}>
      <div className={styles.headerRow}>
        <h3 className={styles.title}>Active opportunity</h3>
      </div>
      <p className={styles.emptyState}>
        Needs both economic and {symbol} price data ingested to assess a setup.
      </p>
    </div>
  );
}
