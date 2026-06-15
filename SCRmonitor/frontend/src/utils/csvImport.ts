import {
  normalizeCsvHeader,
  normalizeNumericText,
  removeControlChars,
  trimText,
} from "./textNormalize";

export type CsvParseError = {
  row: number;
  reason: string;
};

export type CsvParseResult = {
  detectedEncoding: "utf-8" | "utf-8-bom";
  records: Array<Record<string, string>>;
  errors: CsvParseError[];
};

function parseCsvRows(text: string) {
  const rows: string[][] = [];
  let row: string[] = [];
  let cell = "";
  let quoted = false;

  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    const next = text[index + 1];

    if (char === '"' && quoted && next === '"') {
      cell += '"';
      index += 1;
    } else if (char === '"') {
      quoted = !quoted;
    } else if (char === "," && !quoted) {
      row.push(cell);
      cell = "";
    } else if ((char === "\n" || char === "\r") && !quoted) {
      if (char === "\r" && next === "\n") {
        index += 1;
      }
      row.push(cell);
      rows.push(row);
      row = [];
      cell = "";
    } else {
      cell += char;
    }
  }

  row.push(cell);
  rows.push(row);

  return rows;
}

export async function parseCsvFile(file: File): Promise<CsvParseResult> {
  const buffer = await file.arrayBuffer();
  const bytes = new Uint8Array(buffer);
  const hasBom =
    bytes.length >= 3 && bytes[0] === 0xef && bytes[1] === 0xbb && bytes[2] === 0xbf;
  const detectedEncoding = hasBom ? "utf-8-bom" : "utf-8";

  let text: string;
  try {
    text = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  } catch {
    throw new Error("CSV 文件不是有效的 UTF-8 编码，请转换为 UTF-8 后再导入。");
  }

  const rows = parseCsvRows(text);
  const nonEmptyRows = rows.filter((row) => row.some((value) => trimText(value) !== ""));
  if (!nonEmptyRows.length) {
    return { detectedEncoding, records: [], errors: [] };
  }

  const rawHeaders = nonEmptyRows.shift() || [];
  const headers = rawHeaders.map((header) => normalizeCsvHeader(header));
  const errors: CsvParseError[] = [];
  const records: Array<Record<string, string>> = [];

  nonEmptyRows.forEach((values, index) => {
    const rowNumber = index + 2;
    if (values.length !== headers.length) {
      errors.push({
        row: rowNumber,
        reason: `列数不匹配：期望 ${headers.length} 列，实际 ${values.length} 列`,
      });
      return;
    }

    const record: Record<string, string> = {};
    headers.forEach((header, headerIndex) => {
      const rawValue = trimText(removeControlChars(values[headerIndex]));
      record[header] =
        header === "numeric_value" ? normalizeNumericText(rawValue) : rawValue;
    });
    records.push(record);
  });

  return {
    detectedEncoding,
    records,
    errors,
  };
}
