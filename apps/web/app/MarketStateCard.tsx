import type { MarketStateResponse } from "@/lib/api";
import styles from "./MarketStateCard.module.css";

const REGIME_COPY: Record<MarketStateResponse["regime"], string> = {
  TRENDING: "Trending",
  RANGING: "Ranging",
  HIGH_VOLATILITY: "High volatility",
};

const REGIME_CLASS: Record<MarketStateResponse["regime"], string> = {
  TRENDING: styles.regimeTrending!,
  RANGING: styles.regimeRanging!,
  HIGH_VOLATILITY: styles.regimeHighVol!,
};

const TREND_CLASS: Record<MarketStateResponse["trend"], string> = {
  BULLISH: styles.tagPositive!,
  BEARISH: styles.tagNegative!,
  NEUTRAL: styles.tagMuted!,
};

const MOMENTUM_CLASS: Record<MarketStateResponse["momentum"], string> = {
  POSITIVE: styles.tagPositive!,
  NEGATIVE: styles.tagNegative!,
  FLAT: styles.tagMuted!,
};

const VOLATILITY_CLASS: Record<MarketStateResponse["volatility"], string> = {
  HIGH: styles.tagNegative!,
  NORMAL: styles.tagMuted!,
  LOW: styles.tagMuted!,
};

const RSI_CLASS: Record<MarketStateResponse["rsi_condition"], string> = {
  OVERBOUGHT: styles.tagNegative!,
  OVERSOLD: styles.tagPositive!,
  NEUTRAL: styles.tagMuted!,
};

export function MarketStateCard({ data }: { data: MarketStateResponse }) {
  const asOfLabel = new Date(data.as_of).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });

  return (
    <div className={styles.card}>
      <div className={styles.headerRow}>
        <h3 className={styles.title}>Market structure</h3>
        <span className={`${styles.regimeBadge} ${REGIME_CLASS[data.regime]}`}>
          {REGIME_COPY[data.regime]}
        </span>
      </div>
      <p className={styles.asOf}>
        {data.symbol} · {data.interval} · as of {asOfLabel}
      </p>

      <div className={styles.priceRow}>
        <span className={styles.priceLabel}>Close</span>
        <span className={styles.priceValue}>{data.latest_close.toFixed(2)}</span>
      </div>

      <dl className={styles.statGrid}>
        <div className={styles.statRow}>
          <dt>Trend (SMA20 vs SMA50)</dt>
          <dd>
            {data.sma_fast.toFixed(1)} / {data.sma_slow.toFixed(1)}{" "}
            <span className={`${styles.tag} ${TREND_CLASS[data.trend]}`}>
              {data.trend.toLowerCase()}
            </span>
          </dd>
        </div>
        <div className={styles.statRow}>
          <dt>Momentum (10-bar ROC)</dt>
          <dd>
            {data.roc_pct > 0 ? "+" : ""}
            {data.roc_pct}%{" "}
            <span className={`${styles.tag} ${MOMENTUM_CLASS[data.momentum]}`}>
              {data.momentum.toLowerCase()}
            </span>
          </dd>
        </div>
        <div className={styles.statRow}>
          <dt>Volatility (ATR14)</dt>
          <dd>
            {data.atr_pct_of_price}% of price{" "}
            <span className={`${styles.tag} ${VOLATILITY_CLASS[data.volatility]}`}>
              {data.volatility.toLowerCase()}
            </span>
          </dd>
        </div>
        <div className={styles.statRow}>
          <dt>RSI (14)</dt>
          <dd>
            {data.rsi.toFixed(1)}{" "}
            <span className={`${styles.tag} ${RSI_CLASS[data.rsi_condition]}`}>
              {data.rsi_condition.toLowerCase()}
            </span>
          </dd>
        </div>
      </dl>
    </div>
  );
}

export function MarketStateEmptyState({ symbol }: { symbol: string }) {
  return (
    <div className={styles.card}>
      <div className={styles.headerRow}>
        <h3 className={styles.title}>Market structure</h3>
      </div>
      <p className={styles.emptyState}>
        No {symbol} price bars ingested yet. Trigger ingestion to see trend, momentum, and
        volatility here.
      </p>
    </div>
  );
}
