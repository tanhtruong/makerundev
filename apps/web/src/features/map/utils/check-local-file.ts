const PROTOMAPS_BASEMAP = "Protomaps Basemap";

export async function checkLocalFile(url: string): Promise<string | null> {
  const { PMTiles, TileType } = await import("pmtiles");
  const archive = new PMTiles(url);
  let tileType: (typeof TileType)[keyof typeof TileType];
  let metadata: unknown;
  try {
    tileType = (await archive.getHeader()).tileType;
    metadata = await archive.getMetadata();
  } catch {
    return "The file could not be read as a PMTiles archive. It may be damaged or still being copied.";
  }
  if (tileType !== TileType.Mvt) {
    return "The file holds raster tiles, not vector tiles. Only a Protomaps basemap file is supported.";
  }
  if (
    typeof metadata !== "object" ||
    metadata === null ||
    !("name" in metadata) ||
    metadata.name !== PROTOMAPS_BASEMAP
  ) {
    return "The file's metadata does not name the Protomaps basemap, so the bundled style may draw nothing. Only a Protomaps basemap file is supported.";
  }
  return null;
}
