window.UOGA_DATA = (() => {
  let officialBoundaryLookupPromise = null;
  const GIT_LFS_POINTER_PREFIX = 'version https://git-lfs.github.com/spec/v1';

  function isGitLfsPointerText(text) {
    return String(text || '').startsWith(GIT_LFS_POINTER_PREFIX);
  }

  function getCloudflareBase() {
    const configured = String(window.UOGA_CONFIG?.CLOUDFLARE_BASE || '').trim();
    return configured ? configured.replace(/\/+$/, '') : '';
  }

  function getCloudflareFallbackUrl(url) {
    const cloudflareBase = getCloudflareBase();
    if (!cloudflareBase) return '';

    const raw = String(url || '').trim();
    if (!raw) return '';

    // Relative runtime JSON under processed_data should be available from Cloudflare.
    const relativeProcessed = raw.match(/^\.?\/?(processed_data\/.+)$/i);
    if (relativeProcessed?.[1]) {
      return `${cloudflareBase}/${relativeProcessed[1]}`;
    }

    // If primary domain served an LFS pointer, retry same path on Cloudflare.
    try {
      const parsed = new URL(raw, window.location.origin);
      const host = parsed.hostname.toLowerCase();
      if (host === 'huntbuilder.uoga.org' && parsed.pathname.startsWith('/processed_data/')) {
        return `${cloudflareBase}${parsed.pathname}`;
      }
    } catch {
      // Ignore URL parse failures and keep default behavior.
    }
    return '';
  }

  async function fetchJson(url) {
    const attempted = new Set();
    let activeUrl = String(url || '').trim();
    let lastError = null;

    while (activeUrl && !attempted.has(activeUrl)) {
      attempted.add(activeUrl);
      try {
        const resp = await fetch(activeUrl, { cache: 'no-store' });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

        const text = await resp.text();
        if (isGitLfsPointerText(text)) {
          const lfsError = new Error(`Git LFS pointer served instead of JSON: ${activeUrl}`);
          lfsError.code = 'GIT_LFS_POINTER';
          throw lfsError;
        }

        return JSON.parse(text);
      } catch (error) {
        lastError = error;
        if (error?.code === 'GIT_LFS_POINTER') {
          const fallbackUrl = getCloudflareFallbackUrl(activeUrl);
          if (fallbackUrl && !attempted.has(fallbackUrl)) {
            console.warn(`JSON source returned Git LFS pointer, retrying via Cloudflare: ${activeUrl} -> ${fallbackUrl}`);
            activeUrl = fallbackUrl;
            continue;
          }
        }
        throw error;
      }
    }

    throw lastError || new Error('Unable to load JSON source.');
  }

  async function fetchGeoJson(url) {
    return fetchJson(url);
  }

  async function fetchFirstGeoJson(urls) {
    let lastError = null;
    for (const url of urls) {
      try {
        return await fetchGeoJson(url);
      } catch (error) {
        lastError = error;
        console.error('Failed to load GeoJSON from', url, error);
      }
    }
    throw lastError || new Error('No GeoJSON source succeeded');
  }

  async function fetchArcGisPagedGeoJson(layerUrl, where, pageSize = 2000) {
    const allFeatures = [];
    let offset = 0;
    while (true) {
      const url = `${layerUrl}/query?where=${encodeURIComponent(where)}&outFields=*&returnGeometry=true&outSR=4326&f=geojson&resultRecordCount=${pageSize}&resultOffset=${offset}`;
      const geojson = await fetchGeoJson(url);
      const features = Array.isArray(geojson?.features) ? geojson.features : [];
      allFeatures.push(...features);
      if (features.length < pageSize) break;
      offset += pageSize;
    }
    return { type: 'FeatureCollection', features: allFeatures };
  }

  async function loadOfficialBoundaryLookup(deps) {
    const {
      OFFICIAL_HUNT_BOUNDARY_TABLE_SOURCES,
      normalizeHuntCode,
      safe
    } = deps;

    if (!officialBoundaryLookupPromise) {
      officialBoundaryLookupPromise = (async () => {
        const lookup = new Map();
        for (const source of OFFICIAL_HUNT_BOUNDARY_TABLE_SOURCES) {
          try {
            const json = await fetchJson(source);
            const rows = Array.isArray(json?.features)
              ? json.features
              : (Array.isArray(json) ? json : []);
            rows.forEach(feature => {
              const attrs = feature?.attributes || feature || {};
              const huntCode = normalizeHuntCode(attrs.HUNT_NUMBER);
              const boundaryId = safe(attrs.BOUNDARYID).trim();
              const boundaryName = safe(attrs.BOUNDARY_NAME).trim();
              if (!huntCode || (!boundaryId && !boundaryName)) return;
              const current = lookup.get(huntCode) || { ids: new Set(), names: new Set() };
              if (boundaryId) current.ids.add(boundaryId);
              if (boundaryName) current.names.add(boundaryName);
              lookup.set(huntCode, current);
            });
          } catch (error) {
            console.error(`Failed to load official hunt boundary lookup from ${source}.`, error);
          }
        }
        return lookup;
      })();
    }
    return officialBoundaryLookupPromise;
  }

  async function applyOfficialBoundaryMappings(records, deps) {
    const {
      normalizeHuntCode,
      getHuntCode,
      getBoundaryId,
      safe
    } = deps;

    const lookup = await loadOfficialBoundaryLookup(deps);
    if (!lookup?.size) return;
    records.forEach(record => {
      const huntCode = normalizeHuntCode(getHuntCode(record));
      if (!huntCode) return;
      const official = lookup.get(huntCode);
      if (!official) return;
      const officialBoundaryIds = Array.from(official.ids || []);
      const officialBoundaryNames = Array.from(official.names || []);
      if (officialBoundaryIds.length) {
        record.officialBoundaryIds = officialBoundaryIds;
        if (!safe(getBoundaryId(record)).trim() && officialBoundaryIds.length === 1) {
          record.boundaryId = officialBoundaryIds[0];
        }
      }
      if (officialBoundaryNames.length) {
        record.officialBoundaryNames = officialBoundaryNames;
      }
    });
  }

  async function loadOfficialElkBoundaryFeatures(deps) {
    const { ELK_BOUNDARY_TABLE_SOURCES } = deps;
    for (const candidate of ELK_BOUNDARY_TABLE_SOURCES) {
      try {
        const json = await fetchJson(candidate);
        const features = Array.isArray(json?.features) ? json.features : [];
        if (features.length) {
          console.log(`Loaded ${features.length} official elk boundary rows from ${candidate}`);
          return features;
        }
      } catch (error) {
        console.error(`Failed to load official elk boundary rows from ${candidate}.`, error);
      }
    }
    return [];
  }

  function getBoundaryRecordScore(record, deps) {
    const { getSpeciesDisplay, getNormalizedSex, getUnitName, safe } = deps;
    let score = 0;
    if (getSpeciesDisplay(record) === 'Elk') score += 8;
    if (getNormalizedSex(record) === 'Bull') score += 4;
    if (getUnitName(record) && !/units?/i.test(getUnitName(record))) score += 3;
    if (safe(record.sourceBoundaryName).trim()) score += 2;
    if (safe(record.region).trim()) score += 1;
    return score;
  }

  function getRepresentativeBoundaryRecord(records, deps) {
    const { getBoundaryId, safe } = deps;
    const byBoundary = new Map();
    records.forEach(record => {
      const boundaryId = safe(getBoundaryId(record)).trim();
      if (!boundaryId) return;
      const existing = byBoundary.get(boundaryId);
      const existingScore = existing ? getBoundaryRecordScore(existing, deps) : -1;
      const candidateScore = getBoundaryRecordScore(record, deps);
      if (!existing || candidateScore > existingScore) {
        byBoundary.set(boundaryId, record);
      }
    });
    return byBoundary;
  }

  function buildDerivedSpikeElkRecord(template, boundaryRecord, boundaryId, officialFeature, deps) {
    const { firstNonEmpty, getUnitName, normalizeBoundaryKey, safe, getHuntCode } = deps;
    const attrs = officialFeature?.attributes || {};
    const officialName = firstNonEmpty(
      boundaryRecord && getUnitName(boundaryRecord),
      boundaryRecord && boundaryRecord.sourceBoundaryName,
      attrs.UNIT_NAME,
      attrs.BOUNDARY_LABEL,
      attrs.BOUNDARY_NAME,
      template.sourceBoundaryName,
      template.unitName
    );
    const next = {
      ...template,
      boundaryId: Number(boundaryId),
      sourceBoundaryName: officialName,
      unitName: officialName,
      unitCode: normalizeBoundaryKey(officialName || template.unitCode || getHuntCode(template)),
      boundaryLink: template.boundaryLink || `https://dwrapps.utah.gov/huntboundary/hbstart?HN=${encodeURIComponent(getHuntCode(template))}`,
      derivedFromOfficialElkTable: true
    };
    if (boundaryRecord) {
      next.region = firstNonEmpty(boundaryRecord.region, template.region);
    }
    if (!safe(next.unitName).trim()) {
      next.unitName = safe(template.unitName).trim();
    }
    return next;
  }

  async function loadDerivedSpikeElkRecords(existingRecords, deps) {
    const { SPIKE_ELK_HUNT_CODES, normalizeHuntCode, getHuntCode } = deps;
    const features = await loadOfficialElkBoundaryFeatures(deps);
    if (!features.length) return [];

    const templatesByCode = new Map();
    existingRecords.forEach(record => {
      const code = normalizeHuntCode(getHuntCode(record));
      if (!SPIKE_ELK_HUNT_CODES.has(code)) return;
      if (!templatesByCode.has(code)) templatesByCode.set(code, record);
    });
    if (!templatesByCode.size) return [];

    const boundaryRefs = getRepresentativeBoundaryRecord(existingRecords, deps);
    const derived = [];
    const seen = new Set();
    features.forEach(feature => {
      const attrs = feature?.attributes || {};
      const code = normalizeHuntCode(attrs.HUNT_NUMBER);
      const boundaryId = deps.safe(attrs.BOUNDARYID).trim();
      const template = templatesByCode.get(code);
      if (!template || !boundaryId) return;
      const dedupeKey = `${code}|${boundaryId}`;
      if (seen.has(dedupeKey)) return;
      seen.add(dedupeKey);
      const boundaryRecord = boundaryRefs.get(boundaryId);
      derived.push(buildDerivedSpikeElkRecord(template, boundaryRecord, boundaryId, feature, deps));
    });
    return derived;
  }

  function firstNonEmptyRecordValue(...values) {
    for (const value of values) {
      const text = String(value ?? '').trim();
      if (text) return text;
    }
    return '';
  }

  function classifyBlackBearSupplementalRecord(unitName, seasonText) {
    const haystack = `${String(unitName || '')} ${String(seasonText || '')}`.toLowerCase();
    if (haystack.includes('statewide permit')) {
      return { huntType: 'Statewide', huntCategory: 'Statewide Permit', weapon: 'Any Legal Weapon' };
    }
    if (haystack.includes('pursuit')) {
      return { huntType: 'Pursuit', huntCategory: 'Pursuit', weapon: 'Pursuit Only' };
    }
    if (haystack.includes('harvest objective')) {
      return { huntType: 'Harvest Objective', huntCategory: 'Harvest Objective', weapon: 'Any Legal Weapon' };
    }
    if (haystack.includes('private lands only') || haystack.includes('private land only')) {
      return { huntType: 'Private Land Only', huntCategory: 'Private Land Only', weapon: 'Any Legal Weapon' };
    }
    return { huntType: 'Limited Entry', huntCategory: 'Limited Entry', weapon: 'Any Legal Weapon' };
  }

  function inferBlackBearResidencyLabel(unitName) {
    const lower = String(unitName || '').toLowerCase();
    if (lower.includes('nonresident')) return 'Nonresident';
    if (lower.includes('resident')) return 'Resident';
    return 'Both';
  }

  async function loadSupplementalBlackBearRecords(deps) {
    const {
      OFFICIAL_HUNT_BOUNDARY_TABLE_SOURCES,
      normalizeHuntCode,
      safe
    } = deps;

    const source = (Array.isArray(OFFICIAL_HUNT_BOUNDARY_TABLE_SOURCES) ? OFFICIAL_HUNT_BOUNDARY_TABLE_SOURCES : [])
      .find(path => /black_bear_hunt_table_official\.json$/i.test(String(path || '')));
    if (!source) return [];

    let json;
    try {
      json = await fetchJson(source);
    } catch (error) {
      console.error(`Failed to load supplemental black bear table from ${source}.`, error);
      return [];
    }

    const rows = Array.isArray(json) ? json : (Array.isArray(json?.features) ? json.features : []);
    if (!rows.length) return [];

    const dedupeCodes = new Set();
    const output = [];
    rows.forEach((row) => {
      const attrs = row?.attributes || row || {};
      const huntCode = normalizeHuntCode(attrs.HUNT_NUMBER);
      if (!huntCode || dedupeCodes.has(huntCode)) return;
      dedupeCodes.add(huntCode);

      const unitName = safe(attrs.BOUNDARY_NAME).trim() || `Black Bear Unit ${huntCode}`;
      const season = safe(attrs.SEASON).trim();
      const boundaryIdRaw = safe(attrs.BOUNDARYID).trim();
      const classification = classifyBlackBearSupplementalRecord(unitName, season);
      const residency = inferBlackBearResidencyLabel(unitName);

      output.push(normalizeHuntRecordForPlannerMatrix({
        huntCode,
        code: huntCode,
        title: unitName,
        huntTitle: unitName,
        species: 'Black Bear',
        huntType: classification.huntType,
        huntCategory: classification.huntCategory,
        sex: 'Either Sex',
        weapon: classification.weapon,
        residency,
        unitName,
        boundaryId: boundaryIdRaw || '',
        boundaryID: boundaryIdRaw || '',
        dates: season || 'See current Utah DWR bear guidebook',
        sourceBoundaryName: unitName,
        sourceFile: 'black_bear_hunt_table_official.json',
        sourceType: 'official_supplemental_table',
        boundaryLink: `https://dwrapps.utah.gov/huntboundary/hbstart?HN=${encodeURIComponent(huntCode)}`
      }));
    });

    return output;
  }

  function normalizeHuntRecordForPlannerMatrix(record) {
    if (!record || typeof record !== 'object') return record;
    const normalized = { ...record };
    const huntCode = firstNonEmptyRecordValue(normalized.huntCode, normalized.hunt_code, normalized.HuntCode, normalized.code);
    const huntName = firstNonEmptyRecordValue(normalized.title, normalized.huntTitle, normalized.hunt_name, normalized.HuntName, normalized.name);
    const unitName = firstNonEmptyRecordValue(normalized.unitName, normalized.unit_name, normalized.UnitName, normalized.dwr_unit_name, normalized.DwrUnitName, huntName);
    const unitCode = firstNonEmptyRecordValue(normalized.unitCode, normalized.unit_code, normalized.UnitCode, normalized.boundary_id, normalized.boundaryId, normalized.BoundaryID);
    const boundaryId = firstNonEmptyRecordValue(normalized.boundaryId, normalized.boundaryID, normalized.BoundaryID, normalized.boundary_id, normalized.originalBoundaryId);
    const sex = firstNonEmptyRecordValue(normalized.sex, normalized.sex_type, normalized.sexType, normalized.Sex, normalized.SexType);
    const huntType = firstNonEmptyRecordValue(normalized.huntType, normalized.hunt_type, normalized.HuntType, normalized.type);
    const huntCategory = firstNonEmptyRecordValue(normalized.huntCategory, normalized.hunt_class, normalized.huntClass, normalized.HuntCategory, normalized.category);
    const weapon = firstNonEmptyRecordValue(normalized.weapon, normalized.Weapon);
    const dates = firstNonEmptyRecordValue(normalized.seasonLabel, normalized.season_label, normalized.seasonDates, normalized.season_dates, normalized.dates, normalized.season);
    const permitsTotal = firstNonEmptyRecordValue(normalized.permitsTotal, normalized.permits_total, normalized.permitTotal, normalized.permit_total, normalized.totalPermits, normalized.total_permits, normalized.quota);

    if (huntCode && !normalized.huntCode) normalized.huntCode = huntCode;
    if (huntCode && !normalized.code) normalized.code = huntCode;
    if (huntName && !normalized.title) normalized.title = huntName;
    if (huntName && !normalized.huntTitle) normalized.huntTitle = huntName;
    if (unitName && !normalized.unitName) normalized.unitName = unitName;
    if (unitCode && !normalized.unitCode) normalized.unitCode = unitCode;
    if (boundaryId && !normalized.boundaryId) normalized.boundaryId = boundaryId;
    if (sex && !normalized.sex) normalized.sex = sex;
    if (sex && !normalized.sexType) normalized.sexType = sex;
    if (huntType && !normalized.huntType) normalized.huntType = huntType;
    if (huntType && !normalized.type) normalized.type = huntType;
    if (huntCategory && !normalized.huntCategory) normalized.huntCategory = huntCategory;
    if (huntCategory && !normalized.category) normalized.category = huntCategory;
    if (weapon && !normalized.Weapon) normalized.Weapon = weapon;
    if (dates && !normalized.dates) normalized.dates = dates;
    if (permitsTotal && !normalized.permitsTotal) normalized.permitsTotal = permitsTotal;
    if (permitsTotal && !normalized.totalPermits) normalized.totalPermits = permitsTotal;
    return normalized;
  }

  async function loadHuntDataRecords(deps) {
    const {
      HUNT_DATA_SOURCES,
      getHuntRecordKey,
      updateStatus
    } = deps;

    const merged = [];
    const seenKeys = new Set();
    let authoritativeLoaded = false;
    let loadedPrimaryLabel = '';
    updateStatus('Loading hunt data...');

    for (const source of HUNT_DATA_SOURCES) {
      let sourceLoaded = false;
      for (const candidate of source.candidates) {
        try {
          const json = await fetchJson(candidate);
          const records = Array.isArray(json?.records) ? json.records : (Array.isArray(json) ? json : []);
          if (records.length > 0) {
            let added = 0;
            records.forEach(record => {
              const normalizedRecord = normalizeHuntRecordForPlannerMatrix(record);
              const key = getHuntRecordKey(normalizedRecord);
              if (!seenKeys.has(key)) {
                seenKeys.add(key);
                merged.push(normalizedRecord);
                added += 1;
              }
            });
            console.log(`Successfully loaded ${records.length} hunts for ${source.label} from ${candidate} (${added} added after dedupe)`);
            sourceLoaded = true;
            if (!loadedPrimaryLabel) loadedPrimaryLabel = source.label;
            if (source.authoritative) authoritativeLoaded = true;
            break;
          }
        } catch (error) {
          console.error(`Failed to load ${source.label} from ${candidate}.`, error);
        }
      }
      if (sourceLoaded && source.authoritative) {
        break;
      }
    }

    if (!merged.length) {
      throw new Error('Unable to load any hunt data records.');
    }

    // Backfill boundary IDs by hunt code across merged sources so unit mapping can
    // stay comprehensive even when one source omits boundary assignments.
    const boundaryByHuntCode = new Map();
    merged.forEach(record => {
      const huntCode = firstNonEmptyRecordValue(record?.huntCode, record?.hunt_code, record?.HuntCode, record?.code).toUpperCase();
      const boundaryId = firstNonEmptyRecordValue(record?.boundaryId, record?.boundaryID, record?.BoundaryID, record?.boundary_id, record?.originalBoundaryId);
      if (huntCode && boundaryId && !boundaryByHuntCode.has(huntCode)) {
        boundaryByHuntCode.set(huntCode, boundaryId);
      }
    });
    let boundaryBackfills = 0;
    merged.forEach(record => {
      const existingBoundaryId = firstNonEmptyRecordValue(record?.boundaryId, record?.boundaryID, record?.BoundaryID, record?.boundary_id, record?.originalBoundaryId);
      if (existingBoundaryId) return;
      const huntCode = firstNonEmptyRecordValue(record?.huntCode, record?.hunt_code, record?.HuntCode, record?.code).toUpperCase();
      const backfillBoundaryId = huntCode ? boundaryByHuntCode.get(huntCode) : '';
      if (!backfillBoundaryId) return;
      if (!record.boundaryId) record.boundaryId = backfillBoundaryId;
      if (!record.boundaryID) record.boundaryID = backfillBoundaryId;
      if (!record.BoundaryID) record.BoundaryID = backfillBoundaryId;
      if (!record.boundary_id) record.boundary_id = backfillBoundaryId;
      boundaryBackfills += 1;
    });
    if (boundaryBackfills) {
      console.log(`Backfilled boundaryId for ${boundaryBackfills} hunt rows using merged huntCode matches.`);
    }

    if (!authoritativeLoaded) {
      const derivedSpikeRecords = await loadDerivedSpikeElkRecords(merged, deps);
      if (derivedSpikeRecords.length) {
        let added = 0;
        derivedSpikeRecords.forEach(record => {
          const normalizedRecord = normalizeHuntRecordForPlannerMatrix(record);
          const key = getHuntRecordKey(normalizedRecord);
          if (!seenKeys.has(key)) {
            seenKeys.add(key);
            merged.push(normalizedRecord);
            added += 1;
          }
        });
        console.log(`Derived ${derivedSpikeRecords.length} spike elk records from official elk table (${added} added after dedupe)`);
      }

      await applyOfficialBoundaryMappings(merged, deps);
    } else {
      console.log(`Using authoritative hunt data source: ${loadedPrimaryLabel}`);
    }

    const existingHuntCodes = new Set(
      merged
        .map(record => firstNonEmptyRecordValue(record?.huntCode, record?.hunt_code, record?.HuntCode, record?.code).toUpperCase())
        .filter(Boolean)
    );
    const supplementalBlackBear = await loadSupplementalBlackBearRecords(deps);
    if (supplementalBlackBear.length) {
      let added = 0;
      supplementalBlackBear.forEach(record => {
        const huntCode = firstNonEmptyRecordValue(record?.huntCode, record?.hunt_code, record?.HuntCode, record?.code).toUpperCase();
        if (!huntCode || existingHuntCodes.has(huntCode)) return;
        const key = getHuntRecordKey(record);
        if (seenKeys.has(key)) return;
        seenKeys.add(key);
        existingHuntCodes.add(huntCode);
        merged.push(record);
        added += 1;
      });
      if (added) {
        console.log(`Added ${added} supplemental Black Bear hunt rows from official table for matrix coverage.`);
      }
    }

    return merged;
  }

  async function loadFirstNormalizedList(candidates, normalizer, emptyValue = []) {
    for (const candidate of candidates) {
      try {
        const json = await fetchJson(candidate);
        const normalized = normalizer(json);
        if (normalized.length) return normalized;
      } catch (error) {
        console.error('Failed to load data from', candidate, error);
      }
    }
    return emptyValue;
  }

  return {
    fetchJson,
    fetchGeoJson,
    fetchFirstGeoJson,
    fetchArcGisPagedGeoJson,
    loadOfficialBoundaryLookup,
    applyOfficialBoundaryMappings,
    loadOfficialElkBoundaryFeatures,
    loadDerivedSpikeElkRecords,
    loadHuntDataRecords,
    loadFirstNormalizedList
  };
})();
