import { useCallback, useEffect, useMemo, useState } from "react";
import {
  createCharacterizationCollection as createCharacterizationCollectionRequest,
  deleteCharacterizationFile as deleteCharacterizationFileRequest,
  getCharacterizationCollection,
  getCharacterizationFile,
  getCharacterizationFiles,
  getCharacterizationPreviewText,
  getCharacterizationSamples,
  getCharacterizationTree,
  uploadCharacterizationFiles,
} from "../api/characterizationApi";
import type {
  CharacterizationCollection,
  CharacterizationCollectionPayload,
  CharacterizationFile,
  CharacterizationFilesParams,
  CharacterizationSampleListItem,
  CharacterizationTree as CharacterizationTreeData,
  CharacterizationUploadFields,
} from "../types/characterization";
import { buildSearchText, normalizeFilterValue } from "../utils/searchUtils";

type CharacterizationStoreState = {
  samples: CharacterizationSampleListItem[];
  selectedSampleId: string;
  selectedCollectionId: number | null;
  selectedFileId: number | null;
  selectedCollection: CharacterizationCollection | null;
  selectedFile: CharacterizationFile | null;
  tree: CharacterizationTreeData | null;
  files: CharacterizationFile[];
  previewText: string;
  searchQuery: string;
  loading: boolean;
  uploading: boolean;
  error: string;
  setSelectedSampleId: (sampleId: string) => void;
  setSelectedCollectionId: (collectionId: number | null) => void;
  setSelectedFileId: (fileId: number | null) => void;
  setSearchQuery: (query: string) => void;
  refreshCharacterizationTree: () => Promise<void>;
  refreshCharacterizationFiles: (params?: CharacterizationFilesParams) => Promise<void>;
  createCollection: (payload: CharacterizationCollectionPayload) => Promise<void>;
  uploadFiles: (fields: CharacterizationUploadFields, files: File[]) => Promise<void>;
  loadFileDetail: (fileId: number) => Promise<CharacterizationFile | null>;
  deleteFile: (fileId: number) => Promise<void>;
};

export function useCharacterizationStore(): CharacterizationStoreState {
  const [samples, setSamples] = useState<CharacterizationSampleListItem[]>([]);
  const [selectedSampleId, setSelectedSampleId] = useState("");
  const [selectedCollectionId, setSelectedCollectionId] = useState<number | null>(null);
  const [selectedFileId, setSelectedFileId] = useState<number | null>(null);
  const [selectedCollection, setSelectedCollection] =
    useState<CharacterizationCollection | null>(null);
  const [selectedFile, setSelectedFile] = useState<CharacterizationFile | null>(null);
  const [tree, setTree] = useState<CharacterizationTreeData | null>(null);
  const [files, setFiles] = useState<CharacterizationFile[]>([]);
  const [previewText, setPreviewText] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");

  const normalizedQuery = useMemo(
    () => normalizeFilterValue(searchQuery),
    [searchQuery],
  );

  const refreshCharacterizationTree = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const nextSamples = await getCharacterizationSamples("");
      const filteredSamples = normalizedQuery
        ? nextSamples.filter((sample) =>
            buildSearchText([
              sample.sample_code,
              sample.sample_display_code,
              sample.sample_uid,
              sample.name,
              sample.category,
              sample.batch,
              sample.owner,
            ]).includes(normalizedQuery),
          )
        : nextSamples;
      setSamples(filteredSamples);

      let nextSelectedSampleId = selectedSampleId;
      if (!nextSelectedSampleId && filteredSamples.length) {
        nextSelectedSampleId = String(filteredSamples[0].id);
      }
      if (
        nextSelectedSampleId &&
        !filteredSamples.some((sample) => String(sample.id) === String(nextSelectedSampleId))
      ) {
        nextSelectedSampleId = filteredSamples.length ? String(filteredSamples[0].id) : "";
      }

      setSelectedSampleId(nextSelectedSampleId);

      if (nextSelectedSampleId) {
        const nextTree = await getCharacterizationTree(nextSelectedSampleId, "");
        const filteredCategories = normalizedQuery
          ? nextTree.categories
              .map((category) => {
                const filteredCollections = category.collections
                  .map((collection) => {
                    const filteredFiles = (collection.files || []).filter((file) =>
                      buildSearchText([
                        nextTree.sample.sample_code,
                        nextTree.sample.sample_display_code,
                        nextTree.sample.sample_uid,
                        nextTree.sample.name,
                        category.name,
                        collection.name,
                        collection.technique,
                        collection.instrument,
                        collection.operator,
                        file.original_filename,
                        file.title,
                        file.relative_path,
                      ]).includes(normalizedQuery),
                    );

                    const collectionMatches = buildSearchText([
                      nextTree.sample.sample_code,
                      nextTree.sample.sample_display_code,
                      nextTree.sample.sample_uid,
                      nextTree.sample.name,
                      category.name,
                      collection.name,
                      collection.technique,
                      collection.instrument,
                      collection.operator,
                      collection.notes,
                    ]).includes(normalizedQuery);

                    if (!collectionMatches && filteredFiles.length === 0) {
                      return null;
                    }

                    return {
                      ...collection,
                      files: collectionMatches ? collection.files || [] : filteredFiles,
                    };
                  })
                  .filter((collection): collection is NonNullable<typeof collection> => Boolean(collection));

                return filteredCollections.length
                  ? {
                      ...category,
                      collections: filteredCollections,
                      file_count: filteredCollections.reduce(
                        (sum, collection) => sum + (collection.files?.length || 0),
                        0,
                      ),
                    }
                  : null;
              })
              .filter((category): category is NonNullable<typeof category> => Boolean(category))
          : nextTree.categories;

        const nextFilteredTree = {
          ...nextTree,
          categories: filteredCategories,
        };
        setTree(nextFilteredTree);

        const flatCollections = nextFilteredTree.categories.flatMap(
          (category) => category.collections,
        );
        const matchedCollection =
          selectedCollectionId !== null
            ? flatCollections.find((collection) => collection.id === selectedCollectionId) || null
            : null;
        const fallbackCollection = matchedCollection || flatCollections[0] || null;

        setSelectedCollection(fallbackCollection);
        setSelectedCollectionId(fallbackCollection?.id || null);
      } else {
        setTree(null);
        setSelectedCollection(null);
        setSelectedCollectionId(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载表征树失败");
    } finally {
      setLoading(false);
    }
  }, [normalizedQuery, selectedCollectionId, selectedSampleId]);

  const refreshCharacterizationFiles = useCallback(
    async (params: CharacterizationFilesParams = {}) => {
      if (!selectedSampleId) {
        setFiles([]);
        return;
      }

      try {
        const nextFiles = await getCharacterizationFiles({
          sample_id: selectedSampleId,
          query: "",
          ...params,
        });
        const filteredFiles = normalizedQuery
          ? nextFiles.filter((file) =>
              buildSearchText([
                file.sample_code,
                file.sample_display_code,
                file.sample_uid,
                file.sample_name,
                file.category,
                file.collection_name,
                file.technique,
                file.operator,
                file.original_filename,
                file.title,
                file.relative_path,
              ]).includes(normalizedQuery),
            )
          : nextFiles;
        setFiles(filteredFiles);
      } catch (err) {
        setError(err instanceof Error ? err.message : "加载表征文件失败");
      }
    },
    [normalizedQuery, selectedSampleId],
  );

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void refreshCharacterizationTree();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [refreshCharacterizationTree]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void refreshCharacterizationFiles();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [refreshCharacterizationFiles]);

  const createCollection = useCallback(
    async (payload: CharacterizationCollectionPayload) => {
      setUploading(true);
      setError("");

      try {
        const created = await createCharacterizationCollectionRequest(payload);
        setSelectedSampleId(String(created.sample_id));
        setSelectedCollectionId(created.id);
        setSelectedCollection(created);
        await refreshCharacterizationTree();
      } catch (err) {
        setError(err instanceof Error ? err.message : "创建表征数据包失败");
        throw err;
      } finally {
        setUploading(false);
      }
    },
    [refreshCharacterizationTree],
  );

  const uploadFiles = useCallback(
    async (fields: CharacterizationUploadFields, uploadList: File[]) => {
      setUploading(true);
      setError("");

      try {
        const result = await uploadCharacterizationFiles(fields, uploadList);
        setSelectedCollectionId(result.collection_id);
        await refreshCharacterizationTree();
        await refreshCharacterizationFiles({ sample_id: fields.sample_id });
        const collectionDetail = await getCharacterizationCollection(result.collection_id);
        setSelectedCollection(collectionDetail);
      } catch (err) {
        setError(err instanceof Error ? err.message : "上传表征文件失败");
        throw err;
      } finally {
        setUploading(false);
      }
    },
    [refreshCharacterizationFiles, refreshCharacterizationTree],
  );

  const loadFileDetail = useCallback(async (fileId: number) => {
    setError("");

    try {
      const file = await getCharacterizationFile(fileId);
      setSelectedFile(file);
      setSelectedFileId(fileId);

      if (file.preview_type === "text") {
        const text = await getCharacterizationPreviewText(fileId);
        setPreviewText(text);
      } else {
        setPreviewText("");
      }

      return file;
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载文件详情失败");
      return null;
    }
  }, []);

  const deleteFile = useCallback(
    async (fileId: number) => {
      setUploading(true);
      setError("");

      try {
        await deleteCharacterizationFileRequest(fileId);
        if (selectedFileId === fileId) {
          setSelectedFile(null);
          setSelectedFileId(null);
          setPreviewText("");
        }
        await refreshCharacterizationTree();
        await refreshCharacterizationFiles();
      } catch (err) {
        setError(err instanceof Error ? err.message : "删除表征文件失败");
        throw err;
      } finally {
        setUploading(false);
      }
    },
    [refreshCharacterizationFiles, refreshCharacterizationTree, selectedFileId],
  );

  return {
    samples,
    selectedSampleId,
    selectedCollectionId,
    selectedFileId,
    selectedCollection,
    selectedFile,
    tree,
    files,
    previewText,
    searchQuery,
    loading,
    uploading,
    error,
    setSelectedSampleId,
    setSelectedCollectionId,
    setSelectedFileId,
    setSearchQuery,
    refreshCharacterizationTree,
    refreshCharacterizationFiles,
    createCollection,
    uploadFiles,
    loadFileDetail,
    deleteFile,
  };
}
