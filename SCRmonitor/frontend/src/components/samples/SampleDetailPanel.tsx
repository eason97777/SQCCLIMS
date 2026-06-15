import type { Sample } from "../../types/sample";
import {
  getSampleDisplayCode,
  getSampleName,
  getSampleOwner,
  getSampleProcessType,
  getSampleProjectCode,
  getSampleRemark,
  getSampleSeq,
  getSampleUid,
  valueOrDash,
} from "../../utils/sampleFields";
import { SampleStatusBadge } from "./SampleStatusBadge";

type SampleDetailPanelProps = {
  sample: Sample | null;
};

export function SampleDetailPanel({ sample }: SampleDetailPanelProps) {
  if (!sample) {
    return (
      <section className="panel form-panel">
        <div className="panel-header">
          <h3>样品详情</h3>
        </div>
        <div className="empty-row">
          点击左侧样品清单中的任意样品，可在这里查看只读详情。
        </div>
      </section>
    );
  }

  return (
    <section className="panel form-panel">
      <div className="panel-header">
        <h3>样品详情</h3>
      </div>
      <dl className="detail-grid sample-detail-grid">
        <div className="full">
          <dt>样品显示编号</dt>
          <dd>{valueOrDash(getSampleDisplayCode(sample))}</dd>
        </div>
        <div>
          <dt>样品 UID</dt>
          <dd>{valueOrDash(getSampleUid(sample))}</dd>
        </div>
        <div>
          <dt>项目编号</dt>
          <dd>{valueOrDash(getSampleProjectCode(sample))}</dd>
        </div>
        <div>
          <dt>样品名称</dt>
          <dd>{valueOrDash(getSampleName(sample))}</dd>
        </div>
        <div>
          <dt>工艺类型</dt>
          <dd>{valueOrDash(getSampleProcessType(sample))}</dd>
        </div>
        <div>
          <dt>样品序号</dt>
          <dd>{valueOrDash(getSampleSeq(sample))}</dd>
        </div>
        <div>
          <dt>负责人</dt>
          <dd>{valueOrDash(getSampleOwner(sample))}</dd>
        </div>
        <div>
          <dt>状态</dt>
          <dd>
            <SampleStatusBadge status={sample.status} />
          </dd>
        </div>
        <div className="full sample-detail-note">
          <dt>备注</dt>
          <dd>{valueOrDash(getSampleRemark(sample))}</dd>
        </div>
      </dl>
    </section>
  );
}
