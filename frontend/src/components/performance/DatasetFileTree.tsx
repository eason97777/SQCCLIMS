import type { PerformanceDatasetFile } from "../../types/performance";

type TreeNode = {
  name: string;
  path: string;
  children: Map<string, TreeNode>;
  isFile: boolean;
};

type DatasetFileTreeProps = {
  files: PerformanceDatasetFile[];
};

function buildTree(files: PerformanceDatasetFile[]) {
  const root: TreeNode = {
    name: "",
    path: "",
    children: new Map(),
    isFile: false,
  };

  for (const file of files) {
    const segments = file.relative_path.split(/[\\/]/).filter(Boolean);
    let current = root;
    let currentPath = "";

    segments.forEach((segment, index) => {
      currentPath = currentPath ? `${currentPath}/${segment}` : segment;
      if (!current.children.has(segment)) {
        current.children.set(segment, {
          name: segment,
          path: currentPath,
          children: new Map(),
          isFile: index === segments.length - 1,
        });
      }
      current = current.children.get(segment)!;
      if (index === segments.length - 1) {
        current.isFile = true;
      }
    });
  }

  return root;
}

function renderNode(node: TreeNode): React.ReactElement {
  const children = Array.from(node.children.values()).sort((a, b) =>
    a.name.localeCompare(b.name, "zh-CN"),
  );

  return (
    <li key={node.path || "root"}>
      <span>{node.name}</span>
      {children.length ? (
        <ul className="dataset-tree-list">
          {children.map((child) => renderNode(child))}
        </ul>
      ) : null}
    </li>
  );
}

export function DatasetFileTree({ files }: DatasetFileTreeProps) {
  if (!files.length) {
    return <div className="empty-row">该数据集暂无文件结构</div>;
  }

  const root = buildTree(files);
  const children = Array.from(root.children.values()).sort((a, b) =>
    a.name.localeCompare(b.name, "zh-CN"),
  );

  return (
    <ul className="dataset-tree-list">
      {children.map((child) => renderNode(child))}
    </ul>
  );
}
