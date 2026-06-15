import type { Sample } from "../../types/sample";
import type { RawDataListParams } from "../../types/rawData";
import { RAW_DATA_TYPE_OPTIONS } from "../../utils/constants";
import { getSampleDisplayLabel } from "../../utils/sampleFields";

type RawDataFilterProps = {
  filters: Required<RawDataListParams>;
  samples: Sample[];
  onChange: (filters: Partial<Required<RawDataListParams>>) => void;
  onRefresh?: () => void;
};

export function RawDataFilter({ filters, samples, onChange, onRefresh }: RawDataFilterProps) {
  function handleReset() {
    onChange({
      raw_data_id: "",
      sample_id: "",
      data_type: "",
      parser_status: "",
      status: "",
      query: "",
    });
  }

  return (
    <div className="raw-data-filter-panel">
      <div className="raw-data-filter-header">
        <div className="toolbar raw-data-filter-toolbar">
          <label>
            样品
            <select
              value={filters.sample_id}
              onChange={(event) => onChange({ sample_id: event.target.value })}
            >
              <option value="">全部样品</option>
              {samples.map((sample) => (
                <option key={sample.id} value={sample.id}>
                  {getSampleDisplayLabel(sample)}
                </option>
              ))}
            </select>
          </label>
          <label>
            数据类型
            <select
              value={filters.data_type}
              onChange={(event) => onChange({ data_type: event.target.value })}
            >
              <option value="">全部类型</option>
              {RAW_DATA_TYPE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="raw-data-filter-search">
            关键词搜索
            <input
              className="raw-data-search"
              value={filters.query}
              placeholder="搜索编号、样品、类型、人员等..."
              onChange={(event) => onChange({ query: event.target.value })}
            />
          </label>
          <div className="raw-data-filter-actions">
            <button type="button">搜索</button>
            <button className="ghost-button" type="button" onClick={handleReset}>
              重置
            </button>
            {onRefresh ? (
              <button className="ghost-button" type="button" onClick={onRefresh}>
                刷新
              </button>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}
