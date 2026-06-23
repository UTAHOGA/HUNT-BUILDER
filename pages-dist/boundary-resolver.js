window.UOGA_BOUNDARY_RESOLVER = (() => {
  function safeText(value) {
    return String(value ?? '').trim();
  }

  function normalizeHuntCode(value) {
    const raw = safeText(value).toUpperCase();
    if (!raw) return '';
    return raw.replace(/[^A-Z0-9]/g, '');
  }

  function normalizeBoundaryId(value) {
    const raw = safeText(value);
    if (!raw) return '';
    if (/^-?\d+(\.\d+)?$/.test(raw)) {
      return String(Math.trunc(Number(raw)));
    }
    return raw;
  }

  function parseIdList(value) {
    if (Array.isArray(value)) {
      return value
        .flatMap((entry) => parseIdList(entry))
        .map((entry) => normalizeBoundaryId(entry))
        .filter(Boolean);
    }
    if (value == null) return [];
    const raw = safeText(value);
    if (!raw) return [];

    if ((raw.startsWith('[') && raw.endsWith(']')) || (raw.startsWith('{') && raw.endsWith('}'))) {
      try {
        return parseIdList(JSON.parse(raw));
      } catch (_) {
        // Fall through to delimiter parsing.
      }
    }

    if (/[,\|;\/]/.test(raw)) {
      return raw
        .split(/[,\|;\/]/)
        .map((entry) => normalizeBoundaryId(entry))
        .filter(Boolean);
    }

    return [normalizeBoundaryId(raw)].filter(Boolean);
  }

  function unique(values) {
    return Array.from(new Set((Array.isArray(values) ? values : []).filter(Boolean)));
  }

  function firstNonEmpty(obj, candidates) {
    if (!obj || typeof obj !== 'object') return '';
    for (const key of candidates) {
      const value = obj[key];
      if (value == null) continue;
      const text = safeText(value);
      if (text) return value;
    }
    return '';
  }

  function normalizeManifestRow(row) {
    const huntCode = normalizeHuntCode(firstNonEmpty(row, ['hunt_code', 'huntCode', 'HUNT_CODE']));
    const boundaryIdRaw = normalizeBoundaryId(firstNonEmpty(row, ['boundary_id', 'boundaryId', 'BoundaryID', 'display_boundary_id', 'displayBoundaryId']));
    const explicitDwrBoundaryIdRaw = normalizeBoundaryId(firstNonEmpty(row, ['dwr_boundary_id', 'dwrBoundaryId']));
    const mergedBoundaryId = safeText(firstNonEmpty(row, ['merged_boundary_id', 'mergedBoundaryId']));
    const boundaryGeometryType = safeText(firstNonEmpty(row, ['boundary_geometry_type', 'boundaryGeometryType'])).toLowerCase();
    const geometryStatus = safeText(firstNonEmpty(row, ['geometry_status', 'geometryStatus']));
    const boundaryGeojsonPath = safeText(firstNonEmpty(row, ['boundary_geojson_path', 'boundaryGeojsonPath']));
    const boundaryKmzPath = safeText(firstNonEmpty(row, ['boundary_kmz_path', 'boundaryKmzPath']));
    const boundaryKmlPath = safeText(firstNonEmpty(row, ['boundary_kml_path', 'boundaryKmlPath']));
    const dwrBoundaryLink = safeText(firstNonEmpty(row, ['dwr_boundary_link', 'dwrBoundaryLink', 'boundary_link', 'boundaryLink']));
    const memberBoundaryIds = unique(
      parseIdList(firstNonEmpty(row, ['dwr_member_boundary_ids', 'dwrMemberBoundaryIds', 'member_boundary_ids', 'memberBoundaryIds'])).map((value) => normalizeBoundaryId(value)),
    );
    const numericBoundaryId = /^\d+$/.test(boundaryIdRaw) ? boundaryIdRaw : '';
    const explicitDwrBoundaryId = /^\d+$/.test(explicitDwrBoundaryIdRaw) ? explicitDwrBoundaryIdRaw : '';
    const isComposite = !!mergedBoundaryId
      || memberBoundaryIds.length > 1
      || boundaryGeometryType.includes('merged')
      || boundaryGeometryType.includes('bundle')
      || boundaryGeometryType.includes('composite');
    const displayBoundaryId = numericBoundaryId || (huntCode ? `VERIFIED_${huntCode}_2026` : '');
    const dwrBoundaryId = isComposite ? null : (explicitDwrBoundaryId || numericBoundaryId || null);
    const dwrMemberBoundaryIds = isComposite ? memberBoundaryIds : [];

    return {
      ...row,
      hunt_code: huntCode,
      display_boundary_id: displayBoundaryId || null,
      dwr_boundary_id: dwrBoundaryId,
      dwr_member_boundary_ids: dwrMemberBoundaryIds,
      boundary_id: displayBoundaryId || null,
      merged_boundary_id: mergedBoundaryId || null,
      boundary_geometry_type: boundaryGeometryType || null,
      geometry_status: geometryStatus || null,
      boundary_geojson_path: boundaryGeojsonPath || null,
      boundary_kmz_path: boundaryKmzPath || null,
      boundary_kml_path: boundaryKmlPath || null,
      dwr_boundary_link: dwrBoundaryLink || null,
      member_boundary_ids: dwrMemberBoundaryIds,
      member_boundary_count: dwrMemberBoundaryIds.length,
    };
  }

  async function defaultFetchJson(url) {
    const response = await fetch(url, { cache: 'no-store' });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  }

  async function loadBoundaryManifest(options = {}) {
    const fetchJson = typeof options.fetchJson === 'function' ? options.fetchJson : defaultFetchJson;
    const sources = Array.isArray(options.sources) ? options.sources.filter(Boolean) : [];
    let manifestRows = [];
    let sourceUsed = '';
    let lastError = null;

    for (const source of sources) {
      try {
        const payload = await fetchJson(source);
        let rows = [];
        if (Array.isArray(payload)) rows = payload;
        else if (Array.isArray(payload?.rows)) rows = payload.rows;
        else if (Array.isArray(payload?.records)) rows = payload.records;
        else if (Array.isArray(payload?.items)) rows = payload.items;
        if (!rows.length) continue;
        manifestRows = rows.map((row) => normalizeManifestRow(row)).filter((row) => row.hunt_code);
        sourceUsed = source;
        break;
      } catch (error) {
        lastError = error;
      }
    }

    const byHuntCode = new Map();
    const byMergedBoundaryId = new Map();
    manifestRows.forEach((row) => {
      if (row.hunt_code) byHuntCode.set(row.hunt_code, row);
      if (row.merged_boundary_id) byMergedBoundaryId.set(row.merged_boundary_id, row);
    });

    return {
      sourceUsed,
      rowCount: manifestRows.length,
      rows: manifestRows,
      byHuntCode,
      byMergedBoundaryId,
      error: sourceUsed ? null : lastError,
    };
  }

  function getFeatureBoundaryIds(properties) {
    const ids = [];
    const candidates = [
      properties?.BoundaryID,
      properties?.BOUNDARYID,
      properties?.Boundary_Id,
      properties?.boundary_id,
      properties?.member_boundary_ids,
      properties?.memberBoundaryIds,
    ];
    candidates.forEach((value) => {
      parseIdList(value).forEach((id) => ids.push(normalizeBoundaryId(id)));
    });
    return unique(ids);
  }

  function indexBoundaryFeatures(boundaryGeojson) {
    const byBoundaryId = new Map();
    const features = Array.isArray(boundaryGeojson?.features) ? boundaryGeojson.features : [];
    features.forEach((feature) => {
      const properties = feature?.properties || {};
      const ids = getFeatureBoundaryIds(properties);
      ids.forEach((id) => {
        if (!id) return;
        if (!byBoundaryId.has(id)) byBoundaryId.set(id, []);
        byBoundaryId.get(id).push(feature);
      });
    });
    return {
      byBoundaryId,
      featureCount: features.length,
    };
  }

  function buildFeatureCollection(features) {
    return {
      type: 'FeatureCollection',
      features: Array.isArray(features) ? features : [],
    };
  }

  function resolveBoundaryForHunt(hunt, manifestByHuntCode, boundaryFeatureIndex) {
    const huntCode = normalizeHuntCode(
      hunt?.huntCode || hunt?.hunt_code || hunt?.HuntCode || hunt?.code,
    );
    const huntBoundaryId = normalizeBoundaryId(
      hunt?.boundaryId || hunt?.boundary_id || hunt?.BoundaryID || hunt?.boundaryID || hunt?.originalBoundaryId,
    );
    const manifestRow = manifestByHuntCode?.get?.(huntCode) || null;
    const manifestMemberIds = parseIdList(
      manifestRow?.dwr_member_boundary_ids
      || manifestRow?.member_boundary_ids
      || hunt?.dwr_member_boundary_ids
      || hunt?.member_boundary_ids
      || hunt?.memberBoundaryIds,
    );
    const memberBoundaryIds = unique(manifestMemberIds.map((value) => normalizeBoundaryId(value)));
    const mergedBoundaryId = safeText(
      manifestRow?.merged_boundary_id || hunt?.merged_boundary_id || hunt?.mergedBoundaryId,
    );
    const boundaryGeojsonPath = safeText(manifestRow?.boundary_geojson_path || hunt?.boundary_geojson_path || hunt?.boundaryGeojsonPath);
    const boundaryKmzPath = safeText(manifestRow?.boundary_kmz_path || hunt?.boundary_kmz_path || hunt?.boundaryKmzPath);
    const boundaryKmlPath = safeText(manifestRow?.boundary_kml_path || hunt?.boundary_kml_path || hunt?.boundaryKmlPath);
    const dwrBoundaryLink = safeText(manifestRow?.dwr_boundary_link || hunt?.dwr_boundary_link || hunt?.dwrBoundaryLink || hunt?.boundaryLink || hunt?.boundaryURL || hunt?.huntBoundaryLink);
    const geometryType = safeText(manifestRow?.boundary_geometry_type || hunt?.boundary_geometry_type || hunt?.boundaryGeometryType);
    const manifestDwrBoundaryId = normalizeBoundaryId(
      manifestRow?.dwr_boundary_id,
    );
    // If a manifest row exists, only trust an explicit manifest DWR ID.
    // This prevents synthetic legacy IDs from being treated as real DWR IDs.
    const singleBoundaryId = manifestDwrBoundaryId || (!manifestRow ? huntBoundaryId : '');
    const manifestDisplayBoundaryId = safeText(
      manifestRow?.display_boundary_id
      || manifestRow?.boundary_id
      || hunt?.display_boundary_id
      || hunt?.displayBoundaryId
      || hunt?.boundary_id
      || hunt?.boundaryId,
    );
    const derivedDisplayBoundaryId = manifestDisplayBoundaryId
      || (mergedBoundaryId ? `VERIFIED_${huntCode}_2026` : (singleBoundaryId ? singleBoundaryId : (huntCode ? `VERIFIED_${huntCode}_2026` : '')));
    const index = boundaryFeatureIndex?.byBoundaryId instanceof Map ? boundaryFeatureIndex.byBoundaryId : new Map();

    if (boundaryGeojsonPath) {
      return {
        status: 'mapped',
        hunt_code: huntCode,
        display_boundary_id: derivedDisplayBoundaryId || null,
        dwr_boundary_id: singleBoundaryId || null,
        dwr_member_boundary_ids: memberBoundaryIds,
        boundary_id: derivedDisplayBoundaryId || null,
        merged_boundary_id: mergedBoundaryId || null,
        boundary_geometry_type: geometryType || (mergedBoundaryId ? 'merged_kmz' : 'single_kmz'),
        boundary_geojson_path: boundaryGeojsonPath,
        boundary_kmz_path: boundaryKmzPath || null,
        boundary_kml_path: boundaryKmlPath || null,
        dwr_boundary_link: dwrBoundaryLink || null,
        member_boundary_ids: memberBoundaryIds,
      };
    }

    if (singleBoundaryId && index.has(singleBoundaryId)) {
      const features = index.get(singleBoundaryId) || [];
      return {
        status: 'mapped',
        hunt_code: huntCode,
          display_boundary_id: derivedDisplayBoundaryId || null,
          dwr_boundary_id: singleBoundaryId,
          dwr_member_boundary_ids: [],
          boundary_id: derivedDisplayBoundaryId || singleBoundaryId,
        merged_boundary_id: mergedBoundaryId || null,
        boundary_geometry_type: geometryType || 'single_boundary_id',
        boundary_geojson_path: null,
        boundary_kmz_path: boundaryKmzPath || null,
        boundary_kml_path: boundaryKmlPath || null,
        dwr_boundary_link: dwrBoundaryLink || null,
        member_boundary_ids: memberBoundaryIds,
        feature_collection: buildFeatureCollection(features),
      };
    }

    if (memberBoundaryIds.length) {
      const features = [];
      let matchedMemberIds = 0;
      memberBoundaryIds.forEach((memberId) => {
        const bucket = index.get(memberId) || [];
        if (bucket.length) matchedMemberIds += 1;
        bucket.forEach((feature) => features.push(feature));
      });
      if (features.length) {
        return {
          status: 'fallback_member_features',
          hunt_code: huntCode,
          display_boundary_id: derivedDisplayBoundaryId || null,
          dwr_boundary_id: singleBoundaryId || null,
          dwr_member_boundary_ids: memberBoundaryIds,
          boundary_id: derivedDisplayBoundaryId || null,
          merged_boundary_id: mergedBoundaryId || null,
          boundary_geometry_type: geometryType || 'member_fallback',
          boundary_geojson_path: null,
          boundary_kmz_path: boundaryKmzPath || null,
          boundary_kml_path: boundaryKmlPath || null,
          dwr_boundary_link: dwrBoundaryLink || null,
          member_boundary_ids: memberBoundaryIds,
          matched_member_boundary_ids: matchedMemberIds,
          feature_collection: buildFeatureCollection(features),
        };
      }
    }

    return {
      status: 'unavailable',
      hunt_code: huntCode,
      display_boundary_id: derivedDisplayBoundaryId || null,
      dwr_boundary_id: singleBoundaryId || null,
      dwr_member_boundary_ids: memberBoundaryIds,
      boundary_id: derivedDisplayBoundaryId || null,
      merged_boundary_id: mergedBoundaryId || null,
      boundary_geometry_type: geometryType || null,
      boundary_geojson_path: null,
      boundary_kmz_path: boundaryKmzPath || null,
      boundary_kml_path: boundaryKmlPath || null,
      dwr_boundary_link: dwrBoundaryLink || null,
      member_boundary_ids: memberBoundaryIds,
    };
  }

  return {
    loadBoundaryManifest,
    normalizeHuntCode,
    normalizeBoundaryId,
    parseIdList,
    indexBoundaryFeatures,
    resolveBoundaryForHunt,
  };
})();
