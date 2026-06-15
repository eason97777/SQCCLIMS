import type { Sample } from "../../types/sample";
import type { PerformanceDatasetListParams } from "../../types/performance";
import { getSampleDisplayLabel } from "../../utils/sampleFields";

type PerformanceDatasetFilterProps = {
  filters: Required<PerformanceDatasetListParams>;
  samples: Sample[];
  onChange: (nextFilters: Partial<Required<PerformanceDatasetListParams>>) => void;
};

export function PerformanceDatasetFilter({
  filters,
  samples,
  onChange,
}: PerformanceDatasetFilterProps) {
  return (
    <>
      <select
        value={String(filters.sample_id || "")}
        onChange={(event) => onChange({ sample_id: event.target.value })}
      >
        <option value="">全部样品</option>
        {samples.map((sample) => (
          <option key={sample.id} value={sample.id}>
            {getSampleDisplayLabel(sample)}
          </option>
        ))}
      </select>
      <input
        type="search"
        value={filters.query}
        placeholder="搜索样品、数据集、取样编号、状态"
        onChange={(event) => onChange({ query: event.target.value })}
      />
    </>
  );
}
