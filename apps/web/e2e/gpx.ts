export function gpx(
  name: string,
  start: string,
  kilometres: number,
  { heartRate }: { heartRate?: (point: number) => number } = {},
): string {
  const points = Array.from({ length: kilometres * 10 + 1 }, (_, i) => {
    const time = new Date(Date.parse(start) + i * 30_000).toISOString().replace(".000", "");
    const extensions = heartRate
      ? `<extensions><gpxtpx:TrackPointExtension><gpxtpx:hr>${heartRate(i)}</gpxtpx:hr></gpxtpx:TrackPointExtension></extensions>`
      : "";
    return `<trkpt lat="${(55.67 + i * 0.000898).toFixed(6)}" lon="12.560000"><time>${time}</time>${extensions}</trkpt>`;
  });
  return `<?xml version="1.0"?><gpx version="1.1" creator="e2e" xmlns="http://www.topografix.com/GPX/1/1" xmlns:gpxtpx="http://www.garmin.com/xmlschemas/TrackPointExtension/v1"><trk><name>${name}</name><type>running</type><trkseg>${points.join("")}</trkseg></trk></gpx>`;
}
