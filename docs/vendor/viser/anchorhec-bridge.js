/* AnchorHEC static viewer adapter, 2026-11-02.
 * Viser 1.0.24 renders the original points/frustums. This adapter changes only
 * their display state and the observing camera; no calibration runs here.
 */
(() => {
  'use strict';
  let scene, viewer, mode = 'ours', selected = null, ready = false;
  const send = (type, extra = {}) => {
    if (window.parent !== window) window.parent.postMessage({source: 'anchorhec-viewer', type, ...extra}, location.origin);
  };
  const attrs = (name, values) => viewer.sceneTreeActions.updateNodeAttributes(name, values);
  const props = (name, values) => viewer.sceneTreeActions.updateSceneNodeProps(name, values);
  const world = () => window.__anchorhecWorld();
  const vector = (xyz) => viewer.mutable.current.camera.position.clone().set(...xyz);
  function setCamera(position, target, up, fov) {
    const m = viewer.mutable.current, w = world();
    const p = vector(position).applyMatrix4(w), t = vector(target).applyMatrix4(w);
    m.camera.up.copy(vector(up).transformDirection(w));
    m.cameraControl.updateCameraUp();
    m.cameraControl.setFocalOffset(0, 0, 0, false);
    m.cameraControl.setLookAt(p.x, p.y, p.z, t.x, t.y, t.z, false);
    if (fov !== undefined) { m.camera.fov = fov * 180 / Math.PI; m.camera.updateProjectionMatrix(); }
    m.cameraControl.update(0);
  }
  function reset() {
    const c = scene.camera;
    // The saved fit assumes at least a square view. Narrow mobile canvases
    // need a larger distance to retain the same horizontal extent.
    const fit = Math.max(1, 1 / viewer.mutable.current.camera.aspect);
    const position = c.look_at.map((x, i) => x + (c.position[i] - x) * fit);
    setCamera(position, c.look_at, c.up, c.fov);
  }
  function highlight(id) {
    if (selected) {
      attrs(selected.raw_node + '/selected', {visibility: false});
      attrs(selected.ours_node + '/selected', {visibility: false});
    }
    selected = scene.inputs.find(input => input.id === id) || null;
    if (selected) {
      attrs(selected.raw_node + '/selected', {visibility: true});
      attrs(selected.ours_node + '/selected', {visibility: true});
      props(selected.raw_node + '/selected/label', {text: selected.label});
      props(selected.ours_node + '/selected/label', {text: selected.label});
    }
  }
  function setMode(next) {
    if (!['raw', 'ours'].includes(next) || next === mode) return;
    // Keep the viewing camera and robot-base reference fixed. The native Raw
    // reconstruction must visibly differ in orientation, position and scale.
    const after = next === 'ours', t = scene.transform;
    attrs('/pointmap', {position: after ? t.position : [0,0,0], wxyz: after ? t.wxyz : [1,0,0,0], poseUpdateState:'needsUpdate'});
    // Viser scales point sprite size with props.scale. Compensate so the
    // Figure 5 point size remains .002 in each displayed coordinate system.
    props('/pointmap', {scale: after ? t.scale : 1, point_size: scene.point_size / (after ? t.scale : 1)});
    attrs('/Ours', {visibility: after}); attrs('/Raw', {visibility: !after});
    attrs('/base', {visibility: true}); attrs('/grid', {visibility: true});
    mode = next;
  }
  window.addEventListener('message', event => {
    if (event.source !== window.parent || event.origin !== location.origin || event.data?.source !== 'anchorhec-page' || !ready) return;
    const data = event.data;
    if (data.type === 'state') { setMode(data.mode); highlight(data.selected); }
    if (data.type === 'reset') reset();
    send('state', {mode, selected: selected?.id || null});
  });
  const fail = () => send('error');
  window.addEventListener('unhandledrejection', fail);
  window.addEventListener('error', fail);
  (async () => {
    const data = await fetch(new URL('../../assets/data/scenes.json', location.href));
    if (!data.ok) throw new Error('Scene metadata unavailable');
    const catalogue = await data.json();
    scene = catalogue.scenes.find(item => item.id === new URLSearchParams(location.search).get('scene'));
    if (!scene) throw new Error('Unknown scene');
    const started = performance.now();
    function wait() {
      viewer = window.__anchorhecViewer;
      const m = viewer?.mutable.current, nodes = viewer?.useSceneTree.getState();
      if (m?.cameraControl && nodes?.['/ready'] && nodes['/pointmap']?.poseUpdateState === 'updated' && m.messageQueue.length === 0) {
        // Wait for React and initial camera messages to settle before announcing.
        requestAnimationFrame(() => requestAnimationFrame(() => {
          reset(); ready = true; window.__anchorhecReady = true;
          send('ready', {scene:scene.id});
        }));
      } else if (performance.now() - started < 90000) setTimeout(wait, 100);
      else fail();
    }
    wait();
  })().catch(fail);
})();
