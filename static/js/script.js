const STATION_DETAILS_CSV_LINK = "../static/data-outputs/station_details.csv";
const CATEGORY_DETAILS_CSV_LINK = "../static/data-outputs/category_details.csv";
const ALL_CATEGORIES = "All Categories";
const TILE_LIGHT = "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png";
const TILE_DARK  = "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png";

const graphTypeOptions = [
  {
    name: "Single Category, Single Station Timeline",
    number_of_categories_allow: 1,
    number_of_stations_allow: 1,
    auto_add_categories: false,
    description: "Track one category at one station over time."
  },
  {
    name: "Multiple Categories, Single Station Timeline",
    number_of_categories_allow: "All",
    number_of_stations_allow: 1,
    auto_add_categories: true,
    description: "Compare multiple categories at a single station."
  },
  {
    name: "Single Category Across Multiple Stations Comparison",
    number_of_categories_allow: 1,
    number_of_stations_allow: "All",
    auto_add_categories: false,
    description: "Compare one category across several stations."
  },
  {
    name: "Multiple Categories Across Multiple Stations Comparison",
    number_of_categories_allow: "All",
    number_of_stations_allow: "All",
    auto_add_categories: true,
    description: "Create a broader multi-station and multi-category comparison."
  },
  {
    name: "Year-over-Year Comparison",
    number_of_categories_allow: 1,
    number_of_stations_allow: 1,
    auto_add_categories: false,
    description: "Review how a category changes between years."
  },
  {
    name: "Annual Monthly Totals Overview",
    number_of_categories_allow: 1,
    number_of_stations_allow: 1,
    auto_add_categories: false,
    description: "Inspect monthly totals across a selected year range."
  },
  {
    name: "Flow Duration Curve",
    number_of_categories_allow: 1,
    number_of_stations_allow: 1,
    auto_add_categories: false,
    description: "Show how often values are exceeded over the selected period."
  },
  {
    name: "Monthly Distribution Box Plot",
    number_of_categories_allow: 1,
    number_of_stations_allow: 1,
    auto_add_categories: false,
    description: "Display the statistical spread of values for each month."
  },
  {
    name: "Multi-Station Temporal Heatmap",
    number_of_categories_allow: 1,
    number_of_stations_allow: "All",
    auto_add_categories: false,
    description: "Visualize how values change across stations and over time."
  },
  {
    name: "Correlation Scatter Plot",
    number_of_categories_allow: 2,
    number_of_stations_allow: 1,
    auto_add_categories: false,
    description: "Explore the relationship between exactly two categories at one station."
  },
  {
    name: "Anomaly Detection Chart",
    number_of_categories_allow: 1,
    number_of_stations_allow: 1,
    auto_add_categories: false,
    description: "Highlight statistical outliers and anomalies in the data series."
  },
  {
    name: "Rolling Average Trend",
    number_of_categories_allow: 1,
    number_of_stations_allow: 1,
    auto_add_categories: false,
    description: "Overlay 3-month and 12-month rolling averages on raw data to reveal long-term trends."
  },
  {
    name: "Cumulative Departure from Mean",
    number_of_categories_allow: 1,
    number_of_stations_allow: 1,
    auto_add_categories: false,
    description: "Show cumulative deviation from the long-term mean — identifies sustained wet or dry periods."
  },
  {
    name: "Monthly Climatology",
    number_of_categories_allow: 1,
    number_of_stations_allow: 1,
    auto_add_categories: false,
    description: "Display the average seasonal cycle across all years with standard deviation error bars."
  },
  {
    name: "Decade Comparison",
    number_of_categories_allow: 1,
    number_of_stations_allow: 1,
    auto_add_categories: false,
    description: "Compare value distributions decade by decade to see how conditions have shifted over time."
  },
  {
    name: "Station Ranking Bar Chart",
    number_of_categories_allow: 1,
    number_of_stations_allow: "All",
    auto_add_categories: false,
    description: "Rank multiple stations by their average value for a selected category."
  }
];

// ------------------------------
// COUNTRY COLOURS
// ------------------------------
const COUNTRY_COLORS = {
  'China':    '#c0392b',
  'Lao PDR':  '#d68910',
  'Thailand': '#2874a6',
  'Cambodia': '#e67e22',
  'Viet Nam': '#27ae60',
};
const DEFAULT_MARKER_COLOR = '#6b7fa0';

// ------------------------------
// STATE
// ------------------------------
let map;
let markerClusterGroup = null;
let currentTileLayer = null;
let stationMarkers = [];
let activeCountryFilter = '';
let currentMapMode = 'All Categories';
let stationDetailsMap = {};
let categoryDetailsMap = {};
let stationNameList = [];
let categoryNameList = [];
let selectedCategories = [];
let selectedStationEntries = [];
let selectedVisualizations = [];
let selectedGraphOption = null;
let hasAutoAddCategories = false;
let currentFocusedStation = null;

// ------------------------------
// ELEMENTS
// ------------------------------
const graphOptionsDropdown = document.getElementById("options-select");
const categoryDropdown = document.getElementById("categories-select");
const stationDropdown = document.getElementById("stations-select");

const addCategoryBtn = document.getElementById("add-category-btn");
const addStationBtn = document.getElementById("add-station-btn");
const addToDashboardBtn = document.getElementById("add-to-dashboard-btn");
const startVisualizationBtn = document.getElementById("start-visualization-btn");

const selectedCategoriesContainer = document.querySelector(".selected-categories");
const selectedStationsContainer = document.querySelector(".selected-stations");
const visualizationDetailsContainer = document.getElementById("visualization-details");

const graphContainer = document.getElementById("graph-container");
const categorySelectionDiv = document.getElementById("category-selection-div");
const stationDropdownWrapper = document.getElementById("station-dropdown");

const featuredStationName = document.getElementById("featured-station-name");
const featuredStationCountry = document.getElementById("featured-station-country");
const featuredStationCoords = document.getElementById("featured-station-coords");
const featuredStationCategories = document.getElementById("featured-station-categories");

const statTotalStations = document.getElementById("stat-total-stations");
const statTotalCategories = document.getElementById("stat-total-categories");
const statTotalCountries = document.getElementById("stat-total-countries");
const statDateRange = document.getElementById("stat-date-range");

const selectedGraphPreview = document.getElementById("selected-graph-preview");
const selectedCategoriesPreview = document.getElementById("selected-categories-preview");
const selectedStationsPreview = document.getElementById("selected-stations-preview");

const insightStation = document.getElementById("insight-station");
const insightCategory = document.getElementById("insight-category");
const insightDateRange = document.getElementById("insight-date-range");
const insightMean = document.getElementById("insight-mean");
const insightMin = document.getElementById("insight-min");
const insightMax = document.getElementById("insight-max");

const coverageStation = document.getElementById("coverage-station");
const coverageCategory = document.getElementById("coverage-category");
const coverageFirstYear = document.getElementById("coverage-first-year");
const coverageLastYear = document.getElementById("coverage-last-year");
const coverageRecordCount = document.getElementById("coverage-record-count");
const coverageNote = document.getElementById("coverage-note");
const rankingTableBody = document.getElementById("ranking-table-body");

const oneCategoryOnlyAlert = document.getElementById("one-category-only-alert");
const oneStationOnlyAlert = document.getElementById("one-station-only-alert");
const selectCategoryAndStationAlert = document.getElementById("select-category-and-station-alert");

const fullScreenModal = document.getElementById("fullScreenModal");
const closeModalBtn = document.querySelector(".modal .close");

const overviewSection = document.querySelector(".user-guide");
const stationOverviewSection = document.querySelector(".station-overview");
const builderSection = document.querySelector(".custom-visualization-setup");
const dashboardSection = document.querySelector(".visualization-dashboard");
const aboutSection = document.querySelector(".about-us");
const predictionSection = document.querySelector(".prediction");

// ------------------------------
// HELPERS
// ------------------------------
function showAlert(element) {
  if (!element) return;
  element.style.display = "block";
  setTimeout(() => {
    element.style.display = "none";
  }, 2500);
}

function getPlaceholderOption(label = "Select an option...") {
  const option = document.createElement("option");
  option.value = "";
  option.textContent = label;
  option.disabled = true;
  option.selected = true;
  return option;
}

function formatDateToDDMMYYYY(dateString) {
  if (!dateString || !dateString.includes("-")) return dateString || "--";
  const [year, month, day] = dateString.split("-");
  return `${day}-${month}-${year}`;
}

function formatDateToYYYYMMDD(dateString) {
  if (!dateString || !dateString.includes("-")) return dateString || "";
  const [day, month, year] = dateString.split("-");
  return `${year}-${month}-${day}`;
}

function getSelectedGraphConfig() {
  return graphTypeOptions.find(option => option.name === selectedGraphOption);
}

function setSectionVisible(section) {
  [overviewSection, stationOverviewSection, builderSection, dashboardSection, aboutSection, predictionSection].forEach(sec => {
    if (!sec) return;
    sec.classList.add("hidden");
  });

  if (section) {
    section.classList.remove("hidden");
    section.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

function updateBuilderSummary() {
  selectedGraphPreview.textContent = selectedGraphOption || "No graph selected yet";
  selectedCategoriesPreview.textContent = String(selectedCategories.length);

  const uniqueStations = new Set(selectedStationEntries.map(entry => entry.station_name));
  selectedStationsPreview.textContent = String(uniqueStations.size);
}

function updateInsightAndCoverage(summary) {
  if (!summary) return;

  // KPI cards
  const set = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val ?? "--"; };
  set("kpi-mean",    summary.mean    ?? "--");
  set("kpi-max",     summary.max     ?? "--");
  set("kpi-min",     summary.min     ?? "--");
  set("kpi-std",     summary.std_dev ?? "--");
  set("kpi-records", summary.record_count ?? "--");

  // Stat rows
  insightStation.textContent    = summary.station    ?? "--";
  insightCategory.textContent   = summary.category   ?? "--";
  insightDateRange.textContent  = summary.date_range ?? "--";
  insightMean.textContent       = summary.mean       ?? "--";
  insightMin.textContent        = summary.min        ?? "--";
  insightMax.textContent        = summary.max        ?? "--";
  set("insight-std-row", summary.std_dev ?? "--");

  // Coverage
  coverageStation.textContent     = summary.station      ?? "--";
  coverageCategory.textContent    = summary.category     ?? "--";
  coverageFirstYear.textContent   = summary.first_year   ?? "--";
  coverageLastYear.textContent    = summary.last_year    ?? "--";
  coverageRecordCount.textContent = summary.record_count ?? "--";
  coverageNote.textContent        = summary.coverage_note ?? "--";

  const pct = summary.coverage_pct ?? 0;
  set("coverage-pct-label", pct + "%");
  const fill = document.getElementById("coverage-bar-fill");
  if (fill) fill.style.width = Math.min(pct, 100) + "%";

  // Coefficient of variation
  const covEl = document.getElementById("insight-cov");
  if (covEl) {
    const _m = parseFloat(summary.mean);
    const _s = parseFloat(summary.std_dev);
    if (!isNaN(_m) && !isNaN(_s) && _m !== 0) {
      covEl.textContent = ((_s / _m) * 100).toFixed(1) + "%";
    } else {
      covEl.textContent = "--";
    }
  }

  // Data quality row
  updateDataQualityRow(summary);

  // Trend panel
  const dir   = summary.trend_direction ?? "stable";
  const tPct  = summary.trend_pct ?? 0;
  const arrowSvg  = document.getElementById("trend-arrow-svg");
  const trendWrap = document.getElementById("trend-arrow-wrap");
  set("trend-pct", tPct + "%");

  if (dir === "up") {
    if (arrowSvg)  arrowSvg.innerHTML  = `<line x1="12" y1="19" x2="12" y2="5"/><polyline points="5 12 12 5 19 12"/>`;
    if (trendWrap) trendWrap.className = "trend-arrow-wrap trend-up";
    set("trend-direction-label", "Upward trend");
    set("trend-direction-text",  "Increasing ↑");
    set("trend-change-text",     "+" + tPct + "% vs first half");
    set("trend-interpretation",  "Values rising in recent period");
  } else if (dir === "down") {
    if (arrowSvg)  arrowSvg.innerHTML  = `<line x1="12" y1="5" x2="12" y2="19"/><polyline points="5 12 12 19 19 12"/>`;
    if (trendWrap) trendWrap.className = "trend-arrow-wrap trend-down";
    set("trend-direction-label", "Downward trend");
    set("trend-direction-text",  "Decreasing ↓");
    set("trend-change-text",     "-" + tPct + "% vs first half");
    set("trend-interpretation",  "Values declining in recent period");
  } else {
    if (arrowSvg)  arrowSvg.innerHTML  = `<line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/>`;
    if (trendWrap) trendWrap.className = "trend-arrow-wrap trend-stable";
    set("trend-direction-label", "Stable");
    set("trend-direction-text",  "Stable →");
    set("trend-change-text",     tPct + "% variation");
    set("trend-interpretation",  "No significant trend detected");
  }
}

function generateKeyFindings(summary, ranking) {
  const items = [];
  if (!summary) return null;

  // Trend finding
  const dir  = summary.trend_direction || "stable";
  const tPct = summary.trend_pct || 0;
  if (dir === "up") {
    items.push(`Values at <strong>${summary.station}</strong> show an <strong>upward trend of +${tPct}%</strong> when comparing the first and second halves of the study period — conditions are worsening/intensifying over time.`);
  } else if (dir === "down") {
    items.push(`Values at <strong>${summary.station}</strong> show a <strong>downward trend of −${tPct}%</strong> when comparing the first and second halves of the study period — conditions are reducing over time.`);
  } else {
    items.push(`Values at <strong>${summary.station}</strong> remain <strong>relatively stable</strong> across the study period — less than 1% change detected between the first and second half.`);
  }

  // Coverage finding
  const cov = summary.coverage_pct || 0;
  if (cov >= 80) {
    items.push(`Data coverage is <strong>high at ${cov}%</strong> — the record is dense and reliable with minimal gaps. Results can be interpreted with confidence.`);
  } else if (cov >= 50) {
    items.push(`Data coverage is <strong>moderate at ${cov}%</strong>. Some gaps exist in the record — trends are indicative but should be interpreted with some caution.`);
  } else {
    items.push(`Data coverage is <strong>low at ${cov}%</strong>. Significant gaps are present in the record — interpret findings with caution and avoid strong conclusions.`);
  }

  // Variability finding using CV
  const _fMean = parseFloat(summary.mean);
  const _fStd  = parseFloat(summary.std_dev);
  if (!isNaN(_fMean) && !isNaN(_fStd) && _fMean !== 0) {
    const cvPct = ((_fStd / _fMean) * 100).toFixed(1);
    if (cvPct > 50) {
      items.push(`<strong>High variability detected</strong> — coefficient of variation is <strong>${cvPct}%</strong>, suggesting irregular seasonal patterns or the presence of extreme events in the record.`);
    } else if (cvPct > 20) {
      items.push(`<strong>Moderate variability</strong> — coefficient of variation is <strong>${cvPct}%</strong>, consistent with typical seasonal hydrological fluctuations across the basin.`);
    } else {
      items.push(`<strong>Low variability</strong> — coefficient of variation is <strong>${cvPct}%</strong>, indicating stable and relatively consistent conditions throughout the study period.`);
    }
  }

  // Ranking finding
  if (ranking && ranking.length > 1) {
    const top    = ranking[0];
    const bottom = ranking[ranking.length - 1];
    items.push(`Station <strong>${top.station}</strong> ranks highest with a mean of <strong>${top.average_value}</strong> (${top.record_count} records). Station <strong>${bottom.station}</strong> records the lowest average at <strong>${bottom.average_value}</strong>.`);
  } else if (ranking && ranking.length === 1) {
    items.push(`Only one station is ranked — <strong>${ranking[0].station}</strong> with an average of <strong>${ranking[0].average_value}</strong> across ${ranking[0].record_count} records. Add more stations to compare.`);
  }

  return items;
}

function updateDataQualityRow(summary) {
  if (!summary) return;

  // Coverage quality
  const pct    = summary.coverage_pct || 0;
  const covVal = document.getElementById("dq-coverage-val");
  const covSub = document.getElementById("dq-coverage-sub");
  const covDot = document.getElementById("dq-coverage-dot");
  if (covVal) covVal.textContent = pct + "%";
  if (pct >= 80) {
    if (covSub) covSub.textContent = "Excellent — high data density";
    if (covDot) covDot.className = "dq-dot dq-good";
  } else if (pct >= 50) {
    if (covSub) covSub.textContent = "Moderate — some gaps present";
    if (covDot) covDot.className = "dq-dot dq-fair";
  } else {
    if (covSub) covSub.textContent = "Sparse — interpret with caution";
    if (covDot) covDot.className = "dq-dot dq-poor";
  }

  // Trend signal
  const tPct    = summary.trend_pct || 0;
  const dir     = summary.trend_direction || "stable";
  const trendVal = document.getElementById("dq-trend-val");
  const trendSub = document.getElementById("dq-trend-sub");
  const trendDot = document.getElementById("dq-trend-dot");
  const sign = dir === "up" ? "+" : dir === "down" ? "−" : "";
  if (trendVal) trendVal.textContent = sign + tPct + "%";
  if (tPct > 20) {
    if (trendSub) trendSub.textContent = "Strong " + (dir === "up" ? "upward" : dir === "down" ? "downward" : "stable") + " signal";
    if (trendDot) trendDot.className = dir === "stable" ? "dq-dot dq-fair" : "dq-dot dq-good";
  } else if (tPct > 5) {
    if (trendSub) trendSub.textContent = "Moderate signal detected";
    if (trendDot) trendDot.className = "dq-dot dq-fair";
  } else {
    if (trendSub) trendSub.textContent = "Weak or no trend";
    if (trendDot) trendDot.className = "dq-dot dq-neutral";
  }

  // Variability (CV)
  const varVal = document.getElementById("dq-variability-val");
  const varSub = document.getElementById("dq-variability-sub");
  const varDot = document.getElementById("dq-variability-dot");
  const meanNum = parseFloat(summary.mean);
  const stdNum  = parseFloat(summary.std_dev);
  if (!isNaN(meanNum) && !isNaN(stdNum) && meanNum !== 0) {
    const cvPct = ((stdNum / meanNum) * 100).toFixed(1);
    if (varVal) varVal.textContent = "CV " + cvPct + "%";
    if (parseFloat(cvPct) > 50) {
      if (varSub) varSub.textContent = "High — irregular patterns";
      if (varDot) varDot.className = "dq-dot dq-poor";
    } else if (parseFloat(cvPct) > 20) {
      if (varSub) varSub.textContent = "Moderate — seasonal variation";
      if (varDot) varDot.className = "dq-dot dq-fair";
    } else {
      if (varSub) varSub.textContent = "Low — stable conditions";
      if (varDot) varDot.className = "dq-dot dq-good";
    }
  }

  // Study period / time span
  const spanVal = document.getElementById("dq-span-val");
  const spanSub = document.getElementById("dq-span-sub");
  const spanDot = document.getElementById("dq-span-dot");
  const fyNum = parseInt(summary.first_year);
  const lyNum = parseInt(summary.last_year);
  if (!isNaN(fyNum) && !isNaN(lyNum)) {
    const span = lyNum - fyNum;
    if (spanVal) spanVal.textContent = span + (span === 1 ? " year" : " years");
    if (spanSub) spanSub.textContent = summary.first_year + " – " + summary.last_year;
    if (spanDot) spanDot.className = span >= 10 ? "dq-dot dq-good" : span >= 5 ? "dq-dot dq-fair" : "dq-dot dq-poor";
  }
}

function updateRankingTable(ranking) {
  if (!rankingTableBody) return;

  rankingTableBody.innerHTML = "";

  if (!ranking || !ranking.length) {
    rankingTableBody.innerHTML = `
      <tr>
        <td colspan="5">No ranking data available.</td>
      </tr>
    `;
    return;
  }

  const maxAvg = Math.max(...ranking.map(r => r.average_value));

  ranking.forEach((row, index) => {
    const pct = maxAvg > 0 ? ((row.average_value / maxAvg) * 100).toFixed(1) : 0;
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><span class="rank-badge">${index + 1}</span></td>
      <td>${row.station}</td>
      <td>
        <div class="ranking-bar-cell">
          <div class="ranking-bar-fill" style="width:${pct}%"></div>
          <span class="ranking-bar-value">${row.average_value}</span>
        </div>
      </td>
      <td>${row.maximum_value}</td>
      <td>${row.record_count}</td>
    `;
    rankingTableBody.appendChild(tr);
  });
}

function resetSelectedCategoriesAndStations() {
  selectedCategories = [];
  selectedStationEntries = [];
  selectedCategoriesContainer.innerHTML = "";
  selectedStationsContainer.innerHTML = "";
  updateBuilderSummary();
}

function resetVisualizationSetup() {
  resetSelectedCategoriesAndStations();
  selectedGraphOption = null;
  hasAutoAddCategories = false;

  graphOptionsDropdown.selectedIndex = 0;
  categoryDropdown.innerHTML = "";
  stationDropdown.innerHTML = "";

  showCategoryOptionsOnUI();
  showStationOptionsOnUI(ALL_CATEGORIES);

  categoryDropdown.disabled = true;
  stationDropdown.disabled = true;
  categorySelectionDiv.style.display = "block";

  updateBuilderSummary();
}

function getAllCountries() {
  return [...new Set(Object.values(stationDetailsMap).map(station => station.country).filter(Boolean))];
}

function getCoverageRange() {
  const allDates = [];

  Object.values(categoryDetailsMap).forEach(categoryRows => {
    categoryRows.forEach(row => {
      if (row.start_date) allDates.push(row.start_date);
      if (row.end_date) allDates.push(row.end_date);
    });
  });

  if (!allDates.length) return "--";

  const sorted = [...allDates].sort();
  const firstYear = sorted[0]?.slice(0, 4) || "--";
  const lastYear = sorted[sorted.length - 1]?.slice(0, 4) || "--";
  return `${firstYear} - ${lastYear}`;
}

function updateOverviewStats() {
  statTotalStations.textContent = stationNameList.length || "--";
  statTotalCategories.textContent = categoryNameList.length || "--";
  statTotalCountries.textContent = getAllCountries().length || "--";
  statDateRange.textContent = getCoverageRange();

  // Sync about-page highlight stats
  const aboutStations   = document.getElementById("about-stat-stations");
  const aboutCategories = document.getElementById("about-stat-categories");
  if (aboutStations)   aboutStations.textContent   = stationNameList.length  || "--";
  if (aboutCategories) aboutCategories.textContent = categoryNameList.length || "--";
}

function updateFeaturedStationPanel(stationName) {
  const station = stationDetailsMap[stationName];
  if (!station) return;

  currentFocusedStation = stationName;
  featuredStationName.textContent = station.station_name || "--";
  featuredStationCountry.textContent = station.country || "--";
  featuredStationCoords.textContent = `${station.latitude}, ${station.longitude}`;
  featuredStationCategories.textContent = station.available_categories || "--";
}

function getCategoryDateRange(categoryName, stationName) {
  const rows = categoryDetailsMap[categoryName] || [];

  const cleanCategory = (categoryName || "").trim();
  const cleanStation = (stationName || "").trim();

  return (
    rows.find(
      row =>
        (row.category_name || "").trim() === cleanCategory &&
        (row.station_name || "").trim() === cleanStation
    ) || null
  );
}

function addAllCategoriesForStation(stationName) {
  const available = [];

  Object.keys(categoryDetailsMap).forEach(categoryName => {
    const hasStation = categoryDetailsMap[categoryName].some(row => row.station_name === stationName);
    if (hasStation) available.push(categoryName);
  });

  selectedCategories = available;
  renderSelectedCategories();
}

function renderSelectedCategories() {
  selectedCategoriesContainer.innerHTML = "";

  selectedCategories.forEach(category => {
    const item = document.createElement("div");
    item.className = "selected-category-element";

    const label = document.createElement("span");
    label.textContent = category;

    const removeBtn = document.createElement("button");
    removeBtn.textContent = "×";
    removeBtn.type = "button";
    removeBtn.style.marginLeft = "8px";
    removeBtn.style.background = "transparent";
    removeBtn.style.color = "inherit";
    removeBtn.style.fontWeight = "700";

    removeBtn.addEventListener("click", () => {
      selectedCategories = selectedCategories.filter(c => c !== category);

      selectedStationEntries = selectedStationEntries.filter(entry => entry.category_name !== category);
      renderSelectedCategories();
      renderSelectedStations();

      if (selectedCategories.length === 0 && !hasAutoAddCategories) {
        stationDropdown.disabled = true;
        showStationOptionsOnUI(ALL_CATEGORIES);
        showStationsOnMapUI(ALL_CATEGORIES);
      } else {
        showStationOptionsOnUI("Current Categories Selected");
        showStationsOnMapUI("Current Categories Selected");
      }

      updateBuilderSummary();
    });

    item.appendChild(label);
    item.appendChild(removeBtn);
    selectedCategoriesContainer.appendChild(item);
  });

  updateBuilderSummary();
}

function renderSelectedStations() {
  selectedStationsContainer.innerHTML = "";

  selectedStationEntries.forEach((entry, index) => {
    const item = document.createElement("div");
    item.className = "selected-station-element";
    item.style.display = "flex";
    item.style.justifyContent = "space-between";
    item.style.alignItems = "center";
    item.style.width = "100%";
    item.style.borderRadius = "12px";
    item.style.padding = "12px 14px";

    const textWrap = document.createElement("div");

    const line1 = document.createElement("p");
    line1.className = "station-name";
    line1.style.marginBottom = "6px";
    line1.innerHTML = `<strong>${entry.station_name}</strong> - ${entry.category_name}`;

    const line2 = document.createElement("p");
    line2.className = "station-date";
    line2.style.margin = "0";
    line2.textContent = `${entry.start_date} -> ${entry.end_date}`;

    textWrap.appendChild(line1);
    textWrap.appendChild(line2);

    const actions = document.createElement("div");
    actions.style.display = "flex";
    actions.style.gap = "8px";

    const editBtn = document.createElement("button");
    editBtn.type = "button";
    editBtn.textContent = "Edit dates";
    editBtn.className = "secondary-btn";
    editBtn.style.padding = "8px 10px";

    editBtn.addEventListener("click", () => {
      const newStart = prompt("Enter new start date (DD-MM-YYYY):", entry.start_date);
      const newEnd = prompt("Enter new end date (DD-MM-YYYY):", entry.end_date);

      if (newStart && newEnd) {
        selectedStationEntries[index].start_date = newStart;
        selectedStationEntries[index].end_date = newEnd;
        renderSelectedStations();
      }
    });

    const deleteBtn = document.createElement("button");
    deleteBtn.type = "button";
    deleteBtn.textContent = "Remove";
    deleteBtn.className = "secondary-btn";
    deleteBtn.style.padding = "8px 10px";

    deleteBtn.addEventListener("click", () => {
      selectedStationEntries.splice(index, 1);
      renderSelectedStations();
      updateBuilderSummary();
    });

    actions.appendChild(editBtn);
    actions.appendChild(deleteBtn);

    item.appendChild(textWrap);
    item.appendChild(actions);
    selectedStationsContainer.appendChild(item);
  });

  updateBuilderSummary();
}

function showGraphOptionsOnUI() {
  graphOptionsDropdown.innerHTML = "";
  graphOptionsDropdown.appendChild(getPlaceholderOption("Select a visualization type"));

  graphTypeOptions.forEach(optionType => {
    const option = document.createElement("option");
    option.textContent = optionType.name;
    option.value = optionType.name;
    graphOptionsDropdown.appendChild(option);
  });
}

function showCategoryOptionsOnUI() {
  categoryDropdown.innerHTML = "";
  categoryDropdown.appendChild(getPlaceholderOption("Select a category"));

  categoryNameList.forEach(categoryName => {
    const option = document.createElement("option");
    option.textContent = categoryName;
    option.value = categoryName;
    categoryDropdown.appendChild(option);
  });
}

function showStationOptionsOnUI(mode) {
  stationDropdown.innerHTML = "";
  stationDropdown.appendChild(getPlaceholderOption("Select a station"));

  const addedStations = new Set();

  if (mode === ALL_CATEGORIES) {
    Object.values(categoryDetailsMap).forEach(categoryRows => {
      categoryRows.forEach(row => {
        if (!addedStations.has(row.station_name)) {
          const option = document.createElement("option");
          option.textContent = row.station_name;
          option.value = row.station_name;
          stationDropdown.appendChild(option);
          addedStations.add(row.station_name);
        }
      });
    });
    return;
  }

  if (mode === "Current Categories Selected") {
    selectedCategories.forEach(categoryName => {
      (categoryDetailsMap[categoryName] || []).forEach(row => {
        if (!addedStations.has(row.station_name)) {
          const option = document.createElement("option");
          option.textContent = row.station_name;
          option.value = row.station_name;
          stationDropdown.appendChild(option);
          addedStations.add(row.station_name);
        }
      });
    });
  }
}

function updateVisualizationQueueUI() {
  visualizationDetailsContainer.innerHTML = "";

  if (!selectedVisualizations.length) {
    const empty = document.createElement("div");
    empty.className = "summary-box";
    empty.innerHTML = `
      <p class="card-label">Saved visualizations</p>
      <p>No configurations saved yet.</p>
    `;
    visualizationDetailsContainer.appendChild(empty);
    return;
  }

  const title = document.createElement("p");
  title.className = "menu-title";
  title.textContent = "Queued Visualizations for Dashboard";
  visualizationDetailsContainer.appendChild(title);

  selectedVisualizations.forEach((visualization, index) => {
    const wrapper = document.createElement("div");
    wrapper.className = "summary-box";
    wrapper.style.width = "100%";
    wrapper.style.borderRadius = "12px";
    wrapper.style.marginBottom = "12px";

    const header = document.createElement("div");
    header.style.display = "flex";
    header.style.justifyContent = "space-between";
    header.style.alignItems = "center";
    header.style.gap = "12px";
    header.style.marginBottom = "10px";

    const heading = document.createElement("h4");
    heading.style.margin = "0";
    heading.textContent = visualization.graph_type;

    const btnGroup = document.createElement("div");
    btnGroup.style.display = "flex";
    btnGroup.style.gap = "8px";
    btnGroup.style.flexShrink = "0";

    const editBtn = document.createElement("button");
    editBtn.type = "button";
    editBtn.className = "queue-edit-btn";
    editBtn.innerHTML = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg> Edit`;

    editBtn.addEventListener("click", () => {
      loadVisualizationIntoBuilder(visualization, index);
    });

    const removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.className = "queue-delete-btn";
    removeBtn.innerHTML = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/></svg> Delete`;

    removeBtn.addEventListener("click", () => {
      selectedVisualizations.splice(index, 1);
      updateVisualizationQueueUI();
    });

    btnGroup.appendChild(editBtn);
    btnGroup.appendChild(removeBtn);
    header.appendChild(heading);
    header.appendChild(btnGroup);
    wrapper.appendChild(header);

    visualization.data.forEach(detail => {
      const detailP = document.createElement("p");
      detailP.style.marginBottom = "8px";
      detailP.textContent = `${detail.station_name} - ${detail.category_name} (${detail.start_date} -> ${detail.end_date})`;
      wrapper.appendChild(detailP);
    });

    visualizationDetailsContainer.appendChild(wrapper);
  });
}

function loadVisualizationIntoBuilder(visualization, index) {
  // Remove from queue so it can be re-saved after editing
  selectedVisualizations.splice(index, 1);
  updateVisualizationQueueUI();

  // Restore graph type
  selectedGraphOption = visualization.graph_type;
  for (const option of graphOptionsDropdown.options) {
    if (option.value === visualization.graph_type) {
      option.selected = true;
      break;
    }
  }

  // Restore categories and station entries
  selectedCategories    = [...new Set(visualization.data.map(d => d.category_name))];
  selectedStationEntries = visualization.data.map(d => ({ ...d }));

  // Sync auto-add setting and category row visibility
  const graphConfig = getSelectedGraphConfig();
  hasAutoAddCategories = graphConfig ? graphConfig.auto_add_categories : false;
  categorySelectionDiv.style.display = hasAutoAddCategories ? "none" : "block";
  stationDropdown.disabled = false;
  categoryDropdown.disabled = hasAutoAddCategories;

  renderSelectedCategories();
  renderSelectedStations();
  updateBuilderSummary();

  setSectionVisible(builderSection);
  setActiveNav(".custom-visualization-setup-icon");
}

function buildVisualizationFromCurrentSelections() {
  return {
    graph_type: selectedGraphOption,
    data: selectedStationEntries.map(entry => ({
      category_name: entry.category_name,
      station_name: entry.station_name,
      start_date: entry.start_date,
      end_date: entry.end_date
    }))
  };
}

function renderCharts(charts) {
  graphContainer.innerHTML = "";

  const badge = document.getElementById("charts-badge");
  const countEl = document.getElementById("charts-count");
  if (badge && countEl) {
    if (charts && charts.length) {
      countEl.textContent = charts.length;
      badge.classList.remove("hidden");
    } else {
      badge.classList.add("hidden");
    }
  }

  if (!charts || !charts.length) {
    graphContainer.innerHTML = `<p>No charts were returned for this configuration.</p>`;
    return;
  }

  charts.forEach((chartJson, index) => {
    const card = document.createElement("div");
    card.className = "info-panel";
    card.style.width = "100%";
    card.style.marginBottom = "24px";
    card.style.background = "#ffffff";
    card.style.display = "block";
    card.style.padding = "20px";
    card.style.overflowX = "auto";

    const header = document.createElement("div");
    header.style.display = "flex";
    header.style.justifyContent = "space-between";
    header.style.alignItems = "center";
    header.style.marginBottom = "12px";
    header.style.gap = "12px";

    const title = document.createElement("h3");
    title.style.margin = "0";
    title.textContent = `Visualization ${index + 1}`;

    const actions = document.createElement("div");
    actions.style.display = "flex";
    actions.style.gap = "8px";

    const fullBtn = document.createElement("button");
    fullBtn.type = "button";
    fullBtn.className = "secondary-btn";
    fullBtn.textContent = "Open detailed view";
    fullBtn.addEventListener("click", () => {
      showLargeGraph(chartJson);
    });

    const deleteBtn = document.createElement("button");
    deleteBtn.type = "button";
    deleteBtn.className = "chart-delete-btn";
    deleteBtn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4h6v2"/></svg> Delete`;
    deleteBtn.addEventListener("click", () => {
      const cardTitle = title.textContent;
      const nextSibling = card.nextElementSibling;
      card.remove();
      renumberChartCards();
      showUndoToast(cardTitle, card, nextSibling);
    });

    actions.appendChild(fullBtn);
    actions.appendChild(deleteBtn);
    header.appendChild(title);
    header.appendChild(actions);
    title.className = "chart-card-title";

    const graphDiv = document.createElement("div");
    graphDiv.id = `graph-${index}`;
    graphDiv.style.width = "100%";
    graphDiv.style.minWidth = "1000px";
    graphDiv.style.height = "540px";

    card.appendChild(header);
    card.appendChild(graphDiv);
    card.style.display = "block";
    graphContainer.appendChild(card);

    Plotly.newPlot(graphDiv.id, JSON.parse(chartJson), {}, { responsive: true });
  });
}

function renumberChartCards() {
  graphContainer.querySelectorAll(".chart-card-title").forEach((t, i) => {
    t.textContent = `Visualization ${i + 1}`;
  });
}

let _lastDeleted = null;
let _undoTimer   = null;

function showUndoToast(label, card, nextSibling) {
  _lastDeleted = { card, nextSibling };

  const toast    = document.getElementById("undo-toast");
  const textEl   = document.getElementById("undo-toast-text");
  const fill     = document.getElementById("undo-progress-fill");
  if (!toast) return;

  if (textEl) textEl.textContent = `"${label}" deleted`;

  // Restart progress bar animation
  if (fill) { fill.style.animation = "none"; fill.offsetHeight; fill.style.animation = ""; }

  clearTimeout(_undoTimer);
  toast.classList.remove("hidden");

  _undoTimer = setTimeout(() => {
    toast.classList.add("hidden");
    if (_lastDeleted) {
      const gd = _lastDeleted.card.querySelector('[id^="graph-"]');
      if (gd) Plotly.purge(gd.id);
      _lastDeleted = null;
    }
  }, 10000);
}

function setupUndoToast() {
  document.getElementById("undo-restore-btn")?.addEventListener("click", () => {
    if (!_lastDeleted) return;
    clearTimeout(_undoTimer);
    document.getElementById("undo-toast")?.classList.add("hidden");

    const { card, nextSibling } = _lastDeleted;
    if (nextSibling && nextSibling.parentNode === graphContainer) {
      graphContainer.insertBefore(card, nextSibling);
    } else {
      graphContainer.appendChild(card);
    }
    renumberChartCards();
    window.dispatchEvent(new Event("resize")); // re-fit Plotly charts
    _lastDeleted = null;
  });
}

function showLargeGraph(chartJson) {
  fullScreenModal.style.display = "block";
  Plotly.newPlot("fullScreenGraph", JSON.parse(chartJson), {}, { responsive: true });
}

function triggerStartVisualization() {
  if (!selectedVisualizations.length) {
    alert("Please save at least one visualization configuration first.");
    return;
  }

  setSectionVisible(dashboardSection);
  graphContainer.innerHTML = "";

  fetch("/generate_visualization", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(selectedVisualizations)
  })
    .then(response => response.json())
    .then(data => {
  const charts  = data.charts  || [];
  const summary = data.summary || null;
  const ranking = data.ranking || [];

  renderCharts(charts);
  updateInsightAndCoverage(summary);
  updateRankingTable(ranking);

  // Key findings (needs both summary + ranking)
  const findingsList = document.getElementById("findings-list");
  if (findingsList) {
    const findings = generateKeyFindings(summary, ranking);
    if (findings && findings.length) {
      findingsList.innerHTML = findings.map(f => `<li class="finding-item">${f}</li>`).join("");
    } else {
      findingsList.innerHTML = `<li class="finding-placeholder">No findings could be generated for this selection.</li>`;
    }
  }
})
    .catch(error => {
      console.error("Error generating visualizations:", error);
      graphContainer.innerHTML = `<p>There was an error generating the visualization.</p>`;
    });
}

// ------------------------------
// CSV LOADERS
// ------------------------------
function loadCSVStationDetails() {
  return new Promise((resolve, reject) => {
    Papa.parse(STATION_DETAILS_CSV_LINK, {
      download: true,
      header: true,
      complete: function(results) {
        stationDetailsMap = {};
        stationNameList = [];

        results.data
          .filter(row => row.Station_Name && row.Station_Code && row.Country && row.Latitude && row.Longitude)
          .forEach(row => {
            stationDetailsMap[row.Station_Name] = {
              station_name: row.Station_Name,
              station_code: row.Station_Code,
              country: row.Country,
              latitude: parseFloat(row.Latitude),
              longitude: parseFloat(row.Longitude),
              available_categories: row.Available_Categories
            };

            if (!stationNameList.includes(row.Station_Name)) {
              stationNameList.push(row.Station_Name);
            }
          });

        resolve();
      },
      error: reject
    });
  });
}

function loadCSVCategoryDetails() {
  return new Promise((resolve, reject) => {
    Papa.parse(CATEGORY_DETAILS_CSV_LINK, {
      download: true,
      header: true,
      complete: function(results) {
        categoryDetailsMap = {};
        categoryNameList = [];

        results.data
          .filter(row => row.Category_Name && row.Station_Name && row.Start_Date && row.End_Date)
          .forEach(row => {
            if (!categoryDetailsMap[row.Category_Name]) {
              categoryDetailsMap[row.Category_Name] = [];
            }

            categoryDetailsMap[row.Category_Name].push({
              category_name: row.Category_Name,
              station_name: row.Station_Name,
              start_date: row.Start_Date,
              end_date: row.End_Date
            });

            if (!categoryNameList.includes(row.Category_Name)) {
              categoryNameList.push(row.Category_Name);
            }
          });

        resolve();
      },
      error: reject
    });
  });
}

// ------------------------------
// MAP HELPERS
// ------------------------------
function getCountryColor(country) {
  return COUNTRY_COLORS[country] || DEFAULT_MARKER_COLOR;
}

function createStationIcon(country) {
  const color = getCountryColor(country);
  return L.divIcon({
    className: '',
    html: `
      <div class="marker-wrap">
        <div class="marker-glow" style="background:${color};"></div>
        <div class="marker-core" style="background:${color};"></div>
      </div>`,
    iconSize: [30, 30],
    iconAnchor: [15, 15],
    popupAnchor: [0, -17]
  });
}

function buildMapLegend() {
  const legend = document.getElementById('map-legend');
  const filterSelect = document.getElementById('map-country-filter');
  if (!legend) return;

  const entries = Object.entries(COUNTRY_COLORS);

  // Count stations per country
  const countByCountry = {};
  Object.values(stationDetailsMap).forEach(s => {
    countByCountry[s.country] = (countByCountry[s.country] || 0) + 1;
  });

  legend.innerHTML = `
    <h4>Countries</h4>
    ${entries.map(([country, color]) => `
      <div class="legend-item">
        <div class="legend-dot" style="background:${color}"></div>
        <span>${country}</span>
        <span class="legend-count">${countByCountry[country] || 0}</span>
      </div>
    `).join('')}
  `;

  if (filterSelect) {
    entries.forEach(([country]) => {
      const opt = document.createElement('option');
      opt.value = country;
      opt.textContent = country;
      filterSelect.appendChild(opt);
    });
  }
}

function fitMapToStations() {
  if (!map || !stationMarkers.length) return;
  const latlngs = stationMarkers.map(m => m.getLatLng());
  map.fitBounds(L.latLngBounds(latlngs), { padding: [50, 50], maxZoom: 10 });
}

// ------------------------------
// MAP
// ------------------------------
function showStationsOnMapUI(mode) {
  if (!map || !markerClusterGroup) return;

  currentMapMode = mode;
  markerClusterGroup.clearLayers();
  stationMarkers = [];

  const addedStations = new Set();

  const addMarkerForStation = (stationName) => {
    const station = stationDetailsMap[stationName];
    if (!station || isNaN(station.latitude) || isNaN(station.longitude)) return;
    if (addedStations.has(stationName)) return;
    if (activeCountryFilter && station.country !== activeCountryFilter) return;

    const color = getCountryColor(station.country);
    const cats = (station.available_categories || '').split(', ').filter(Boolean);
    const badges = cats.map(c =>
      `<span style="display:inline-block;padding:3px 9px;background:${color}1a;border:1px solid ${color}55;border-radius:999px;font-size:0.75rem;font-weight:600;margin:2px 2px 0 0;color:${color};">${c}</span>`
    ).join('');

    const popupHtml = `
      <div class="map-popup">
        <div class="map-popup-header" style="background:${color};">
          <strong>${station.station_name}</strong>
          <span>${station.country}</span>
        </div>
        <div class="map-popup-body">
          <p><strong>Coordinates:</strong> ${station.latitude.toFixed(4)}, ${station.longitude.toFixed(4)}</p>
          <p style="margin-bottom:4px;"><strong>Categories:</strong></p>
          <div style="margin-top:2px;">${badges || '--'}</div>
        </div>
        <div class="map-popup-footer">
          <button class="map-popup-btn" onclick="window.focusStationFromMap('${station.station_name.replace(/'/g, "\\'")}')">
            View station details
          </button>
        </div>
      </div>
    `;

    const icon = createStationIcon(station.country);
    const marker = L.marker([station.latitude, station.longitude], { icon })
      .bindPopup(popupHtml, { maxWidth: 280 })
      .bindTooltip(station.station_name, {
        permanent: false,
        direction: 'top',
        offset: [0, -12],
        className: 'station-tooltip'
      });

    marker.on("click", () => {
      updateFeaturedStationPanel(station.station_name);
    });

    markerClusterGroup.addLayer(marker);
    stationMarkers.push(marker);
    addedStations.add(stationName);
  };

  if (mode === ALL_CATEGORIES) {
    Object.values(categoryDetailsMap).forEach(rows => {
      rows.forEach(row => addMarkerForStation(row.station_name));
    });
    return;
  }

  if (mode === "Current Categories Selected") {
    selectedCategories.forEach(categoryName => {
      (categoryDetailsMap[categoryName] || []).forEach(row => addMarkerForStation(row.station_name));
    });
  }
}

window.focusStationFromMap = function(stationName) {
  updateFeaturedStationPanel(stationName);
  setSectionVisible(stationOverviewSection);
};

function initializeMap() {
  map = L.map("map", {
    minZoom: 4,
    maxZoom: 18,
    zoomControl: false
  }).setView([15.87, 100.99], 5);

  L.control.zoom({ position: 'bottomright' }).addTo(map);

  const bounds = L.latLngBounds(L.latLng(-10, 40), L.latLng(50, 155));
  map.setMaxBounds(bounds);
  map.on("drag", function() {
    map.panInsideBounds(bounds, { animate: false });
  });

  const initDark = localStorage.getItem('theme') === 'dark';
  currentTileLayer = L.tileLayer(initDark ? TILE_DARK : TILE_LIGHT, {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/">CARTO</a>',
    subdomains: "abcd",
    maxZoom: 18
  }).addTo(map);

  // Plain layer group — no clustering, all stations visible at once
  markerClusterGroup = L.layerGroup();
  map.addLayer(markerClusterGroup);

  // GeoJSON basin overlay
  fetch("/mekong_geojson")
    .then(response => response.json())
    .then(data => {
      L.geoJSON(data, {
        style: {
          color: "#5ba3d4",
          weight: 2,
          fillColor: "#1a4f7a",
          fillOpacity: 0.18,
          lineCap: "round",
          lineJoin: "round"
        },
        onEachFeature: function(feature, layer) {
          if (feature.properties && feature.properties.name) {
            layer.bindTooltip(feature.properties.name, { sticky: true });
          }
        }
      }).addTo(map);
    })
    .catch(error => console.error("Error loading GeoJSON:", error));

  // Build legend and populate country filter
  buildMapLegend();

  // Wire controls
  document.getElementById("map-fit-btn")?.addEventListener("click", fitMapToStations);

  document.getElementById("map-country-filter")?.addEventListener("change", function() {
    activeCountryFilter = this.value;
    showStationsOnMapUI(currentMapMode);
  });
}

// ------------------------------
// EVENTS
// ------------------------------
function setActiveNav(selector) {
  document.querySelectorAll('.sidebar-nav .nav-item').forEach(el => el.classList.remove('active'));
  const navEl = document.querySelector('.sidebar-nav ' + selector);
  if (navEl) navEl.classList.add('active');
}

function bindSectionTriggers(selector, section) {
  document.querySelectorAll(selector).forEach(element => {
    element.addEventListener("click", () => {
      setSectionVisible(section);
      setActiveNav(selector);
    });
  });
}

function setupNavigation() {
  bindSectionTriggers(".user-guide-icon", overviewSection);
  bindSectionTriggers(".station-overview-icon", stationOverviewSection);
  bindSectionTriggers(".custom-visualization-setup-icon", builderSection);
  bindSectionTriggers(".visualization-dashboard-icon", dashboardSection);
  bindSectionTriggers(".prediction-icon", predictionSection);
  bindSectionTriggers(".about-us-icon", aboutSection);
}

function setupBuilderEvents() {
  categoryDropdown.disabled = true;
  stationDropdown.disabled = true;
  startVisualizationBtn.style.display = "inline-block";

  graphOptionsDropdown.addEventListener("change", function() {
    selectedGraphOption = graphOptionsDropdown.value;
    updateBuilderSummary();

    const graphConfig = getSelectedGraphConfig();
    if (!graphConfig) return;

    hasAutoAddCategories = graphConfig.auto_add_categories;

    resetSelectedCategoriesAndStations();

    if (hasAutoAddCategories) {
      categorySelectionDiv.style.display = "none";
      categoryDropdown.disabled = true;
      stationDropdown.disabled = false;
      showStationOptionsOnUI(ALL_CATEGORIES);
      showStationsOnMapUI(ALL_CATEGORIES);
    } else {
      categorySelectionDiv.style.display = "block";
      categoryDropdown.disabled = false;
      stationDropdown.disabled = true;
      showCategoryOptionsOnUI();
      showStationOptionsOnUI(ALL_CATEGORIES);
      showStationsOnMapUI(ALL_CATEGORIES);
    }
  });

  addCategoryBtn.addEventListener("click", function() {
    const currentCategory = categoryDropdown.value;
    const graphConfig = getSelectedGraphConfig();

    if (!graphConfig || !currentCategory) return;

    if (
      graphConfig.number_of_categories_allow !== "All" &&
      selectedCategories.length >= graphConfig.number_of_categories_allow
    ) {
      showAlert(oneCategoryOnlyAlert);
      return;
    }

    if (!selectedCategories.includes(currentCategory)) {
      selectedCategories.push(currentCategory);
      renderSelectedCategories();
      stationDropdown.disabled = false;
      showStationOptionsOnUI("Current Categories Selected");
      showStationsOnMapUI("Current Categories Selected");
    }
  });

addStationBtn.addEventListener("click", function() {
  const currentStation = (stationDropdown.value || "").trim();
  const graphConfig = getSelectedGraphConfig();

  if (!graphConfig) {
    alert("Please choose a visualization type first.");
    return;
  }

  if (!currentStation) {
    alert("Please choose a station first.");
    return;
  }

  if (hasAutoAddCategories) {
    addAllCategoriesForStation(currentStation);
  }

  const uniqueStationCount = new Set(
    selectedStationEntries.map(entry => entry.station_name)
  ).size;

  const stationAlreadyExists = selectedStationEntries.some(
    entry => entry.station_name === currentStation
  );

  if (
    graphConfig.number_of_stations_allow !== "All" &&
    uniqueStationCount >= graphConfig.number_of_stations_allow &&
    !stationAlreadyExists
  ) {
    showAlert(oneStationOnlyAlert);
    return;
  }

  const categoriesToUse = [...selectedCategories];

  if (!categoriesToUse.length) {
    alert("Please add at least one category first.");
    return;
  }

  let addedAnything = false;

  categoriesToUse.forEach(categoryName => {
    const detail = getCategoryDateRange(categoryName, currentStation);

    if (!detail) {
      console.log("No matching data found for:", categoryName, currentStation);
      return;
    }

    const duplicate = selectedStationEntries.some(
      entry =>
        entry.station_name === currentStation &&
        entry.category_name === categoryName
    );

    if (!duplicate) {
      selectedStationEntries.push({
        station_name: currentStation,
        category_name: categoryName,
        start_date: formatDateToDDMMYYYY(detail.start_date),
        end_date: formatDateToDDMMYYYY(detail.end_date)
      });

      addedAnything = true;
    }
  });

  if (!addedAnything) {
    alert("This station could not be added for the selected category.");
    return;
  }

  updateFeaturedStationPanel(currentStation);
  renderSelectedStations();
  updateBuilderSummary();
});

  addToDashboardBtn.addEventListener("click", function() {
    if (!selectedGraphOption || !selectedStationEntries.length || !selectedCategories.length) {
      showAlert(selectCategoryAndStationAlert);
      return;
    }

    const newVisualization = buildVisualizationFromCurrentSelections();
    selectedVisualizations.push(newVisualization);
    updateVisualizationQueueUI();
    resetVisualizationSetup();
    setSectionVisible(builderSection);
  });

  startVisualizationBtn.addEventListener("click", function() {
    triggerStartVisualization();
  });
}

function setupModalEvents() {
  closeModalBtn?.addEventListener("click", () => {
    fullScreenModal.style.display = "none";
    Plotly.purge("fullScreenGraph");
  });

  window.addEventListener("click", (event) => {
    if (event.target === fullScreenModal) {
      fullScreenModal.style.display = "none";
      Plotly.purge("fullScreenGraph");
    }
  });
}

// ------------------------------
// DARK MODE
// ------------------------------
function applyTheme(dark) {
  document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light');
  localStorage.setItem('theme', dark ? 'dark' : 'light');

  const btn = document.getElementById('theme-toggle-btn');
  if (btn) {
    btn.querySelector('.theme-icon-moon').style.display = dark ? 'none' : 'block';
    btn.querySelector('.theme-icon-sun').style.display  = dark ? 'block' : 'none';
    btn.querySelector('.theme-toggle-label').textContent = dark ? 'Light Mode' : 'Dark Mode';
  }

  if (map && currentTileLayer) {
    map.removeLayer(currentTileLayer);
    currentTileLayer = L.tileLayer(dark ? TILE_DARK : TILE_LIGHT, {
      attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
      subdomains: 'abcd',
      maxZoom: 18
    }).addTo(map);
    currentTileLayer.bringToBack();
  }
}

function setupThemeToggle() {
  document.getElementById('theme-toggle-btn')?.addEventListener('click', () => {
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    applyTheme(!isDark);
  });
  if (localStorage.getItem('theme') === 'dark') applyTheme(true);
}

// ------------------------------
// PREDICTION
// ------------------------------
function populatePredictionDropdowns() {
  const predStation  = document.getElementById('pred-station-select');
  const predCategory = document.getElementById('pred-category-select');
  if (!predStation || !predCategory) return;

  predStation.innerHTML = '<option value="">Select a station...</option>';
  stationNameList.forEach(name => {
    const opt = document.createElement('option');
    opt.value = name; opt.textContent = name;
    predStation.appendChild(opt);
  });

  predCategory.innerHTML = '<option value="">Select a category...</option>';
  categoryNameList.forEach(name => {
    const opt = document.createElement('option');
    opt.value = name; opt.textContent = name;
    predCategory.appendChild(opt);
  });
}

function updatePredCategoriesForStation(stationName) {
  const predCategory = document.getElementById('pred-category-select');
  if (!predCategory) return;

  const prev = predCategory.value;
  predCategory.innerHTML = '<option value="">Select a category...</option>';

  const available = stationName
    ? categoryNameList.filter(name =>
        (categoryDetailsMap[name] || []).some(row => row.station_name === stationName)
      )
    : categoryNameList;

  available.forEach(name => {
    const opt = document.createElement('option');
    opt.value = name; opt.textContent = name;
    predCategory.appendChild(opt);
  });

  // Restore previous selection only if it's still valid for the new station
  if (prev && available.includes(prev)) {
    predCategory.value = prev;
  }
}

function autofillPredDateRange() {
  const station  = document.getElementById('pred-station-select')?.value;
  const category = document.getElementById('pred-category-select')?.value;
  const startEl  = document.getElementById('pred-start-date');
  const endEl    = document.getElementById('pred-end-date');

  if (!station || !category) {
    if (startEl) startEl.value = '';
    if (endEl)   endEl.value   = '';
    return;
  }

  const detail = getCategoryDateRange(category, station);
  if (detail) {
    if (startEl) startEl.value = formatDateToDDMMYYYY(detail.start_date);
    if (endEl)   endEl.value   = formatDateToDDMMYYYY(detail.end_date);
  } else {
    // No data for this combo — clear so user knows something is wrong
    if (startEl) startEl.value = '';
    if (endEl)   endEl.value   = '';
  }
}

function setupPredictionEvents() {
  document.getElementById('pred-station-select')?.addEventListener('change', function() {
    updatePredCategoriesForStation(this.value);
    autofillPredDateRange();
  });
  document.getElementById('pred-category-select')?.addEventListener('change', autofillPredDateRange);

  document.getElementById('pred-generate-btn')?.addEventListener('click', function() {
    const station        = document.getElementById('pred-station-select')?.value;
    const category       = document.getElementById('pred-category-select')?.value;
    const startDate      = document.getElementById('pred-start-date')?.value;
    const endDate        = document.getElementById('pred-end-date')?.value;
    const forecastMonths = parseInt(document.getElementById('pred-horizon-select')?.value || '12');

    if (!station || !category || !startDate || !endDate) {
      showAlert(document.getElementById('pred-alert'));
      return;
    }

    const btn = document.getElementById('pred-generate-btn');
    btn.disabled = true;
    btn.textContent = 'Generating…';
    document.getElementById('pred-model-info')?.classList.add('hidden');
    document.getElementById('pred-chart-container')?.classList.add('hidden');

    fetch('/generate_prediction', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ station_name: station, category_name: category, start_date: startDate, end_date: endDate, forecast_months: forecastMonths })
    })
    .then(r => r.json())
    .then(data => {
      if (data.error) { alert('Forecast error: ' + data.error); return; }

      const info = data.model_info;
      const gammaRow = info.gamma !== null
        ? `<div class="pred-info-card"><span class="pred-info-label">γ (seasonal)</span><span class="pred-info-value">${info.gamma}</span></div>`
        : '';

      document.getElementById('pred-model-info').innerHTML = `
        <div class="pred-info-grid">
          <div class="pred-info-card"><span class="pred-info-label">Model</span><span class="pred-info-value">${info.model_type}</span></div>
          <div class="pred-info-card"><span class="pred-info-label">Historical data</span><span class="pred-info-value">${info.historical_months} months</span></div>
          <div class="pred-info-card"><span class="pred-info-label">Forecast period</span><span class="pred-info-value">${info.last_historical} → ${info.forecast_end}</span></div>
          <div class="pred-info-card"><span class="pred-info-label">AIC</span><span class="pred-info-value">${info.aic}</span></div>
          <div class="pred-info-card"><span class="pred-info-label">RMSE</span><span class="pred-info-value">${info.rmse}</span></div>
          <div class="pred-info-card"><span class="pred-info-label">α (level)</span><span class="pred-info-value">${info.alpha}</span></div>
          <div class="pred-info-card"><span class="pred-info-label">β (trend)</span><span class="pred-info-value">${info.beta}</span></div>
          ${gammaRow}
        </div>`;
      document.getElementById('pred-model-info').classList.remove('hidden');
      document.getElementById('pred-chart-container').classList.remove('hidden');
      Plotly.newPlot('pred-chart', JSON.parse(data.chart), {}, { responsive: true });
    })
    .catch(err => alert('Error: ' + err.message))
    .finally(() => { btn.disabled = false; btn.textContent = 'Generate Forecast'; });
  });
}

// ------------------------------
// INIT
// ------------------------------
document.addEventListener("DOMContentLoaded", async function() {
  try {
    await Promise.all([loadCSVStationDetails(), loadCSVCategoryDetails()]);

    initializeMap();
    showGraphOptionsOnUI();
    showCategoryOptionsOnUI();
    showStationOptionsOnUI(ALL_CATEGORIES);
    showStationsOnMapUI(ALL_CATEGORIES);

    updateOverviewStats();
    updateBuilderSummary();
    updateVisualizationQueueUI();

    if (stationNameList.length) {
      updateFeaturedStationPanel(stationNameList[0]);
    }

    setupNavigation();
    setupBuilderEvents();
    setupModalEvents();
    populatePredictionDropdowns();
    setupPredictionEvents();
    setupThemeToggle();
    setupUndoToast();
  } catch (error) {
    console.error("Initialization error:", error);
  }
});