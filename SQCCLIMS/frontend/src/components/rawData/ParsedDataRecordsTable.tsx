import { useEffect, useState } from "react";
import { getParsedDataRecords } from "../../api/rawDataApi";
import type { ParsedDataRecord, ParsedRecordItem } from "../../types/rawData";

type ParsedDataRecordsTableProps = {
  parsedData: ParsedDataRecord | null;
};

const PAGE_SIZE_OPTIONS = [100, 200, 500];
const CD_SEM_FILTER_FIELDS = ["row_group", "side", "direction", "dose", "location", "die_id"] as const;
type CdSemFilterKey = (typeof CD_SEM_FILTER_FIELDS)[number];

const RECORD_COLUMNS: Record<string, Array<{ key: keyof ParsedRecordItem; label: string }>> = {
  cd_sem: [
    { key: "record_index", label: "record_index" },
    { key: "row_group", label: "row_group" },
    { key: "side", label: "side" },
    { key: "direction", label: "direction" },
    { key: "die_id", label: "die_id" },
    { key: "dose", label: "dose" },
    { key: "location", label: "location" },
    { key: "numeric_value", label: "numeric_value" },
    { key: "raw_value", label: "raw_value" },
    { key: "cleaned_value", label: "cleaned_value" },
  ],
};

function emptyFilters(): Record<CdSemFilterKey, string> {
  return {
    row_group: "",
    side: "",
    direction: "",
    dose: "",
    location: "",
    die_id: "",
  };
}

function valueOrDash(value: unknown) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  return String(value);
}

function formatCellValue(key: keyof ParsedRecordItem, value: unknown) {
  if (["numeric_value", "x_value", "y_value"].includes(key) && typeof value === "number") {
    return value.toFixed(3);
  }
  return valueOrDash(value);
}

function columnClassName(key: keyof ParsedRecordItem) {
  if (["record_index", "numeric_value", "x_value", "y_value"].includes(key)) {
    return "numeric-cell";
  }
  return "text-cell";
}

export function ParsedDataRecordsTable({ parsedData }: ParsedDataRecordsTableProps) {
  const [pageSize, setPageSize] = useState(100);
  const [currentPage, setCurrentPage] = useState(1);
  const [records, setRecords] = useState<ParsedRecordItem[]>([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [filters, setFilters] = useState<Record<CdSemFilterKey, string>>(emptyFilters);
  const [q, setQ] = useState("");
  const columns = parsedData ? RECORD_COLUMNS[parsedData.data_type] || RECORD_COLUMNS.cd_sem : RECORD_COLUMNS.cd_sem;

  useEffect(() => {
    setCurrentPage(1);
    setRecords([]);
    setTotal(0);
    setTotalPages(1);
    setErrorMessage("");
    setFilters(emptyFilters());
    setQ("");
  }, [parsedData?.id]);

  useEffect(() => {
    if (!parsedData) {
      return;
    }

    const abortToken = { cancelled: false };
    setIsLoading(true);
    setErrorMessage("");

    getParsedDataRecords(parsedData.id, {
      page: currentPage,
      page_size: pageSize,
      row_group: filters.row_group || undefined,
      side: filters.side || undefined,
      direction: filters.direction || undefined,
      dose: filters.dose || undefined,
      location: filters.location || undefined,
      die_id: filters.die_id || undefined,
      q: q || undefined,
    })
      .then((response) => {
        if (abortToken.cancelled) {
          return;
        }
        setRecords(response.items);
        setTotal(response.total);
        setTotalPages(Math.max(1, response.total_pages || 1));
      })
      .catch((error: unknown) => {
        if (abortToken.cancelled) {
          return;
        }
        setRecords([]);
        setTotal(0);
        setTotalPages(1);
        setErrorMessage(error instanceof Error ? error.message : "records load failed");
      })
      .finally(() => {
        if (!abortToken.cancelled) {
          setIsLoading(false);
        }
      });

    return () => {
      abortToken.cancelled = true;
    };
  }, [currentPage, filters, pageSize, parsedData, q]);

  function updatePage(nextPage: number) {
    setCurrentPage(Math.min(Math.max(nextPage, 1), totalPages));
  }

  function updatePageSize(nextPageSize: number) {
    setPageSize(nextPageSize);
    setCurrentPage(1);
  }

  function updateFilter(key: CdSemFilterKey, value: string) {
    setFilters((current) => ({ ...current, [key]: value }));
    setCurrentPage(1);
  }

  if (!parsedData) {
    return (
      <section className="raw-parsed-section raw-parsed-records-section">
        <h5>Parsed records</h5>
        <div className="empty-row">Please select parsed data</div>
      </section>
    );
  }

  return (
    <section className="raw-parsed-section raw-parsed-records-section">
      <h5>Parsed records</h5>
      <div className="parsed-records-filters">
        {CD_SEM_FILTER_FIELDS.map((field) => (
          <label key={field}>
            {field}
            <input value={filters[field]} onChange={(event) => updateFilter(field, event.target.value)} />
          </label>
        ))}
        <label>
          q
          <input
            value={q}
            onChange={(event) => {
              setQ(event.target.value);
              setCurrentPage(1);
            }}
          />
        </label>
      </div>
      {errorMessage ? <div className="empty-row">{errorMessage}</div> : null}
      <div className="parsed-records-table-wrap">
        <table className="raw-records-table">
          <thead>
            <tr>
              {columns.map((column) => (
                <th key={column.key}>{column.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {records.map((record) => (
              <tr key={record.id}>
                {columns.map((column) => (
                  <td key={column.key} className={columnClassName(column.key)} title={valueOrDash(record[column.key])}>
                    {formatCellValue(column.key, record[column.key])}
                  </td>
                ))}
              </tr>
            ))}
            {!isLoading && records.length === 0 ? (
              <tr>
                <td className="text-cell" colSpan={columns.length}>
                  No records
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
      <div className="parsed-records-toolbar">
        <span>{isLoading ? "Loading..." : `Total ${total}`}</span>
        <div className="parsed-records-pagination">
          <label>
            Page size
            <select value={pageSize} onChange={(event) => updatePageSize(Number(event.target.value))}>
              {PAGE_SIZE_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>
          <button type="button" onClick={() => updatePage(currentPage - 1)} disabled={currentPage <= 1}>
            Prev
          </button>
          <span>{currentPage} / {totalPages}</span>
          <button type="button" onClick={() => updatePage(currentPage + 1)} disabled={currentPage >= totalPages}>
            Next
          </button>
        </div>
      </div>
    </section>
  );
}
