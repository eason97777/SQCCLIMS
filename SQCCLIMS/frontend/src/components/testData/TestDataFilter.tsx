import type { TestDataListParams } from "../../types/testData";

type TestDataFilterProps = {
  filters: Required<TestDataListParams>;
  onChange: (nextFilters: Partial<Required<TestDataListParams>>) => void;
};

export function TestDataFilter({
  filters,
  onChange,
}: TestDataFilterProps) {
  return (
    <input
      className="test-data-search"
      type="search"
      value={filters.query}
      placeholder="搜索样品、测试、指标、人员"
      onChange={(event) => onChange({ query: event.target.value })}
    />
  );
}
