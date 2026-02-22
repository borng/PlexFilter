import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import FilterEditor from "../components/FilterEditor";

// ---------------------------------------------------------------------------
// Types (local — the api module uses `any`)
// ---------------------------------------------------------------------------

interface Profile {
  id: number;
  name: string;
  plex_user: string | null;
  filters: Record<string, boolean> | string;
  mode: string;
  created_at: string;
}

/** Ensure filters is always a parsed object (backend may return JSON string). */
function parseFilters(raw: unknown): Record<string, boolean> {
  if (typeof raw === "string") {
    try {
      return JSON.parse(raw);
    } catch {
      return {};
    }
  }
  if (raw && typeof raw === "object") return raw as Record<string, boolean>;
  return {};
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function Profiles() {
  const queryClient = useQueryClient();

  // ---- Data fetching ----
  const {
    data: profiles,
    isLoading,
    error,
  } = useQuery<Profile[]>({
    queryKey: ["profiles"],
    queryFn: () => api.profiles(),
  });

  // ---- Mutations ----
  const createMutation = useMutation({
    mutationFn: (data: { name: string; mode: string }) =>
      api.createProfile(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["profiles"] });
      setNewName("");
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: number;
      data: { filters?: Record<string, boolean>; name?: string; mode?: string };
    }) => api.updateProfile(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["profiles"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.deleteProfile(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["profiles"] });
      setExpandedId(null);
    },
  });

  // ---- Local state ----
  const [newName, setNewName] = useState("");
  const [newMode, setNewMode] = useState<"skip" | "mute">("skip");
  const [expandedId, setExpandedId] = useState<number | null>(null);

  // Draft filters for the expanded profile (local until Save is clicked)
  const [draftFilters, setDraftFilters] = useState<Record<string, boolean>>({});
  const [dirty, setDirty] = useState(false);

  // ---- Handlers ----

  function handleExpand(profile: Profile) {
    if (expandedId === profile.id) {
      setExpandedId(null);
      setDirty(false);
      return;
    }
    setExpandedId(profile.id);
    setDraftFilters(parseFilters(profile.filters));
    setDirty(false);
  }

  function handleFilterChange(next: Record<string, boolean>) {
    setDraftFilters(next);
    setDirty(true);
  }

  function handleSave(profileId: number) {
    updateMutation.mutate(
      { id: profileId, data: { filters: draftFilters } },
      {
        onSuccess: () => setDirty(false),
      }
    );
  }

  function handleCreate() {
    const trimmed = newName.trim();
    if (!trimmed) return;
    createMutation.mutate({ name: trimmed, mode: newMode });
  }

  // ---- Render ----

  return (
    <div className="max-w-2xl mx-auto">
      <h2 className="text-2xl font-bold text-gray-100 mb-4">Filter Profiles</h2>

      {/* ---- Create form ---- */}
      <div className="bg-gray-800 rounded-lg p-4 mb-6 space-y-3">
        <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">
          New Profile
        </h3>
        <div className="flex gap-2">
          <input
            type="text"
            placeholder="Profile name..."
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleCreate()}
            className="flex-1 bg-gray-700 text-gray-100 text-sm rounded px-3 py-2 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <select
            value={newMode}
            onChange={(e) => setNewMode(e.target.value as "skip" | "mute")}
            className="bg-gray-700 text-gray-100 text-sm rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="skip">Skip</option>
            <option value="mute">Mute</option>
          </select>
          <button
            onClick={handleCreate}
            disabled={!newName.trim() || createMutation.isPending}
            className="bg-blue-600 hover:bg-blue-500 disabled:bg-gray-600 disabled:cursor-not-allowed text-white text-sm font-medium rounded px-4 py-2 transition-colors"
          >
            {createMutation.isPending ? "Creating..." : "Create"}
          </button>
        </div>
        {createMutation.isError && (
          <p className="text-red-400 text-xs">
            {(createMutation.error as Error).message}
          </p>
        )}
      </div>

      {/* ---- Loading / error states ---- */}
      {isLoading && <p className="text-gray-400">Loading profiles...</p>}
      {error && (
        <p className="text-red-400">
          Failed to load profiles: {(error as Error).message}
        </p>
      )}

      {/* ---- Profile list ---- */}
      {profiles && profiles.length === 0 && (
        <p className="text-gray-500 text-sm">
          No profiles yet. Create one above to get started.
        </p>
      )}

      <div className="space-y-2">
        {profiles?.map((profile) => {
          const isExpanded = expandedId === profile.id;
          const filterCount = Object.keys(parseFilters(profile.filters)).length;

          return (
            <div
              key={profile.id}
              className="bg-gray-800 rounded-lg overflow-hidden"
            >
              {/* Profile header row */}
              <div
                className="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-gray-700"
                onClick={() => handleExpand(profile)}
              >
                <div className="flex items-center gap-3">
                  <span className="text-gray-400 text-xs select-none">
                    {isExpanded ? "\u25BC" : "\u25B6"}
                  </span>
                  <div>
                    <span className="text-gray-100 font-medium">
                      {profile.name}
                    </span>
                    <span className="ml-2 text-xs text-gray-500">
                      {profile.mode} &middot; {filterCount} filter
                      {filterCount !== 1 ? "s" : ""}
                    </span>
                  </div>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    if (confirm(`Delete profile "${profile.name}"?`)) {
                      deleteMutation.mutate(profile.id);
                    }
                  }}
                  className="text-gray-500 hover:text-red-400 text-xs px-2 py-1 rounded transition-colors"
                >
                  Delete
                </button>
              </div>

              {/* Expanded: filter editor */}
              {isExpanded && (
                <div className="px-4 pb-4 border-t border-gray-700">
                  <div className="pt-3">
                    <FilterEditor
                      filters={draftFilters}
                      onChange={handleFilterChange}
                    />
                  </div>

                  {/* Save / status bar */}
                  <div className="mt-3 flex items-center gap-3">
                    <button
                      onClick={() => handleSave(profile.id)}
                      disabled={!dirty || updateMutation.isPending}
                      className="bg-green-600 hover:bg-green-500 disabled:bg-gray-600 disabled:cursor-not-allowed text-white text-sm font-medium rounded px-4 py-2 transition-colors"
                    >
                      {updateMutation.isPending ? "Saving..." : "Save"}
                    </button>
                    {dirty && (
                      <span className="text-yellow-400 text-xs">
                        Unsaved changes
                      </span>
                    )}
                    {updateMutation.isSuccess && !dirty && (
                      <span className="text-green-400 text-xs">Saved</span>
                    )}
                    {updateMutation.isError && (
                      <span className="text-red-400 text-xs">
                        {(updateMutation.error as Error).message}
                      </span>
                    )}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
