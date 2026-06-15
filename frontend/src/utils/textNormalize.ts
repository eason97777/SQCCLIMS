/**
 * Trim leading and trailing whitespace from a text value.
 */
export function trimText(value: string | null | undefined) {
  return String(value ?? "").trim();
}

/**
 * Collapse repeated whitespace into a single space while preserving line breaks.
 */
export function normalizeWhitespace(value: string | null | undefined) {
  return trimText(value)
    .replace(/\u3000/g, " ")
    .replace(/[ \t]+/g, " ");
}

function isRemovableControlChar(charCode: number) {
  return (
    (charCode >= 0x00 && charCode <= 0x08) ||
    charCode === 0x0b ||
    charCode === 0x0c ||
    (charCode >= 0x0e && charCode <= 0x1f) ||
    charCode === 0x7f
  );
}

/**
 * Remove invisible control characters while preserving line breaks and tabs.
 */
export function removeControlChars(value: string | null | undefined) {
  const source = String(value ?? "");
  let result = "";

  for (const char of source) {
    const charCode = char.charCodeAt(0);
    if (!isRemovableControlChar(charCode)) {
      result += char;
    }
  }

  return result;
}

/**
 * Normalize text for search matching without overwriting the user's original text.
 */
export function normalizeSearchText(value: string | null | undefined) {
  return normalizeWhitespace(removeControlChars(value))
    .toLowerCase()
    .replace(/\u3000/g, " ");
}

/**
 * Normalize technical identifier-like input such as sample codes and batch codes.
 */
export function normalizeCodeText(value: string | null | undefined) {
  return normalizeWhitespace(removeControlChars(value))
    .replace(/\u3000/g, " ")
    .replace(/\uFF1A/g, ":")
    .replace(/\uFF0C/g, ",");
}

/**
 * Convert a filename to a safe filename segment without performing path joins.
 */
export function normalizeFilename(value: string | null | undefined) {
  const cleaned = trimText(removeControlChars(value))
    .replace(/[<>:"/\\|?*]/g, "_")
    .replace(/[. ]+$/g, "")
    .replace(/^\.+/g, "");

  return cleaned || "unnamed";
}

/**
 * Normalize CSV header text by trimming whitespace and removing a BOM if present.
 */
export function normalizeCsvHeader(value: string | null | undefined) {
  return trimText(removeControlChars(value)).replace(/^\uFEFF/, "");
}

/**
 * Normalize numeric text by converting common full-width digits and separators.
 */
export function normalizeNumericText(value: string | null | undefined) {
  const source = trimText(removeControlChars(value));
  const fullWidthDigits = "０１２３４５６７８９";
  let normalized = "";

  for (const char of source) {
    const index = fullWidthDigits.indexOf(char);
    if (index >= 0) {
      normalized += String(index);
      continue;
    }

    if (char === "\uFF0C" || char === ",") {
      continue;
    }

    if (char === "\uFF0E") {
      normalized += ".";
      continue;
    }

    if (char === "\uFF0D") {
      normalized += "-";
      continue;
    }

    normalized += char;
  }

  return normalized;
}

/**
 * Convert normalized numeric text to a number, or null if parsing fails.
 */
export function toNumberOrNull(value: string | number | null | undefined) {
  if (typeof value === "number") {
    return Number.isFinite(value) ? value : null;
  }

  const normalized = normalizeNumericText(String(value ?? ""));
  if (!normalized) {
    return null;
  }

  const number = Number(normalized);
  return Number.isFinite(number) ? number : null;
}

/**
 * Normalize note-like text while preserving line breaks and most user intent.
 */
export function normalizeNoteText(value: string | null | undefined) {
  return trimText(removeControlChars(value))
    .replace(/\r\n/g, "\n")
    .replace(/\r/g, "\n");
}

