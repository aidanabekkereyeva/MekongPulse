const STATION_DETAILS_CSV_LINK = "/static/data-outputs/station_details.csv";
const CATEGORY_DETAILS_CSV_LINK = "/static/data-outputs/category_details.csv";
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
let selectedStations = [];
let selectedCategories = [];
let selectedStationEntries = [];
let selectedVisualizations = [];
let selectedGraphOption = null;
let hasAutoAddCategories = false;
const EXPORT_SOURCE_META = {
  dashboard: { label: "Visualization Dashboard", slug: "visualization_dashboard" },
  forecast: { label: "Forecast Workspace", slug: "forecast_workspace" },
  correlation: { label: "Correlation Explorer", slug: "correlation_explorer" },
  seasonal: { label: "Seasonal Decomposition", slug: "seasonal_decomposition" },
  analyze: { label: "Analysis Builder", slug: "analysis_builder" },
};
let exportSessions = Object.fromEntries(
  Object.keys(EXPORT_SOURCE_META).map(key => [key, {
    title: EXPORT_SOURCE_META[key].label,
    slug: EXPORT_SOURCE_META[key].slug,
    charts: [],
    reportHtml: "",
    reportText: "",
    meta: [],
    generatedAt: "",
    available: false,
  }])
);

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
const builderSection = document.querySelector(".custom-visualization-setup");
const dashboardSection = document.querySelector(".visualization-dashboard");
const aboutSection = document.querySelector(".about-us");
const predictionSection = document.querySelector(".prediction");
const analyzeSection      = document.querySelector(".analyze-section");
const correlationSection  = document.querySelector(".correlation-section");
const seasonalSection     = document.querySelector(".seasonal-section");
const exportSection       = document.querySelector(".export-section");
const datasetOverviewSection = document.querySelector(".dataset-overview-section");
const researchSection     = document.querySelector(".research-section");
const newsSection         = document.querySelector(".news-section");

const SECTION_TITLES = new Map([
  [overviewSection,        "Overview"],
  [builderSection,         "Visualization Builder"],
  [dashboardSection,       "Dashboard"],
  [predictionSection,      "Prediction"],
  [analyzeSection,         "Analyze"],
  [correlationSection,     "Correlation"],
  [seasonalSection,        "Seasonal"],
  [exportSection,          "Export"],
  [datasetOverviewSection, "Dataset Overview"],
  [researchSection,        "Research Lab"],
  [newsSection,            "News"],
  [aboutSection,           "About"],
]);

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

function createCustomAlert(message) {
  const alert = document.createElement("div");
  alert.className = "warning-alert";
  alert.textContent = message;
  alert.style.display = "block";
  alert.style.position = "fixed";
  alert.style.top = "20px";
  alert.style.left = "50%";
  alert.style.transform = "translateX(-50%)";
  alert.style.zIndex = "9999";
  alert.style.maxWidth = "500px";
  alert.style.padding = "12px 16px";
  document.body.appendChild(alert);

  setTimeout(() => {
    alert.remove();
  }, 3000);

  return alert;
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

function normalizeGraphName(name) {
  return String(name || "").trim();
}

function findGraphConfigByName(name) {
  const normalizedName = normalizeGraphName(name);
  return graphTypeOptions.find(option => normalizeGraphName(option.name) === normalizedName);
}

function getCurrentBuilderGraphName() {
  if (!graphOptionsDropdown) return "";

  const value = normalizeGraphName(graphOptionsDropdown.value);
  if (value) return value;

  const selectedOption = graphOptionsDropdown.options[graphOptionsDropdown.selectedIndex];
  return normalizeGraphName(selectedOption?.textContent);
}

function getCurrentBuilderCategoryName() {
  if (!categoryDropdown) return "";

  const value = normalizeGraphName(categoryDropdown.value);
  if (value) return value;

  const selectedOption = categoryDropdown.options[categoryDropdown.selectedIndex];
  return normalizeGraphName(selectedOption?.textContent);
}

function getCurrentBuilderStationName() {
  if (!stationDropdown) return "";

  const value = normalizeGraphName(stationDropdown.value);
  if (value) return value;

  const selectedOption = stationDropdown.options[stationDropdown.selectedIndex];
  return normalizeGraphName(selectedOption?.textContent);
}

function getSelectedGraphConfig() {
  return findGraphConfigByName(selectedGraphOption);
}

function validateGraphRequirements() {
  const config = getSelectedGraphConfig();
  if (!config) {
    return { valid: false, error: "Please select a visualization type first." };
  }

  // Check categories
  if (config.number_of_categories_allow !== "All") {
    if (selectedCategories.length < config.number_of_categories_allow) {
      return {
        valid: false,
        error: `This visualization requires ${config.number_of_categories_allow} categor${config.number_of_categories_allow === 1 ? 'y' : 'ies'}, but you selected ${selectedCategories.length}.`
      };
    }
  }

  // Check stations
  const uniqueStations = new Set(selectedStationEntries.map(e => e.station_name));
  if (config.number_of_stations_allow !== "All") {
    if (uniqueStations.size < config.number_of_stations_allow) {
      return {
        valid: false,
        error: `This visualization requires ${config.number_of_stations_allow} station${config.number_of_stations_allow === 1 ? '' : 's'}, but you selected ${uniqueStations.size}.`
      };
    }
  }

  return { valid: true };
}

function displayGraphRequirements(requirementsElId = "graph-requirements-text") {
  const config = getSelectedGraphConfig();
  const requirementsEl = document.getElementById(requirementsElId);
  if (!config || !requirementsEl) return;

  let requirementText = "Requires: ";

  // Categories requirement
  if (config.number_of_categories_allow === "All") {
    requirementText += "any number of categories";
  } else if (config.number_of_categories_allow === 1) {
    requirementText += "1 category";
  } else {
    requirementText += `${config.number_of_categories_allow} categories`;
  }

  requirementText += " • ";

  // Stations requirement
  if (config.number_of_stations_allow === "All") {
    requirementText += "any number of stations";
  } else if (config.number_of_stations_allow === 1) {
    requirementText += "1 station";
  } else {
    requirementText += `${config.number_of_stations_allow} stations`;
  }

  requirementsEl.textContent = requirementText;
}

function displayGraphRequirementsForAnalyze(graphName) {
  const config = findGraphConfigByName(graphName);
  const requirementsEl = document.getElementById("az-graph-requirements-text");
  if (!config || !requirementsEl) return;

  let requirementText = "Requires: ";

  // Categories requirement
  if (config.number_of_categories_allow === "All") {
    requirementText += "any number of categories";
  } else if (config.number_of_categories_allow === 1) {
    requirementText += "1 category";
  } else {
    requirementText += `${config.number_of_categories_allow} categories`;
  }

  requirementText += " • ";

  // Stations requirement
  if (config.number_of_stations_allow === "All") {
    requirementText += "any number of stations";
  } else if (config.number_of_stations_allow === 1) {
    requirementText += "1 station";
  } else {
    requirementText += `${config.number_of_stations_allow} stations`;
  }

  requirementsEl.textContent = requirementText;
}

function refreshBuilderRequirements() {
  const requirementsEl = document.getElementById("graph-requirements-text");
  const graphName = getCurrentBuilderGraphName();
  if (!requirementsEl) return;

  const config = findGraphConfigByName(graphName);
  if (!config) {
    requirementsEl.textContent = "Select a visualization type to see requirements";
    return;
  }

  const categoryText = config.number_of_categories_allow === "All"
    ? "any number of categories"
    : `${config.number_of_categories_allow} categor${config.number_of_categories_allow === 1 ? "y" : "ies"}`;

  const stationText = config.number_of_stations_allow === "All"
    ? "any number of stations"
    : `${config.number_of_stations_allow} station${config.number_of_stations_allow === 1 ? "" : "s"}`;

  requirementsEl.textContent = `Requires: ${categoryText} • ${stationText}`;
}

function handleAddCategorySelection() {
  const currentCategory = getCurrentBuilderCategoryName();
  const graphConfig = getSelectedGraphConfig();

  if (!graphConfig || !currentCategory || currentCategory.toLowerCase().startsWith("select ")) {
    return;
  }

  if (!selectedStations.length) {
    showAlert(document.getElementById("no-station-alert"));
    return;
  }

  if (
    graphConfig.number_of_categories_allow !== "All" &&
    selectedCategories.length >= graphConfig.number_of_categories_allow
  ) {
    showAlert(oneCategoryOnlyAlert);
    return;
  }

  if (!selectedCategories.includes(currentCategory)) {
    selectedCategories.push(currentCategory);
    rebuildSelectedStationEntries();
    renderSelectedCategories();
    renderSelectedStations();
  }
}

function handleAddStationSelection() {
  const currentStation = getCurrentBuilderStationName();
  const graphConfig = getSelectedGraphConfig();

  if (!currentStation || currentStation.toLowerCase().startsWith("select ")) {
    showAlert(document.getElementById("no-station-alert"));
    return;
  }

  const stationAlreadyExists = selectedStations.includes(currentStation);
  const stationLimit = graphConfig?.number_of_stations_allow;

  if (stationLimit !== "All" && stationLimit && selectedStations.length >= stationLimit && !stationAlreadyExists) {
    showAlert(oneStationOnlyAlert);
    return;
  }

  if (!stationAlreadyExists) {
    selectedStations.push(currentStation);
    selectedStations.sort((a, b) => a.localeCompare(b));
  }

  if (selectedCategories.length) {
    const availableCategories = new Set(getAvailableCategoriesForStations());
    selectedCategories = selectedCategories.filter(category => availableCategories.has(category));
    renderSelectedCategories();
  }

  categoryDropdown.disabled = !selectedStations.length;
  showCategoryOptionsOnUI();
  rebuildSelectedStationEntries();
  renderSelectedStations();
  updateBuilderSummary();
}

function setSectionVisible(section) {
  collapseExpandedMap();

  [overviewSection, builderSection, dashboardSection, aboutSection, predictionSection, analyzeSection, correlationSection, seasonalSection, exportSection, datasetOverviewSection, researchSection, newsSection].forEach(sec => {
    if (!sec) return;
    sec.classList.add("hidden");
    sec.classList.remove("section-entering");
  });

  if (section) {
    section.classList.remove("hidden");
    void section.offsetWidth; // force reflow to re-trigger animation
    section.classList.add("section-entering");
    section.scrollIntoView({ behavior: "smooth", block: "start" });
    const title = SECTION_TITLES.get(section) || "Overview";
    document.title = `MekongPulse \u00b7 ${title}`;
  }
}

function collapseExpandedMap() {
  const mapView = document.getElementById('map-view');
  const expandBtn = document.getElementById('map-expand-btn');
  if (!mapView || !mapView.classList.contains('map-expanded')) return;

  mapView.classList.remove('map-expanded');
  if (expandBtn) {
    expandBtn.setAttribute('title', 'Click to expand map to fullscreen');
  }

  setTimeout(() => {
    map?.invalidateSize();
    if (stationMarkers.length) fitMapToStations();
  }, 0);
}

function updateBuilderSummary() {
  selectedGraphPreview.textContent = selectedGraphOption || "No graph selected yet";
  selectedCategoriesPreview.textContent = String(selectedCategories.length);

  const uniqueStations = selectedStations.length
    ? new Set(selectedStations)
    : new Set(selectedStationEntries.map(entry => entry.station_name));
  selectedStationsPreview.textContent = String(uniqueStations.size);
}

function updateInsightAndCoverage(summary) {
  if (!summary) return;

  // KPI cards — animate numeric values from 0 to target
  function animateCounter(el, rawVal) {
    if (!el) return;
    const str = String(rawVal ?? "--");
    const match = str.match(/^([\d,]+\.?\d*)(.*)$/);
    if (!match) { el.textContent = str; return; }
    const numStr = match[1].replace(/,/g, "");
    const suffix = match[2] || "";
    const target = parseFloat(numStr);
    if (isNaN(target)) { el.textContent = str; return; }
    const decimals = numStr.includes(".") ? (numStr.split(".")[1] || "").length : 0;
    const duration = 650;
    const startTime = performance.now();
    function step(now) {
      const p = Math.min((now - startTime) / duration, 1);
      const eased = 1 - Math.pow(1 - p, 3);
      const current = target * eased;
      el.textContent = (decimals > 0 ? current.toFixed(decimals) : Math.round(current).toLocaleString()) + suffix;
      if (p < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }
  const set = (id, val) => animateCounter(document.getElementById(id), val);
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
  selectedStations = [];
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
  stationDropdown.disabled = false;
  categorySelectionDiv.style.display = "block";

  updateBuilderSummary();
  refreshBuilderRequirements();
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

function getCategoryDateRange(categoryName, stationName) {
  const cleanCategory = (categoryName || "").trim().toLowerCase();
  const cleanStation  = (stationName  || "").trim().toLowerCase();

  // Primary: exact match in the category's rows
  const rows = categoryDetailsMap[categoryName] || [];
  const exact = rows.find(row =>
    (row.category_name || "").trim().toLowerCase() === cleanCategory &&
    (row.station_name  || "").trim().toLowerCase() === cleanStation
  );
  if (exact) return exact;

  // Fallback: search all categories for this station and return widest date span
  let earliest = null, latest = null;
  Object.values(categoryDetailsMap).forEach(catRows => {
    catRows.forEach(row => {
      if ((row.station_name || "").trim().toLowerCase() !== cleanStation) return;
      if (!earliest || row.start_date < earliest) earliest = row.start_date;
      if (!latest   || row.end_date   > latest)   latest   = row.end_date;
    });
  });
  if (earliest && latest) return { start_date: earliest, end_date: latest };
  return null;
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

function getAvailableCategoriesForStations(stations = selectedStations) {
  if (!stations.length) return [];

  const stationCategorySets = stations.map(stationName => {
    const categories = new Set();
    Object.keys(categoryDetailsMap).forEach(categoryName => {
      const hasStation = (categoryDetailsMap[categoryName] || []).some(row => row.station_name === stationName);
      if (hasStation) categories.add(categoryName);
    });
    return categories;
  });

  if (!stationCategorySets.length) return [];

  const [firstSet, ...restSets] = stationCategorySets;
  return [...firstSet].filter(categoryName =>
    restSets.every(categorySet => categorySet.has(categoryName))
  ).sort((a, b) => a.localeCompare(b));
}

function rebuildSelectedStationEntries() {
  const preservedEntries = new Map(
    selectedStationEntries.map(entry => [
      `${entry.station_name}::${entry.category_name}`,
      entry
    ])
  );

  const rebuiltEntries = [];

  selectedStations.forEach(stationName => {
    selectedCategories.forEach(categoryName => {
      const detail = getCategoryDateRange(categoryName, stationName);
      if (!detail) return;

      const key = `${stationName}::${categoryName}`;
      const preserved = preservedEntries.get(key);

      rebuiltEntries.push({
        station_name: stationName,
        category_name: categoryName,
        start_date: preserved?.start_date || formatDateToDDMMYYYY(detail.start_date),
        end_date: preserved?.end_date || formatDateToDDMMYYYY(detail.end_date)
      });
    });
  });

  selectedStationEntries = rebuiltEntries;
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
      rebuildSelectedStationEntries();
      renderSelectedCategories();
      renderSelectedStations();
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

  selectedStations.forEach((stationName, index) => {
    const stationMeta = stationDetailsMap[stationName];
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
    line1.innerHTML = `<strong>${stationName}</strong>${stationMeta?.country ? ` - ${stationMeta.country}` : ""}`;

    const line2 = document.createElement("p");
    line2.className = "station-date";
    line2.style.margin = "0";
    const matchedCount = selectedStationEntries.filter(entry => entry.station_name === stationName).length;
    line2.textContent = matchedCount
      ? `${matchedCount} category match${matchedCount === 1 ? "" : "es"} ready`
      : "Choose categories to build this station configuration";

    textWrap.appendChild(line1);
    textWrap.appendChild(line2);

    const actions = document.createElement("div");
    actions.style.display = "flex";
    actions.style.gap = "8px";

    const deleteBtn = document.createElement("button");
    deleteBtn.type = "button";
    deleteBtn.textContent = "Remove";
    deleteBtn.className = "secondary-btn";
    deleteBtn.style.padding = "8px 10px";

    deleteBtn.addEventListener("click", () => {
      selectedStations = selectedStations.filter(station => station !== stationName);
      const availableCategories = new Set(getAvailableCategoriesForStations());
      selectedCategories = selectedCategories.filter(category => availableCategories.has(category));
      renderSelectedCategories();
      categoryDropdown.disabled = !selectedStations.length;
      rebuildSelectedStationEntries();
      renderSelectedStations();
      updateBuilderSummary();
    });

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

  refreshBuilderRequirements();
}

function showCategoryOptionsOnUI() {
  categoryDropdown.innerHTML = "";
  categoryDropdown.appendChild(getPlaceholderOption("Select a category"));

  getAvailableCategoriesForStations().forEach(categoryName => {
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
    Object.values(stationDetailsMap).forEach(station => {
      if (!station?.station_name || addedStations.has(station.station_name)) return;

      const option = document.createElement("option");
      option.textContent = station.station_name;
      option.value = station.station_name;
      stationDropdown.appendChild(option);
      addedStations.add(station.station_name);
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
  selectedStations      = [...new Set(visualization.data.map(d => d.station_name))];
  selectedCategories    = [...new Set(visualization.data.map(d => d.category_name))];
  selectedStationEntries = visualization.data.map(d => ({ ...d }));

  // Sync auto-add setting and category row visibility
  const graphConfig = getSelectedGraphConfig();
  hasAutoAddCategories = false;
  categorySelectionDiv.style.display = "block";
  stationDropdown.disabled = false;
  categoryDropdown.disabled = !selectedStations.length;

  showStationOptionsOnUI(ALL_CATEGORIES);
  showCategoryOptionsOnUI();
  renderSelectedCategories();
  renderSelectedStations();
  updateBuilderSummary();
  refreshBuilderRequirements();

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

  // Sync sidebar nav badge
  const navBadge = document.getElementById("nav-dashboard-badge");
  if (navBadge) {
    if (charts && charts.length) {
      navBadge.textContent = charts.length;
      navBadge.classList.remove("hidden");
    } else {
      navBadge.classList.add("hidden");
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
    showAlert(document.getElementById("no-saved-viz-alert"));
    setSectionVisible(builderSection);
    setActiveNav(".custom-visualization-setup-icon");
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

  const findings = generateKeyFindings(summary, ranking) || [];

  // Store for AI analysis
  lastSummaryForAI = summary;
  lastRankingForAI = ranking;
  const aiPanel = document.getElementById('ai-analysis-panel');
  const aiBody = document.getElementById('ai-analysis-body');
  if (aiPanel) {
    aiPanel.classList.remove('hidden');
    aiBody.innerHTML = '<p class="ai-analysis-placeholder">Click "Analyze with AI" to generate an analytical summary of your current visualization data.</p>';
  }

  // Key findings (needs both summary + ranking)
  const findingsList = document.getElementById("findings-list");
  if (findingsList) {
    if (findings && findings.length) {
      findingsList.innerHTML = findings.map(f => `<li class="finding-item">${f}</li>`).join("");
    } else {
      findingsList.innerHTML = `<li class="finding-placeholder">No findings could be generated for this selection.</li>`;
    }
  }

  const queueSummary = selectedVisualizations.map((viz, index) => ({
    label: `Visualization ${index + 1}`,
    value: viz.graph_type
  }));
  const findingsHtml = findings.length
    ? `<div class="az-section"><h4 class="az-section-title">Key Findings</h4><ul class="corr-findings-list">${findings.map(item => `<li>${item}</li>`).join('')}</ul></div>`
    : '';
  setExportSessionPayload('dashboard', {
    charts,
    title: 'Visualization Dashboard',
    reportHtml: findingsHtml,
    reportText: findings.join('\n'),
    meta: [
      { label: 'Queued visualizations', value: String(charts.length || selectedVisualizations.length || 0) },
      ...queueSummary.slice(0, 4),
      { label: 'Primary station', value: summary?.station ?? '--' },
      { label: 'Primary category', value: summary?.category ?? '--' },
      { label: 'Date range', value: summary?.date_range ?? '--' },
      { label: 'Coverage', value: summary?.coverage_pct != null ? `${summary.coverage_pct}%` : '--' },
    ],
  });
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
    html: `<div class="station-pin">
      <svg viewBox="0 0 20 26" width="20" height="26" xmlns="http://www.w3.org/2000/svg">
        <path d="M10 1C5.86 1 2.5 4.36 2.5 8.5C2.5 14.5 10 25 10 25S17.5 14.5 17.5 8.5C17.5 4.36 14.14 1 10 1Z"
              fill="${color}" stroke="white" stroke-width="1.5"/>
        <circle cx="10" cy="8.5" r="3" fill="white" opacity="0.85"/>
      </svg>
    </div>`,
    iconSize: [20, 26],
    iconAnchor: [10, 26],
    popupAnchor: [0, -30]
  });
}

let _activeHighlightCountry = null;

function applyCountryHighlight(country) {
  _activeHighlightCountry = country;
  stationMarkers.forEach(m => {
    const el = m.getElement();
    if (!el) return;
    const pin = el.querySelector('.station-pin');
    if (!pin) return;
    if (country && m._country !== country) {
      pin.classList.add('pin-faded');
    } else {
      pin.classList.remove('pin-faded');
    }
  });

  // Update legend item styles
  document.querySelectorAll('.legend-item[data-country]').forEach(item => {
    const isSel = item.dataset.country === country;
    item.classList.toggle('legend-active', !!country && isSel);
    item.classList.toggle('legend-faded', !!country && !isSel);
  });

  const clearBtn = document.getElementById('legend-clear-btn');
  if (clearBtn) clearBtn.style.display = country ? 'block' : 'none';
}

function getMapFilterCountries() {
  const countries = new Set();

  Object.keys(COUNTRY_COLORS || {}).forEach(country => {
    if (country) countries.add(country);
  });

  Object.values(stationDetailsMap || {}).forEach(station => {
    if (station?.country) countries.add(station.country);
  });

  return Array.from(countries).sort((a, b) => a.localeCompare(b));
}

function syncMapCountryFilterOptions() {
  const filterSelect = document.getElementById('map-country-filter');
  if (!filterSelect) return;

  const countries = getMapFilterCountries();
  if (!countries.length) return;

  const selectedValue = filterSelect.value;
  filterSelect.innerHTML = '<option value="">All Countries</option>';

  countries.forEach(country => {
    const opt = document.createElement('option');
    opt.value = country;
    opt.textContent = country;
    filterSelect.appendChild(opt);
  });

  filterSelect.value = countries.includes(selectedValue) ? selectedValue : '';
}

function renderInitialMapStations() {
  const filterSelect = document.getElementById('map-country-filter');
  activeCountryFilter = '';
  if (filterSelect) filterSelect.value = '';

  showStationsOnMapUI(ALL_CATEGORIES);

  if (!map) return;

  map.invalidateSize();
  if (stationMarkers.length) fitMapToStations();
}

function buildMapLegend() {
  const legend = document.getElementById('map-legend');
  if (!legend) return;

  const entries = getMapFilterCountries().map(country => [country, getCountryColor(country)]);

  const countByCountry = {};
  Object.values(stationDetailsMap).forEach(s => {
    countByCountry[s.country] = (countByCountry[s.country] || 0) + 1;
  });

  legend.innerHTML = `
    <h4>Countries</h4>
    ${entries.map(([country, color]) => `
      <div class="legend-item" data-country="${country}">
        <div class="legend-dot" style="background:${color}"></div>
        <span>${country}</span>
        <span class="legend-count">${countByCountry[country] || 0}</span>
      </div>
    `).join('')}
    <button id="legend-clear-btn" class="legend-clear-btn" style="display:none">✕ Clear filter</button>
  `;

  // Click to highlight
  legend.querySelectorAll('.legend-item[data-country]').forEach(item => {
    item.addEventListener('click', () => {
      const country = item.dataset.country;
      applyCountryHighlight(_activeHighlightCountry === country ? null : country);
    });
  });

  document.getElementById('legend-clear-btn')?.addEventListener('click', () => {
    applyCountryHighlight(null);
  });

  syncMapCountryFilterOptions();
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

  const addMarkerForStation = (stationOrName) => {
    const station = typeof stationOrName === 'string'
      ? stationDetailsMap[stationOrName]
      : stationOrName;

    if (!station || isNaN(station.latitude) || isNaN(station.longitude)) return;
    if (addedStations.has(station.station_name)) return;
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
          <button class="map-popup-btn map-popup-btn-outline" onclick="window.goToBuilder()">Visualization</button>
          <button class="map-popup-btn" onclick="window.goToAnalyze()">Analyze</button>
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

    marker._country = station.country;

    marker.on("mouseover", function() { this.setZIndexOffset(1000); });
    marker.on("mouseout",  function() { this.setZIndexOffset(0); });

    markerClusterGroup.addLayer(marker);
    stationMarkers.push(marker);
    addedStations.add(station.station_name);
  };

  if (mode === ALL_CATEGORIES) {
    Object.values(stationDetailsMap).forEach(addMarkerForStation);
    return;
  }

  if (mode === "Current Categories Selected") {
    selectedCategories.forEach(categoryName => {
      (categoryDetailsMap[categoryName] || []).forEach(row => addMarkerForStation(row.station_name));
    });
  }
}

window.goToBuilder = function() {
  setSectionVisible(builderSection);
  setActiveNav(".custom-visualization-setup-icon");
};

window.goToAnalyze = function() {
  setSectionVisible(analyzeSection);
  setActiveNav(".analyze-section-icon");
};

window.goToDatasetOverview = function() {
  generateAndDisplayDatasetOverview();
  setSectionVisible(datasetOverviewSection);
  setActiveNav(".dataset-overview-icon");
};

function formatDatasetMonthLabel(date) {
  if (!(date instanceof Date) || Number.isNaN(date.getTime())) return "--";
  return date.toLocaleDateString("en-GB", { month: "short", year: "numeric" });
}

function formatDatasetYearLabel(date) {
  if (!(date instanceof Date) || Number.isNaN(date.getTime())) return "--";
  return String(date.getFullYear());
}

function escapeDatasetHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function buildDatasetOverviewModel() {
  const categories = Object.keys(categoryDetailsMap).sort();
  const allStations = Array.from(new Set(
    Object.values(categoryDetailsMap).flatMap(rows => rows.map(row => row.station_name))
  )).sort();
  const countries = Array.from(new Set(
    allStations.map(station => stationDetailsMap[station]?.country).filter(Boolean)
  )).sort();

  const stationMap = {};
  const categoryMap = {};
  const yearlyActivity = {};
  let globalStart = null;
  let globalEnd = null;

  allStations.forEach(station => {
    stationMap[station] = {
      station,
      country: stationDetailsMap[station]?.country || "Unknown",
      categories: [],
      categoryDetails: {},
      earliest: null,
      latest: null,
      longestSpan: 0,
      avgSpan: 0,
      readiness: 0,
    };
  });

  categories.forEach(category => {
    categoryMap[category] = {
      category,
      stations: [],
      countries: new Set(),
      earliest: null,
      latest: null,
    };

    (categoryDetailsMap[category] || []).forEach(row => {
      const start = new Date(row.start_date);
      const end = new Date(row.end_date);
      if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return;

      const years = end.getFullYear() - start.getFullYear() + 1;
      const stationEntry = stationMap[row.station_name];
      if (!stationEntry) return;

      if (!globalStart || start < globalStart) globalStart = start;
      if (!globalEnd || end > globalEnd) globalEnd = end;

      if (!stationEntry.categories.includes(category)) {
        stationEntry.categories.push(category);
      }
      stationEntry.categoryDetails[category] = { start, end, years };
      stationEntry.longestSpan = Math.max(stationEntry.longestSpan, years);
      stationEntry.earliest = !stationEntry.earliest || start < stationEntry.earliest ? start : stationEntry.earliest;
      stationEntry.latest = !stationEntry.latest || end > stationEntry.latest ? end : stationEntry.latest;

      categoryMap[category].stations.push({
        station: row.station_name,
        country: stationEntry.country,
        start,
        end,
        years,
      });
      categoryMap[category].countries.add(stationEntry.country);
      categoryMap[category].earliest = !categoryMap[category].earliest || start < categoryMap[category].earliest ? start : categoryMap[category].earliest;
      categoryMap[category].latest = !categoryMap[category].latest || end > categoryMap[category].latest ? end : categoryMap[category].latest;
    });
  });

  const yearStart = globalStart ? globalStart.getFullYear() : null;
  const yearEnd = globalEnd ? globalEnd.getFullYear() : null;

  if (yearStart !== null && yearEnd !== null) {
    for (let year = yearStart; year <= yearEnd; year += 1) {
      yearlyActivity[year] = {
        activePairs: 0,
        activeStations: new Set(),
        activeCategories: new Set(),
      };
    }

    categories.forEach(category => {
      (categoryDetailsMap[category] || []).forEach(row => {
        const startYear = new Date(row.start_date).getFullYear();
        const endYear = new Date(row.end_date).getFullYear();
        for (let year = startYear; year <= endYear; year += 1) {
          if (!yearlyActivity[year]) continue;
          yearlyActivity[year].activePairs += 1;
          yearlyActivity[year].activeStations.add(row.station_name);
          yearlyActivity[year].activeCategories.add(category);
        }
      });
    });
  }

  const stationSummaries = Object.values(stationMap)
    .map(station => {
      const spans = Object.values(station.categoryDetails);
      const avgSpan = spans.length ? spans.reduce((sum, item) => sum + item.years, 0) / spans.length : 0;
      const categoryCount = station.categories.length;
      const readiness = Math.min(
        100,
        Math.round(
          Math.min(categoryCount * 18, 45) +
          Math.min(avgSpan * 1.3, 35) +
          Math.min(station.longestSpan * 0.6, 20)
        )
      );

      return {
        ...station,
        categories: [...station.categories].sort(),
        categoryCount,
        avgSpan: Math.round(avgSpan || 0),
        readiness,
      };
    })
    .sort((a, b) => b.readiness - a.readiness || b.longestSpan - a.longestSpan);

  const categorySummaries = Object.values(categoryMap)
    .map(category => ({
      category: category.category,
      stations: [...new Set(category.stations.map(item => item.station))].sort(),
      stationCount: new Set(category.stations.map(item => item.station)).size,
      countries: Array.from(category.countries).sort(),
      countryCount: category.countries.size,
      earliest: category.earliest,
      latest: category.latest,
      strongestStations: [...category.stations]
        .sort((a, b) => b.years - a.years)
        .slice(0, 5)
        .map(item => ({ station: item.station, years: item.years, country: item.country })),
      spanYears: category.earliest && category.latest
        ? category.latest.getFullYear() - category.earliest.getFullYear() + 1
        : 0,
    }))
    .sort((a, b) => b.stationCount - a.stationCount || b.spanYears - a.spanYears);

  const categoryPairs = [];
  for (let i = 0; i < categories.length; i += 1) {
    for (let j = i + 1; j < categories.length; j += 1) {
      const left = categories[i];
      const right = categories[j];
      const overlapStations = stationSummaries
        .filter(station => station.categories.includes(left) && station.categories.includes(right))
        .map(station => ({
          station: station.station,
          country: station.country,
          sharedYears: Math.min(
            station.categoryDetails[left]?.years || 0,
            station.categoryDetails[right]?.years || 0
          ),
        }))
        .sort((a, b) => b.sharedYears - a.sharedYears);

      categoryPairs.push({
        left,
        right,
        pair: `${left} x ${right}`,
        overlapCount: overlapStations.length,
        averageSharedYears: overlapStations.length
          ? Math.round(overlapStations.reduce((sum, item) => sum + item.sharedYears, 0) / overlapStations.length)
          : 0,
        topStations: overlapStations.slice(0, 3),
      });
    }
  }
  categoryPairs.sort((a, b) => b.overlapCount - a.overlapCount || b.averageSharedYears - a.averageSharedYears);

  const activeYears = Object.entries(yearlyActivity)
    .map(([year, info]) => ({
      year: Number(year),
      activePairs: info.activePairs,
      activeStations: info.activeStations.size,
      activeCategories: info.activeCategories.size,
    }))
    .sort((a, b) => a.year - b.year);

  const decadeSummary = {};
  activeYears.forEach(entry => {
    const decade = Math.floor(entry.year / 10) * 10;
    if (!decadeSummary[decade]) {
      decadeSummary[decade] = { decade, years: 0, totalPairs: 0, totalStations: 0 };
    }
    decadeSummary[decade].years += 1;
    decadeSummary[decade].totalPairs += entry.activePairs;
    decadeSummary[decade].totalStations += entry.activeStations;
  });

  const decadeCards = Object.values(decadeSummary)
    .map(item => ({
      label: `${item.decade}s`,
      avgPairs: Math.round(item.totalPairs / Math.max(item.years, 1)),
      avgStations: Math.round(item.totalStations / Math.max(item.years, 1)),
    }))
    .sort((a, b) => a.label.localeCompare(b.label));

  const topActivity = activeYears.reduce((best, entry) => (
    !best || entry.activePairs > best.activePairs ? entry : best
  ), null);

  return {
    categories,
    countries,
    allStations,
    stationSummaries,
    categorySummaries,
    categoryPairs,
    activeYears,
    decadeCards,
    globalStart,
    globalEnd,
    topActivity,
  };
}

function scoreStationForObjective(station, objective, selectedCategory) {
  if (selectedCategory && !station.categories.includes(selectedCategory)) return -1;

  if (objective === "trend") {
    return station.longestSpan * 1.7 + station.avgSpan * 0.8 + station.categoryCount * 6;
  }
  if (objective === "correlation") {
    return station.categoryCount * 24 + station.avgSpan * 0.7 + station.longestSpan * 0.4;
  }
  if (objective === "scarcity") {
    return (100 - station.categoryCount * 10) + station.longestSpan * 0.9 + station.avgSpan * 0.5;
  }
  return station.readiness * 1.2 + station.categoryCount * 10 + station.longestSpan * 0.5;
}

function scoreCategoryForObjective(category, objective, selectedCountry) {
  if (selectedCountry && !category.countries.includes(selectedCountry)) return -1;

  if (objective === "trend") {
    return category.spanYears * 1.5 + category.stationCount * 3;
  }
  if (objective === "correlation") {
    return category.stationCount * 10 + category.countryCount * 8 + category.spanYears * 0.5;
  }
  if (objective === "scarcity") {
    return (100 - category.stationCount) * 3 + category.spanYears * 0.6;
  }
  return category.stationCount * 14 + category.countryCount * 10;
}

function getDatasetObjectiveNarrative(objective) {
  if (objective === "trend") return "Trend Analysis mode favors deep historical records and long continuous windows.";
  if (objective === "correlation") return "Correlation Ready mode favors stations and variables that overlap well across the archive.";
  if (objective === "scarcity") return "Scarcity Scan mode helps users inspect the thin or specialized edges of the archive.";
  return "Broad Coverage mode favors robust, high-footprint data that is easiest to work with across the network.";
}

function renderDatasetOverviewWorkbench(model, state) {
  const recommendationEl = document.getElementById("datasetRecommendationPanel");
  const stationListEl = document.getElementById("datasetStationResults");
  const pairListEl = document.getElementById("datasetPairResults");
  const diagnosticsEl = document.getElementById("datasetDiagnostics");
  if (!recommendationEl || !stationListEl || !pairListEl || !diagnosticsEl) return;

  const query = state.search.trim().toLowerCase();

  const filteredStations = model.stationSummaries
    .filter(station => !state.country || station.country === state.country)
    .filter(station => !state.category || station.categories.includes(state.category))
    .filter(station => station.longestSpan >= state.minYears)
    .filter(station => {
      if (!query) return true;
      return station.station.toLowerCase().includes(query)
        || station.country.toLowerCase().includes(query)
        || station.categories.some(category => category.toLowerCase().includes(query));
    })
    .map(station => ({
      ...station,
      objectiveScore: scoreStationForObjective(station, state.objective, state.category),
    }))
    .filter(station => station.objectiveScore >= 0)
    .sort((a, b) => b.objectiveScore - a.objectiveScore)
    .slice(0, 8);

  const filteredCategories = model.categorySummaries
    .filter(category => !state.country || category.countries.includes(state.country))
    .filter(category => !state.category || category.category === state.category)
    .map(category => ({
      ...category,
      objectiveScore: scoreCategoryForObjective(category, state.objective, state.country),
    }))
    .filter(category => category.objectiveScore >= 0)
    .sort((a, b) => b.objectiveScore - a.objectiveScore);

  const filteredPairs = model.categoryPairs
    .filter(pair => !state.category || pair.left === state.category || pair.right === state.category)
    .filter(pair => !state.country || pair.topStations.some(item => item.country === state.country))
    .sort((a, b) => b.overlapCount - a.overlapCount || b.averageSharedYears - a.averageSharedYears)
    .slice(0, 6);

  const topStation = filteredStations[0] || null;
  const topCategory = filteredCategories[0] || null;
  const topPair = filteredPairs[0] || null;
  const latestDecade = model.decadeCards[model.decadeCards.length - 1] || null;

  recommendationEl.innerHTML = `
    <div class="dataset-output-head">
      <div>
        <p class="dataset-section-kicker">Recommendation Engine</p>
        <h4>Best Starting Point For This Goal</h4>
      </div>
      <p>${escapeDatasetHtml(getDatasetObjectiveNarrative(state.objective))}</p>
    </div>
    <div class="dataset-recommend-grid">
      <article class="dataset-recommend-card">
        <span class="dataset-output-label">Recommended Station</span>
        <strong>${escapeDatasetHtml(topStation?.station || "--")}</strong>
        <p>${topStation ? `${topStation.country} | ${topStation.categoryCount} categories | ${topStation.longestSpan} year max span` : "No station matches the current filters."}</p>
      </article>
      <article class="dataset-recommend-card">
        <span class="dataset-output-label">Recommended Category</span>
        <strong>${escapeDatasetHtml(topCategory?.category || "--")}</strong>
        <p>${topCategory ? `${topCategory.stationCount} stations across ${topCategory.countryCount} countries and ${topCategory.spanYears} years.` : "No category matches the current filters."}</p>
      </article>
      <article class="dataset-recommend-card">
        <span class="dataset-output-label">Best Variable Pair</span>
        <strong>${escapeDatasetHtml(topPair ? `${topPair.left} x ${topPair.right}` : "--")}</strong>
        <p>${topPair ? `${topPair.overlapCount} overlapping stations with ${topPair.averageSharedYears} average shared years.` : "No pair is available for the current filters."}</p>
      </article>
    </div>
  `;

  stationListEl.innerHTML = `
    <div class="dataset-output-head">
      <div>
        <p class="dataset-section-kicker">Station Explorer</p>
        <h4>High-Value Stations</h4>
      </div>
      <p>These are the strongest station candidates under the current filters.</p>
    </div>
    <div class="dataset-result-list">
      ${filteredStations.length ? filteredStations.map((station, index) => `
        <article class="dataset-result-card">
          <div class="dataset-result-top">
            <div>
              <span class="dataset-rank">#${index + 1}</span>
              <strong>${escapeDatasetHtml(station.station)}</strong>
              <p>${escapeDatasetHtml(station.country)}</p>
            </div>
            <span class="dataset-score-pill">${Math.round(station.objectiveScore)}</span>
          </div>
          <div class="dataset-result-meta">
            <span>${station.categoryCount} categories</span>
            <span>${station.longestSpan}y max span</span>
            <span>${formatDatasetYearLabel(station.earliest)}-${formatDatasetYearLabel(station.latest)}</span>
          </div>
          <div class="dataset-tag-row">
            ${station.categories.map(category => `<span class="dataset-tag">${escapeDatasetHtml(category)}</span>`).join("")}
          </div>
        </article>
      `).join("") : `<p class="dataset-empty-state">No stations match the current filters.</p>`}
    </div>
  `;

  pairListEl.innerHTML = `
    <div class="dataset-output-head">
      <div>
        <p class="dataset-section-kicker">Compatibility Explorer</p>
        <h4>Category Pairs That Actually Work</h4>
      </div>
      <p>These pairs have enough shared footprint to support joined interpretation.</p>
    </div>
    <div class="dataset-pair-list">
      ${filteredPairs.length ? filteredPairs.map(pair => `
        <article class="dataset-pair-card">
          <div class="dataset-pair-head">
            <strong>${escapeDatasetHtml(pair.left)} x ${escapeDatasetHtml(pair.right)}</strong>
            <span class="dataset-score-pill">${pair.overlapCount} stations</span>
          </div>
          <p>${pair.averageSharedYears} average shared years across overlapping stations.</p>
          <div class="dataset-mini-list">
            ${pair.topStations.map(item => `
              <div class="dataset-mini-item">
                <span>${escapeDatasetHtml(item.station)}</span>
                <strong>${item.sharedYears}y</strong>
              </div>
            `).join("")}
          </div>
        </article>
      `).join("") : `<p class="dataset-empty-state">No category pairs match the current filters.</p>`}
    </div>
  `;

  diagnosticsEl.innerHTML = `
    <div class="dataset-output-head">
      <div>
        <p class="dataset-section-kicker">Coverage Diagnostics</p>
        <h4>What The Current Selection Means</h4>
      </div>
      <p>This explains the practical shape of the filtered archive instead of leaving the user to infer it alone.</p>
    </div>
    <div class="dataset-diagnostic-grid">
      <article class="dataset-diagnostic-card">
        <span class="dataset-output-label">Stations left</span>
        <strong>${filteredStations.length}</strong>
        <p>${filteredCategories.length} categories remain after the current filter stack.</p>
      </article>
      <article class="dataset-diagnostic-card">
        <span class="dataset-output-label">Peak network year</span>
        <strong>${model.topActivity?.year || "--"}</strong>
        <p>${model.topActivity ? `${model.topActivity.activePairs} active links were available at the archive peak.` : "No year summary available."}</p>
      </article>
      <article class="dataset-diagnostic-card">
        <span class="dataset-output-label">Archive window</span>
        <strong>${formatDatasetMonthLabel(model.globalStart)} to ${formatDatasetMonthLabel(model.globalEnd)}</strong>
        <p>${model.globalStart && model.globalEnd ? model.globalEnd.getFullYear() - model.globalStart.getFullYear() + 1 : 0} years of metadata coverage.</p>
      </article>
      <article class="dataset-diagnostic-card">
        <span class="dataset-output-label">Recent decade card</span>
        <strong>${escapeDatasetHtml(latestDecade?.label || "--")}</strong>
        <p>${latestDecade ? `${latestDecade.avgPairs} average links and ${latestDecade.avgStations} average active stations.` : "No decade summary available."}</p>
      </article>
    </div>
    <div class="dataset-decade-row">
      ${model.decadeCards.map(card => `
        <div class="dataset-decade-chip">
          <strong>${escapeDatasetHtml(card.label)}</strong>
          <span>${card.avgPairs} links</span>
          <span>${card.avgStations} stations</span>
        </div>
      `).join("")}
    </div>
  `;
}

function attachDatasetOverviewEvents(model) {
  const objectiveSelect = document.getElementById("datasetObjectiveSelect");
  const countrySelect = document.getElementById("datasetCountrySelect");
  const categorySelect = document.getElementById("datasetCategorySelect");
  const searchInput = document.getElementById("datasetSearchInput");
  const minYearsInput = document.getElementById("datasetMinYearsInput");
  const minYearsValue = document.getElementById("datasetMinYearsValue");
  const resetButton = document.getElementById("datasetResetBtn");
  const quickButtons = document.querySelectorAll("[data-dataset-objective]");

  const state = {
    objective: objectiveSelect?.value || "coverage",
    country: countrySelect?.value || "",
    category: categorySelect?.value || "",
    search: searchInput?.value || "",
    minYears: Number(minYearsInput?.value || 0),
  };

  const syncAndRender = () => {
    state.objective = objectiveSelect?.value || "coverage";
    state.country = countrySelect?.value || "";
    state.category = categorySelect?.value || "";
    state.search = searchInput?.value || "";
    state.minYears = Number(minYearsInput?.value || 0);
    if (minYearsValue) minYearsValue.textContent = `${state.minYears} years`;
    quickButtons.forEach(button => {
      button.classList.toggle("active", button.getAttribute("data-dataset-objective") === state.objective);
    });
    renderDatasetOverviewWorkbench(model, state);
  };

  objectiveSelect?.addEventListener("change", syncAndRender);
  countrySelect?.addEventListener("change", syncAndRender);
  categorySelect?.addEventListener("change", syncAndRender);
  searchInput?.addEventListener("input", syncAndRender);
  minYearsInput?.addEventListener("input", syncAndRender);

  quickButtons.forEach(button => {
    button.addEventListener("click", () => {
      if (objectiveSelect) objectiveSelect.value = button.getAttribute("data-dataset-objective") || "coverage";
      syncAndRender();
    });
  });

  resetButton?.addEventListener("click", () => {
    if (objectiveSelect) objectiveSelect.value = "coverage";
    if (countrySelect) countrySelect.value = "";
    if (categorySelect) categorySelect.value = "";
    if (searchInput) searchInput.value = "";
    if (minYearsInput) minYearsInput.value = "0";
    syncAndRender();
  });

  syncAndRender();
}

async function generateAndDisplayDatasetOverview() {
  try {
    const [coverageData, availabilityData, stationsData] = await Promise.all([
      fetch('/api/coverage').then(r => r.json()),
      fetch('/api/availability').then(r => r.json()),
      fetch('/api/stations/overview').then(r => r.json())
    ]);

    // Populate stats bar with real numbers
    const statsBar = document.getElementById('doStatsBar');
    if (statsBar) {
      const stationCount = stationsData.rows.length;
      const countries = [...new Set(stationsData.rows.map(r => r.country))];
      const minYear = Math.min(...stationsData.rows.map(r => r.first_year));
      const maxYear = Math.max(...stationsData.rows.map(r => r.last_year));
      const varCount = availabilityData.variables.length;

      statsBar.innerHTML = `
        <div class="do-stat-card">
          <div class="do-stat-num">${stationCount}</div>
          <div class="do-stat-label">Stations</div>
        </div>
        <div class="do-stat-card">
          <div class="do-stat-num">${countries.length}</div>
          <div class="do-stat-label">Countries</div>
        </div>
        <div class="do-stat-card">
          <div class="do-stat-num">${minYear}–${maxYear}</div>
          <div class="do-stat-label">Year Range</div>
        </div>
        <div class="do-stat-card">
          <div class="do-stat-num">${varCount}</div>
          <div class="do-stat-label">Variables</div>
        </div>
      `;
    }

    // Shared tooltip element
    if (!document.getElementById('doTooltip')) {
      const tip = document.createElement('div');
      tip.id = 'doTooltip';
      document.body.appendChild(tip);
    }

    // Wire up section nav tabs
    document.querySelectorAll('.do-nav-btn').forEach(btn => {
      btn.addEventListener('click', function () {
        document.querySelectorAll('.do-nav-btn').forEach(b => b.classList.remove('active'));
        this.classList.add('active');
        const target = document.getElementById(this.dataset.target);
        if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    });

    // Render all four sections in parallel
    await Promise.all([
      renderCoverageHeatmap(coverageData),
      renderAvailabilityMatrix(availabilityData),
      renderStationExplorer(stationsData),
      renderProvenanceDisclosure()
    ]);
  } catch (err) {
    console.error('Error loading dataset overview:', err);
  }
}

// ===== SECTION 1: COVERAGE HEATMAP =====
async function renderCoverageHeatmap(data) {
  const container = document.getElementById('datasetCoverageApp');

  container.innerHTML = `
    <div class="do-heatmap-wrap">
      <div class="do-hint">
        <strong>How to read this:</strong> Each row is a station. Each column is a decade (1960s, 1970s…).
        Hover any cell to see the exact completeness percentage for that decade.
        Use the filters below to focus on a specific variable or country.
      </div>
      <div class="do-controls-bar">
        <div class="do-control-field">
          <label class="do-control-label">Show coverage for variable</label>
          <select id="heatmapVariableFilter" class="dropdown">
            <option value="">All Variables (overall)</option>
            ${data.variables.map(v => `<option value="${escapeHtml(v)}">${escapeHtml(v)}</option>`).join('')}
          </select>
        </div>
        <div class="do-control-field">
          <label class="do-control-label">Filter by country</label>
          <select id="heatmapCountryFilter" class="dropdown">
            <option value="">All Countries</option>
            ${data.countries.map(c => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join('')}
          </select>
        </div>
        <div class="do-control-field do-control-field--wide">
          <label class="do-control-label">Hide stations below &nbsp;<span id="heatmapThresholdValue" class="do-threshold-val">0%</span> completeness</label>
          <input id="heatmapThreshold" type="range" min="0" max="100" value="0" class="do-range" />
        </div>
      </div>
      <div class="do-heatmap-grid" id="coverageGrid"></div>
      <div class="do-legend">
        <span class="do-legend-label">No data</span>
        <div class="do-legend-bar"></div>
        <span class="do-legend-label">100% complete</span>
      </div>
    </div>
  `;

  renderCoverageGrid(data);

  document.getElementById('heatmapVariableFilter')?.addEventListener('change', () => renderCoverageGrid(data));
  document.getElementById('heatmapCountryFilter')?.addEventListener('change', () => renderCoverageGrid(data));
  document.getElementById('heatmapThreshold')?.addEventListener('input', (e) => {
    document.getElementById('heatmapThresholdValue').textContent = e.target.value + '%';
    renderCoverageGrid(data);
  });
}

function renderCoverageGrid(data) {
  const grid = document.getElementById('coverageGrid');
  const varFilter = document.getElementById('heatmapVariableFilter')?.value || '';
  const countryFilter = document.getElementById('heatmapCountryFilter')?.value || '';
  const threshold = parseInt(document.getElementById('heatmapThreshold')?.value || 0);

  const filtered = data.stations.filter(s => !countryFilter || s.country === countryFilter);

  let html = '<div class="do-heatmap-header"><span class="do-corner">Station</span>';
  data.decades.forEach(d => html += `<div class="do-decade-col">${d}s</div>`);
  html += '</div>';

  filtered.forEach(station => {
    html += `<div class="do-heatmap-row"><span class="do-station-name-col">${escapeHtml(station.station_name)}</span>`;

    station.cells.forEach(cell => {
      let pct = cell.overall_pct;
      if (varFilter && cell.by_variable[varFilter] !== undefined) {
        pct = cell.by_variable[varFilter];
      }

      const faded = pct !== null && pct < threshold;
      // Teal/blue water theme: light (no data) → deep teal (complete)
      const bg = pct === null
        ? 'var(--bg-subtle)'
        : `hsl(197, ${40 + pct * 0.38}%, ${93 - pct * 0.30}%)`;
      const tip = `${escapeHtml(station.station_name)} · ${cell.decade}s: ${pct !== null ? pct + '% complete' : 'No data'}`;

      html += `<div class="do-heatmap-cell${faded ? ' do-cell-faded' : ''}" style="background:${bg}" data-tip="${tip}"></div>`;
    });
    html += '</div>';
  });

  grid.innerHTML = html;

  // Attach tooltip handlers
  const tip = document.getElementById('doTooltip');
  grid.querySelectorAll('.do-heatmap-cell[data-tip]').forEach(cell => {
    cell.addEventListener('mouseenter', (e) => {
      tip.textContent = cell.dataset.tip;
      tip.classList.add('visible');
    });
    cell.addEventListener('mousemove', (e) => {
      tip.style.left = (e.clientX + 14) + 'px';
      tip.style.top = (e.clientY - 32) + 'px';
    });
    cell.addEventListener('mouseleave', () => tip.classList.remove('visible'));
  });
}

// ===== SECTION 2: AVAILABILITY MATRIX =====
async function renderAvailabilityMatrix(data) {
  const container = document.getElementById('datasetAvailabilityApp');

  container.innerHTML = `
    <div class="do-availability-wrap">
      <div class="do-hint">
        <strong>How to read this:</strong> Find your station in the left column.
        Look across the row — colored cells mean that variable was measured there.
        The number shows how many years of data exist. Gray cells mean the variable was never recorded at that station.
        <br><strong>Example:</strong> If you want to compare discharge vs. water level, both columns must be colored in the same row.
      </div>
      <div class="do-controls-bar">
        <div class="do-control-field do-control-field--wide">
          <label class="do-control-label">Only show stations with at least &nbsp;<span id="minYearsValue" class="do-threshold-val">0 years</span> of data for a variable</label>
          <input id="minYearsSlider" type="range" min="0" max="60" value="0" class="do-range" />
        </div>
      </div>
      <div class="do-matrix-scroll" id="availabilityMatrix"></div>
    </div>
  `;

  renderAvailabilityMatrixTable(data);

  document.getElementById('minYearsSlider')?.addEventListener('input', (e) => {
    document.getElementById('minYearsValue').textContent = e.target.value + ' years';
    renderAvailabilityMatrixTable(data);
  });
}

function renderAvailabilityMatrixTable(data) {
  const matrix = document.getElementById('availabilityMatrix');
  const minYears = parseInt(document.getElementById('minYearsSlider')?.value || 0);
  const filtered = data.rows.filter(row =>
    Object.values(row.variables).some(cell => cell && cell.years >= minYears)
  );

  const tip = document.getElementById('doTooltip');

  let html = '<table class="do-avail-table"><thead><tr><th>Station</th>';
  data.variables.forEach(v => html += `<th>${escapeHtml(v)}</th>`);
  html += '</tr></thead><tbody>';

  filtered.forEach(row => {
    html += `<tr><td class="do-station-cell">${escapeHtml(row.station_name)}<small>${escapeHtml(row.country)}</small></td>`;
    data.variables.forEach(v => {
      const cell = row.variables[v];
      const years = cell?.years || 0;
      const density = cell?.density_pct || 0;
      // Teal water theme matching heatmap
      const bg = !cell || years === 0
        ? 'var(--bg-subtle)'
        : `hsl(197, ${40 + density * 0.38}%, ${93 - density * 0.30}%)`;
      const tipText = cell ? `${years}y · ${density}% density` : 'No data';
      html += `<td style="background:${bg}" data-tip="${escapeHtml(row.station_name)} / ${escapeHtml(v)}: ${tipText}">${years > 0 ? years + 'y' : '—'}</td>`;
    });
    html += '</tr>';
  });
  html += '</tbody></table>';

  matrix.innerHTML = html;

  // Tooltip on matrix cells
  matrix.querySelectorAll('td[data-tip]').forEach(cell => {
    cell.addEventListener('mouseenter', () => {
      tip.textContent = cell.dataset.tip;
      tip.classList.add('visible');
    });
    cell.addEventListener('mousemove', (e) => {
      tip.style.left = (e.clientX + 14) + 'px';
      tip.style.top = (e.clientY - 32) + 'px';
    });
    cell.addEventListener('mouseleave', () => tip.classList.remove('visible'));
  });
}

// ===== SECTION 3: STATION EXPLORER =====
async function renderStationExplorer(data) {
  const container = document.getElementById('datasetStationExplorerApp');
  const countries = [...new Set(data.rows.map(r => r.country))].sort();

  container.innerHTML = `
    <div class="do-explorer-wrap">
      <div class="do-hint">
        <strong>How to use:</strong> Sort by <em>Longest Records</em> to find stations with the most data,
        or by <em>Most Variables</em> to find the richest stations.
        Click any row to expand it and see which variables were measured — then click
        <em>Open in Visualization Builder</em> to start charting.
        <br><strong>Ratings:</strong> Excellent = long records + multiple variables. Strong = solid coverage. Limited = short or sparse data — use with caution.
      </div>
      <div class="do-explorer-controls">
        <input id="stationSearch" type="text" placeholder="Search by station name or country…" class="dropdown" />
        <select id="stationCountryFilter" class="dropdown">
          <option value="">All Countries</option>
          ${countries.map(c => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join('')}
        </select>
        <select id="stationSort" class="dropdown">
          <option value="name">Sort: A–Z</option>
          <option value="years">Longest Records first</option>
          <option value="variables">Most Variables first</option>
        </select>
      </div>
      <div class="do-explorer-count" id="stationCount"></div>
      <div class="do-station-list" id="stationTable"></div>
    </div>
  `;

  renderStationTable(data);

  document.getElementById('stationSearch')?.addEventListener('input', () => renderStationTable(data));
  document.getElementById('stationCountryFilter')?.addEventListener('change', () => renderStationTable(data));
  document.getElementById('stationSort')?.addEventListener('change', () => renderStationTable(data));
}

function renderStationTable(data) {
  const table = document.getElementById('stationTable');
  const countEl = document.getElementById('stationCount');
  const search = document.getElementById('stationSearch')?.value.toLowerCase() || '';
  const countryFilter = document.getElementById('stationCountryFilter')?.value || '';
  const sort = document.getElementById('stationSort')?.value || 'name';

  let rows = [...data.rows];

  if (search) {
    rows = rows.filter(r =>
      r.station_name.toLowerCase().includes(search) ||
      r.country.toLowerCase().includes(search)
    );
  }
  if (countryFilter) {
    rows = rows.filter(r => r.country === countryFilter);
  }

  rows.sort((a, b) => {
    if (sort === 'years') return (b.last_year - b.first_year) - (a.last_year - a.first_year);
    if (sort === 'variables') return b.variable_count - a.variable_count;
    return a.station_name.localeCompare(b.station_name);
  });

  if (countEl) {
    countEl.textContent = rows.length
      ? `${rows.length} station${rows.length !== 1 ? 's' : ''} — click any row to expand and see which variables were measured`
      : '';
  }

  if (!rows.length) {
    table.innerHTML = '<div class="do-explorer-empty">No stations match your filters. Try clearing the search or changing the country.</div>';
    return;
  }

  let html = '';
  rows.forEach((row, idx) => {
    const years = row.last_year - row.first_year + 1;
    const strength = getStationStrength(row.variable_count, years);
    const pillClass = strength === 'Excellent' ? 'do-strength-excellent' : strength === 'Strong' ? 'do-strength-strong' : 'do-strength-limited';

    const badges = row.per_variable_badges.map(b => {
      const pct = b.completeness_pct;
      const quality = pct >= 80 ? 'do-badge-good' : pct >= 40 ? 'do-badge-partial' : 'do-badge-sparse';
      return `<span class="do-var-badge ${quality}" title="${escapeHtml(b.variable)}: ${pct}% of years have data">${escapeHtml(b.variable)} <span class="do-badge-pct">${pct}%</span></span>`;
    }).join('');

    const badgesNote = row.per_variable_badges.length
      ? '<p class="do-expanded-note">Each badge shows a variable and its data completeness (% of years with records).</p>'
      : '<p class="do-expanded-note">No variable detail available for this station.</p>';

    html += `
      <div class="do-station-row" data-idx="${idx}">
        <div class="do-station-hd">
          <div>
            <div class="do-stn-name">${escapeHtml(row.station_name)}</div>
            <div class="do-stn-meta">${escapeHtml(row.country)} · ${row.first_year}–${row.last_year} (${years} years)</div>
          </div>
          <div class="do-stn-stats">
            <span class="do-stn-stat">${row.variable_count} variable${row.variable_count !== 1 ? 's' : ''} measured</span>
            <span class="do-strength-pill ${pillClass}" title="Excellent = long records + multiple variables. Strong = solid. Limited = short or sparse.">${strength}</span>
          </div>
          <span class="do-expand-chevron">›</span>
        </div>
        <div class="do-station-body">
          <div class="do-station-body-inner">
            ${badgesNote}
            <div class="do-var-badges">${badges}</div>
            <button class="primary-btn" onclick="window.goToBuilder('${escapeHtml(row.station_name)}')">Open in Visualization Builder →</button>
          </div>
        </div>
      </div>
    `;
  });

  table.innerHTML = html;

  table.querySelectorAll('.do-station-hd').forEach(hd => {
    hd.addEventListener('click', function () {
      const row = this.closest('.do-station-row');
      const isOpen = row.classList.contains('open');
      // Close all
      table.querySelectorAll('.do-station-row').forEach(r => r.classList.remove('open'));
      // Open clicked one if it was closed
      if (!isOpen) row.classList.add('open');
    });
  });
}

function getStationStrength(variables, years) {
  const score = variables * years / 10;
  if (score > 30) return 'Excellent';
  if (score > 15) return 'Strong';
  return 'Limited';
}

// ===== SECTION 4: PROVENANCE DISCLOSURE =====
async function renderProvenanceDisclosure() {
  const container = document.getElementById('datasetProvenanceApp');

  container.innerHTML = `
    <div class="do-provenance-wrap">
      <div class="do-accordion">

        <div class="do-acc-panel open">
          <div class="do-acc-header">
            Where does this data come from?
            <span class="do-acc-chevron">▾</span>
          </div>
          <div class="do-acc-body">
            <div class="do-acc-body-inner">
              <p>Data comes from <strong>national water authorities</strong> in Thailand, Laos, Cambodia, and Vietnam, coordinated through the <strong>Mekong River Commission (MRC)</strong>. Each country operates its own monitoring network; records typically span from 1960 to present depending on the station.</p>
              <ul>
                <li><strong>Thailand:</strong> Royal Irrigation Department</li>
                <li><strong>Laos:</strong> Department of Meteorology &amp; Hydrology</li>
                <li><strong>Cambodia:</strong> Ministry of Water Resources</li>
                <li><strong>Vietnam:</strong> Institute of Meteorology &amp; Hydrology</li>
              </ul>
            </div>
          </div>
        </div>

        <div class="do-acc-panel">
          <div class="do-acc-header">
            What are the known issues I should be aware of?
            <span class="do-acc-chevron">▾</span>
          </div>
          <div class="do-acc-body">
            <div class="do-acc-body-inner">
              <div class="limitation">
                <span class="severity-badge severity-high">Critical</span>
                <span><strong>Pre-2000 records are unreliable for trend analysis.</strong> Equipment quality varied significantly before 2000, especially water level readings at Laotian stations. Use these with caution for any long-term trend work.</span>
              </div>
              <div class="limitation">
                <span class="severity-badge severity-medium">Important</span>
                <span><strong>Some stations have multi-year gaps.</strong> Political instability or equipment failures caused 5–10 year blackouts at certain sites. Always check the heatmap first before committing to a station for your analysis.</span>
              </div>
              <div class="limitation">
                <span class="severity-badge severity-low">Minor</span>
                <span><strong>Discharge timestamps may be off by up to ±4 hours.</strong> This is negligible for monthly or annual analysis, but worth noting if you're doing daily-level work.</span>
              </div>
            </div>
          </div>
        </div>

        <div class="do-acc-panel">
          <div class="do-acc-header">
            Can I use this data for my specific analysis?
            <span class="do-acc-chevron">▾</span>
          </div>
          <div class="do-acc-body">
            <div class="do-acc-body-inner">
              <p style="margin-bottom:14px; color: var(--text-secondary); font-size:0.85rem;">🟢 Yes = reliable for this use &nbsp;·&nbsp; 🟡 With care = possible but check limitations &nbsp;·&nbsp; 🔴 No = data quality insufficient</p>
              <table class="suitability-table">
                <thead>
                  <tr><th>What I want to do</th><th>Discharge</th><th>Water Level</th><th>Rainfall</th><th>Sediment</th></tr>
                </thead>
                <tbody>
                  <tr><td>Analyze trends over decades</td><td>🟢 Yes</td><td>🟢 Yes</td><td>🟡 With care</td><td>🔴 No</td></tr>
                  <tr><td>Correlate two variables</td><td colspan="4">🟢 Yes — as long as both are measured at the same station (check the matrix above)</td></tr>
                  <tr><td>Forecast the next month</td><td>🟡 Limited</td><td>🟢 Good</td><td>🟡 Limited</td><td>🔴 No</td></tr>
                  <tr><td>Compare upstream vs. downstream</td><td>🟢 Yes</td><td>🟢 Yes</td><td>🔴 No</td><td>🔴 No</td></tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>

      </div>
    </div>
  `;

  // CSS-based accordion — toggle .open class only
  container.querySelectorAll('.do-acc-header').forEach(header => {
    header.addEventListener('click', function () {
      const panel = this.closest('.do-acc-panel');
      const isOpen = panel.classList.contains('open');
      container.querySelectorAll('.do-acc-panel').forEach(p => p.classList.remove('open'));
      if (!isOpen) panel.classList.add('open');
    });
  });
}

// ===== HELPER =====
function escapeHtml(text) {
  const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
  return String(text).replace(/[&<>"']/g, m => map[m]);
}

// Add to window for onclick handlers
// Override the goToBuilder function to accept station pre-population
window.goToBuilder = function(stationName) {
  // Navigate to builder section
  setSectionVisible(builderSection);
  setActiveNav(".custom-visualization-setup-icon");

  if (stationName) {
    // Set default graph option if not already selected
    if (!graphOptionsDropdown.value) {
      graphOptionsDropdown.value = "Single Category, Single Station Timeline";
      graphOptionsDropdown.dispatchEvent(new Event("change"));
    }

    // Wait a moment for categories to populate
    setTimeout(() => {
      // Populate station dropdown
      stationDropdown.value = stationName;

      // Show available categories for this station
      const stationData = categoryDetailsMap[Object.keys(categoryDetailsMap)[0]]?.find(
        row => row.station_name === stationName
      );

      if (stationData) {
        // Highlight first available category
        const firstCategory = Object.keys(categoryDetailsMap)[0];
        if (firstCategory && categoryDropdown) {
          categoryDropdown.value = firstCategory;
        }
      }

      // Scroll to the builder section
      builderSection.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 300);
  }
};


function initializeMap() {
  map = L.map("map", {
    minZoom: 4,
    maxZoom: 18,
    zoomControl: false
  }).setView([16.5, 103.5], 7);

  L.control.zoom({ position: 'topright' }).addTo(map);

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
  currentTileLayer.once('load', () => {
    setTimeout(renderInitialMapStations, 0);
  });

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

  map.whenReady(() => {
    setTimeout(renderInitialMapStations, 0);
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

function bindSectionTriggers(selector, section, callback) {
  document.querySelectorAll(selector).forEach(element => {
    element.addEventListener("click", () => {
      setSectionVisible(section);
      setActiveNav(selector);
      if (callback) callback();
    });
  });
}

function setupNavigation() {
  bindSectionTriggers(".user-guide-icon", overviewSection);
  bindSectionTriggers(".custom-visualization-setup-icon", builderSection);
  bindSectionTriggers(".visualization-dashboard-icon", dashboardSection);
  bindSectionTriggers(".prediction-icon", predictionSection);
  bindSectionTriggers(".analyze-section-icon", analyzeSection);
  bindSectionTriggers(".correlation-icon", correlationSection);
  bindSectionTriggers(".seasonal-icon", seasonalSection);
  bindSectionTriggers(".export-icon", exportSection);
  bindSectionTriggers(".dataset-overview-icon", datasetOverviewSection, () => generateAndDisplayDatasetOverview());
  bindSectionTriggers(".research-icon", researchSection);
  bindSectionTriggers(".about-us-icon", aboutSection);
  bindSectionTriggers(".news-icon", newsSection, () => loadNewsSection());
}

function setupBuilderEvents() {
  categoryDropdown.disabled = true;
  stationDropdown.disabled = false;
  startVisualizationBtn.style.display = "inline-block";

  const handleGraphTypeChange = function() {
    selectedGraphOption = getCurrentBuilderGraphName();
    updateBuilderSummary();
    refreshBuilderRequirements();

    const graphConfig = getSelectedGraphConfig();
    if (!graphConfig) {
      hasAutoAddCategories = false;
      categorySelectionDiv.style.display = "block";
      categoryDropdown.disabled = true;
      selectedCategories = [];
      selectedStationEntries = [];
      renderSelectedCategories();
      renderSelectedStations();
      showCategoryOptionsOnUI();
      return;
    }

    hasAutoAddCategories = false;
    categorySelectionDiv.style.display = "block";
    categoryDropdown.disabled = !selectedStations.length;
    const availableCategories = new Set(getAvailableCategoriesForStations());
    selectedCategories = selectedCategories.filter(category => availableCategories.has(category));

    if (graphConfig.number_of_stations_allow !== "All" && selectedStations.length > graphConfig.number_of_stations_allow) {
      selectedStations = selectedStations.slice(0, graphConfig.number_of_stations_allow);
      showAlert(oneStationOnlyAlert);
    }

    if (
      graphConfig.number_of_categories_allow !== "All" &&
      selectedCategories.length > graphConfig.number_of_categories_allow
    ) {
      selectedCategories = selectedCategories.slice(0, graphConfig.number_of_categories_allow);
      showAlert(oneCategoryOnlyAlert);
    }

    showStationOptionsOnUI(ALL_CATEGORIES);
    showCategoryOptionsOnUI();
    rebuildSelectedStationEntries();
    renderSelectedCategories();
    renderSelectedStations();
  };

  graphOptionsDropdown.addEventListener("change", handleGraphTypeChange);
  graphOptionsDropdown.addEventListener("input", handleGraphTypeChange);

  stationDropdown.addEventListener("change", () => {
    const selectedStation = getCurrentBuilderStationName();
    if (!selectedStation || selectedStation.toLowerCase().startsWith("select ")) return;
    handleAddStationSelection();
  });

  addCategoryBtn.addEventListener("click", handleAddCategorySelection);

  addStationBtn.addEventListener("click", handleAddStationSelection);

  addToDashboardBtn.addEventListener("click", function() {
    if (!selectedGraphOption || !selectedStationEntries.length || !selectedCategories.length) {
      showAlert(selectCategoryAndStationAlert);
      return;
    }

    // Validate graph requirements
    const validation = validateGraphRequirements();
    if (!validation.valid) {
      showAlert(createCustomAlert(validation.error));
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
// AI ANALYSIS
// ------------------------------
let lastSummaryForAI = null;
let lastRankingForAI = [];

function setupAiAnalysis() {
  const btn = document.getElementById('run-ai-analysis-btn');
  const body = document.getElementById('ai-analysis-body');
  if (!btn || !body) return;

  btn.addEventListener('click', async () => {
    if (!lastSummaryForAI) {
      body.innerHTML = '<p class="ai-analysis-error">Generate a visualization first before running AI analysis.</p>';
      return;
    }
    btn.disabled = true;
    btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="animation:spin 1s linear infinite"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg> Analyzing...`;
    body.innerHTML = '<p class="ai-analysis-placeholder">AI is analyzing your data...</p>';

    try {
      const res = await fetch('/analyze_with_ai', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          summary: lastSummaryForAI,
          ranking: lastRankingForAI,
          graph_type: azSelectedGraph || 'Unknown',
          stations: azSelectedStations || [],
          categories: azSelectedCategories || []
        })
      });
      const data = await res.json();
      if (data.error) throw new Error(data.error);

      const paragraphs = data.analysis.split('\n').filter(p => p.trim()).map(p =>
        `<p class="ai-para">${p.trim()}</p>`
      ).join('');
      body.innerHTML = paragraphs;
      setExportSessionReport('dashboard', data.analysis, paragraphs);
    } catch (err) {
      body.innerHTML = `<p class="ai-analysis-error">Analysis failed: ${err.message}. Make sure ANTHROPIC_API_KEY is set.</p>`;
    } finally {
      btn.disabled = false;
      btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"/></svg> Analyze with AI`;
    }
  });
}

// ------------------------------
// ANALYZE SECTION
// ------------------------------
let azSelectedGraph = null;
let azSelectedCategories = [];
let azSelectedStations = [];

function azRenderSummary() {
  const graphEl = document.getElementById('az-graph-preview');
  const catEl   = document.getElementById('az-categories-preview');
  const staEl   = document.getElementById('az-stations-preview');
  if (graphEl) graphEl.textContent = azSelectedGraph || 'No graph selected yet';
  if (catEl)   catEl.textContent   = azSelectedCategories.length || '0';
  if (staEl)   staEl.textContent   = azSelectedStations.length || '0';
}

function azRenderTags(containerId, items, onRemove) {
  const container = document.getElementById(containerId);
  if (!container) return;
  container.innerHTML = items.map((item, i) =>
    `<span class="selected-tag">${item}<button class="tag-remove-btn" data-index="${i}" aria-label="Remove">×</button></span>`
  ).join('');
  container.querySelectorAll('.tag-remove-btn').forEach(btn => {
    btn.addEventListener('click', () => onRemove(parseInt(btn.dataset.index)));
  });
}

function azUpdateGraphConstraints() {
  const config = graphTypeOptions.find(o => o.name === azSelectedGraph);
  if (!config) return;

  const catDiv = document.getElementById('az-category-selection-div');
  if (config.auto_add_categories) {
    azSelectedCategories = [...categoryNameList];
    catDiv && (catDiv.style.display = 'none');
  } else {
    catDiv && (catDiv.style.display = '');
  }

  // Enforce limits
  const maxCat = config.number_of_categories_allow;
  const maxSta = config.number_of_stations_allow;
  if (maxCat !== 'All' && azSelectedCategories.length > maxCat) azSelectedCategories = azSelectedCategories.slice(0, maxCat);
  if (maxSta !== 'All' && azSelectedStations.length > maxSta)   azSelectedStations   = azSelectedStations.slice(0, maxSta);

  azRenderTags('az-selected-categories', azSelectedCategories, (i) => {
    azSelectedCategories.splice(i, 1);
    azRenderTags('az-selected-categories', azSelectedCategories, arguments.callee);
    azRenderSummary();
  });
  azRenderTags('az-selected-stations', azSelectedStations, (i) => {
    azSelectedStations.splice(i, 1);
    azRenderTags('az-selected-stations', azSelectedStations, arguments.callee);
    azRenderSummary();
  });
  azRenderSummary();
}

function showPredictionAnalysis(analysis, source) {
  const panel = document.getElementById('pred-analysis-panel');
  const body  = document.getElementById('pred-analysis-body');
  if (!panel || !body || !analysis) return;
  const sourceTag = source === 'gemini'
    ? '<span class="analysis-source-tag gemini-tag">Gemini AI</span>'
    : '<span class="analysis-source-tag fallback-tag">Pre-plan Analysis</span>';
  body.innerHTML = sourceTag + azBuildAnalysisReport(analysis);
  panel.classList.remove('hidden');
  setExportSessionReport('forecast', analysis, body.innerHTML);
}

function azBuildAnalysisReport(text) {
  // Parse section headers (e.g. "Data Quality and Coverage Assessment:")
  const sectionPattern = /^([A-Z][^:\n]{5,80}):[ \t]*$/gm;
  const parts = [];
  let lastIndex = 0;
  let match;
  const plainText = text.trim();
  const matches = [];
  let m;
  const re = /^([A-Z][^:\n]{5,80}):[ \t]*$/gm;
  while ((m = re.exec(plainText)) !== null) matches.push(m);

  if (matches.length === 0) {
    // Fallback: plain paragraphs
    return plainText.split(/\n+/).filter(p => p.trim()).map(p =>
      `<p class="az-para">${p.trim()}</p>`
    ).join('');
  }

  let html = '';
  matches.forEach((match, idx) => {
    const headerStart = match.index;
    const contentStart = headerStart + match[0].length;
    const contentEnd = idx + 1 < matches.length ? matches[idx + 1].index : plainText.length;
    const header = match[1].trim();
    const body = plainText.slice(contentStart, contentEnd).trim();
    const paras = body.split(/\n+/).filter(p => p.trim()).map(p =>
      `<p class="az-para">${p.trim()}</p>`
    ).join('');
    html += `<div class="az-section"><h4 class="az-section-title">${header}</h4>${paras}</div>`;
  });
  return html;
}

function setupAnalyzeEvents() {
  const graphSelect = document.getElementById('az-options-select');
  const catSelect   = document.getElementById('az-categories-select');
  const staSelect   = document.getElementById('az-stations-select');
  const addCatBtn   = document.getElementById('az-add-category-btn');
  const addStaBtn   = document.getElementById('az-add-station-btn');
  const generateBtn = document.getElementById('az-generate-btn');

  if (!graphSelect) return;

  // Populate graph type dropdown (same options as builder)
  graphTypeOptions.forEach(opt => {
    const o = document.createElement('option');
    o.value = opt.name;
    o.textContent = opt.name;
    graphSelect.appendChild(o);
  });

  // Populate categories
  categoryNameList.forEach(cat => {
    const o = document.createElement('option');
    o.value = cat; o.textContent = cat;
    catSelect.appendChild(o);
  });

  // Populate stations
  stationNameList.forEach(sta => {
    const o = document.createElement('option');
    o.value = sta; o.textContent = sta;
    staSelect.appendChild(o);
  });

  graphSelect.addEventListener('change', function() {
    azSelectedGraph = this.value;
    azSelectedCategories = [];
    azSelectedStations = [];
    displayGraphRequirementsForAnalyze(azSelectedGraph);
    azUpdateGraphConstraints();
  });

  addCatBtn?.addEventListener('click', () => {
    const val = catSelect.value;
    if (!val) return;
    const config = graphTypeOptions.find(o => o.name === azSelectedGraph);
    const max = config?.number_of_categories_allow;
    if (max !== 'All' && azSelectedCategories.length >= max) {
      showAlert(document.getElementById('az-one-category-alert'));
      return;
    }
    if (!azSelectedCategories.includes(val)) {
      azSelectedCategories.push(val);
      azRenderTags('az-selected-categories', azSelectedCategories, (i) => {
        azSelectedCategories.splice(i, 1);
        azRenderTags('az-selected-categories', azSelectedCategories, () => {});
        azRenderSummary();
      });
      azRenderSummary();
    }
  });

  addStaBtn?.addEventListener('click', () => {
    const val = staSelect.value;
    if (!val) return;
    const config = graphTypeOptions.find(o => o.name === azSelectedGraph);
    const max = config?.number_of_stations_allow;
    if (max !== 'All' && azSelectedStations.length >= max) {
      showAlert(document.getElementById('az-one-station-alert'));
      return;
    }
    if (!azSelectedStations.includes(val)) {
      azSelectedStations.push(val);
      azRenderTags('az-selected-stations', azSelectedStations, (i) => {
        azSelectedStations.splice(i, 1);
        azRenderTags('az-selected-stations', azSelectedStations, () => {});
        azRenderSummary();
      });
      azRenderSummary();
    }
  });

  generateBtn?.addEventListener('click', async () => {
    if (!azSelectedGraph || azSelectedCategories.length === 0 || azSelectedStations.length === 0) {
      showAlert(document.getElementById('az-no-selection-alert'));
      return;
    }

    // Validate graph requirements for Analyze section
    const config = graphTypeOptions.find(o => o.name === azSelectedGraph);
    if (config) {
      if (config.number_of_categories_allow !== "All" && azSelectedCategories.length < config.number_of_categories_allow) {
        createCustomAlert(`This visualization requires ${config.number_of_categories_allow} categor${config.number_of_categories_allow === 1 ? 'y' : 'ies'}, but you selected ${azSelectedCategories.length}.`);
        return;
      }
      if (config.number_of_stations_allow !== "All" && azSelectedStations.length < config.number_of_stations_allow) {
        createCustomAlert(`This visualization requires ${config.number_of_stations_allow} station${config.number_of_stations_allow === 1 ? '' : 's'}, but you selected ${azSelectedStations.length}.`);
        return;
      }
    }

    generateBtn.disabled = true;
    generateBtn.innerHTML = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="animation:spin 1s linear infinite;vertical-align:middle;margin-right:6px;"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>Generating…`;

    const chartContainer = document.getElementById('az-chart-container');
    const analysisPanel  = document.getElementById('az-analysis-panel');
    const analysisBody   = document.getElementById('az-analysis-body');
    const loadingEl      = document.getElementById('az-analysis-loading');

    chartContainer?.classList.add('hidden');
    analysisPanel?.classList.add('hidden');

    // Build viz payload — attach date range from categoryDetailsMap for each pair
    const dataEntries = azSelectedCategories.flatMap(cat =>
      azSelectedStations.flatMap(sta => {
        const detail = getCategoryDateRange(cat, sta);
        if (!detail) return [];  // skip pairs with no known date range
        return [{
          category_name: cat,
          station_name: sta,
          start_date: formatDateToDDMMYYYY(detail.start_date),
          end_date:   formatDateToDDMMYYYY(detail.end_date),
        }];
      })
    );
    if (dataEntries.length === 0) {
      analysisBody.innerHTML = '<p class="az-error">No data available for the selected station and category combination.</p>';
      analysisPanel?.classList.remove('hidden');
      generateBtn.disabled = false;
      generateBtn.innerHTML = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;margin-right:6px;"><path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20z"/><path d="M12 8v4l3 3"/></svg>Generate Analysis`;
      return;
    }
    const payload = [{ graph_type: azSelectedGraph, data: dataEntries }];

    try {
      // Step 1: generate chart
      const vizRes  = await fetch('/generate_visualization', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const vizData = await vizRes.json();
      if (vizData.error) throw new Error(vizData.error);

      const charts  = vizData.charts || [];
      const summary = vizData.summary || {};
      const ranking = vizData.ranking || [];

      if (charts.length > 0) {
        chartContainer?.classList.remove('hidden');
        Plotly.newPlot('az-chart', JSON.parse(charts[0]), {}, { responsive: true });
      }
      setExportSessionPayload('analyze', {
        charts: charts.slice(0, 1),
        title: 'Analysis Builder',
        reportHtml: '',
        reportText: '',
        meta: [
          { label: 'Visualization type', value: azSelectedGraph },
          { label: 'Stations', value: azSelectedStations.join(', ') },
          { label: 'Categories', value: azSelectedCategories.join(', ') },
          { label: 'Returned charts', value: String(charts.length) },
          { label: 'Coverage window', value: summary?.date_range || '--' },
        ],
      });

      // Step 2: AI analysis
      analysisPanel?.classList.remove('hidden');
      analysisBody.innerHTML = '';
      loadingEl?.classList.remove('hidden');

      const aiRes  = await fetch('/analyze_with_ai', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          summary,
          ranking,
          graph_type: azSelectedGraph,
          stations: azSelectedStations,
          categories: azSelectedCategories
        })
      });
      const aiData = await aiRes.json();
      loadingEl?.classList.add('hidden');

      if (aiData.error) throw new Error(aiData.error);
      analysisBody.innerHTML = azBuildAnalysisReport(aiData.analysis);
      setExportSessionReport('analyze', aiData.analysis, analysisBody.innerHTML);

    } catch (err) {
      loadingEl?.classList.add('hidden');
      analysisPanel?.classList.remove('hidden');
      analysisBody.innerHTML = `<p class="az-error">Error: ${err.message}. Make sure GEMINI_API_KEY is set.</p>`;
    } finally {
      generateBtn.disabled = false;
      generateBtn.innerHTML = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;margin-right:6px;"><path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20z"/><path d="M12 8v4l3 3"/></svg>Generate Analysis`;
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

function setupSidebarToggle() {
  const sidebar = document.getElementById('sidebar');
  const toggleBtn = document.getElementById('sidebar-toggle');
  if (!sidebar || !toggleBtn) return;

  const STORAGE_KEY = 'sidebarCollapsed';
  if (localStorage.getItem(STORAGE_KEY) === 'true') {
    sidebar.classList.remove('expanded');
    sidebar.classList.add('collapsed');
  }

  toggleBtn.addEventListener('click', () => {
    const isCollapsed = sidebar.classList.contains('collapsed');
    if (isCollapsed) {
      sidebar.classList.remove('collapsed');
      sidebar.classList.add('expanded');
      localStorage.setItem(STORAGE_KEY, 'false');
    } else {
      sidebar.classList.remove('expanded');
      sidebar.classList.add('collapsed');
      localStorage.setItem(STORAGE_KEY, 'true');
    }
    // Let Plotly charts reflow after sidebar transition
    setTimeout(() => window.dispatchEvent(new Event('resize')), 260);
  });
}

function setupThemeToggle() {
  document.getElementById('theme-toggle-btn')?.addEventListener('click', () => {
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    applyTheme(!isDark);
  });
  if (localStorage.getItem('theme') === 'dark') applyTheme(true);
}

function setupMapExpandButton() {
  const expandBtn = document.getElementById('map-expand-btn');
  const mapView = document.getElementById('map-view');
  if (!expandBtn || !mapView) return;

  expandBtn.addEventListener('click', () => {
    mapView.classList.toggle('map-expanded');
    if (mapView.classList.contains('map-expanded')) {
      expandBtn.setAttribute('title', 'Click to collapse map');
    } else {
      expandBtn.setAttribute('title', 'Click to expand map to fullscreen');
    }
    // Trigger map resize to recalculate dimensions
    if (map) {
      setTimeout(() => map.invalidateSize(), 100);
    }
  });
}

// ------------------------------
// PREDICTION
// ------------------------------

// ML station map: { "Station Name": ["Category", ...] }  — fetched once at load
let mlStationMap = {};

async function loadMLStationMap() {
  try {
    const res = await fetch('/ml_stations');
    mlStationMap = await res.json();
  } catch (e) {
    mlStationMap = {};
  }
}

function populatePredMLDropdowns() {
  const predStation  = document.getElementById('pred-station-select');
  const predCategory = document.getElementById('pred-category-select');
  if (!predStation || !predCategory) return;

  predStation.innerHTML = '<option value="">Select a station...</option>';
  Object.keys(mlStationMap).sort().forEach(name => {
    const opt = document.createElement('option');
    opt.value = name; opt.textContent = name;
    predStation.appendChild(opt);
  });

  predCategory.innerHTML = '<option value="">Select a category...</option>';
}

function updatePredMLCategoriesForStation(stationName) {
  const predCategory = document.getElementById('pred-category-select');
  if (!predCategory) return;
  predCategory.innerHTML = '<option value="">Select a category...</option>';
  const cats = stationName ? (mlStationMap[stationName] || []) : [];
  cats.forEach(name => {
    const opt = document.createElement('option');
    opt.value = name; opt.textContent = name;
    predCategory.appendChild(opt);
  });
}

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

const MODEL_META = {
  holt_winters: {
    label: "Holt-Winters Prediction",
    desc: "<strong>Holt-Winters</strong> — Triple exponential smoothing that decomposes the series into level, trend, and seasonal components. Best for data with clear seasonal patterns.",
    infoCards: (info) => [
      ["Model", info.model_type],
      ["Historical data", `${info.historical_months} months`],
      ["Forecast period", `${info.last_historical} → ${info.forecast_end}`],
      ["AIC", info.aic],
      ["RMSE", info.rmse],
      ["α (level)", info.alpha],
      ["β (trend)", info.beta],
      ...(info.gamma != null ? [["γ (seasonal)", info.gamma]] : []),
    ],
  },
  // ── Pre-trained ML models (load from CSV, horizon in days) ──
  LSTM: {
    label: "LSTM Forecast",
    desc: "<strong>LSTM</strong> — Long Short-Term Memory recurrent network pre-trained on daily hydrological time series. Excels at capturing long-range temporal dependencies and sequential patterns in river flow data.",
    ml: true,
    infoCards: (info) => [
      ["Model", info.model],
      ["Horizon", `${info.horizon_days} days`],
      ["RMSE", info.rmse],
      ["MAPE", info.mape],
      ["Last historical", info.last_historical],
      ["Forecast end", info.forecast_end],
    ],
  },
  PatchTST: {
    label: "PatchTST Forecast",
    desc: "<strong>PatchTST</strong> — Patch-based Transformer for time series. Divides the input sequence into patches and applies self-attention, enabling efficient long-context modelling of hydrological signals.",
    ml: true,
    infoCards: (info) => [
      ["Model", info.model],
      ["Horizon", `${info.horizon_days} days`],
      ["RMSE", info.rmse],
      ["MAPE", info.mape],
      ["Last historical", info.last_historical],
      ["Forecast end", info.forecast_end],
    ],
  },
  DLinear: {
    label: "DLinear Forecast",
    desc: "<strong>DLinear</strong> — Decomposition Linear model that separates trend and seasonal components before applying a linear mapping. Surprisingly competitive with deep models while remaining fully interpretable.",
    ml: true,
    infoCards: (info) => [
      ["Model", info.model],
      ["Horizon", `${info.horizon_days} days`],
      ["RMSE", info.rmse],
      ["MAPE", info.mape],
      ["Last historical", info.last_historical],
      ["Forecast end", info.forecast_end],
    ],
  },
  GRU: {
    label: "GRU Forecast",
    desc: "<strong>GRU</strong> — Gated Recurrent Unit, a streamlined recurrent network pre-trained on Mekong daily series. Uses reset and update gates to efficiently model sequential dependencies without the complexity of LSTM.",
    ml: true,
    infoCards: (info) => [
      ["Model", info.model],
      ["Horizon", `${info.horizon_days} days`],
      ["RMSE", info.rmse],
      ["MAPE", info.mape],
      ["Last historical", info.last_historical],
      ["Forecast end", info.forecast_end],
    ],
  },
  iTransformer: {
    label: "iTransformer Forecast",
    desc: "<strong>iTransformer</strong> — Inverted Transformer (ICLR 2024). Applies attention across the variate dimension rather than time, enabling each variable's full temporal context to be embedded before cross-series attention is applied.",
    ml: true,
    infoCards: (info) => [
      ["Model", info.model],
      ["Horizon", `${info.horizon_days} days`],
      ["RMSE", info.rmse],
      ["MAPE", info.mape],
      ["Last historical", info.last_historical],
      ["Forecast end", info.forecast_end],
    ],
  },
  stacking_ensemble: {
    label: "Advanced Stacking Ensemble",
    desc: "<strong>Stacking Ensemble with Ridge Meta-Model</strong> — Level-0: 5 diverse base models (LSTM, GRU, PatchTST, DLinear, iTransformer). Level-1: Ridge Regression meta-model learns optimal combination of base predictions. Shows all base models + ensemble result. <em>More complex than simple weighted average.</em>",
    ml: true,
    infoCards: (info) => [
      ["Model", info.model],
      ["Base Models", info.base_models],
      ["Horizon", `${info.horizon_days} days`],
      ["Meta Coefficients", info.meta_weights],
      ["Meta-Model", info.meta_intercept],
      ["Forecast Period", `${info.last_historical} → ${info.forecast_end}`],
    ],
  },
  ml_compare: {
    label: "Multi-Model Comparison",
    desc: "<strong>Compare All</strong> — Overlays LSTM, GRU, PatchTST, DLinear, and iTransformer forecasts on one chart with a ranked RMSE/MAPE table to identify the best-performing model for this station and feature.",
    ml: true,
    infoCards: () => [],
  },
};

let selectedPredModel = 'holt_winters';

Object.assign(MODEL_META.holt_winters, {
  desc: "<strong>Holt-Winters</strong> - Exponential smoothing for level, trend, and seasonality. A strong baseline when the Mekong signal follows a smooth wet-dry cycle and medium-term structure remains stable.",
  family: "Statistical Forecast",
  highlights: ["Strong seasonal baseline", "Interpretable smoothing terms", "Monthly forecast horizon"],
  infoCards: (info) => [
    ["Model", info.model_type],
    ["Historical data", `${info.historical_months} months`],
    ["Forecast period", `${info.last_historical} -> ${info.forecast_end}`],
    ["AIC", info.aic],
    ["RMSE", info.rmse],
    ["MAPE", info.mape],
    ["MAE", info.mae],
    ["Bias", info.bias],
    ["Alpha", info.alpha],
    ["Beta", info.beta],
    ...(info.gamma != null ? [["Gamma", info.gamma]] : []),
  ],
});

// Removed: sarima, random_forest, gradient_boosting, linear_seasonal, svr

["LSTM", "GRU", "PatchTST", "DLinear", "iTransformer"].forEach((key) => {
  MODEL_META[key].family = "Pre-trained ML Forecast";
  MODEL_META[key].highlights = MODEL_META[key].highlights || [
    "Daily forecast horizon",
    "Precomputed model output",
    "Optional AI narrative"
  ];
});
MODEL_META.ml_compare.aiSupported = false;
MODEL_META.ml_compare.family = "Model Comparison";
MODEL_META.ml_compare.highlights = [
  "Overlays all pre-trained ML models",
  "Ranks performance quickly",
  "Best for model selection before deeper reading"
];

const ML_HORIZON_OPTIONS = [
  { value: '7',  label: '7 days ahead' },
  { value: '14', label: '14 days ahead', selected: true },
  { value: '21', label: '21 days ahead' },
  { value: '30', label: '30 days ahead' },
];
const STAT_HORIZON_OPTIONS = [
  { value: '6',  label: '6 months ahead' },
  { value: '12', label: '12 months ahead', selected: true },
  { value: '24', label: '24 months ahead' },
  { value: '36', label: '36 months ahead' },
];

function _isMLModel(modelKey) {
  return !!(MODEL_META[modelKey] && MODEL_META[modelKey].ml);
}

function _modelSupportsAi(modelKey) {
  return MODEL_META[modelKey]?.aiSupported !== false;
}

function _renderPredictionHighlights(modelKey) {
  const container = document.getElementById('pred-highlights');
  const meta = MODEL_META[modelKey];
  if (!container || !meta) return;

  const highlights = meta.highlights || [];
  if (!highlights.length) {
    container.innerHTML = '';
    container.classList.add('hidden');
    return;
  }

  container.innerHTML = `
    <div class="pred-highlight-grid">
      ${highlights.map(item => `<div class="pred-highlight-card">${item}</div>`).join('')}
    </div>
  `;
  container.classList.remove('hidden');
}

function _renderPredictionInfo(info, modelKey) {
  const meta = MODEL_META[modelKey];
  const container = document.getElementById('pred-model-info');
  if (!meta || !container) return;

  const cards = meta.infoCards(info).map(([label, val]) =>
    `<div class="pred-info-card"><span class="pred-info-label">${label}</span><span class="pred-info-value">${val ?? '--'}</span></div>`
  ).join('');

  container.innerHTML = `<div class="pred-info-grid">${cards}</div>`;
  container.classList.remove('hidden');
}

function _syncPredictionMetaUi(modelKey) {
  const meta = MODEL_META[modelKey];
  if (!meta) return;

  const titleEl = document.getElementById('pred-section-title');
  const descEl = document.getElementById('pred-model-desc');
  const modeChip = document.getElementById('pred-mode-chip');
  const speedChip = document.getElementById('pred-speed-chip');
  const aiToggle = document.getElementById('pred-ai-toggle');
  const aiCopy = document.getElementById('pred-ai-toggle-copy');

  if (titleEl) titleEl.textContent = meta.label;
  if (descEl) descEl.innerHTML = meta.desc;
  if (modeChip) modeChip.textContent = meta.family || (_isMLModel(modelKey) ? 'Pre-trained ML Forecast' : 'Statistical Forecast');

  if (aiToggle) {
    aiToggle.disabled = !_modelSupportsAi(modelKey);
    if (!_modelSupportsAi(modelKey)) aiToggle.checked = false;
  }

  const aiEnabled = !!aiToggle?.checked && _modelSupportsAi(modelKey);
  if (speedChip) speedChip.textContent = aiEnabled ? 'Deeper analysis mode' : 'Fast chart-only mode';
  if (aiCopy) {
    aiCopy.textContent = !_modelSupportsAi(modelKey)
      ? 'AI reporting is disabled for the comparison view. Switch to a single model if you want a forecast narrative.'
      : aiEnabled
        ? `AI report is enabled for ${meta.label}. Forecast generation will take longer because the narrative is produced after the model result.`
        : `AI report is off for ${meta.label}. This is the fastest way to generate the forecast chart and performance cards.`;
  }

  _renderPredictionHighlights(modelKey);
}

function _syncPredFormForModel(modelKey) {
  const dateGroup    = document.getElementById('pred-date-group');
  const horizonSel   = document.getElementById('pred-horizon-select');
  const isML = _isMLModel(modelKey);

  // Show/hide date inputs
  if (dateGroup) dateGroup.style.display = isML ? 'none' : '';

  // Swap horizon options
  if (horizonSel) {
    const opts = isML ? ML_HORIZON_OPTIONS : STAT_HORIZON_OPTIONS;
    const curVal = horizonSel.value;
    horizonSel.innerHTML = opts.map(o =>
      `<option value="${o.value}"${o.selected || o.value === curVal ? ' selected' : ''}>${o.label}</option>`
    ).join('');
  }
}

function setupPredictionEvents() {
  document.getElementById('pred-station-select')?.addEventListener('change', function() {
    if (_isMLModel(selectedPredModel)) {
      updatePredMLCategoriesForStation(this.value);
    } else {
      updatePredCategoriesForStation(this.value);
      autofillPredDateRange();
    }
  });
  document.getElementById('pred-category-select')?.addEventListener('change', function() {
    if (!_isMLModel(selectedPredModel)) autofillPredDateRange();
  });

  // Model tab switching
  document.querySelectorAll('.model-tab').forEach(tab => {
    tab.addEventListener('click', function() {
      document.querySelectorAll('.model-tab').forEach(t => t.classList.remove('active'));
      this.classList.add('active');
      selectedPredModel = this.dataset.model;
      const meta = MODEL_META[selectedPredModel];
      const titleEl = document.getElementById('pred-section-title');
      const descEl  = document.getElementById('pred-model-desc');
      if (titleEl) titleEl.textContent = meta.label;
      if (descEl)  descEl.innerHTML   = meta.desc;
      // Reset output panels
      document.getElementById('pred-model-info')?.classList.add('hidden');
      document.getElementById('pred-chart-container')?.classList.add('hidden');
      document.getElementById('pred-compare-table')?.classList.add('hidden');
      // Swap station/category dropdowns based on model type
      if (_isMLModel(selectedPredModel)) {
        populatePredMLDropdowns();
      } else {
        populatePredictionDropdowns();
      }
      // Adapt form fields (dates, horizon units)
      _syncPredFormForModel(selectedPredModel);
    });
  });

  document.getElementById('pred-generate-btn')?.addEventListener('click', function() {
    const station  = document.getElementById('pred-station-select')?.value;
    const category = document.getElementById('pred-category-select')?.value;
    const horizon  = parseInt(document.getElementById('pred-horizon-select')?.value || '12');
    const isML     = _isMLModel(selectedPredModel);
    const includeAnalysis = !!document.getElementById('pred-ai-toggle')?.checked && _modelSupportsAi(selectedPredModel);
    const startDate = document.getElementById('pred-start-date')?.value;
    const endDate   = document.getElementById('pred-end-date')?.value;

    if (!station || !category || (!isML && (!startDate || !endDate))) {
      showAlert(document.getElementById('pred-alert'));
      return;
    }

    const btn = document.getElementById('pred-generate-btn');
    btn.disabled = true;
    btn.textContent = 'Generating…';
    document.getElementById('pred-model-info')?.classList.add('hidden');
    document.getElementById('pred-chart-container')?.classList.add('hidden');
    document.getElementById('pred-compare-table')?.classList.add('hidden');
    document.getElementById('pred-analysis-panel')?.classList.add('hidden');

    // ── ML: Compare All ────────────────────────────────────────────────────
    if (selectedPredModel === 'ml_compare') {
      fetch('/compare_models', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ station_name: station, category_name: category, horizon_days: horizon }),
      })
      .then(r => r.json())
      .then(data => {
        if (data.error) {
          const el = document.getElementById('pred-alert');
          if (el) { el.textContent = 'Comparison error: ' + data.error; showAlert(el); }
          return;
        }
        // Chart
        document.getElementById('pred-chart-container').classList.remove('hidden');
        Plotly.newPlot('pred-chart', JSON.parse(data.chart), {}, { responsive: true });
        // Metrics table
        const info = data.model_info;
        const tbody = document.getElementById('pred-compare-tbody');
        if (tbody && info.metrics) {
          const sorted = [...info.metrics].sort((a, b) => {
            const ar = parseFloat(a.RMSE), br = parseFloat(b.RMSE);
            if (isNaN(ar)) return 1; if (isNaN(br)) return -1;
            return ar - br;
          });
          tbody.innerHTML = sorted.map((m, i) => {
            const best = m.Model === info.best_model;
            return `<tr class="${best ? 'best-model-row' : ''}">
              <td>${m.Model}${best ? ' <span class="best-badge">Best</span>' : ''}</td>
              <td>${m.RMSE}</td><td>${m.MAPE}</td><td>#${i + 1}</td></tr>`;
          }).join('');
        }
        document.getElementById('pred-compare-table').classList.remove('hidden');
      })
      .catch(err => {
        const el = document.getElementById('pred-alert');
        if (el) { el.textContent = 'Error: ' + err.message; showAlert(el); }
      })
      .finally(() => { btn.disabled = false; btn.textContent = 'Generate Forecast'; });
      return;
    }

    // ── ML: stacking ensemble ──────────────────────────────────────────────
    if (selectedPredModel === 'stacking_ensemble') {
      fetch('/generate_stacking_ensemble', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          station_name: station,
          category_name: category,
          horizon_days: horizon,
          include_analysis: includeAnalysis,
        }),
      })
      .then(r => r.json())
      .then(data => {
        if (data.error) {
          const el = document.getElementById('pred-alert');
          if (el) { el.textContent = 'Forecast error: ' + data.error; showAlert(el); }
          return;
        }
        const info = data.model_info;
        const meta = MODEL_META[selectedPredModel];
        const cards = meta.infoCards(info).map(([label, val]) =>
          `<div class="pred-info-card"><span class="pred-info-label">${label}</span><span class="pred-info-value">${val ?? '--'}</span></div>`
        ).join('');
        document.getElementById('pred-model-info').innerHTML = `<div class="pred-info-grid">${cards}</div>`;
        document.getElementById('pred-model-info').classList.remove('hidden');
        document.getElementById('pred-chart-container').classList.remove('hidden');
        Plotly.newPlot('pred-chart', JSON.parse(data.chart), {}, { responsive: true });
        showPredictionAnalysis(data.analysis, data.analysis_source);
      })
      .catch(err => {
        const el = document.getElementById('pred-alert');
        if (el) { el.textContent = 'Error: ' + err.message; showAlert(el); }
      })
      .finally(() => { btn.disabled = false; btn.textContent = 'Generate Forecast'; });
      return;
    }

    // ── ML: single model ───────────────────────────────────────────────────
    if (isML) {
      fetch('/generate_ml_prediction', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: selectedPredModel,
          station_name: station,
          category_name: category,
          horizon_days: horizon,
          include_analysis: includeAnalysis,
        }),
      })
      .then(r => r.json())
      .then(data => {
        if (data.error) {
          const el = document.getElementById('pred-alert');
          if (el) { el.textContent = 'Forecast error: ' + data.error; showAlert(el); }
          return;
        }
        const info = data.model_info;
        const meta = MODEL_META[selectedPredModel];
        const cards = meta.infoCards(info).map(([label, val]) =>
          `<div class="pred-info-card"><span class="pred-info-label">${label}</span><span class="pred-info-value">${val ?? '--'}</span></div>`
        ).join('');
        document.getElementById('pred-model-info').innerHTML = `<div class="pred-info-grid">${cards}</div>`;
        document.getElementById('pred-model-info').classList.remove('hidden');
        document.getElementById('pred-chart-container').classList.remove('hidden');
        Plotly.newPlot('pred-chart', JSON.parse(data.chart), {}, { responsive: true });
        showPredictionAnalysis(data.analysis, data.analysis_source);
      })
      .catch(err => {
        const el = document.getElementById('pred-alert');
        if (el) { el.textContent = 'Error: ' + err.message; showAlert(el); }
      })
      .finally(() => { btn.disabled = false; btn.textContent = 'Generate Forecast'; });
      return;
    }

    // ── Statistical models (original flow) ────────────────────────────────
    fetch('/generate_prediction', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: selectedPredModel,
        station_name: station,
        category_name: category,
        start_date: startDate,
        end_date: endDate,
        forecast_months: horizon,
      }),
    })
    .then(r => r.json())
    .then(data => {
      if (data.error) {
        const el = document.getElementById('pred-alert');
        if (el) { el.textContent = 'Forecast error: ' + data.error; showAlert(el); }
        return;
      }
      const info = data.model_info;
      const meta = MODEL_META[selectedPredModel];
      const cards = meta.infoCards(info).map(([label, val]) =>
        `<div class="pred-info-card"><span class="pred-info-label">${label}</span><span class="pred-info-value">${val ?? '--'}</span></div>`
      ).join('');
      document.getElementById('pred-model-info').innerHTML = `<div class="pred-info-grid">${cards}</div>`;
      document.getElementById('pred-model-info').classList.remove('hidden');
      document.getElementById('pred-chart-container').classList.remove('hidden');
      Plotly.newPlot('pred-chart', JSON.parse(data.chart), {}, { responsive: true });
      showPredictionAnalysis(data.analysis, data.analysis_source);
    })
    .catch(err => {
      const el = document.getElementById('pred-alert');
      if (el) { el.textContent = 'Error: ' + err.message; showAlert(el); }
    })
    .finally(() => { btn.disabled = false; btn.textContent = 'Generate Forecast'; });
  });
}

function setupPredictionEvents() {
  document.getElementById('pred-station-select')?.addEventListener('change', function() {
    if (_isMLModel(selectedPredModel)) {
      updatePredMLCategoriesForStation(this.value);
    } else {
      updatePredCategoriesForStation(this.value);
      autofillPredDateRange();
    }
  });

  document.getElementById('pred-category-select')?.addEventListener('change', function() {
    if (!_isMLModel(selectedPredModel)) autofillPredDateRange();
  });

  document.querySelectorAll('.model-tab').forEach(tab => {
    tab.addEventListener('click', function() {
      document.querySelectorAll('.model-tab').forEach(t => t.classList.remove('active'));
      this.classList.add('active');
      selectedPredModel = this.dataset.model;

      document.getElementById('pred-model-info')?.classList.add('hidden');
      document.getElementById('pred-chart-container')?.classList.add('hidden');
      document.getElementById('pred-compare-table')?.classList.add('hidden');
      document.getElementById('pred-analysis-panel')?.classList.add('hidden');

      if (_isMLModel(selectedPredModel)) {
        populatePredMLDropdowns();
      } else {
        populatePredictionDropdowns();
      }

      _syncPredFormForModel(selectedPredModel);
      _syncPredictionMetaUi(selectedPredModel);
    });
  });

  document.getElementById('pred-ai-toggle')?.addEventListener('change', function() {
    _syncPredictionMetaUi(selectedPredModel);
  });

  document.getElementById('pred-generate-btn')?.addEventListener('click', function() {
    const station = document.getElementById('pred-station-select')?.value;
    const category = document.getElementById('pred-category-select')?.value;
    const horizon = parseInt(document.getElementById('pred-horizon-select')?.value || '12');
    const isML = _isMLModel(selectedPredModel);
    const includeAnalysis = !!document.getElementById('pred-ai-toggle')?.checked && _modelSupportsAi(selectedPredModel);
    const startDate = document.getElementById('pred-start-date')?.value;
    const endDate = document.getElementById('pred-end-date')?.value;

    if (!station || !category || (!isML && (!startDate || !endDate))) {
      showAlert(document.getElementById('pred-alert'));
      return;
    }

    const btn = document.getElementById('pred-generate-btn');
    btn.disabled = true;
    btn.textContent = includeAnalysis ? 'Generating forecast + AI report...' : 'Generating forecast...';
    document.getElementById('pred-model-info')?.classList.add('hidden');
    document.getElementById('pred-chart-container')?.classList.add('hidden');
    document.getElementById('pred-compare-table')?.classList.add('hidden');
    document.getElementById('pred-analysis-panel')?.classList.add('hidden');

    if (selectedPredModel === 'ml_compare') {
      fetch('/compare_models', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ station_name: station, category_name: category, horizon_days: horizon }),
      })
      .then(r => r.json())
      .then(data => {
        if (data.error) {
          const el = document.getElementById('pred-alert');
          if (el) { el.textContent = 'Comparison error: ' + data.error; showAlert(el); }
          return;
        }
        document.getElementById('pred-chart-container').classList.remove('hidden');
        Plotly.newPlot('pred-chart', JSON.parse(data.chart), {}, { responsive: true });
        const info = data.model_info;
        const tbody = document.getElementById('pred-compare-tbody');
        if (tbody && info.metrics) {
          const sorted = [...info.metrics].sort((a, b) => {
            const ar = parseFloat(a.RMSE), br = parseFloat(b.RMSE);
            if (isNaN(ar)) return 1;
            if (isNaN(br)) return -1;
            return ar - br;
          });
          tbody.innerHTML = sorted.map((m, i) => {
            const best = m.Model === info.best_model;
            return `<tr class="${best ? 'best-model-row' : ''}"><td>${m.Model}${best ? ' <span class="best-badge">Best</span>' : ''}</td><td>${m.RMSE}</td><td>${m.MAPE}</td><td>#${i + 1}</td></tr>`;
          }).join('');
        }
        document.getElementById('pred-compare-table').classList.remove('hidden');
        setExportSessionPayload('forecast', {
          charts: data.chart ? [data.chart] : [],
          title: 'Forecast Workspace',
          reportHtml: '',
          reportText: '',
          meta: [
            { label: 'Mode', value: 'Compare all ML models' },
            { label: 'Station', value: station },
            { label: 'Category', value: category },
            { label: 'Horizon', value: `${horizon} days` },
            { label: 'Best model', value: info.best_model || '--' },
          ],
        });
      })
      .catch(err => {
        const el = document.getElementById('pred-alert');
        if (el) { el.textContent = 'Error: ' + err.message; showAlert(el); }
      })
      .finally(() => {
        btn.disabled = false;
        btn.textContent = 'Generate Forecast';
        _syncPredictionMetaUi(selectedPredModel);
      });
      return;
    }

    // ── Stacking ensemble ──────────────────────────────────────────────────
    if (selectedPredModel === 'stacking_ensemble') {
      fetch('/generate_stacking_ensemble', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          station_name: station,
          category_name: category,
          horizon_days: horizon,
          include_analysis: includeAnalysis,
        }),
      })
      .then(r => r.json())
      .then(data => {
        if (data.error) {
          const el = document.getElementById('pred-alert');
          if (el) { el.textContent = 'Forecast error: ' + data.error; showAlert(el); }
          return;
        }
        _renderPredictionInfo(data.model_info, selectedPredModel);
        document.getElementById('pred-chart-container').classList.remove('hidden');
        Plotly.newPlot('pred-chart', JSON.parse(data.chart), {}, { responsive: true });
        setExportSessionPayload('forecast', {
          charts: data.chart ? [data.chart] : [],
          title: 'Forecast Workspace',
          reportHtml: '',
          reportText: '',
          meta: [
            { label: 'Model', value: 'Stacking Ensemble' },
            { label: 'Base Models', value: data.model_info?.base_models || '--' },
            { label: 'Station', value: station },
            { label: 'Category', value: category },
            { label: 'Horizon', value: `${horizon} days` },
          ],
        });
        if (includeAnalysis) showPredictionAnalysis(data.analysis, data.analysis_source);
      })
      .catch(err => {
        const el = document.getElementById('pred-alert');
        if (el) { el.textContent = 'Error: ' + err.message; showAlert(el); }
      })
      .finally(() => {
        btn.disabled = false;
        btn.textContent = 'Generate Forecast';
        _syncPredictionMetaUi(selectedPredModel);
      });
      return;
    }

    if (isML) {
      fetch('/generate_ml_prediction', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: selectedPredModel,
          station_name: station,
          category_name: category,
          horizon_days: horizon,
          include_analysis: includeAnalysis,
        }),
      })
      .then(r => r.json())
      .then(data => {
        if (data.error) {
          const el = document.getElementById('pred-alert');
          if (el) { el.textContent = 'Forecast error: ' + data.error; showAlert(el); }
          return;
        }
        _renderPredictionInfo(data.model_info, selectedPredModel);
        document.getElementById('pred-chart-container').classList.remove('hidden');
        Plotly.newPlot('pred-chart', JSON.parse(data.chart), {}, { responsive: true });
        setExportSessionPayload('forecast', {
          charts: data.chart ? [data.chart] : [],
          title: 'Forecast Workspace',
          reportHtml: '',
          reportText: '',
          meta: [
            { label: 'Model', value: MODEL_META[selectedPredModel]?.label || selectedPredModel },
            { label: 'Station', value: station },
            { label: 'Category', value: category },
            { label: 'Horizon', value: `${horizon} days` },
            { label: 'RMSE', value: data.model_info?.rmse ?? '--' },
            { label: 'MAPE', value: data.model_info?.mape ?? '--' },
          ],
        });
        if (includeAnalysis) showPredictionAnalysis(data.analysis, data.analysis_source);
      })
      .catch(err => {
        const el = document.getElementById('pred-alert');
        if (el) { el.textContent = 'Error: ' + err.message; showAlert(el); }
      })
      .finally(() => {
        btn.disabled = false;
        btn.textContent = 'Generate Forecast';
        _syncPredictionMetaUi(selectedPredModel);
      });
      return;
    }

    fetch('/generate_prediction', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: selectedPredModel,
        station_name: station,
        category_name: category,
        start_date: startDate,
        end_date: endDate,
        forecast_months: horizon,
        include_analysis: includeAnalysis,
      }),
    })
    .then(r => r.json())
    .then(data => {
      if (data.error) {
        const el = document.getElementById('pred-alert');
        if (el) { el.textContent = 'Forecast error: ' + data.error; showAlert(el); }
        return;
      }
      _renderPredictionInfo(data.model_info, selectedPredModel);
      document.getElementById('pred-chart-container').classList.remove('hidden');
      Plotly.newPlot('pred-chart', JSON.parse(data.chart), {}, { responsive: true });
      setExportSessionPayload('forecast', {
        charts: data.chart ? [data.chart] : [],
        title: 'Forecast Workspace',
        reportHtml: '',
        reportText: '',
        meta: [
          { label: 'Model', value: MODEL_META[selectedPredModel]?.label || selectedPredModel },
          { label: 'Station', value: station },
          { label: 'Category', value: category },
          { label: 'Training window', value: `${startDate} to ${endDate}` },
          { label: 'Forecast horizon', value: `${horizon} months` },
          { label: 'RMSE', value: data.model_info?.rmse ?? '--' },
          { label: 'MAPE', value: data.model_info?.mape ?? '--' },
        ],
      });
      if (includeAnalysis) showPredictionAnalysis(data.analysis, data.analysis_source);
    })
    .catch(err => {
      const el = document.getElementById('pred-alert');
      if (el) { el.textContent = 'Error: ' + err.message; showAlert(el); }
    })
    .finally(() => {
      btn.disabled = false;
      btn.textContent = 'Generate Forecast';
      _syncPredictionMetaUi(selectedPredModel);
    });
  });

  _syncPredFormForModel(selectedPredModel);
  _syncPredictionMetaUi(selectedPredModel);
}

// ------------------------------
// CORRELATION EXPLORER
// ------------------------------
function populateCorrelationDropdowns() {
  const stationSel = document.getElementById('corr-station-select');
  if (!stationSel) return;

  const previousStation = stationSel.value;
  stationSel.innerHTML = '<option value="">Select a station...</option>';
  stationNameList.forEach(name => {
    const opt = document.createElement('option');
    opt.value = name;
    opt.textContent = name;
    stationSel.appendChild(opt);
  });
  if (previousStation && stationNameList.includes(previousStation)) {
    stationSel.value = previousStation;
  }

  updateCorrelationCategoryOptions(stationSel.value);
}

function updateCorrelationCategoryOptions(stationName) {
  const catA = document.getElementById('corr-category-a-select');
  const catB = document.getElementById('corr-category-b-select');
  if (!catA || !catB) return;

  const previousA = catA.value;
  const previousB = catB.value;
  const available = stationName
    ? categoryNameList.filter(name =>
        (categoryDetailsMap[name] || []).some(row => row.station_name === stationName)
      )
    : categoryNameList;

  catA.innerHTML = '<option value="">Select first variable...</option>';
  catB.innerHTML = '<option value="">Select second variable...</option>';

  available.forEach(name => {
    const optA = document.createElement('option');
    optA.value = name;
    optA.textContent = name;
    catA.appendChild(optA);

    const optB = document.createElement('option');
    optB.value = name;
    optB.textContent = name;
    catB.appendChild(optB);
  });

  if (previousA && available.includes(previousA)) catA.value = previousA;
  if (previousB && available.includes(previousB)) catB.value = previousB;
  updateCorrelationOverlap();
}

function getCorrelationOverlap(stationName, categoryA, categoryB) {
  const detailA = getCategoryDateRange(categoryA, stationName);
  const detailB = getCategoryDateRange(categoryB, stationName);
  if (!detailA || !detailB) return null;

  const startA = new Date(detailA.start_date);
  const endA = new Date(detailA.end_date);
  const startB = new Date(detailB.start_date);
  const endB = new Date(detailB.end_date);

  const overlapStart = new Date(Math.max(startA.getTime(), startB.getTime()));
  const overlapEnd = new Date(Math.min(endA.getTime(), endB.getTime()));
  if (overlapStart > overlapEnd) return null;

  const toIso = (d) => d.toISOString().slice(0, 10);
  return { start_date: toIso(overlapStart), end_date: toIso(overlapEnd) };
}

function updateCorrelationOverlap() {
  const station = document.getElementById('corr-station-select')?.value;
  const categoryA = document.getElementById('corr-category-a-select')?.value;
  const categoryB = document.getElementById('corr-category-b-select')?.value;
  const startEl = document.getElementById('corr-start-date');
  const endEl = document.getElementById('corr-end-date');
  const overlapPreview = document.getElementById('corr-overlap-preview');
  const focusPreview = document.getElementById('corr-focus-preview');

  if (!station) {
    if (startEl) startEl.value = '';
    if (endEl) endEl.value = '';
    if (overlapPreview) overlapPreview.textContent = 'Select a station and two different variables';
    if (focusPreview) focusPreview.textContent = 'Correlation structure, seasonal co-movement, and lag behavior';
    return;
  }

  // Determine the best date range we can show given current selections
  const refCategory = categoryA || categoryB;
  let dateRange = null;

  if (categoryA && categoryB && categoryA !== categoryB) {
    // Both different — compute true overlap
    dateRange = getCorrelationOverlap(station, categoryA, categoryB);
    if (overlapPreview) overlapPreview.textContent = dateRange
      ? `${formatDateToDDMMYYYY(dateRange.start_date)} to ${formatDateToDDMMYYYY(dateRange.end_date)}`
      : 'No overlapping date range found';
    if (focusPreview) focusPreview.textContent = `${categoryA} against ${categoryB} at ${station}`;
  } else if (refCategory) {
    // Same variable in both slots, or only one chosen — use that variable's range
    dateRange = getCategoryDateRange(refCategory, station);
    if (overlapPreview) overlapPreview.textContent = 'Select two different variables for correlation';
    if (focusPreview) focusPreview.textContent = 'Correlation structure, seasonal co-movement, and lag behavior';
  } else {
    // No category selected yet — use widest range for this station
    dateRange = getCategoryDateRange('', station);
    if (overlapPreview) overlapPreview.textContent = 'Select a station and two different variables';
    if (focusPreview) focusPreview.textContent = 'Correlation structure, seasonal co-movement, and lag behavior';
  }

  if (dateRange) {
    if (startEl) startEl.value = formatDateToDDMMYYYY(dateRange.start_date);
    if (endEl) endEl.value = formatDateToDDMMYYYY(dateRange.end_date);
  } else {
    if (startEl) startEl.value = '';
    if (endEl) endEl.value = '';
  }
}

function formatCorrelationLag(lag, frequency) {
  const unit = frequency === 'monthly' ? 'months' : 'days';
  if (lag === 0) return `0 ${unit}`;
  return `${lag > 0 ? '+' : ''}${lag} ${unit}`;
}

function _showCorrAnalysis(analysis, source) {
  const panel = document.getElementById('corr-analysis-panel');
  const body  = document.getElementById('corr-analysis-body');
  if (!panel || !body || !analysis) return;
  const tag = source === 'gemini'
    ? '<span class="analysis-source-tag gemini-tag">Gemini AI</span>'
    : '<span class="analysis-source-tag fallback-tag">Pre-plan Analysis</span>';
  body.innerHTML = tag + azBuildAnalysisReport(analysis);
  panel.classList.remove('hidden');
  setExportSessionReport('correlation', analysis, body.innerHTML);
}

function renderCorrelationFindings(findings, summary) {
  const body = document.getElementById('corr-analysis-body');
  if (!body) return;

  const bullets = (findings || []).map(item => `<li>${item}</li>`).join('');
  body.innerHTML = `
    <span class="analysis-source-tag fallback-tag">Deterministic Analysis</span>
    <div class="az-section">
      <h4 class="az-section-title">Relationship Summary</h4>
      <p class="az-para">
        ${summary.category_a} and ${summary.category_b} at ${summary.station} were aligned on a ${summary.freq_label.toLowerCase()}
        basis across ${summary.n_obs} overlapping observations. This lets the explorer compare direct association,
        seasonal co-movement, and delayed response patterns inside the same station context.
      </p>
    </div>
    <div class="az-section">
      <h4 class="az-section-title">Key Findings</h4>
      <ul class="corr-findings-list">${bullets}</ul>
    </div>
    <div class="az-section">
      <h4 class="az-section-title">Interpretation Guide</h4>
      <p class="az-para">
        Pearson r reflects linear association, while Spearman rho checks whether the variables still move together in ranked order
        even when the response is non-linear. The lag scan is especially useful for hydrological systems where rainfall, water level,
        discharge, and sediment response may be offset rather than synchronous.
      </p>
    </div>
  `;
  setExportSessionReport('correlation', stripHtmlToText(body.innerHTML), body.innerHTML);
}

function setupCorrelationEvents() {
  populateCorrelationDropdowns();

  document.getElementById('corr-station-select')?.addEventListener('change', function() {
    updateCorrelationCategoryOptions(this.value);
  });

  document.getElementById('corr-category-a-select')?.addEventListener('change', updateCorrelationOverlap);
  document.getElementById('corr-category-b-select')?.addEventListener('change', updateCorrelationOverlap);

  document.getElementById('corr-generate-btn')?.addEventListener('click', function() {
    const station = document.getElementById('corr-station-select')?.value;
    const categoryA = document.getElementById('corr-category-a-select')?.value;
    const categoryB = document.getElementById('corr-category-b-select')?.value;
    const startDate = document.getElementById('corr-start-date')?.value;
    const endDate = document.getElementById('corr-end-date')?.value;
    const includeAnalysis = !!document.getElementById('corr-ai-toggle')?.checked;

    if (!station || !categoryA || !categoryB || categoryA === categoryB || !startDate || !endDate) {
      showAlert(document.getElementById('corr-alert'));
      return;
    }

    const btn = this;
    btn.disabled = true;
    btn.textContent = includeAnalysis ? 'Running + AI report...' : 'Running...';

    document.getElementById('corr-stats-grid')?.classList.add('hidden');
    document.getElementById('corr-chart-grid')?.classList.add('hidden');
    document.getElementById('corr-analysis-panel')?.classList.add('hidden');

    fetch('/generate_correlation', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        station_name: station,
        category_a: categoryA,
        category_b: categoryB,
        start_date: startDate,
        end_date: endDate,
        include_analysis: includeAnalysis,
      }),
    })
    .then(r => r.json())
    .then(data => {
      if (data.error) {
        const el = document.getElementById('corr-alert');
        if (el) {
          el.textContent = 'Correlation explorer error: ' + data.error;
          showAlert(el);
        }
        return;
      }

      const s = data.summary || {};
      document.getElementById('corr-stat-pearson').textContent = s.pearson_str || 'n/a';
      document.getElementById('corr-stat-spearman').textContent = s.spearman_str || 'n/a';
      document.getElementById('corr-stat-strength').textContent = `${s.strength_label || 'Unknown'} ${s.direction_label || ''}`.trim();
      document.getElementById('corr-stat-obs').textContent = `${s.n_obs || 0} obs`;
      document.getElementById('corr-stat-lag').textContent = `${formatCorrelationLag(s.best_lag || 0, s.align_frequency)} (${s.best_lag_corr_str || 'n/a'})`;
      document.getElementById('corr-stat-seasonal').textContent = s.seasonal_corr_str || 'n/a';
      document.getElementById('corr-stats-grid').classList.remove('hidden');

      const charts = data.charts || {};
      Plotly.newPlot('corr-chart-timeline', JSON.parse(charts.timeline), {}, { responsive: true });
      Plotly.newPlot('corr-chart-scatter', JSON.parse(charts.scatter), {}, { responsive: true });
      Plotly.newPlot('corr-chart-lag', JSON.parse(charts.lag), {}, { responsive: true });
      Plotly.newPlot('corr-chart-seasonal', JSON.parse(charts.seasonal), {}, { responsive: true });
      Plotly.newPlot('corr-chart-rolling', JSON.parse(charts.rolling), {}, { responsive: true });
      document.getElementById('corr-chart-grid').classList.remove('hidden');

      setExportSessionPayload('correlation', {
        charts: [charts.timeline, charts.scatter, charts.lag, charts.seasonal, charts.rolling].filter(Boolean),
        title: 'Correlation Explorer',
        reportHtml: '',
        reportText: '',
        meta: [
          { label: 'Station', value: s.station || station },
          { label: 'Variable A', value: s.category_a || categoryA },
          { label: 'Variable B', value: s.category_b || categoryB },
          { label: 'Aligned frequency', value: s.freq_label || s.align_frequency || '--' },
          { label: 'Observations', value: s.n_obs || '--' },
          { label: 'Pearson r', value: s.pearson_str || '--' },
          { label: 'Spearman rho', value: s.spearman_str || '--' },
          { label: 'Best lag', value: `${formatCorrelationLag(s.best_lag || 0, s.align_frequency)} (${s.best_lag_corr_str || 'n/a'})` },
        ],
      });

      if (includeAnalysis && data.analysis) {
        _showCorrAnalysis(data.analysis, data.analysis_source);
      } else {
        renderCorrelationFindings(data.findings, s);
        document.getElementById('corr-analysis-panel').classList.remove('hidden');
      }
    })
    .catch(err => {
      const el = document.getElementById('corr-alert');
      if (el) {
        el.textContent = 'Error: ' + err.message;
        showAlert(el);
      }
    })
    .finally(() => {
      btn.disabled = false;
      btn.textContent = 'Run Correlation Explorer';
    });
  });
}

// ------------------------------
// SEASONAL DECOMPOSITION
// ------------------------------
function populateSeasonalDropdowns() {
  const staSel = document.getElementById('seas-station-select');
  const catSel = document.getElementById('seas-category-select');
  if (!staSel || !catSel) return;

  const prevSta = staSel.value;
  staSel.innerHTML = '<option value="">Select a station...</option>';
  stationNameList.forEach(name => {
    const opt = document.createElement('option');
    opt.value = name; opt.textContent = name;
    staSel.appendChild(opt);
  });
  if (prevSta && stationNameList.includes(prevSta)) staSel.value = prevSta;

  _updateSeasonalCategories(staSel.value);
}

function _updateSeasonalCategories(stationName) {
  const catSel = document.getElementById('seas-category-select');
  if (!catSel) return;
  const prev = catSel.value;
  catSel.innerHTML = '<option value="">Select a category...</option>';

  const available = stationName
    ? categoryNameList.filter(name =>
        (categoryDetailsMap[name] || []).some(row => row.station_name === stationName)
      )
    : categoryNameList;

  available.forEach(name => {
    const opt = document.createElement('option');
    opt.value = name; opt.textContent = name;
    catSel.appendChild(opt);
  });
  if (prev && available.includes(prev)) catSel.value = prev;
}

function _autofillSeasonalDates() {
  const station  = document.getElementById('seas-station-select')?.value;
  const category = document.getElementById('seas-category-select')?.value;
  const startEl  = document.getElementById('seas-start-date');
  const endEl    = document.getElementById('seas-end-date');
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
    if (startEl) startEl.value = '';
    if (endEl)   endEl.value   = '';
  }
}

function _showSeasonalAnalysis(analysis, source) {
  const panel = document.getElementById('seas-analysis-panel');
  const body  = document.getElementById('seas-analysis-body');
  if (!panel || !body || !analysis) return;
  const tag = source === 'gemini'
    ? '<span class="analysis-source-tag gemini-tag">Gemini AI</span>'
    : '<span class="analysis-source-tag fallback-tag">Pre-plan Analysis</span>';
  body.innerHTML = tag + azBuildAnalysisReport(analysis);
  panel.classList.remove('hidden');
  setExportSessionReport('seasonal', analysis, body.innerHTML);
}

function setupSeasonalEvents() {
  populateSeasonalDropdowns();

  document.getElementById('seas-station-select')?.addEventListener('change', function() {
    _updateSeasonalCategories(this.value);
    _autofillSeasonalDates();
  });
  document.getElementById('seas-category-select')?.addEventListener('change', _autofillSeasonalDates);

  document.getElementById('seas-generate-btn')?.addEventListener('click', function() {
    const station  = document.getElementById('seas-station-select')?.value;
    const category = document.getElementById('seas-category-select')?.value;
    const startDate = document.getElementById('seas-start-date')?.value;
    const endDate   = document.getElementById('seas-end-date')?.value;
    const period    = parseInt(document.getElementById('seas-period-select')?.value || '12');

    if (!station || !category || !startDate || !endDate) {
      showAlert(document.getElementById('seas-alert'));
      return;
    }

    const btn = this;
    btn.disabled = true;
    btn.textContent = 'Running…';

    // Hide previous results
    document.getElementById('seas-stats-grid')?.classList.add('hidden');
    document.getElementById('seas-chart-container')?.classList.add('hidden');
    document.getElementById('seas-analysis-panel')?.classList.add('hidden');

    fetch('/generate_seasonal', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        station_name: station,
        category_name: category,
        start_date: startDate,
        end_date: endDate,
        period: period,
      }),
    })
    .then(r => r.json())
    .then(data => {
      if (data.error) {
        const el = document.getElementById('seas-alert');
        if (el) { el.textContent = 'Decomposition error: ' + data.error; showAlert(el); }
        return;
      }

      const s = data.summary;

      // Stats grid
      const trendDir = s.trend_direction;
      const trendColour = trendDir === 'Increasing' ? '#16a34a' : trendDir === 'Decreasing' ? '#dc2626' : '#6b7fa0';
      document.getElementById('seas-stat-trend-dir').textContent = trendDir;
      document.getElementById('seas-stat-trend-dir').style.color = trendColour;
      document.getElementById('seas-stat-trend-str').textContent = (s.trend_strength * 100).toFixed(1) + '%';
      document.getElementById('seas-stat-seas-str').textContent  = (s.seasonal_strength * 100).toFixed(1) + '%';
      document.getElementById('seas-stat-peak').textContent      = s.peak_month;
      document.getElementById('seas-stat-trough').textContent    = s.trough_month;
      document.getElementById('seas-stat-anomalies').textContent = s.anomaly_count + ' months';
      document.getElementById('seas-stats-grid').classList.remove('hidden');

      // Chart
      document.getElementById('seas-chart-container').classList.remove('hidden');
      Plotly.newPlot('seas-chart', JSON.parse(data.chart), {}, { responsive: true });
      setExportSessionPayload('seasonal', {
        charts: data.chart ? [data.chart] : [],
        title: 'Seasonal Decomposition',
        reportHtml: '',
        reportText: '',
        meta: [
          { label: 'Station', value: station },
          { label: 'Category', value: category },
          { label: 'Window', value: `${startDate} to ${endDate}` },
          { label: 'Period', value: `${period} months` },
          { label: 'Trend direction', value: s.trend_direction },
          { label: 'Trend strength', value: (s.trend_strength * 100).toFixed(1) + '%' },
          { label: 'Seasonal strength', value: (s.seasonal_strength * 100).toFixed(1) + '%' },
        ],
      });

      // Analysis
      _showSeasonalAnalysis(data.analysis, data.analysis_source);
    })
    .catch(err => {
      const el = document.getElementById('seas-alert');
      if (el) { el.textContent = 'Error: ' + err.message; showAlert(el); }
    })
    .finally(() => { btn.disabled = false; btn.textContent = 'Run Decomposition'; });
  });
}

// ------------------------------
// DATA EXPORT
// ------------------------------
function stripHtmlToText(html) {
  const div = document.createElement('div');
  div.innerHTML = html || '';
  return (div.textContent || div.innerText || '').replace(/\n{3,}/g, '\n\n').trim();
}

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function buildExportFilename(sectionKey, suffix, extension) {
  const meta = EXPORT_SOURCE_META[sectionKey] || { slug: 'export' };
  const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-');
  return `${meta.slug}_${suffix}_${stamp}.${extension}`;
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function setExportSessionPayload(sectionKey, payload) {
  const existing = exportSessions[sectionKey] || {};
  exportSessions[sectionKey] = {
    ...existing,
    ...payload,
    title: payload.title || existing.title || EXPORT_SOURCE_META[sectionKey]?.label || 'Export',
    slug: existing.slug || EXPORT_SOURCE_META[sectionKey]?.slug || 'export',
    generatedAt: new Date().toISOString(),
    available: !!((payload.charts && payload.charts.length) || payload.reportHtml || payload.reportText || (payload.meta && payload.meta.length)),
  };
  refreshExportSourceSnapshot();
}

function setExportSessionReport(sectionKey, reportText, reportHtml) {
  const existing = exportSessions[sectionKey];
  if (!existing) return;
  exportSessions[sectionKey] = {
    ...existing,
    reportText: reportText || stripHtmlToText(reportHtml || ''),
    reportHtml: reportHtml || (reportText ? azBuildAnalysisReport(reportText) : ''),
    generatedAt: new Date().toISOString(),
    available: true,
  };
  refreshExportSourceSnapshot();
}

function populateExportControls() {
  const stationSel = document.getElementById('export-station-select');
  const sourceSel = document.getElementById('export-source-select');
  if (!stationSel || !sourceSel) return;

  const prevStation = stationSel.value;
  stationSel.innerHTML = '<option value="">Select a station...</option>';
  stationNameList.forEach(name => {
    const opt = document.createElement('option');
    opt.value = name;
    opt.textContent = name;
    stationSel.appendChild(opt);
  });
  if (prevStation && stationNameList.includes(prevStation)) stationSel.value = prevStation;

  const prevSource = sourceSel.value || 'dashboard';
  sourceSel.innerHTML = Object.entries(EXPORT_SOURCE_META).map(([key, meta]) =>
    `<option value="${key}">${meta.label}</option>`
  ).join('');
  sourceSel.value = EXPORT_SOURCE_META[prevSource] ? prevSource : 'dashboard';

  updateExportCategoryOptions(stationSel.value);
  refreshExportSourceSnapshot();
}

function updateExportCategoryOptions(stationName) {
  const catSel = document.getElementById('export-category-select');
  if (!catSel) return;
  const previous = catSel.value;
  const available = stationName
    ? categoryNameList.filter(name => (categoryDetailsMap[name] || []).some(row => row.station_name === stationName))
    : categoryNameList;

  catSel.innerHTML = '<option value="">Select a category...</option>';
  available.forEach(name => {
    const opt = document.createElement('option');
    opt.value = name;
    opt.textContent = name;
    catSel.appendChild(opt);
  });
  if (previous && available.includes(previous)) catSel.value = previous;
  autofillExportDateRange();
}

function autofillExportDateRange() {
  const station = document.getElementById('export-station-select')?.value;
  const category = document.getElementById('export-category-select')?.value;
  const startEl = document.getElementById('export-start-date');
  const endEl = document.getElementById('export-end-date');
  const preview = document.getElementById('export-date-preview');

  if (!station || !category) {
    if (startEl) startEl.value = '';
    if (endEl) endEl.value = '';
    if (preview) preview.textContent = 'Select a station and category';
    return;
  }

  const detail = getCategoryDateRange(category, station);
  if (!detail) {
    if (startEl) startEl.value = '';
    if (endEl) endEl.value = '';
    if (preview) preview.textContent = 'No known overlap for this selection';
    return;
  }

  if (startEl) startEl.value = formatDateToDDMMYYYY(detail.start_date);
  if (endEl) endEl.value = formatDateToDDMMYYYY(detail.end_date);
  if (preview) preview.textContent = `${formatDateToDDMMYYYY(detail.start_date)} to ${formatDateToDDMMYYYY(detail.end_date)}`;
}

function refreshExportSourceSnapshot() {
  const sourceSel = document.getElementById('export-source-select');
  const statusEl = document.getElementById('export-source-status');
  const chartCountEl = document.getElementById('export-source-chart-count');
  const reportEl = document.getElementById('export-source-report-status');
  if (!sourceSel || !statusEl || !chartCountEl || !reportEl) return;

  const session = exportSessions[sourceSel.value];
  const hasCharts = !!(session?.charts?.length);
  const hasReport = !!(session?.reportHtml || session?.reportText);

  statusEl.textContent = session?.available ? `Ready from ${session.title}` : 'No output generated yet';
  chartCountEl.textContent = String(session?.charts?.length || 0);
  reportEl.textContent = hasReport ? 'Available' : 'Unavailable';
}

async function chartJsonToImage(chartJson, width = 1800, height = 1080) {
  const temp = document.createElement('div');
  temp.style.position = 'fixed';
  temp.style.left = '-10000px';
  temp.style.top = '0';
  temp.style.width = `${width}px`;
  temp.style.height = `${height}px`;
  temp.style.background = '#ffffff';
  document.body.appendChild(temp);

  try {
    const figure = JSON.parse(chartJson);
    await Plotly.newPlot(
      temp,
      figure.data || figure,
      figure.layout || {},
      { ...(figure.config || {}), responsive: false, displayModeBar: false }
    );
    return await Plotly.toImage(temp, { format: 'png', width, height, scale: 2 });
  } finally {
    Plotly.purge(temp);
    temp.remove();
  }
}

async function exportChartsAsPng(sectionKey) {
  const session = exportSessions[sectionKey];
  if (!session?.charts?.length) return false;

  for (let i = 0; i < session.charts.length; i += 1) {
    const dataUrl = await chartJsonToImage(session.charts[i]);
    const response = await fetch(dataUrl);
    const blob = await response.blob();
    downloadBlob(blob, buildExportFilename(sectionKey, `chart_${i + 1}`, 'png'));
  }
  return true;
}

function buildExportHtmlDocument(session, imageUrls = []) {
  const metaHtml = (session.meta || []).map(item =>
    `<div class="meta-row"><span class="meta-label">${escapeHtml(item.label)}</span><span class="meta-value">${escapeHtml(item.value)}</span></div>`
  ).join('');

  const figuresHtml = imageUrls.map((src, index) =>
    `<figure class="figure-block"><img src="${src}" alt="Exported chart ${index + 1}" /><figcaption>Figure ${index + 1}</figcaption></figure>`
  ).join('');

  const reportHtml = session.reportHtml
    ? `<section class="report-block"><h2>Analytical Report</h2>${session.reportHtml}</section>`
    : `<section class="report-block"><h2>Analytical Report</h2><p class="empty-copy">No narrative report was generated for this output. You can still use the exported figures and metadata.</p></section>`;

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>${escapeHtml(session.title)}</title>
  <style>
    body { font-family: Georgia, "Times New Roman", serif; color: #1e293b; margin: 0; background: #f8fafc; }
    .page { max-width: 980px; margin: 0 auto; padding: 42px 36px 56px; background: #ffffff; }
    .eyebrow { text-transform: uppercase; letter-spacing: 0.16em; font-size: 11px; color: #8a5b17; margin-bottom: 10px; }
    h1 { font-size: 34px; line-height: 1.15; margin: 0 0 8px; color: #0f172a; }
    .subhead { font-size: 15px; color: #475569; margin: 0 0 24px; }
    .meta-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px 18px; padding: 18px 20px; background: #f8fafc; border: 1px solid #dbe4ee; border-radius: 18px; margin-bottom: 28px; }
    .meta-row { display: flex; justify-content: space-between; gap: 12px; padding-bottom: 8px; border-bottom: 1px solid #e2e8f0; }
    .meta-label { font-size: 12px; text-transform: uppercase; letter-spacing: 0.08em; color: #64748b; }
    .meta-value { font-size: 14px; font-weight: 600; color: #0f172a; text-align: right; }
    .figure-block { margin: 0 0 26px; padding: 18px; border: 1px solid #dbe4ee; border-radius: 18px; background: #ffffff; }
    .figure-block img { width: 100%; height: auto; display: block; border-radius: 12px; }
    .figure-block figcaption { margin-top: 10px; font-size: 13px; color: #64748b; }
    .report-block { margin-top: 30px; }
    .report-block h2 { font-size: 24px; margin: 0 0 16px; color: #0f172a; }
    .az-section { margin-bottom: 18px; }
    .az-section-title { font-size: 17px; margin: 0 0 8px; color: #0f172a; }
    .az-para, .empty-copy, .report-block li { font-size: 15px; line-height: 1.72; color: #334155; }
    .analysis-source-tag { display: inline-block; margin-bottom: 16px; padding: 6px 10px; border-radius: 999px; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; background: #e2e8f0; color: #334155; }
    .corr-findings-list { margin: 0; padding-left: 20px; }
    @media print {
      body { background: #ffffff; }
      .page { max-width: none; padding: 24px; }
      .figure-block { break-inside: avoid; }
    }
  </style>
</head>
<body>
  <div class="page">
    <div class="eyebrow">MekongPulse Export</div>
    <h1>${escapeHtml(session.title)}</h1>
    <p class="subhead">Generated ${escapeHtml(new Date(session.generatedAt || Date.now()).toLocaleString())}</p>
    <div class="meta-grid">${metaHtml || '<div class="meta-row"><span class="meta-label">Status</span><span class="meta-value">No metadata available</span></div>'}</div>
    ${figuresHtml}
    ${reportHtml}
  </div>
</body>
</html>`;
}

async function buildExportDocument(session) {
  const imageUrls = [];
  for (const chart of session.charts || []) {
    imageUrls.push(await chartJsonToImage(chart));
  }
  return buildExportHtmlDocument(session, imageUrls);
}

function buildExportText(session) {
  const header = [
    session.title,
    `Generated: ${new Date(session.generatedAt || Date.now()).toLocaleString()}`,
    '',
    'Metadata',
    ...(session.meta || []).map(item => `- ${item.label}: ${item.value}`),
    '',
    'Analytical Report',
    session.reportText || 'No narrative report was generated for this output.',
  ];
  return header.join('\n');
}

function getSelectedExportSession(alertId) {
  const sourceSel = document.getElementById('export-source-select');
  const session = exportSessions[sourceSel?.value || 'dashboard'];
  if (!session?.available) {
    showAlert(document.getElementById(alertId));
    return null;
  }
  return { session, sectionKey: sourceSel.value };
}

function setupExportEvents() {
  populateExportControls();

  document.getElementById('export-station-select')?.addEventListener('change', function() {
    updateExportCategoryOptions(this.value);
  });
  document.getElementById('export-category-select')?.addEventListener('change', autofillExportDateRange);
  document.getElementById('export-source-select')?.addEventListener('change', refreshExportSourceSnapshot);

  document.getElementById('export-csv-btn')?.addEventListener('click', async function() {
    const station = document.getElementById('export-station-select')?.value;
    const category = document.getElementById('export-category-select')?.value;
    const startDate = document.getElementById('export-start-date')?.value;
    const endDate = document.getElementById('export-end-date')?.value;
    if (!station || !category || !startDate || !endDate) {
      showAlert(document.getElementById('export-csv-alert'));
      return;
    }

    const btn = this;
    btn.disabled = true;
    btn.textContent = 'Preparing CSV...';
    try {
      const response = await fetch('/export_station_data', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          station_name: station,
          category_name: category,
          start_date: startDate,
          end_date: endDate,
        }),
      });
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.error || 'CSV export failed');
      }
      const blob = await response.blob();
      const disposition = response.headers.get('Content-Disposition') || '';
      const match = disposition.match(/filename="?([^"]+)"?/i);
      downloadBlob(blob, match?.[1] || buildExportFilename('dashboard', 'filtered_data', 'csv'));
    } catch (err) {
      const alertEl = document.getElementById('export-csv-alert');
      if (alertEl) {
        alertEl.textContent = `CSV export error: ${err.message}`;
        showAlert(alertEl);
      }
    } finally {
      btn.disabled = false;
      btn.innerHTML = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>Download CSV`;
    }
  });

  document.getElementById('export-chart-png-btn')?.addEventListener('click', async function() {
    const selected = getSelectedExportSession('export-session-alert');
    if (!selected) return;
    if (!selected.session.charts.length) {
      showAlert(document.getElementById('export-session-alert'));
      return;
    }

    const btn = this;
    btn.disabled = true;
    btn.textContent = 'Rendering PNGs...';
    try {
      await exportChartsAsPng(selected.sectionKey);
    } catch (err) {
      const alertEl = document.getElementById('export-session-alert');
      if (alertEl) {
        alertEl.textContent = `Chart export error: ${err.message}`;
        showAlert(alertEl);
      }
    } finally {
      btn.disabled = false;
      btn.textContent = 'Download Chart PNGs';
    }
  });

  document.getElementById('export-report-html-btn')?.addEventListener('click', async function() {
    const selected = getSelectedExportSession('export-session-alert');
    if (!selected) return;

    const btn = this;
    btn.disabled = true;
    btn.textContent = 'Building HTML report...';
    try {
      const html = await buildExportDocument(selected.session);
      downloadBlob(new Blob([html], { type: 'text/html;charset=utf-8' }), buildExportFilename(selected.sectionKey, 'report', 'html'));
    } catch (err) {
      const alertEl = document.getElementById('export-session-alert');
      if (alertEl) {
        alertEl.textContent = `Report export error: ${err.message}`;
        showAlert(alertEl);
      }
    } finally {
      btn.disabled = false;
      btn.textContent = 'Download Report HTML';
    }
  });

  document.getElementById('export-report-txt-btn')?.addEventListener('click', function() {
    const selected = getSelectedExportSession('export-session-alert');
    if (!selected) return;
    const text = buildExportText(selected.session);
    downloadBlob(new Blob([text], { type: 'text/plain;charset=utf-8' }), buildExportFilename(selected.sectionKey, 'report', 'txt'));
  });

  document.getElementById('export-pdf-btn')?.addEventListener('click', async function() {
    const selected = getSelectedExportSession('export-pdf-alert');
    if (!selected) return;

    const btn = this;
    btn.disabled = true;
    btn.textContent = 'Preparing print report...';
    try {
      const html = await buildExportDocument(selected.session);
      const win = window.open('', '_blank');
      if (!win) throw new Error('Allow pop-ups to open the print report window.');
      win.document.open();
      win.document.write(html);
      win.document.close();
      win.focus();
      setTimeout(() => win.print(), 500);
    } catch (err) {
      const alertEl = document.getElementById('export-pdf-alert');
      if (alertEl) {
        alertEl.textContent = `PDF export error: ${err.message}`;
        showAlert(alertEl);
      }
    } finally {
      btn.disabled = false;
      btn.innerHTML = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9V2h9l5 5v13a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2z"/><path d="M14 2v6h6"/><path d="M8 13h8"/><path d="M8 17h8"/></svg>Open Print-Ready PDF Report`;
    }
  });
}

// ------------------------------
// RESEARCH LAB
// ------------------------------
const RESEARCH_STORAGE_KEY = 'mekongpulse_research_sessions_v1';

function _fillStationSelect(selectId) {
  const sel = document.getElementById(selectId);
  if (!sel) return;
  const prev = sel.value;
  sel.innerHTML = '<option value="">Select a station...</option>';
  stationNameList.forEach(name => {
    const opt = document.createElement('option');
    opt.value = name;
    opt.textContent = name;
    sel.appendChild(opt);
  });
  if (prev && stationNameList.includes(prev)) sel.value = prev;
}

function _fillCategorySelect(selectId, stationName) {
  const sel = document.getElementById(selectId);
  if (!sel) return;
  const prev = sel.value;
  const available = stationName
    ? categoryNameList.filter(name => (categoryDetailsMap[name] || []).some(row => row.station_name === stationName))
    : categoryNameList;
  sel.innerHTML = '<option value="">Select a category...</option>';
  available.forEach(name => {
    const opt = document.createElement('option');
    opt.value = name;
    opt.textContent = name;
    sel.appendChild(opt);
  });
  if (prev && available.includes(prev)) sel.value = prev;
}

function _fillCommonCategorySelect(selectId, stationA, stationB) {
  const sel = document.getElementById(selectId);
  if (!sel) return;
  const prev = sel.value;
  const availableA = stationA
    ? categoryNameList.filter(name => (categoryDetailsMap[name] || []).some(row => row.station_name === stationA))
    : [];
  const availableB = stationB
    ? categoryNameList.filter(name => (categoryDetailsMap[name] || []).some(row => row.station_name === stationB))
    : [];
  const common = availableA.filter(name => availableB.includes(name));
  sel.innerHTML = '<option value="">Select a category...</option>';
  common.forEach(name => {
    const opt = document.createElement('option');
    opt.value = name;
    opt.textContent = name;
    sel.appendChild(opt);
  });
  if (prev && common.includes(prev)) sel.value = prev;
}

function _autofillResearchDates(stationId, categoryId, startId, endId) {
  const station = document.getElementById(stationId)?.value;
  const category = document.getElementById(categoryId)?.value;
  const startEl = document.getElementById(startId);
  const endEl = document.getElementById(endId);
  if (!station || !category) {
    if (startEl) startEl.value = '';
    if (endEl) endEl.value = '';
    return;
  }
  const detail = getCategoryDateRange(category, station);
  if (!detail) return;
  if (startEl) startEl.value = formatDateToDDMMYYYY(detail.start_date);
  if (endEl) endEl.value = formatDateToDDMMYYYY(detail.end_date);
}

function _renderResearchSummary(containerId, summary) {
  const el = document.getElementById(containerId);
  if (!el || !summary) return;
  el.innerHTML = Object.entries(summary).map(([key, value]) => `
    <div class="research-summary-card">
      <span class="research-summary-label">${key.replace(/_/g, ' ')}</span>
      <span class="research-summary-value">${value ?? '--'}</span>
    </div>
  `).join('');
}

function _renderResearchFindings(containerId, findings, title = 'Key Findings') {
  const el = document.getElementById(containerId);
  if (!el) return;
  el.innerHTML = `
    <h3>${title}</h3>
    <ul class="corr-findings-list">${(findings || []).map(item => `<li>${item}</li>`).join('')}</ul>
  `;
}

function _plotResearchChart(id, chartJson) {
  if (!chartJson) return;
  Plotly.newPlot(id, JSON.parse(chartJson), {}, { responsive: true });
}

function _readResearchSessions() {
  try {
    return JSON.parse(localStorage.getItem(RESEARCH_STORAGE_KEY) || '[]');
  } catch {
    return [];
  }
}

function _writeResearchSessions(items) {
  localStorage.setItem(RESEARCH_STORAGE_KEY, JSON.stringify(items));
}

function renderResearchSessions() {
  const list = document.getElementById('research-sessions-list');
  if (!list) return;
  const sessions = _readResearchSessions();
  if (!sessions.length) {
    list.innerHTML = '<p class="helper-text">No saved sessions yet. Generate charts or reports elsewhere in the app, then save them here.</p>';
    return;
  }
  list.innerHTML = sessions.map((item, index) => `
    <div class="research-session-item">
      <div>
        <strong>${item.name}</strong>
        <p>${new Date(item.savedAt).toLocaleString()} · ${item.availableCount} export bundle(s)</p>
      </div>
      <div class="research-session-actions">
        <button type="button" class="secondary-btn research-load-session" data-index="${index}">Load</button>
        <button type="button" class="secondary-btn research-delete-session" data-index="${index}">Delete</button>
      </div>
    </div>
  `).join('');

  list.querySelectorAll('.research-load-session').forEach(btn => {
    btn.addEventListener('click', () => {
      const session = _readResearchSessions()[parseInt(btn.dataset.index, 10)];
      if (!session) return;
      exportSessions = session.payload;
      populateExportControls();
      refreshExportSourceSnapshot();
      setSectionVisible(exportSection);
      setActiveNav('.export-icon');
    });
  });
  list.querySelectorAll('.research-delete-session').forEach(btn => {
    btn.addEventListener('click', () => {
      const sessionsLocal = _readResearchSessions();
      sessionsLocal.splice(parseInt(btn.dataset.index, 10), 1);
      _writeResearchSessions(sessionsLocal);
      renderResearchSessions();
    });
  });
}

function setupResearchLabEvents() {
  ['rq-station-select','rl-station-a-select','rl-station-b-select','re-station-select','rs-station-select','rf-station-select'].forEach(_fillStationSelect);
  ['rq-category-select','re-category-select','rs-category-select','rf-category-select'].forEach(id => _fillCategorySelect(id, document.getElementById(id.replace('category','station'))?.value));
  _fillCommonCategorySelect('rl-category-select', document.getElementById('rl-station-a-select')?.value, document.getElementById('rl-station-b-select')?.value);

  document.querySelectorAll('.research-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.research-tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.research-panel').forEach(panel => panel.classList.remove('active'));
      tab.classList.add('active');
      document.querySelector(`.research-panel[data-research-panel="${tab.dataset.researchTab}"]`)?.classList.add('active');
    });
  });

  [['rq-station-select','rq-category-select','rq-start-date','rq-end-date'],['re-station-select','re-category-select','re-start-date','re-end-date'],['rs-station-select','rs-category-select','rs-start-a','rs-end-a'],['rf-station-select','rf-category-select','rf-start-date','rf-end-date']].forEach(([sta,cat,start,end]) => {
    document.getElementById(sta)?.addEventListener('change', function() {
      _fillCategorySelect(cat, this.value);
      _autofillResearchDates(sta, cat, start, end);
      if (sta === 'rs-station-select') {
        const endB = document.getElementById('rs-end-b');
        const startB = document.getElementById('rs-start-b');
        if (startB && endB && document.getElementById(start)?.value && document.getElementById(end)?.value) {
          startB.value = document.getElementById(start).value;
          endB.value = document.getElementById(end).value;
        }
      }
    });
    document.getElementById(cat)?.addEventListener('change', () => _autofillResearchDates(sta, cat, start, end));
  });

  document.getElementById('rl-station-a-select')?.addEventListener('change', () => _fillCommonCategorySelect('rl-category-select', document.getElementById('rl-station-a-select')?.value, document.getElementById('rl-station-b-select')?.value));
  document.getElementById('rl-station-b-select')?.addEventListener('change', () => _fillCommonCategorySelect('rl-category-select', document.getElementById('rl-station-a-select')?.value, document.getElementById('rl-station-b-select')?.value));

  document.getElementById('rq-run-btn')?.addEventListener('click', async function() {
    const station = document.getElementById('rq-station-select')?.value;
    const category = document.getElementById('rq-category-select')?.value;
    const start = document.getElementById('rq-start-date')?.value;
    const end = document.getElementById('rq-end-date')?.value;
    if (!station || !category || !start || !end) return showAlert(document.getElementById('rq-alert'));
    this.disabled = true; this.textContent = 'Running...';
    try {
      const res = await fetch('/generate_quality', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ station_name: station, category_name: category, start_date: start, end_date: end })});
      const data = await res.json(); if (data.error) throw new Error(data.error);
      _renderResearchSummary('rq-summary', data.summary);
      _plotResearchChart('rq-chart-coverage', data.charts.coverage);
      _plotResearchChart('rq-chart-availability', data.charts.availability);
      _renderResearchFindings('rq-findings', data.findings, 'Data Quality Interpretation');
      document.getElementById('rq-results')?.classList.remove('hidden');
    } catch (err) {
      const el = document.getElementById('rq-alert'); if (el) { el.textContent = err.message; showAlert(el); }
    } finally { this.disabled = false; this.textContent = 'Run Quality Explorer'; }
  });

  document.getElementById('rl-run-btn')?.addEventListener('click', async function() {
    const stationA = document.getElementById('rl-station-a-select')?.value;
    const stationB = document.getElementById('rl-station-b-select')?.value;
    const category = document.getElementById('rl-category-select')?.value;
    if (!stationA || !stationB || stationA === stationB || !category) return showAlert(document.getElementById('rl-alert'));
    this.disabled = true; this.textContent = 'Running...';
    try {
      const res = await fetch('/generate_station_linkage', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ station_a: stationA, station_b: stationB, category_name: category })});
      const data = await res.json(); if (data.error) throw new Error(data.error);
      _renderResearchSummary('rl-summary', data.summary);
      _plotResearchChart('rl-chart-timeline', data.charts.timeline);
      _plotResearchChart('rl-chart-scatter', data.charts.scatter);
      _plotResearchChart('rl-chart-lag', data.charts.lag);
      _renderResearchFindings('rl-findings', data.findings, 'Station Linkage Interpretation');
      document.getElementById('rl-results')?.classList.remove('hidden');
    } catch (err) {
      const el = document.getElementById('rl-alert'); if (el) { el.textContent = err.message; showAlert(el); }
    } finally { this.disabled = false; this.textContent = 'Run Station Linkage'; }
  });

  document.getElementById('re-run-btn')?.addEventListener('click', async function() {
    const payload = {
      station_name: document.getElementById('re-station-select')?.value,
      category_name: document.getElementById('re-category-select')?.value,
      threshold_mode: document.getElementById('re-threshold-mode')?.value,
      threshold_value: document.getElementById('re-threshold-value')?.value,
      direction: document.getElementById('re-direction')?.value,
      start_date: document.getElementById('re-start-date')?.value,
      end_date: document.getElementById('re-end-date')?.value,
    };
    if (!payload.station_name || !payload.category_name || !payload.start_date || !payload.end_date) return showAlert(document.getElementById('re-alert'));
    this.disabled = true; this.textContent = 'Running...';
    try {
      const res = await fetch('/generate_extremes', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) });
      const data = await res.json(); if (data.error) throw new Error(data.error);
      _renderResearchSummary('re-summary', data.summary);
      _plotResearchChart('re-chart-timeline', data.charts.timeline);
      _plotResearchChart('re-chart-annual', data.charts.annual);
      _plotResearchChart('re-chart-monthly', data.charts.monthly);
      _renderResearchFindings('re-findings', data.findings, 'Extreme Event Interpretation');
      document.getElementById('re-results')?.classList.remove('hidden');
    } catch (err) {
      const el = document.getElementById('re-alert'); if (el) { el.textContent = err.message; showAlert(el); }
    } finally { this.disabled = false; this.textContent = 'Run Extreme Event Analysis'; }
  });

  document.getElementById('rs-run-btn')?.addEventListener('click', async function() {
    const payload = {
      station_name: document.getElementById('rs-station-select')?.value,
      category_name: document.getElementById('rs-category-select')?.value,
      start_a: document.getElementById('rs-start-a')?.value,
      end_a: document.getElementById('rs-end-a')?.value,
      start_b: document.getElementById('rs-start-b')?.value,
      end_b: document.getElementById('rs-end-b')?.value,
    };
    if (!payload.station_name || !payload.category_name || !payload.start_a || !payload.end_a || !payload.start_b || !payload.end_b) return showAlert(document.getElementById('rs-alert'));
    this.disabled = true; this.textContent = 'Running...';
    try {
      const res = await fetch('/generate_scenario_compare', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) });
      const data = await res.json(); if (data.error) throw new Error(data.error);
      _renderResearchSummary('rs-summary', data.summary);
      _plotResearchChart('rs-chart-distribution', data.charts.distribution);
      _plotResearchChart('rs-chart-profile', data.charts.profile);
      _renderResearchFindings('rs-findings', data.findings, 'Scenario Comparison Interpretation');
      document.getElementById('rs-results')?.classList.remove('hidden');
    } catch (err) {
      const el = document.getElementById('rs-alert'); if (el) { el.textContent = err.message; showAlert(el); }
    } finally { this.disabled = false; this.textContent = 'Run Scenario Compare'; }
  });

  document.getElementById('rf-run-btn')?.addEventListener('click', async function() {
    const payload = {
      station_name: document.getElementById('rf-station-select')?.value,
      category_name: document.getElementById('rf-category-select')?.value,
      model_key: document.getElementById('rf-model-select')?.value,
      horizon: document.getElementById('rf-horizon-select')?.value,
      start_date: document.getElementById('rf-start-date')?.value,
      end_date: document.getElementById('rf-end-date')?.value,
    };
    if (!payload.station_name || !payload.category_name || !payload.start_date || !payload.end_date) return showAlert(document.getElementById('rf-alert'));
    this.disabled = true; this.textContent = 'Running...';
    try {
      const res = await fetch('/generate_forecast_diagnostics', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) });
      const data = await res.json(); if (data.error) throw new Error(data.error);
      _renderResearchSummary('rf-summary', data.summary);
      _plotResearchChart('rf-chart-backtest', data.charts.backtest);
      _plotResearchChart('rf-chart-residuals', data.charts.residuals);
      _plotResearchChart('rf-chart-seasonal', data.charts.seasonal_error);
      _renderResearchFindings('rf-findings', data.findings, 'Forecast Reliability Interpretation');
      document.getElementById('rf-results')?.classList.remove('hidden');
    } catch (err) {
      const el = document.getElementById('rf-alert'); if (el) { el.textContent = err.message; showAlert(el); }
    } finally { this.disabled = false; this.textContent = 'Run Forecast Diagnostics'; }
  });

  document.getElementById('rsave-btn')?.addEventListener('click', () => {
    const name = document.getElementById('rsave-name')?.value?.trim() || `Research Session ${new Date().toLocaleString()}`;
    const availableCount = Object.values(exportSessions).filter(item => item?.available).length;
    const sessions = _readResearchSessions();
    sessions.unshift({ name, savedAt: new Date().toISOString(), availableCount, payload: exportSessions });
    _writeResearchSessions(sessions.slice(0, 12));
    document.getElementById('rsave-name').value = '';
    renderResearchSessions();
  });

  document.getElementById('rclear-sessions-btn')?.addEventListener('click', () => {
    _writeResearchSessions([]);
    renderResearchSessions();
  });

  renderResearchSessions();
}

// ------------------------------
// INIT
// ------------------------------
document.addEventListener("DOMContentLoaded", async function() {
  // Populate country filter immediately from hardcoded constant — no data loading needed
  syncMapCountryFilterOptions();

  // Bind navigation and chrome events immediately — must never be blocked by data loading
  setupNavigation();
  setupModalEvents();
  setupSidebarToggle();
  setupThemeToggle();
  setupMapExpandButton();
  setupUndoToast();
  setupShortcuts();

  // Load CSV data, then initialise all data-dependent UI
  try {
    await Promise.all([loadCSVStationDetails(), loadCSVCategoryDetails(), loadMLStationMap()]);

    initializeMap();
    showGraphOptionsOnUI();
    showCategoryOptionsOnUI();
    showStationOptionsOnUI(ALL_CATEGORIES);
    renderInitialMapStations();
    requestAnimationFrame(renderInitialMapStations);
    window.addEventListener('load', renderInitialMapStations, { once: true });
    setTimeout(renderInitialMapStations, 250);

    updateOverviewStats();
    updateBuilderSummary();
    updateVisualizationQueueUI();

    setupBuilderEvents();
    populatePredictionDropdowns();
    setupPredictionEvents();
    setupCorrelationEvents();
    setupSeasonalEvents();
    setupExportEvents();
    setupResearchLabEvents();
    setupAiAnalysis();
    setupAnalyzeEvents();
    setupNewsEvents();
    setupNewsDetailPanel();
  } catch (error) {
    console.error("Data loading error:", error);
  }
});

// ------------------------------
// KEYBOARD SHORTCUTS
// ------------------------------
function setupShortcuts() {
  const modal    = document.getElementById("shortcuts-modal");
  const closeBtn = document.getElementById("shortcuts-close");
  const trigger  = document.getElementById("shortcuts-trigger");

  function open()  { modal?.classList.remove("hidden"); }
  function close() { modal?.classList.add("hidden"); }
  function toggle(){ modal?.classList.toggle("hidden"); }

  trigger?.addEventListener("click", toggle);
  closeBtn?.addEventListener("click", close);
  modal?.addEventListener("click", e => { if (e.target === modal) close(); });

  const NAV_KEYS = [
    [overviewSection,        ".user-guide-icon"],
    [builderSection,         ".custom-visualization-setup-icon"],
    [dashboardSection,       ".visualization-dashboard-icon"],
    [predictionSection,      ".prediction-icon"],
    [analyzeSection,         ".analyze-section-icon"],
    [correlationSection,     ".correlation-icon"],
    [seasonalSection,        ".seasonal-icon"],
    [exportSection,          ".export-icon"],
  ];

  document.addEventListener("keydown", e => {
    if (e.target.tagName === "INPUT" || e.target.tagName === "SELECT" || e.target.tagName === "TEXTAREA") return;
    if (e.ctrlKey || e.metaKey || e.altKey) return;

    if (e.key === "?") { e.preventDefault(); toggle(); return; }
    if (e.key === "Escape") { close(); return; }

    const idx = parseInt(e.key, 10) - 1;
    if (idx >= 0 && idx < NAV_KEYS.length) {
      e.preventDefault();
      const [section, selector] = NAV_KEYS[idx];
      setSectionVisible(section);
      setActiveNav(selector);
    }
  });
}


// ==============================
// NEWS MODULE
// ==============================

let _newsLoaded = false;
let _newsFloodFilter = false;
let _newsArticles = [];
let _newsFallbackImages = [];

function loadNewsSection(forceRefresh) {
  if (_newsLoaded && !forceRefresh) return;
  _showNewsState("loading");
  fetch("/api/news?limit=10")
    .then(r => r.json())
    .then(data => {
      if (data.error) throw new Error(data.error);
      _newsArticles = data.articles || [];
      if (data.fallback_images && data.fallback_images.length) _newsFallbackImages = data.fallback_images;
      _newsLoaded = true;
      _updateNewsMeta(data.last_sync, data.total_stored);
      _renderNewsArticles(_newsArticles);
    })
    .catch(err => {
      console.error("[News] Load error:", err);
      _showNewsState("error", err.message || "Failed to load news.");
    });
}

function _updateNewsMeta(lastSync, totalStored) {
  const syncLabel = document.getElementById("news-last-sync-label");
  const countLabel = document.getElementById("news-count-label");
  if (syncLabel) {
    if (lastSync) {
      const d = new Date(lastSync);
      syncLabel.textContent = "Last synced: " + d.toLocaleString();
    } else {
      syncLabel.textContent = "Not yet synced — click Refresh";
    }
  }
  if (countLabel) {
    countLabel.textContent = totalStored ? totalStored + " articles stored" : "";
  }
}

function _showNewsState(state, message) {
  const loading = document.getElementById("news-loading");
  const error   = document.getElementById("news-error");
  const empty   = document.getElementById("news-empty");
  const grid    = document.getElementById("news-grid");
  const errMsg  = document.getElementById("news-error-msg");

  [loading, error, empty, grid].forEach(el => el && el.classList.add("hidden"));
  if (state === "loading" && loading) loading.classList.remove("hidden");
  if (state === "error") {
    if (error) error.classList.remove("hidden");
    if (errMsg && message) errMsg.textContent = message;
  }
  if (state === "empty" && empty) empty.classList.remove("hidden");
  if (state === "articles" && grid) grid.classList.remove("hidden");
}

function _formatRelativeDate(isoString) {
  if (!isoString) return "";
  const now = new Date();
  const then = new Date(isoString);
  const diffMs = now - then;
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 60) return diffMins <= 1 ? "Just now" : diffMins + "m ago";
  const diffHrs = Math.floor(diffMins / 60);
  if (diffHrs < 24) return diffHrs + "h ago";
  const diffDays = Math.floor(diffHrs / 24);
  if (diffDays < 7) return diffDays + "d ago";
  return then.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function _renderNewsArticles(articles) {
  const grid = document.getElementById("news-grid");
  if (!grid) return;

  const filtered = _newsFloodFilter ? articles.filter(a => a.is_flood_related) : articles;

  if (!filtered.length) {
    _showNewsState("empty");
    return;
  }

  _showNewsState("articles");
  grid.innerHTML = filtered.map(a => _buildArticleCard(a)).join("");
}

function _placeholderVariant(a) {
  if (a.is_flood_related) return "ncp--flood";
  const allTags = (a.tags || []).join(" ").toLowerCase();
  if (/dam|hydro|reservoir|salinity|drought/.test(allTags)) return "ncp--hydro";
  return "";
}

// Pick a Mekong fallback image URL for an article (consistent per article ID).
function _pickFallback(a) {
  if (!_newsFallbackImages.length) return null;
  const hash = (a.id || "x").split("").reduce((s, c) => s + c.charCodeAt(0), 0);
  return _newsFallbackImages[hash % _newsFallbackImages.length];
}

// CSS-only placeholder (used when even the fallback photo fails to load).
function _buildCssPlaceholder(a) {
  const variant = _placeholderVariant(a);
  const initial = _escHtml((a.source_name || "M").charAt(0).toUpperCase());
  const topic   = _escHtml(a.topic || "Mekong River");
  return `
    <div class="news-card-img-placeholder ${variant}">
      <svg class="ncp-waves" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 80" preserveAspectRatio="none" aria-hidden="true">
        <path d="M0,45 C60,15 130,70 200,42 S310,12 400,45 V80 H0Z" fill="rgba(255,255,255,0.09)"/>
        <path d="M0,60 C90,32 190,78 290,54 C360,36 390,62 400,60 V80 H0Z" fill="rgba(255,255,255,0.06)"/>
        <path d="M0,72 C110,50 220,80 340,65 C375,58 395,70 400,72 V80 H0Z" fill="rgba(255,255,255,0.04)"/>
      </svg>
      <div class="ncp-bar">
        <span class="ncp-initial">${initial}</span>
        <span class="ncp-topic">${topic}</span>
      </div>
    </div>`;
}

// Main placeholder builder: uses a real Mekong photo when available.
function _buildPlaceholder(a) {
  const fallbackUrl = _pickFallback(a);
  if (fallbackUrl) {
    // Real Mekong photo — if it fails to load, drop to CSS-only placeholder.
    const cssHtml = _buildCssPlaceholder(a).replace(/`/g, "\\`").replace(/'/g, "\\'");
    return `<div class="news-card-img-wrap"
                 data-source="${_escHtml(a.source_name || '')}"
                 data-topic="${_escHtml(a.topic || 'Mekong River')}"
                 data-flood="${a.is_flood_related}"
                 data-tags="${_escHtml((a.tags||[]).join(','))}"
                 data-is-fallback="true">
               <img class="news-card-img" src="${_escHtml(fallbackUrl)}" alt="Mekong River" loading="lazy"
                    onerror="_newsFallbackImgError(this)"/>
             </div>`;
  }
  return _buildCssPlaceholder(a);
}

// Called when a real article image fails — try a Mekong fallback photo first.
function _newsImgError(el) {
  const wrap = el.closest(".news-card-img-wrap");
  if (!wrap) return;
  const a = {
    id:               wrap.dataset.id    || "",
    source_name:      wrap.dataset.source || "",
    topic:            wrap.dataset.topic  || "Mekong River",
    is_flood_related: wrap.dataset.flood === "true",
    tags:             (wrap.dataset.tags || "").split(",").filter(Boolean),
  };
  wrap.outerHTML = _buildPlaceholder(a);
}

// Called when a Mekong fallback photo itself fails — drop to CSS-only design.
function _newsFallbackImgError(el) {
  const wrap = el.closest(".news-card-img-wrap");
  if (!wrap) return;
  const a = {
    source_name:     wrap.dataset.source || "",
    topic:           wrap.dataset.topic  || "Mekong River",
    is_flood_related: wrap.dataset.flood === "true",
    tags:            (wrap.dataset.tags || "").split(",").filter(Boolean),
  };
  wrap.outerHTML = _buildCssPlaceholder(a);
}

function _buildArticleCard(a) {
  const tags = (a.tags || []).slice(0, 3).map(t =>
    `<span class="news-tag">${_escHtml(t)}</span>`
  ).join("");

  const floodBadge = a.is_flood_related
    ? `<span class="news-flood-badge">Flood</span>`
    : "";

  const imgHtml = a.image_url
    ? `<div class="news-card-img-wrap"
           data-id="${_escHtml(a.id)}"
           data-source="${_escHtml(a.source_name || '')}"
           data-topic="${_escHtml(a.topic || 'Mekong River')}"
           data-flood="${a.is_flood_related}"
           data-tags="${_escHtml((a.tags||[]).join(','))}">
         <img class="news-card-img" src="${_escHtml(a.image_url)}" alt="" loading="lazy"
              onerror="_newsImgError(this)"/>
       </div>`
    : _buildPlaceholder(a);

  const score = a.relevance_score ? Math.round(a.relevance_score * 100) : null;
  const scoreBadge = score !== null
    ? `<span class="news-relevance-badge" title="AI relevance score">${score}%</span>`
    : "";

  const articleDataAttr = `data-article-id="${_escHtml(a.id)}"`;

  return `
  <article class="news-card" ${articleDataAttr} role="button" tabindex="0" title="Click to read details">
    ${imgHtml}
    <div class="news-card-body">
      <div class="news-card-meta">
        <span class="news-source">${_escHtml(a.source_name || "Unknown source")}</span>
        <span class="news-date">${_formatRelativeDate(a.published_at)}</span>
        ${floodBadge}
        ${scoreBadge}
      </div>
      <h3 class="news-card-title">${_escHtml(a.title)}</h3>
      ${a.summary ? `<p class="news-card-summary">${_escHtml(a.summary)}</p>` : ""}
      <div class="news-card-footer">
        ${tags ? `<div class="news-tag-row">${tags}</div>` : ""}
        <div class="news-card-actions">
          <span class="news-read-link">
            Details
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>
          </span>
          ${a.article_url ? `<a class="news-card-ext-link" href="${_escHtml(a.article_url)}" target="_blank" rel="noopener noreferrer" onclick="event.stopPropagation()">
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
            Read article
          </a>` : ""}
        </div>
      </div>
    </div>
  </article>`;
}

function _escHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function setupNewsEvents() {
  // Filter buttons
  document.querySelectorAll(".news-filter-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".news-filter-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      _newsFloodFilter = btn.dataset.filter === "flood";
      _renderNewsArticles(_newsArticles);
    });
  });

  // Refresh button — triggers background sync, shows current articles immediately,
  // then polls until the sync finishes and refreshes the feed.
  const refreshBtn = document.getElementById("news-refresh-btn");
  if (refreshBtn) {
    refreshBtn.addEventListener("click", () => {
      refreshBtn.disabled = true;

      // Animated label while sync runs in background
      let dotCount = 0;
      let labelIdx = 0;
      const dotLabels = ["Fetching feeds", "Filtering articles", "Running AI", "Saving results"];
      const _setLabel = () => {
        dotCount = (dotCount + 1) % 4;
        const dots = ".".repeat(dotCount + 1);
        refreshBtn.textContent = dotLabels[Math.min(labelIdx, dotLabels.length - 1)] + dots;
      };
      _setLabel();
      const _dotTimer = setInterval(() => {
        dotCount++;
        if (dotCount % 8 === 0) labelIdx = Math.min(labelIdx + 1, dotLabels.length - 1);
        _setLabel();
      }, 600);

      const _resetBtn = () => {
        clearInterval(_dotTimer);
        refreshBtn.disabled = false;
        refreshBtn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg> Refresh`;
      };

      const _applyArticles = (data) => {
        _newsArticles = data.articles || [];
        if (data.fallback_images && data.fallback_images.length) _newsFallbackImages = data.fallback_images;
        _newsLoaded = true;
        _updateNewsMeta(data.last_sync, data.total_stored);
        _renderNewsArticles(_newsArticles);
      };

      // Poll /api/news every 3 s until syncing is false (max 30 attempts = 90 s)
      const _pollUntilDone = (attemptsLeft) => {
        if (attemptsLeft <= 0) { _resetBtn(); return; }
        setTimeout(() => {
          fetch("/api/news?limit=10")
            .then(r => r.json())
            .then(data => {
              if (data.error) throw new Error(data.error);
              _applyArticles(data);
              if (data.syncing) {
                labelIdx = Math.min(labelIdx + 1, dotLabels.length - 1);
                _pollUntilDone(attemptsLeft - 1);
              } else {
                _resetBtn();
              }
            })
            .catch(() => _resetBtn());
        }, 3000);
      };

      // Fire the sync (returns immediately with current cached articles)
      if (!_newsArticles.length) _showNewsState("loading");
      fetch("/api/news/sync", { method: "POST" })
        .then(r => r.json())
        .then(data => {
          if (data.error) throw new Error(data.error);
          // Show current articles right away (no waiting for AI)
          _applyArticles(data);
          // Then poll until background sync finishes
          _pollUntilDone(30);
        })
        .catch(err => {
          console.error("[News] Refresh error:", err);
          if (!_newsArticles.length) _showNewsState("error", err.message || "Sync failed.");
          _resetBtn();
        });
    });
  }
}

// ==============================
// NEWS DETAIL PANEL
// ==============================

const _ndpPanel    = document.getElementById("news-detail-panel");
const _ndpBackdrop = document.getElementById("news-detail-backdrop");

function _openArticleDetail(article) {
  if (!_ndpPanel) return;

  // Hero image
  const imgWrap = document.getElementById("ndp-img-wrap");
  const imgEl   = document.getElementById("ndp-img");
  if (article.image_url) {
    imgEl.src = article.image_url;
    imgEl.alt = article.title || "";
    imgWrap.classList.remove("hidden");
  } else {
    imgWrap.classList.add("hidden");
    imgEl.src = "";
  }

  // Populate fields
  document.getElementById("ndp-source").textContent  = article.source_name || "";
  document.getElementById("ndp-date").textContent    = _formatRelativeDate(article.published_at);
  document.getElementById("ndp-title").textContent   = article.title || "";
  document.getElementById("ndp-summary").textContent = article.summary || "";

  const floodBadge = document.getElementById("ndp-flood-badge");
  floodBadge.classList.toggle("hidden", !article.is_flood_related);

  const topicEl = document.getElementById("ndp-topic");
  topicEl.textContent = article.topic || "";
  topicEl.style.display = article.topic ? "" : "none";

  const regionEl = document.getElementById("ndp-region");
  if (article.country_or_region) {
    regionEl.textContent = article.country_or_region;
    regionEl.style.display = "";
  } else {
    regionEl.style.display = "none";
  }

  const scoreEl = document.getElementById("ndp-score");
  if (article.relevance_score) {
    scoreEl.textContent = Math.round(article.relevance_score * 100) + "% relevant";
    scoreEl.style.display = "";
  } else {
    scoreEl.style.display = "none";
  }

  // Full reading content — split on double newlines into <p> tags
  const contentWrap = document.getElementById("ndp-content-wrap");
  const contentEl   = document.getElementById("ndp-content");
  const rawContent  = (article.reading_content || "").trim();
  if (rawContent) {
    contentEl.innerHTML = rawContent
      .split(/\n\n+/)
      .filter(p => p.trim())
      .map(p => `<p>${_escHtml(p.trim())}</p>`)
      .join("");
    contentWrap.classList.remove("hidden");
  } else {
    // No cached content — fetch on-demand from the server
    contentWrap.classList.remove("hidden");
    contentEl.innerHTML = '<p class="ndp-loading">Loading article content\u2026</p>';
    fetch(`/api/news/${encodeURIComponent(article.id)}/content`)
      .then(r => r.json())
      .then(data => {
        if (data.content && data.content.trim()) {
          // Cache on the in-memory article object so re-opens are instant
          article.reading_content = data.content;
          contentEl.innerHTML = data.content
            .split(/\n\n+/)
            .filter(p => p.trim())
            .map(p => `<p>${_escHtml(p.trim())}</p>`)
            .join("");
        } else {
          contentWrap.classList.add("hidden");
          contentEl.innerHTML = "";
        }
      })
      .catch(() => {
        contentWrap.classList.add("hidden");
        contentEl.innerHTML = "";
      });
  }

  // Tags
  const tagsEl = document.getElementById("ndp-tags");
  tagsEl.innerHTML = (article.tags || []).map(t =>
    `<span class="news-tag">${_escHtml(t)}</span>`
  ).join("");

  // Summary section
  document.getElementById("ndp-summary-wrap").style.display = article.summary ? "" : "none";

  // External link (subtle footer link)
  const linkEl = document.getElementById("ndp-link");
  linkEl.href = article.article_url || "#";
  linkEl.innerHTML = `Read full article at ${_escHtml(article.source_name || "source")} <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>`;

  // Show panel + backdrop
  _ndpBackdrop.classList.remove("hidden");
  _ndpPanel.classList.remove("hidden");
  requestAnimationFrame(() => {
    _ndpPanel.classList.add("news-detail-open");
    _ndpBackdrop.classList.add("news-detail-open");
  });
  document.getElementById("news-detail-close")?.focus();
}

function _closeArticleDetail() {
  if (!_ndpPanel) return;
  _ndpPanel.classList.remove("news-detail-open");
  _ndpBackdrop.classList.remove("news-detail-open");
  setTimeout(() => {
    _ndpPanel.classList.add("hidden");
    _ndpBackdrop.classList.add("hidden");
  }, 280);
}

function setupNewsDetailPanel() {
  document.getElementById("news-detail-close")?.addEventListener("click", _closeArticleDetail);
  _ndpBackdrop?.addEventListener("click", _closeArticleDetail);
  document.addEventListener("keydown", e => {
    if (e.key === "Escape" && _ndpPanel && !_ndpPanel.classList.contains("hidden")) {
      _closeArticleDetail();
    }
  });

  // Delegate click on article cards
  document.getElementById("news-grid")?.addEventListener("click", e => {
    const card = e.target.closest("[data-article-id]");
    if (!card) return;
    // Don't intercept the "Open Full Article" link inside the detail panel
    if (e.target.closest("#ndp-link")) return;
    const articleId = card.dataset.articleId;
    const article = _newsArticles.find(a => a.id === articleId);
    if (article) _openArticleDetail(article);
  });

  document.getElementById("news-grid")?.addEventListener("keydown", e => {
    if (e.key === "Enter" || e.key === " ") {
      const card = e.target.closest("[data-article-id]");
      if (card) {
        e.preventDefault();
        const article = _newsArticles.find(a => a.id === card.dataset.articleId);
        if (article) _openArticleDetail(article);
      }
    }
  });
}
