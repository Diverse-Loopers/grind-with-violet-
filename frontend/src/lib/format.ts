/**
 * Indian Rupee Number Formatting: e.g. 1,23,456.78
 */
export function formatINR(amount: number | undefined | null, includeDecimals = true): string {
  if (amount === undefined || amount === null || isNaN(amount)) return "₹0.00";
  const isNegative = amount < 0;
  const absAmount = Math.abs(amount);

  const parts = absAmount.toFixed(includeDecimals ? 2 : 0).split(".");
  let intPart = parts[0];
  const decPart = parts.length > 1 ? "." + parts[1] : "";

  // Indian number system regex: last 3 digits, then groups of 2
  if (intPart.length > 3) {
    const lastThree = intPart.substring(intPart.length - 3);
    const otherNumbers = intPart.substring(0, intPart.length - 3);
    intPart = otherNumbers.replace(/\B(?=(\d{2})+(?!\d))/g, ",") + "," + lastThree;
  }

  return `${isNegative ? "-" : ""}₹${intPart}${decPart}`;
}

export function formatPct(value: number | undefined | null, includeSign = true): string {
  if (value === undefined || value === null || isNaN(value)) return "0.00%";
  const sign = includeSign && value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

export function formatISTTime(isoString: string | null | undefined): string {
  if (!isoString) return "--:--:--";
  try {
    const d = new Date(isoString);
    return d.toLocaleTimeString("en-IN", {
      timeZone: "Asia/Kolkata",
      hour12: true,
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return isoString;
  }
}
