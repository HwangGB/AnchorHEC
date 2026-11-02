(() => {
  'use strict';
  const scenes = JSON.parse(document.querySelector('#scenes-data').textContent);
  let selectedScene = scenes.scenes[0], mode = 'ours', selectedInput = null;
  let viewerLoaded = false, viewerReady = false, loadTimeout;
  const frame = document.querySelector('#scene-viewer');
  const status = document.querySelector('#viewer-status');
  const instructions = 'Drag to rotate · Right-drag to pan · Scroll or pinch to zoom';
  const element = (tag, text, css) => {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (css) node.className = css;
    return node;
  };
  function send(type) {
    if (viewerReady) frame.contentWindow.postMessage({source:'anchorhec-page', type, mode, selected:selectedInput}, location.origin);
  }
  function viewerURL() {
    const url = new URL(scenes.client, document.baseURI);
    url.searchParams.set('playbackPath', new URL(selectedScene.file.path, document.baseURI).href);
    url.searchParams.set('scene', selectedScene.id);
    return url.href;
  }
  function fail() {
    clearTimeout(loadTimeout); viewerReady = false;
    document.querySelector('#reset-view').disabled = false;
    status.textContent = 'The 3D view could not load. Use Reset view to retry, or view the figures below.';
  }
  function load() {
    if (location.protocol === 'file:') {
      status.textContent = 'Open the local HTTP preview described in the README to use 3D.'; return;
    }
    clearTimeout(loadTimeout); viewerLoaded = true; viewerReady = false;
    document.querySelector('#viewer-placeholder').hidden = true;
    document.querySelector('#reset-view').disabled = true;
    frame.hidden = false; frame.title = selectedScene.label + ' — raw / AnchorHEC comparison';
    status.textContent = `Loading ${selectedScene.label.toLowerCase()} (${(selectedScene.file.bytes/1e6).toFixed(1)} MB)…`;
    frame.src = viewerURL();
    loadTimeout = setTimeout(fail, 90000);
  }
  function updateSelection() {
    document.querySelectorAll('[data-input]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.input === selectedInput)));
    document.querySelectorAll('[data-mode]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.mode === mode)));
    document.querySelector('#coordinate-label').textContent = mode === 'raw' ? 'Raw · unaligned to robot base' : 'AnchorHEC · robot-base frame (m)';
    const input = selectedScene.inputs.find(item => item.id === selectedInput);
    document.querySelector('#selected-input').textContent = input ? `${input.label} highlighted in magenta${input.role === 'fixed' && mode === 'ours' ? ' · input frames share one calibrated camera pose' : ''}.` : 'Select an input image to highlight its camera in 3D.';
    send('state');
  }
  function updateScene() {
    selectedInput = null;
    document.querySelectorAll('[data-scene]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.scene === selectedScene.id)));
    for (const role of ['wrist', 'fixed']) {
      const inputs = selectedScene.inputs.filter(input => input.role === role);
      document.querySelector(`#${role}-input-count`).textContent = `(${inputs.length})`;
      const container = document.querySelector(`#${role}-inputs`); container.replaceChildren();
      for (const input of inputs) {
        const button = element('button', undefined, 'input-image'); button.type = 'button'; button.dataset.input = input.id;
        button.setAttribute('aria-pressed','false'); button.setAttribute('aria-label',`Highlight ${input.label.toLowerCase()} in 3D`);
        const image = element('img');image.src=input.image;image.alt=input.label+' input image';image.loading='lazy';image.width=384;image.height=216;
        button.append(image,element('span',input.label));
        button.addEventListener('click', () => { selectedInput = input.id; updateSelection(); if (!viewerLoaded) load(); });
        container.append(button);
      }
      container.scrollTop = 0;
    }
    const poster=document.querySelector('#viewer-poster');poster.src=selectedScene.poster;poster.alt=selectedScene.label+' reconstruction preview';
    updateSelection();
    if (viewerLoaded) load();
  }
  window.addEventListener('message', event => {
    if (event.origin !== location.origin || event.source !== frame.contentWindow || event.data?.source !== 'anchorhec-viewer') return;
    if (event.data.type === 'ready' && event.data.scene === selectedScene.id) {
      clearTimeout(loadTimeout); viewerReady = true;
      document.querySelector('#reset-view').disabled = false;status.textContent = instructions;send('state');
    } else if (event.data.type === 'error') fail();
  });
  document.querySelectorAll('[data-scene]').forEach(button => button.addEventListener('click', () => {
    if (selectedScene.id === button.dataset.scene) return;
    viewerReady = false;selectedScene = scenes.scenes.find(scene => scene.id === button.dataset.scene);updateScene();
  }));
  document.querySelectorAll('[data-mode]').forEach(button => button.addEventListener('click', () => { mode = button.dataset.mode;updateSelection(); if (!viewerLoaded) load(); }));
  document.querySelector('#load-viewer').addEventListener('click', load);
  document.querySelector('#reset-view').addEventListener('click', () => viewerReady ? send('reset') : load());
  const fullscreen = document.querySelector('#fullscreen-view'), workbench=document.querySelector('#viewer-workbench');
  if (!workbench.requestFullscreen) fullscreen.hidden=true;
  fullscreen.addEventListener('click', async () => {
    try { if (document.fullscreenElement) await document.exitFullscreen(); else await workbench.requestFullscreen(); }
    catch (_) { status.textContent='Full screen is unavailable in this browser.'; }
  });
  document.addEventListener('fullscreenchange', () => { fullscreen.textContent=document.fullscreenElement?'Exit full screen':'Full screen'; });
  updateScene();
  const dialog = document.querySelector('#figure-dialog');
  document.querySelectorAll('[data-zoom]').forEach(link => link.addEventListener('click', event => {
    if (typeof dialog.showModal !== 'function') return;
    event.preventDefault();
    const image = document.querySelector('#figure-dialog-image');
    image.src = link.href;
    image.alt = link.querySelector('img').alt;
    document.querySelector('#figure-original').href = link.href;
    document.querySelector('#figure-dialog-caption').textContent = link.dataset.caption;
    dialog.showModal();
  }));
  dialog.querySelector('.dialog-close').addEventListener('click', () => dialog.close());
  dialog.addEventListener('click', event => {
    const bounds = dialog.getBoundingClientRect();
    if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) dialog.close();
  });

  const copy = document.querySelector('#copy-citation');
  if (copy) copy.addEventListener('click', async () => {
    const citation = document.querySelector('#bibtex').textContent;
    let copied = false;
    try {
      await navigator.clipboard.writeText(citation);
      copied = true;
    } catch (_) {
      const field = element('textarea', citation);
      field.setAttribute('readonly', '');
      field.style.position = 'fixed';
      field.style.top = '-1000px';
      document.body.append(field);
      field.select();
      copied = document.execCommand('copy');
      field.remove();
      copy.focus();
    }
    copy.textContent = copied ? 'Copied!' : 'Select and copy below';
    setTimeout(() => { copy.textContent = 'Copy BibTeX'; }, 2500);
  });


})();
