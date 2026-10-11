from pathlib import Path
import gpxpy

from llama_index.core import Document


def read_gpx(path: Path) -> Document:
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        gpx = gpxpy.parse(fh)

    lines = [
        f"GPX file: {path.name}",
        f"Creator: {getattr(gpx, 'creator', '') or ''}",
    ]

    total_points = 0
    total_distance = 0.0

    for ti, track in enumerate(gpx.tracks, start=1):
        lines.append(f"Track {ti}: {track.name or ''}")
        for si, segment in enumerate(track.segments, start=1):
            points = segment.points
            total_points += len(points)
            if points:
                distance = segment.length_3d() or segment.length_2d()
                total_distance += distance or 0.0
                lines.append(
                    f"  Segment {si}: {len(points)} points, "
                    f"distance_m={distance or 0.0:.1f}"
                )
                for p in points:
                    lines.append(
                        f"    {p.time.isoformat() if p.time else ''} "
                        f"lat={p.latitude:.7f} lon={p.longitude:.7f} "
                        f"elev={p.elevation if p.elevation is not None else ''}"
                    )

    lines.append(f"Total points: {total_points}")
    lines.append(f"Total distance_m: {total_distance:.1f}")

    return Document(
        text="\n".join(lines),
        metadata={
            "source_path": str(path),
            "file_name": path.name,
            "file_type": "gpx",
        },
        id_=str(path),
    )
