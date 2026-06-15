import { useMemo, useState } from "react";
import {
  buildCharacterizationDownloadUrl,
  buildCharacterizationPreviewUrl,
} from "../api/characterizationApi";
import { CharacterizationTree } from "../components/characterization/CharacterizationTree";
import { CollectionForm } from "../components/characterization/CollectionForm";
import { FilePreviewModal } from "../components/characterization/FilePreviewModal";
import { FileUploadPanel } from "../components/characterization/FileUploadPanel";
import { useCharacterizationStore } from "../stores/characterizationStore";
import type {
  CharacterizationCollection,
  CharacterizationFile,
  CharacterizationCollectionPayload,
  CharacterizationUploadFields,
} from "../types/characterization";

export function CharacterizationPage() {
  const {
    samples,
    selectedSampleId,
    selectedCollectionId,
    selectedCollection,
    selectedFile,
    tree,
    previewText,
    searchQuery,
    loading,
    uploading,
    error,
    setSelectedSampleId,
    setSelectedCollectionId,
    setSearchQuery,
    refreshCharacterizationTree,
    createCollection,
    uploadFiles,
    loadFileDetail,
    deleteFile,
  } = useCharacterizationStore();

  const [collapsedCategories, setCollapsedCategories] = useState<Set<string>>(new Set());
  const [collapsedCollections, setCollapsedCollections] = useState<Set<number>>(new Set());
  const [imageFit, setImageFit] = useState(true);
  const [previewOpen, setPreviewOpen] = useState(false);

  const pageError = useMemo(() => error, [error]);

  async function handleCreateCollection(payload: CharacterizationCollectionPayload) {
    await createCollection(payload);
  }

  async function handleUpload(
    fields: CharacterizationUploadFields,
    files: File[],
  ) {
    await uploadFiles(fields, files);
  }

  async function handlePreview(file: CharacterizationFile) {
    const detail = await loadFileDetail(file.id);
    if (detail) {
      setImageFit(true);
      setPreviewOpen(true);
    }
  }

  async function handleDelete(file: CharacterizationFile) {
    const confirmed = window.confirm("确认删除这个表征文件？");
    if (!confirmed) {
      return;
    }

    await deleteFile(file.id);
  }

  return (
    <section>
      <div className="section-head">
        <div>
          <p className="eyebrow">Characterization Center</p>
          <h2>表征数据中心</h2>
        </div>
        <div className="toolbar">
          <input
            type="search"
            placeholder="搜索样品、分类、文件、设备"
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.target.value)}
          />
          <button
            className="ghost-button"
            type="button"
            onClick={() => void refreshCharacterizationTree()}
          >
            刷新
          </button>
        </div>
      </div>

      {pageError ? (
        <section className="panel panel-section-spacing">
          <div className="empty-row">
            <div className="page-message">
              <strong>表征数据中心操作失败</strong>
              <span>{pageError}</span>
            </div>
          </div>
        </section>
      ) : null}

      {loading ? (
        <section className="panel">
          <div className="empty-row">加载中...</div>
        </section>
      ) : (
        <CharacterizationTree
          samples={samples}
          selectedSampleId={selectedSampleId}
          tree={tree}
          selectedCollectionId={selectedCollectionId}
          collapsedCategories={collapsedCategories}
          collapsedCollections={collapsedCollections}
          onSelectSample={setSelectedSampleId}
          onToggleCategory={(categoryKey) =>
            setCollapsedCategories((current) => {
              const next = new Set(current);
              if (next.has(categoryKey)) {
                next.delete(categoryKey);
              } else {
                next.add(categoryKey);
              }
              return next;
            })
          }
          onToggleCollection={(collectionId) =>
            setCollapsedCollections((current) => {
              const next = new Set(current);
              if (next.has(collectionId)) {
                next.delete(collectionId);
              } else {
                next.add(collectionId);
              }
              return next;
            })
          }
          onSelectCollection={(collection: CharacterizationCollection) => {
            setSelectedCollectionId(collection.id);
          }}
          onPreviewFile={(file) => void handlePreview(file)}
          onDeleteFile={(file) => void handleDelete(file)}
          buildDownloadUrl={buildCharacterizationDownloadUrl}
        />
      )}

      <section className="panel characterization-upload-panel">
        <div className="panel-header">
          <h3>创建表征数据包</h3>
        </div>
        <CollectionForm
          key={selectedSampleId || "new-collection"}
          samples={samples}
          saving={uploading}
          selectedSampleId={selectedSampleId}
          onSubmit={handleCreateCollection}
        />
      </section>

      <section className="panel characterization-upload-panel">
        <div className="panel-header">
          <h3>上传表征文件</h3>
        </div>
        <FileUploadPanel
          selectedCollection={selectedCollection}
          uploading={uploading}
          onUpload={handleUpload}
        />
      </section>

      {previewOpen ? (
        <FilePreviewModal
          file={selectedFile}
          textContent={previewText}
          previewUrl={
            selectedFile ? buildCharacterizationPreviewUrl(selectedFile.id) : ""
          }
          downloadUrl={
            selectedFile ? buildCharacterizationDownloadUrl(selectedFile.id) : ""
          }
          onClose={() => setPreviewOpen(false)}
          onToggleImageFit={() => setImageFit((current) => !current)}
          imageFit={imageFit}
        />
      ) : null}
    </section>
  );
}
