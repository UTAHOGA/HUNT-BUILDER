(() => {
  const DATA_URL = "./public/data/hunt-season-calendar-2026.json";
  const monthNames = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
  ];
  const allowedMonths = [];
  for (let month = 0; month < 12; month += 1) allowedMonths.push({ year: 2026, month });
  allowedMonths.push({ year: 2027, month: 0 }, { year: 2027, month: 1 });

  const state = {
    data: null,
    monthIndex: 7,
    selectedDate: "2026-08-01",
    species: "",
    query: "",
  };

  const byId = (id) => document.getElementById(id);
  const esc = (value) => String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");

  function isoDate(year, month, day) {
    return `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
  }

  function formatDate(value) {
    return new Intl.DateTimeFormat("en-US", {
      weekday: "long",
      month: "long",
      day: "numeric",
      year: "numeric",
      timeZone: "America/Denver",
    }).format(new Date(`${value}T12:00:00-06:00`));
  }

  function filteredEvents() {
    if (!state.data) return [];
    const query = state.query.trim().toLowerCase();
    return state.data.events.filter((event) => {
      if (state.species && event.species !== state.species) return false;
      if (!query) return true;
      const hay = [
        event.huntCode,
        event.huntName,
        event.species,
        event.sexType,
        event.weapon,
        event.huntType,
        event.seasonType,
        event.label,
        event.seasonDateText,
      ].join(" ").toLowerCase();
      return hay.includes(query);
    });
  }

  function boundariesForDate(value, events = filteredEvents()) {
    const output = [];
    events.forEach((event) => {
      if (event.start === value) output.push({ kind: "start", event });
      if (event.end === value) output.push({ kind: "end", event });
    });
    return output.sort((a, b) => `${a.kind}-${a.event.species}-${a.event.huntCode}`.localeCompare(`${b.kind}-${b.event.species}-${b.event.huntCode}`));
  }

  function renderDetails() {
    const boundaries = boundariesForDate(state.selectedDate);
    byId("detailTitle").textContent = formatDate(state.selectedDate);
    byId("detailCount").textContent = boundaries.length
      ? `${boundaries.length} published start/end marker${boundaries.length === 1 ? "" : "s"}`
      : "No published hunt starts or ends on this date for the current filters.";
    byId("detailList").innerHTML = boundaries.map(({ kind, event }) => `
      <article class="detail-card ${kind}">
        <strong>${kind === "start" ? "START" : "END"}: ${esc(event.huntCode)} - ${esc(event.huntName)}</strong>
        <span>${esc(event.species)} | ${esc(event.sexType)} | ${esc(event.weapon || event.huntType)}</span>
        <span>${esc(event.label)} | ${esc(event.rangeText)}</span>
        <a href="${esc(event.sourceUrl)}" target="_blank" rel="noopener">Open official Hunt Planner record</a>
      </article>
    `).join("");
  }

  function renderMonth() {
    const { year, month } = allowedMonths[state.monthIndex];
    const events = filteredEvents();
    byId("calendarMonth").value = String(state.monthIndex);
    byId("monthTitle").textContent = `${monthNames[month]} ${year}`;
    const first = new Date(year, month, 1);
    const startDay = first.getDay();
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const previousDays = new Date(year, month, 0).getDate();
    const cells = [];

    for (let index = 0; index < 42; index += 1) {
      let cellYear = year;
      let cellMonth = month;
      let day = index - startDay + 1;
      let outside = false;
      if (day < 1) {
        outside = true;
        cellMonth -= 1;
        if (cellMonth < 0) { cellMonth = 11; cellYear -= 1; }
        day = previousDays + day;
      } else if (day > daysInMonth) {
        outside = true;
        day -= daysInMonth;
        cellMonth += 1;
        if (cellMonth > 11) { cellMonth = 0; cellYear += 1; }
      }
      const value = isoDate(cellYear, cellMonth, day);
      const boundaries = boundariesForDate(value, events);
      const chips = boundaries.slice(0, 3).map(({ kind, event }) =>
        `<span class="boundary-chip ${kind}">${kind === "start" ? "START" : "END"} ${esc(event.huntCode)} ${esc(event.species)}</span>`
      ).join("");
      const more = boundaries.length > 3 ? `<span class="more-events">+${boundaries.length - 3} more</span>` : "";
      cells.push(`
        <button type="button" class="calendar-day${outside ? " outside" : ""}${value === state.selectedDate ? " selected" : ""}" data-date="${value}" aria-label="${esc(formatDate(value))}, ${boundaries.length} hunt boundaries">
          <span class="day-number">${day}</span>${chips}${more}
        </button>
      `);
    }
    byId("monthGrid").innerHTML = cells.join("");
    byId("monthGrid").querySelectorAll("[data-date]").forEach((button) => {
      button.addEventListener("click", () => {
        state.selectedDate = button.dataset.date;
        renderMonth();
        renderDetails();
      });
    });
    renderDetails();
  }

  function changeMonth(nextIndex) {
    state.monthIndex = Math.max(0, Math.min(allowedMonths.length - 1, nextIndex));
    const { year, month } = allowedMonths[state.monthIndex];
    state.selectedDate = isoDate(year, month, 1);
    renderMonth();
  }

  function initializeControls() {
    byId("calendarMonth").innerHTML = allowedMonths.map(({ year, month }, index) =>
      `<option value="${index}">${monthNames[month]} ${year}</option>`
    ).join("");
    byId("calendarMonth").addEventListener("change", (event) => changeMonth(Number(event.target.value)));
    byId("previousMonth").addEventListener("click", () => changeMonth(state.monthIndex - 1));
    byId("nextMonth").addEventListener("click", () => changeMonth(state.monthIndex + 1));
    byId("speciesFilter").addEventListener("change", (event) => {
      state.species = event.target.value;
      renderMonth();
    });
    byId("huntSearch").addEventListener("input", (event) => {
      state.query = event.target.value;
      renderMonth();
    });
    document.querySelectorAll("[data-tab]").forEach((button) => {
      button.addEventListener("click", () => {
        document.querySelectorAll("[data-tab]").forEach((item) => item.classList.toggle("active", item === button));
        const official = button.dataset.tab === "official";
        byId("seasonDatesView").hidden = official;
        byId("officialCalendarView").hidden = !official;
      });
    });
  }

  async function init() {
    initializeControls();
    const response = await fetch(DATA_URL, { cache: "no-store" });
    if (!response.ok) throw new Error(`Calendar data request failed (${response.status})`);
    state.data = await response.json();
    const { meta, speciesCounts } = state.data;
    byId("calendarSummary").textContent = `${meta.huntCodesWithExactDates.toLocaleString()} hunt codes | ${meta.seasonRanges.toLocaleString()} published date ranges | 2026-27 boundaries`;
    byId("sourceStamp").textContent = `DWR snapshot: ${new Date(meta.sourceRetrievedAt).toLocaleDateString()}`;
    byId("speciesFilter").innerHTML += Object.keys(speciesCounts).map((species) =>
      `<option value="${esc(species)}">${esc(species)} (${speciesCounts[species].toLocaleString()})</option>`
    ).join("");
    renderMonth();
  }

  init().catch((error) => {
    byId("calendarSummary").textContent = "The Hunt Planner calendar data could not be loaded.";
    byId("detailList").innerHTML = `<p>${esc(error.message)}</p>`;
  });
})();
