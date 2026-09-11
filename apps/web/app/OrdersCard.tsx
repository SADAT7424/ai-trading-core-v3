import type { OrderResponse } from "@/lib/api";
import styles from "./OrdersCard.module.css";

export function OrdersCard({ orders }: { orders: OrderResponse[] }) {
  return (
    <div className={styles.card}>
      <div className={styles.headerRow}>
        <h3 className={styles.title}>Recent orders</h3>
        <span className={styles.paperBadge}>Paper only</span>
      </div>

      {orders.length === 0 ? (
        <p className={styles.emptyState}>
          No orders submitted yet. POST /api/v1/execution/orders/XAUUSD to try one.
        </p>
      ) : (
        <ul className={styles.orderList}>
          {orders.map((order) => (
            <li key={order.id} className={styles.orderRow}>
              <div className={styles.orderMain}>
                <span
                  className={`${styles.statusDot} ${
                    order.status === "FILLED" ? styles.dotFilled : styles.dotRejected
                  }`}
                />
                <span className={styles.direction}>{order.direction}</span>
                <span className={styles.status}>{order.status.toLowerCase()}</span>
              </div>
              {order.status === "FILLED" ? (
                <span className={styles.detail}>
                  {order.units.toFixed(4)} oz @ {order.filled_price?.toFixed(2)} · $
                  {order.risk_amount.toFixed(2)} risk
                </span>
              ) : (
                <span className={styles.detail}>
                  {(order.rejection_reasons || "").replaceAll(",", ", ").replaceAll("_", " ").toLowerCase() ||
                    "no setup"}
                </span>
              )}
              <span className={styles.timestamp}>
                {new Date(order.created_at).toLocaleString("en-US", {
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
