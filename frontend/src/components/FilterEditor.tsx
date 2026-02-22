import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface CategoryNode {
  id: number;
  display_title: string;
  key: string;
  parent_id: number | null;
  ordering: number;
  children: CategoryNode[];
}

interface FilterEditorProps {
  filters: Record<string, boolean>;
  onChange: (filters: Record<string, boolean>) => void;
}

/** The v1 groups we expose in the editor. */
const V1_GROUPS = ["Language", "Nudity", "Sex", "Violence"];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function FilterEditor({ filters, onChange }: FilterEditorProps) {
  const {
    data: tree,
    isLoading,
    error,
  } = useQuery<CategoryNode[]>({
    queryKey: ["categories"],
    queryFn: () => api.categories(),
    staleTime: Infinity, // categories rarely change
  });

  // Track which groups and categories are expanded
  const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>({});
  const [expandedCats, setExpandedCats] = useState<Record<string, boolean>>({});

  if (isLoading) {
    return <p className="text-gray-400 text-sm py-2">Loading categories...</p>;
  }
  if (error) {
    return (
      <p className="text-red-400 text-sm py-2">
        Failed to load categories: {(error as Error).message}
      </p>
    );
  }
  if (!tree) return null;

  // Filter the tree to only v1 groups
  const groups = tree.filter((node) => V1_GROUPS.includes(node.display_title));

  // -------------------------------------------------------------------------
  // Helpers
  // -------------------------------------------------------------------------

  function toggleGroup(groupKey: string) {
    setExpandedGroups((prev) => ({ ...prev, [groupKey]: !prev[groupKey] }));
  }

  function toggleCat(catKey: string) {
    setExpandedCats((prev) => ({ ...prev, [catKey]: !prev[catKey] }));
  }

  /** Toggle a filter key and propagate via onChange. */
  function toggleFilter(key: string) {
    const next = { ...filters };
    if (next[key]) {
      delete next[key];
    } else {
      next[key] = true;
    }
    onChange(next);
  }

  /** Read a filter value, defaulting to false if absent. */
  function isOn(key: string): boolean {
    return !!filters[key];
  }

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  return (
    <div className="space-y-1">
      {groups.map((group) => {
        const groupKey = group.display_title; // e.g. "Language"
        const isExpanded = !!expandedGroups[groupKey];

        return (
          <div key={group.id} className="rounded bg-gray-800">
            {/* Level 1 — Group header */}
            <div
              className="flex items-center justify-between px-3 py-2 cursor-pointer hover:bg-gray-700 rounded"
              onClick={() => toggleGroup(groupKey)}
            >
              <div className="flex items-center gap-2">
                <span className="text-gray-400 text-xs w-4 text-center select-none">
                  {isExpanded ? "\u25BC" : "\u25B6"}
                </span>
                <span className="font-medium text-gray-100">{groupKey}</span>
                <span className="text-gray-500 text-xs">
                  ({group.children.length})
                </span>
              </div>
              <label
                className="flex items-center"
                onClick={(e) => e.stopPropagation()}
              >
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded bg-gray-600 border-gray-500 text-blue-500 focus:ring-blue-500 focus:ring-offset-gray-800"
                  checked={isOn(groupKey)}
                  onChange={() => toggleFilter(groupKey)}
                />
              </label>
            </div>

            {/* Level 2 — Categories within this group */}
            {isExpanded && (
              <div className="ml-6 border-l border-gray-700 pl-2 pb-1">
                {group.children.map((cat) => {
                  const catFilterKey = `${groupKey}:${cat.display_title}`;
                  const catExpandKey = `${group.id}:${cat.id}`;
                  const isCatExpanded = !!expandedCats[catExpandKey];
                  const hasChildren = cat.children.length > 0;

                  return (
                    <div key={cat.id}>
                      <div
                        className="flex items-center justify-between px-2 py-1.5 cursor-pointer hover:bg-gray-700 rounded"
                        onClick={() => hasChildren && toggleCat(catExpandKey)}
                      >
                        <div className="flex items-center gap-2">
                          {hasChildren ? (
                            <span className="text-gray-400 text-xs w-4 text-center select-none">
                              {isCatExpanded ? "\u25BC" : "\u25B6"}
                            </span>
                          ) : (
                            <span className="w-4" />
                          )}
                          <span className="text-gray-200 text-sm">
                            {cat.display_title}
                          </span>
                        </div>
                        <label
                          className="flex items-center"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <input
                            type="checkbox"
                            className="h-4 w-4 rounded bg-gray-600 border-gray-500 text-blue-500 focus:ring-blue-500 focus:ring-offset-gray-800"
                            checked={isOn(catFilterKey)}
                            onChange={() => toggleFilter(catFilterKey)}
                          />
                        </label>
                      </div>

                      {/* Level 3 — Subcategories */}
                      {isCatExpanded && hasChildren && (
                        <div className="ml-6 border-l border-gray-600 pl-2 pb-1">
                          {cat.children.map((sub) => {
                            const subFilterKey = `${groupKey}:${sub.display_title}`;

                            return (
                              <div
                                key={sub.id}
                                className="flex items-center justify-between px-2 py-1 hover:bg-gray-700 rounded"
                              >
                                <div className="flex items-center gap-2">
                                  <span className="w-4" />
                                  <span className="text-gray-300 text-xs">
                                    {sub.display_title}
                                  </span>
                                </div>
                                <label
                                  className="flex items-center"
                                  onClick={(e) => e.stopPropagation()}
                                >
                                  <input
                                    type="checkbox"
                                    className="h-3.5 w-3.5 rounded bg-gray-600 border-gray-500 text-blue-500 focus:ring-blue-500 focus:ring-offset-gray-800"
                                    checked={isOn(subFilterKey)}
                                    onChange={() => toggleFilter(subFilterKey)}
                                  />
                                </label>
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}

      {groups.length === 0 && (
        <p className="text-gray-500 text-sm py-2">
          No categories available. Run a VidAngel sync first.
        </p>
      )}
    </div>
  );
}
