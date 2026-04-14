import type { BucketType, RecommendationDecisionStatus, WatchlistStatus } from "../api/types";
import { labelBucket, labelFilter } from "../utils/labels";

interface FilterBarProps {
  bucket?: BucketType | "all";
  status?: WatchlistStatus | RecommendationDecisionStatus | "all";
  statusOptions?: readonly string[];
  onBucketChange?: (bucket: BucketType | "all") => void;
  onStatusChange?: (status: string) => void;
}

const bucketOptions: Array<BucketType | "all"> = ["all", "core", "swing", "event"];

export function FilterBar({
  bucket = "all",
  status = "all",
  statusOptions,
  onBucketChange,
  onStatusChange
}: FilterBarProps) {
  return (
    <div className="filter-bar">
      {onBucketChange ? (
        <label>
          Bucket
          <select value={bucket} onChange={(event) => onBucketChange(event.target.value as BucketType | "all")}>
            {bucketOptions.map((option) => (
              <option key={option} value={option}>
                {option === "all" ? "All" : labelBucket(option)}
              </option>
            ))}
          </select>
        </label>
      ) : null}

      {onStatusChange && statusOptions ? (
        <label>
          Status
          <select value={status} onChange={(event) => onStatusChange(event.target.value)}>
            {statusOptions.map((option) => (
              <option key={option} value={option}>
                {labelFilter(option)}
              </option>
            ))}
          </select>
        </label>
      ) : null}
    </div>
  );
}
