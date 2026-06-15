import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { SampleDetailPanel } from "../components/samples/SampleDetailPanel";
import { SampleTable } from "../components/samples/SampleTable";
import { useSamplesStore } from "../stores/samplesStore";
import type { Sample } from "../types/sample";
import { SAMPLE_STATUS_OPTIONS } from "../utils/constants";
import {
  getSampleName,
  getSampleOwner,
  getSampleProcessType,
  getSampleProjectCode,
  getSampleSeq,
  sortSamplesByBusinessRule,
} from "../utils/sampleFields";
import { buildSearchText, includesNormalizedText } from "../utils/searchUtils";

export function SamplesPage() {
  const { samples, filters, loading, error, setFilters } = useSamplesStore();
  const [selectedSample, setSelectedSample] = useState<Sample | null>(null);
  const [keyword, setKeyword] = useState("");

  const filteredSamples = useMemo(() => {
    const matchedSamples = keyword.trim()
      ? samples.filter((sample) =>
          includesNormalizedText(
            buildSearchText([
              getSampleProjectCode(sample),
              getSampleName(sample),
              getSampleProcessType(sample),
              getSampleSeq(sample),
              getSampleOwner(sample),
            ]),
            keyword,
          ),
        )
      : samples;

    return sortSamplesByBusinessRule(matchedSamples);
  }, [keyword, samples]);

  return (
    <section>
      {error ? (
        <section className="panel panel-section-spacing">
          <div className="empty-row">
            <div className="page-message">
              <strong>样品信息库加载失败</strong>
              <span>{error}</span>
            </div>
          </div>
        </section>
      ) : null}

      <div className="split-layout samples-layout">
        <section className="panel">
          <div className="panel-header samples-list-header">
            <h3>样品清单</h3>
            <div className="toolbar samples-list-actions">
              <input
                className="samples-list-search"
                value={keyword}
                placeholder="检索样品"
                onChange={(event) => {
                  setKeyword(event.target.value);
                  setSelectedSample(null);
                }}
              />
              <select
                value={filters.status}
                onChange={(event) => {
                  setSelectedSample(null);
                  setFilters({ status: event.target.value });
                }}
              >
                <option value="">全部状态</option>
                {SAMPLE_STATUS_OPTIONS.map((status) => (
                  <option key={status} value={status}>
                    {status}
                  </option>
                ))}
              </select>
              <Link className="ghost-link samples-maintenance-link" to="/samples/maintenance">
                维护
              </Link>
            </div>
          </div>
          {loading ? (
            <div className="empty-row">加载中...</div>
          ) : (
            <SampleTable
              samples={filteredSamples}
              readonly
              selectedSampleId={selectedSample?.id}
              onSelect={setSelectedSample}
            />
          )}
        </section>

        <SampleDetailPanel sample={selectedSample} />
      </div>
    </section>
  );
}
