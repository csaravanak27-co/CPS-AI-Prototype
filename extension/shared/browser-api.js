// C.P.S. browser API compatibility layer.
// Firefox exposes `browser`, Chromium exposes `chrome`; both are Promise based
// for the APIs used here in MV3.  Keeping the small differences in one place
// lets the extension run in Chrome, Edge, Brave, and Firefox.
(function exposeBrowserApi(global) {
  const nativeApi = global.browser || global.chrome;
  if (!nativeApi) throw new Error('C.P.S. requires a WebExtension runtime');

  const sidePanel = {
    open: async (options = {}) => {
      if (nativeApi.sidePanel && typeof nativeApi.sidePanel.open === 'function') {
        return nativeApi.sidePanel.open(options);
      }
      if (nativeApi.sidebarAction && typeof nativeApi.sidebarAction.open === 'function') {
        return nativeApi.sidebarAction.open();
      }
      // A last-resort tab fallback is useful on Firefox builds without the
      // desktop sidebar API and on Chromium forks that omit sidePanel.
      if (nativeApi.tabs && typeof nativeApi.tabs.create === 'function') {
        const url = nativeApi.runtime.getURL('sidebar/sidebar.html');
        return nativeApi.tabs.create({ url });
      }
      throw new Error('This browser does not provide a sidebar or side panel');
    },
    setPanelBehavior: async (options = {}) => {
      if (nativeApi.sidePanel && typeof nativeApi.sidePanel.setPanelBehavior === 'function') {
        return nativeApi.sidePanel.setPanelBehavior(options);
      }
      return undefined;
    },
  };

  // Keep event objects and raw namespaces intact while normalising the one
  // capability whose name and availability differ between browsers.
  global.cpsBrowser = new Proxy(nativeApi, {
    get(target, property) {
      if (property === 'sidePanel') return sidePanel;
      return Reflect.get(target, property, target);
    },
  });
})(globalThis);
