import { normalizeSearchText, trimText } from "./textNormalize";

/**
 * Join multiple searchable fields into one normalized search string.
 */
export function buildSearchText(fields: Array<string | null | undefined>) {
  return normalizeSearchText(fields.filter((value) => value != null).join(" "));
}

/**
 * Normalize a filter value for comparison. Empty-like values stay empty.
 */
export function normalizeFilterValue(value: string | null | undefined) {
  const trimmed = trimText(value);
  return trimmed ? normalizeSearchText(trimmed) : "";
}

/**
 * Compare source text against a keyword using normalized matching.
 */
export function includesNormalizedText(
  source: string | null | undefined,
  keyword: string | null | undefined,
) {
  const normalizedKeyword = normalizeFilterValue(keyword);
  if (!normalizedKeyword) {
    return true;
  }

  return normalizeSearchText(source).includes(normalizedKeyword);
}
