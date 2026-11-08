(() => {
  const views = {
    interview: { title: "Interview", endpoint: "/api/interviews/INT-01/state", mock: "/static/mock/state.json" },
    contracts: { title: "Contracts", endpoint: "/api/contracts", mock: "/static/mock/contracts.json" },
    drift: { title: "Drift", endpoint: "/api/drift", mock: "/static/mock/drift.json" },
    finding: { title: "Finding detail", endpoint: "/api/findings", mock: "/static/mock/findings.json" },
    settings: { title: "Client settings" }
  };
  const useMocks = new URLSearchParams(window.location.search).get("mock") === "1";
  const title = document.getElementById("page-title");
  const status = document.getElementById("connection-status");
  const navigation = [...document.querySelectorAll("[data-route]")];
  let activeRequest = 0;

  function currentRoute() {
    const fragment = window.location.hash.slice(1) || "interview";
    const [route, findingId] = fragment.split("/");
    if (route === "finding") return { name: "finding", findingId: findingId || "F-01" };
    return { name: Object.hasOwn(views, route) ? route : "interview" };
  }

  function showRoute() {
    const route = currentRoute();
    const config = views[route.name];
    title.textContent = config.title;
    document.querySelectorAll(".view-panel").forEach((section) => {
      section.hidden = section.id !== `${route.name}-view`;
    });
    navigation.forEach((link) => {
      if (link.dataset.route === route.name) link.setAttribute("aria-current", "page");
      else link.removeAttribute("aria-current");
    });
    loadView(route, config);
  }

  async function loadView(route, config) {
    const requestId = ++activeRequest;
    const message = document.querySelector(`[data-message="${route.name}"]`);
    const skeletons = document.querySelector(`#${route.name}-view .loading-grid`);
    if (!config.endpoint || route.name === "settings") {
      status.textContent = "Local client settings";
      if (skeletons) skeletons.hidden = true;
      if (message) message.textContent = "";
      return;
    }

    if (skeletons) skeletons.hidden = false;
    if (message) message.textContent = "Loading…";
    const url = useMocks ? config.mock : config.endpoint;
    try {
      const response = await fetch(url, { headers: { Accept: "application/json" } });
      if (!response.ok) throw new Error(`Request failed (${response.status})`);
      await response.json();
      if (requestId !== activeRequest) return;
      status.textContent = useMocks ? "Showing synthetic preview data" : "Connected to local server";
      if (skeletons) skeletons.hidden = true;
      if (message) message.textContent = "Evidence view is ready.";
    } catch (error) {
      if (requestId !== activeRequest) return;
      status.textContent = "Local server unavailable";
      if (message) message.textContent = `${error.message}. Loading placeholders remain visible.`;
    }
  }

  window.addEventListener("hashchange", showRoute);
  showRoute();
})();
