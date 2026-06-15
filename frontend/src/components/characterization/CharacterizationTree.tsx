import type {
  CharacterizationCollection,
  CharacterizationFile,
  CharacterizationSampleListItem,
  CharacterizationTree as CharacterizationTreeData,
} from "../../types/characterization";
import { getSampleDisplayCode } from "../../utils/sampleFields";
import { CharacterizationFileList } from "./CharacterizationFileList";

type CharacterizationTreeProps = {
  samples: CharacterizationSampleListItem[];
  selectedSampleId: string;
  tree: CharacterizationTreeData | null;
  selectedCollectionId: number | null;
  collapsedCategories: Set<string>;
  collapsedCollections: Set<number>;
  onSelectSample: (sampleId: string) => void;
  onToggleCategory: (categoryKey: string) => void;
  onToggleCollection: (collectionId: number) => void;
  onSelectCollection: (collection: CharacterizationCollection) => void;
  onPreviewFile: (file: CharacterizationFile) => void;
  onDeleteFile: (file: CharacterizationFile) => void;
  buildDownloadUrl: (fileId: number) => string;
};

function formatBytes(value = 0) {
  if (value < 1024) {
    return `${value} B`;
  }
  if (value < 1024 * 1024) {
    return `${(value / 1024).toFixed(1).replace(/\.0$/, "")} KB`;
  }
  return `${(value / 1024 / 1024).toFixed(1).replace(/\.0$/, "")} MB`;
}

export function CharacterizationTree({
  samples,
  selectedSampleId,
  tree,
  selectedCollectionId,
  collapsedCategories,
  collapsedCollections,
  onSelectSample,
  onToggleCategory,
  onToggleCollection,
  onSelectCollection,
  onPreviewFile,
  onDeleteFile,
  buildDownloadUrl,
}: CharacterizationTreeProps) {
  return (
    <div className="characterization-center">
      <aside className="panel characterization-samples">
        <div className="panel-header">
          <h3>样品</h3>
        </div>
        <div className="sample-list">
          {samples.length ? (
            samples.map((sample) => (
              <button
                key={sample.id}
                className={`sample-list-item ${
                  String(sample.id) === String(selectedSampleId) ? "active" : ""
                }`}
                type="button"
                onClick={() => onSelectSample(String(sample.id))}
              >
                <strong>{getSampleDisplayCode(sample)}</strong>
                <span>{sample.sample_uid || sample.name}</span>
                <small>
                  {sample.collection_count || 0} 个数据包 /{" "}
                  {sample.characterization_file_count || 0} 个文件
                </small>
              </button>
            ))
          ) : (
            <div className="empty-row">暂无样品</div>
          )}
        </div>
      </aside>

      <section className="panel characterization-browser">
        <div className="panel-header">
          <div>
            <h3>
              {tree ? getSampleDisplayCode(tree.sample) : "选择样品"}
            </h3>
            <span className="subtle-text">
              {tree
                ? `${tree.categories.length} 个分类 / ${tree.categories.reduce(
                    (sum, category) => sum + category.collections.length,
                    0,
                  )} 个数据包 / ${tree.categories.reduce(
                    (sum, category) => sum + category.file_count,
                    0,
                  )} 个文件`
                : "按样品查看表征分类和数据包"}
            </span>
          </div>
        </div>

        <div className="characterization-tree">
          {!tree ? (
            <div className="empty-row">暂无可展示内容</div>
          ) : tree.categories.length ? (
            tree.categories.map((category) => {
              const categoryKey = `${selectedSampleId}:${category.name}`;
              const categoryCollapsed = collapsedCategories.has(categoryKey);

              return (
                <section
                  key={categoryKey}
                  className={`char-category ${categoryCollapsed ? "collapsed" : ""}`}
                >
                  <header>
                    <button
                      className="collapse-toggle"
                      type="button"
                      onClick={() => onToggleCategory(categoryKey)}
                    >
                      <span className="chevron">{categoryCollapsed ? ">" : "v"}</span>
                      <h4>{category.name}</h4>
                    </button>
                    <span>
                      {category.collections.length} 个数据包 / {category.file_count} 个文件
                    </span>
                  </header>

                  {!categoryCollapsed ? (
                    <div className="char-collection-list">
                      {category.collections.map((collection) => {
                        const collectionCollapsed = collapsedCollections.has(collection.id);
                        const selected = selectedCollectionId === collection.id;

                        return (
                          <article
                            key={collection.id}
                            className={`char-collection ${
                              collectionCollapsed ? "collapsed" : ""
                            } ${selected ? "char-collection-selected" : ""}`}
                          >
                            <div className="char-collection-head">
                              <button
                                className="collapse-toggle collection-toggle"
                                type="button"
                                onClick={() => {
                                  onSelectCollection(collection);
                                  onToggleCollection(collection.id);
                                }}
                              >
                                <span className="chevron">
                                  {collectionCollapsed ? ">" : "v"}
                                </span>
                                <span>
                                  <h5>{collection.name}</h5>
                                  <span>
                                    {collection.technique || "-"} /{" "}
                                    {collection.captured_at || "未记录日期"} /{" "}
                                    {formatBytes(collection.total_bytes || 0)}
                                  </span>
                                </span>
                              </button>
                              <span className="tag">{collection.files?.length || 0} files</span>
                            </div>

                            {!collectionCollapsed ? (
                              <CharacterizationFileList
                                files={collection.files || []}
                                onPreview={onPreviewFile}
                                onDelete={onDeleteFile}
                                buildDownloadUrl={buildDownloadUrl}
                              />
                            ) : null}
                          </article>
                        );
                      })}
                    </div>
                  ) : null}
                </section>
              );
            })
          ) : (
            <div className="empty-row">该样品暂无表征数据</div>
          )}
        </div>
      </section>
    </div>
  );
}
