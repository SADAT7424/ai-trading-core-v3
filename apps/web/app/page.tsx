import { getHealth, getMacroRegime, getReady } from "@/lib/api";
import { MacroRegimeCard, MacroRegimeEmptyState } from "./MacroRegimeCard";
import styles from "./page.module.css";

/**
 * Foundation-stage Command Center.
 *
 * Macro Regime is now live data (Stage 3). Active Opportunities, Portfolio
 * Risk, and Open Positions remain placeholders for later build stages — see
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
    // Not yet ingested, or another transient issue — the empty state below
    // handles this without treating it as a page-level error.
    macroRegime = null;
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

        {["Active Opportunities", "Portfolio Risk", "Open Positions"].map((title) => (
          <div key={title} className={styles.placeholderCard}>
            <h3>{title}</h3>
            <p className={styles.muted}>Coming in a later build stage.</p>
          </div>
        ))}
      </section>
    </main>
  );
}
