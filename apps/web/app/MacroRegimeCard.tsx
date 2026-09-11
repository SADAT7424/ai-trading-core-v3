import type { GoldScore, MacroRegimeResponse } from "@/lib/api";
import styles from "./MacroRegimeCard.module.css";

const REGIME_COPY: Record<MacroRegimeResponse["regime"], string> = {
  REFLATION: "Reflation",
  STAGFLATION: "Stagflation",
  GOLDILOCKS: "Goldilocks",
  DEFLATIONARY: "Deflationary",
};

const REGIME_CLASS: Record<MacroRegimeResponse["regime"], string> = {
  REFLATION: styles.regimeReflation!,
  STAGFLATION: styles.regimeStagflation!,
  GOLDILOCKS: styles.regimeGoldilocks!,
  DEFLATIONARY: styles.regimeDeflationary!,
};

const BIAS_CLASS: Record<GoldScore["bias"], string> = {
  BULLISH: styles.biasBullish!,
  NEUTRAL: styles.biasNeutral!,
  BEARISH: styles.biasBearish!,
};

const CONTRIBUTION_MAX = 35;

function formatSigned(value: number): string {
  if (value > 0) return `+${value}`;
  return `${value}`;
}

function ContributionBar({ label, value }: { label: string; value: number }) {
  const widthPct = Math.min(100, (Math.abs(value) / CONTRIBUTION_MAX) * 100);
  const positive = value > 0;
  const flat = value === 0;

  return (
    <div className={styles.contributionRow}>
      <span className={styles.contributionLabel}>{label}</span>
      <div className={styles.barTrack}>
        {!flat && (
          <div
            className={positive ? styles.barFillPositive : styles.barFillNegative}
            style={{ width: `${widthPct}%` }}
          />
        )}
      </div>
      <span className={styles.contributionValue}>{formatSigned(value)}</span>
    </div>
  );
}

export function MacroRegimeCard({ data }: { data: MacroRegimeResponse }) {
  const asOfLabel = new Date(data.as_of).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });

  return (
    <div className={styles.card}>
      <div className={styles.headerRow}>
        <h3 className={styles.title}>Macro regime</h3>
        <span className={`${styles.regimeBadge} ${REGIME_CLASS[data.regime]}`}>
          {REGIME_COPY[data.regime]}
        </span>
      </div>
      <p className={styles.asOf}>As of {asOfLabel}</p>

      <dl className={styles.statGrid}>
        <div className={styles.statRow}>
          <dt>Inflation (CPI, YoY)</dt>
          <dd>
            {data.inflation_yoy_pct}%{" "}
            <span className={styles.tag}>{data.inflation_level.toLowerCase()}</span>
          </dd>
        </div>
        <div className={styles.statRow}>
          <dt>Employment</dt>
          <dd>
            {data.unemployment_rate_pct}%{" "}
            <span className={styles.tag}>{data.employment_condition.toLowerCase()}</span>
          </dd>
        </div>
        <div className={styles.statRow}>
          <dt>Fed funds rate</dt>
          <dd>
            {data.fed_funds_rate_pct}%{" "}
            <span className={styles.tag}>{data.policy_stance.toLowerCase()}</span>
          </dd>
        </div>
        <div className={styles.statRow}>
          <dt>10Y real yield</dt>
          <dd>
            {data.real_yield_10y_pct}%{" "}
            <span className={styles.tag}>{data.real_yield_level.toLowerCase()}</span>
          </dd>
        </div>
        <div className={styles.statRow}>
          <dt>USD index</dt>
          <dd>
            {data.usd_index_level.toFixed(1)}{" "}
            <span className={styles.tag}>{data.usd_condition.toLowerCase()}</span>
          </dd>
        </div>
        <div className={styles.statRow}>
          <dt>Breakeven inflation</dt>
          <dd>
            {data.breakeven_inflation_10y_pct}%{" "}
            <span className={styles.tagMuted}>context only</span>
          </dd>
        </div>
      </dl>

      <div className={styles.goldSection}>
        <div className={styles.headerRow}>
          <h4 className={styles.subtitle}>Gold bias</h4>
          <span className={`${styles.biasBadge} ${BIAS_CLASS[data.gold_score.bias]}`}>
            {data.gold_score.bias.toLowerCase()} · {formatSigned(data.gold_score.total)}
          </span>
        </div>
        <div className={styles.contributions}>
          <ContributionBar label="Real yield" value={data.gold_score.real_yield_contribution} />
          <ContributionBar label="Inflation" value={data.gold_score.inflation_contribution} />
          <ContributionBar label="Policy" value={data.gold_score.policy_contribution} />
          <ContributionBar label="USD" value={data.gold_score.usd_contribution} />
        </div>
      </div>
    </div>
  );
}

export function MacroRegimeEmptyState() {
  return (
    <div className={styles.card}>
      <div className={styles.headerRow}>
        <h3 className={styles.title}>Macro regime</h3>
      </div>
      <p className={styles.emptyState}>
        No economic data ingested yet. Trigger ingestion for CPIAUCSL, UNRATE, FEDFUNDS,
        DFII10, T10YIE, and DTWEXBGS to see the current regime here.
      </p>
    </div>
  );
}
