from typing import List, Dict, Any, Optional
import statistics


class MetricsCollector:
    """Collects performance metrics for searches and downloads.

    - search_times: durations in seconds for search operations
    - download_speeds: instantaneous download speeds (bytes/sec)
    - downloads: list of {bytes, duration} to compute throughput
    """

    def __init__(self) -> None:
        self.search_times: List[float] = []
        self.download_speeds: List[float] = []
        self.downloads: List[Dict[str, float]] = []

    def record_search_time(self, seconds: float) -> None:
        self.search_times.append(float(seconds))

    def record_download_speed(self, bytes_per_sec: float) -> None:
        self.download_speeds.append(float(bytes_per_sec))

    def record_download(self, bytes_count: float, duration_seconds: float) -> None:
        self.downloads.append({"bytes": float(bytes_count), "duration": float(duration_seconds)})

    def _summary(self, values: List[float]) -> Dict[str, Optional[float]]:
        if not values:
            return {"mean": None, "stdev": None, "min": None, "max": None}
        mean = statistics.mean(values)
        stdev = statistics.stdev(values) if len(values) > 1 else 0.0
        return {"mean": mean, "stdev": stdev, "min": min(values), "max": max(values)}

    def get_statistics(self) -> Dict[str, Any]:
        """Return summary stats for recorded metrics, including overall throughput.

        Throughput is computed as total_bytes / total_duration across recorded downloads.
        """
        total_bytes = sum(d["bytes"] for d in self.downloads) if self.downloads else 0.0
        total_duration = sum(d["duration"] for d in self.downloads) if self.downloads else 0.0
        throughput = (total_bytes / total_duration) if total_duration > 0 else None

        return {
            "search_times": self._summary(self.search_times),
            "download_speeds": self._summary(self.download_speeds),
            "throughput_bytes_per_sec": throughput,
        }