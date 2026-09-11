import {
  evaluateTrade,
  getHealth,
  getMacroRegime,
  getMarketState,
  getOpportunity,
  getReady,
} from "@/lib/api";
import { MacroRegimeCard, MacroRegimeEmptyState } from "./MacroRegimeCard";
import { MarketStateCard, MarketStateEmptyState } from "./MarketStateCard";
import { OpportunityCard, OpportunityEmptyState } from "./OpportunityCard";
import { RiskCard, RiskCardEmptyState } from "./RiskCard";
import styles from "./page.module.css";

const PRIMARY_SYMBOL = "XAUUSD";

/**
 * Foundation-stage Command Center.
 *
 * Macro Regime (Stage 3), Market Structure (Stage 4), Active Opportunity
 * (Stage 5), and Risk Check (Stage 6) are now live data. Open Positions
 * remains a placeholder for Stage 8 — see
 * docs/RAH_OS_Master_Plan.docx section 15.5.
 */
export default async function Home() {
  let health: Awaited<ReturnType<typeof getHealth>> | null = null;
  let ready: Awaited<ReturnType<typeof getReady>> | null = null;
  let apiError: string | null = null;

  try {
    [health, ready] = await Promise.all([getHealth(), getReady()]);
  } catch (err) {
    apiError = err instanceof Error ? err.message : "Unknown error reaching the API";
  }

  let macroRegime: Awaited<ReturnType<typeof getMacroRegime>> | null = null;
  try {
    macroRegime = await getMacroRegime();
  } catch {
    macroRegime = null;
  }

  let marketState: Awaited<ReturnType<typeof getMarketState>> | null = null;
  try {
    marketState = await getMarketState(PRIMARY_SYMBOL);
  } catch {
    marketState = null;
  }

  let opportunity: Awaited<ReturnType<typeof getOpportunity>> | null = null;
  try {
    opportunity = await getOpportunity(PRIMARY_SYMBOL);
  } catch {
    opportunity = null;
  }

  let riskEvaluation: Awaited<ReturnType<typeof evaluateTrade>> | null = null;
  try {
    riskEvaluation = await evaluateTrade(PRIMARY_SYMBOL);
  } catch {
    riskEvaluation = null;
  }

  return (
    <main className={styles.main}>
      <header className={styles.header}>
        <h1 className={styles.logo}>RAH OS</h1>
        <span className={styles.badge}>BUILD 01 — FOUNDATION</span>
      </header>

      <section className={styles.statusCard}>
        <h2>System Status</h2>
        {apiError ? (
          <p className={styles.error}>
            Could not reach the API at the configured URL. Is it running?
            <br />
            <code>{apiError}</code>
          </p>
        ) : (
          <div className={styles.statusGrid}>
            <div>
              <span className={styles.label}>API</span>
              <span className={styles.value}>{health?.status}</span>
            </div>
            <div>
              <span className={styles.label}>Environment</span>
              <span className={styles.value}>{health?.environment}</span>
            </div>
            <div>
              <span className={styles.label}>Database</span>
              <span className={styles.value}>{ready?.dependencies.database}</span>
            </div>
            <div>
              <span className={styles.label}>Redis</span>
              <span className={styles.value}>{ready?.dependencies.redis}</span>
            </div>
          </div>
        )}
      </section>

      <section className={styles.placeholderGrid}>
        {macroRegime ? (
          <MacroRegimeCard data={macroRegime} />
        ) : (
          <MacroRegimeEmptyState />
        )}

        {marketState ? (
          <MarketStateCard data={marketState} />
        ) : (
          <MarketStateEmptyState symbol={PRIMARY_SYMBOL} />
        )}

        {opportunity ? (
          <OpportunityCard data={opportunity} />
        ) : (
          <OpportunityEmptyState symbol={PRIMARY_SYMBOL} />
        )}

        {riskEvaluation ? <RiskCard data={riskEvaluation} /> : <RiskCardEmptyState />}

        <div className={styles.placeholderCard}>
          <h3>Open Positions</h3>
          <p className={styles.muted}>Coming in a later build stage.</p>
        </div>
      </section>
    </main>
  );
}
