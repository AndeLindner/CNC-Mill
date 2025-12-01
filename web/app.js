import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

const api = "/api";
const wsUrl = `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`;

const els = {
  fileSelect: document.getElementById("file-select"),
  refreshFiles: document.getElementById("refresh-files"),
  fileUpload: document.getElementById("file-upload"),
  uploadBtn: document.getElementById("upload-btn"),
  toolSelect: document.getElementById("tool-select"),
  newToolBtn: document.getElementById("new-tool-btn"),
  toolForm: document.getElementById("tool-form-card"),
  saveToolBtn: document.getElementById("save-tool-btn"),
  startBtn: document.getElementById("start-btn"),
  pauseBtn: document.getElementById("pause-btn"),
  resumeBtn: document.getElementById("resume-btn"),
  stopBtn: document.getElementById("stop-btn"),
  homeBtn: document.getElementById("home-btn"),
  statusBar: document.getElementById("status-bar"),
  lineInfo: document.getElementById("line-info"),
  posDisplay: document.getElementById("pos-display"),
  wcoX: document.getElementById("wco-x"),
  wcoY: document.getElementById("wco-y"),
  wcoZ: document.getElementById("wco-z"),
  setWcoBtn: document.getElementById("set-wco-btn"),
  manualToggle: document.getElementById("manual-toggle"),
};

let viewer;
let tools = [];
let currentPreview = null;
let manualEnabled = false;
const manualStep = 1;
const manualKeyMap = {
  KeyA: { axis: "X", delta: -1 },
  KeyD: { axis: "X", delta: 1 },
  KeyW: { axis: "Y", delta: 1 },
  KeyS: { axis: "Y", delta: -1 },
  ArrowUp: { axis: "Z", delta: 1 },
  ArrowDown: { axis: "Z", delta: -1 },
};

function setManualMode(enabled) {
  manualEnabled = enabled;
  if (!els.manualToggle) return;
  els.manualToggle.classList.toggle("active", enabled);
  els.manualToggle.textContent = enabled ? "Manuelles Steuern an" : "Manuelles Steuern aus";
}

function handleManualKey(event) {
  if (!manualEnabled) return;
  const tag = document.activeElement?.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
  const map = manualKeyMap[event.code];
  if (!map) return;
  event.preventDefault();
  const multiplier = event.shiftKey ? 5 : 1;
  jogAxis(map.axis, map.delta * manualStep * multiplier);
}

async function jogAxis(axis, delta) {
  try {
    await fetchJson(`${api}/jog`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ axis, delta }),
    });
  } catch (err) {
    console.error("Jog failed", err);
  }
}

async function fetchJson(url, options = {}) {
  const res = await fetch(url, options);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

async function loadFiles(preferredName) {
  const files = await fetchJson(`${api}/files`);
  els.fileSelect.innerHTML = "";
  files.forEach((f) => {
    const opt = document.createElement("option");
    opt.value = f.name;
    opt.textContent = `${f.name} (${(f.size / 1024).toFixed(1)} KB)`;
    els.fileSelect.appendChild(opt);
  });
  if (!files.length) {
    currentPreview = null;
    return files;
  }
  let targetName = preferredName || els.fileSelect.value;
  if (!files.find((f) => f.name === targetName)) targetName = files[0].name;
  els.fileSelect.value = targetName;
  await loadPreview(targetName);
  return files;
}

async function loadTools() {
  tools = await fetchJson(`${api}/tools`);
  els.toolSelect.innerHTML = "";
  const noneOpt = document.createElement("option");
  noneOpt.value = "";
  noneOpt.textContent = "Kein Werkzeug";
  els.toolSelect.appendChild(noneOpt);
  tools.forEach((t) => {
    const opt = document.createElement("option");
    opt.value = t.id;
    opt.textContent = `${t.name} (${t.diameter_mm}mm)`;
    els.toolSelect.appendChild(opt);
  });
}

async function loadPreview(name) {
  try {
    const preview = await fetchJson(`${api}/files/${encodeURIComponent(name)}/preview`);
    currentPreview = preview;
    const tool = tools.find((t) => String(t.id) === String(els.toolSelect.value));
    const diameter = tool ? tool.diameter_mm : 3;
    viewer.load(preview, diameter, getWorkOffset());
  } catch (err) {
    console.error(err);
  }
}

async function uploadFile() {
  const file = els.fileUpload.files[0];
  if (!file) return alert("Datei wählen");
  const form = new FormData();
  form.append("upload", file);
  await fetchJson(`${api}/files`, { method: "POST", body: form });
  await loadFiles(file.name);
}

async function saveTool() {
  const payload = {
    name: document.getElementById("tool-name").value,
    diameter_mm: parseFloat(document.getElementById("tool-diameter").value),
    length_mm: parseFloat(document.getElementById("tool-length").value),
    rpm: parseFloat(document.getElementById("tool-rpm").value),
    feed_mm_min: parseFloat(document.getElementById("tool-feed").value),
    direction: document.getElementById("tool-dir").value,
    climb: document.getElementById("tool-climb").checked,
  };
  await fetchJson(`${api}/tools`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  els.toolForm.style.display = "none";
  await loadTools();
}

async function startJob() {
  const filename = els.fileSelect.value;
  if (!filename) return alert("Keine Datei gewählt");
  const toolId = els.toolSelect.value || null;
  await fetchJson(`${api}/job/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ filename, tool_id: toolId ? Number(toolId) : null }),
  });
}

async function setWorkOffset() {
  const payload = getWorkOffset();
  await fetchJson(`${api}/workoffset`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (currentPreview) viewer.load(currentPreview, viewer.toolDiameter, payload);
}

function getWorkOffset() {
  return {
    x: parseFloat(els.wcoX.value || "0") || 0,
    y: parseFloat(els.wcoY.value || "0") || 0,
    z: parseFloat(els.wcoZ.value || "0") || 0,
  };
}

function wireEvents() {
  els.refreshFiles.onclick = () => loadFiles();
  els.fileSelect.onchange = (e) => loadPreview(e.target.value);
  els.toolSelect.onchange = () => {
    const tool = tools.find((t) => String(t.id) === String(els.toolSelect.value));
    viewer.setToolDiameter(tool ? tool.diameter_mm : 3);
    if (currentPreview) viewer.load(currentPreview, viewer.toolDiameter, getWorkOffset());
  };
  els.uploadBtn.onclick = uploadFile;
  els.newToolBtn.onclick = () => (els.toolForm.style.display = "block");
  els.saveToolBtn.onclick = saveTool;
  els.startBtn.onclick = startJob;
  els.pauseBtn.onclick = () => fetchJson(`${api}/job/pause`, { method: "POST" });
  els.resumeBtn.onclick = () => fetchJson(`${api}/job/resume`, { method: "POST" });
  els.stopBtn.onclick = () => fetchJson(`${api}/job/stop`, { method: "POST" });
  els.homeBtn.onclick = () => fetchJson(`${api}/job/home`, { method: "POST" });
  els.setWcoBtn.onclick = setWorkOffset;
  if (els.manualToggle) {
    els.manualToggle.onclick = () => setManualMode(!manualEnabled);
  }
}

function connectWS() {
  const ws = new WebSocket(wsUrl);
  ws.onmessage = (evt) => {
    const payload = JSON.parse(evt.data);
    if (!payload.state) return;
    renderState(payload.state);
  };
  ws.onclose = () => setTimeout(connectWS, 1000);
}

function renderState(state) {
  els.statusBar.textContent = `Status: ${state.status} | Feed: ${state.feed_rate.toFixed(
    1
  )} mm/min | Spindle: ${state.spindle_rpm.toFixed(0)} rpm ${state.spindle_dir}`;
  els.lineInfo.textContent = `Zeile ${state.current_line} / ${state.total_lines} | Datei: ${
    state.job_file || "--"
  }`;
  const pos = state.machine_pos || [0, 0, 0];
  els.posDisplay.textContent = `X: ${pos[0].toFixed(3)} Y: ${pos[1].toFixed(3)} Z: ${pos[2].toFixed(3)}`;
  viewer.updatePosition(pos);
  if (state.work_offset) {
    els.wcoX.value = state.work_offset.x.toFixed(3);
    els.wcoY.value = state.work_offset.y.toFixed(3);
    els.wcoZ.value = state.work_offset.z.toFixed(3);
  }
}

class Viewer {
  constructor(canvas) {
    this.canvas = canvas;
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x0b1224);
    this.camera = new THREE.PerspectiveCamera(50, canvas.clientWidth / canvas.clientHeight, 0.1, 5000);
    this.camera.position.set(-200, 200, 200);
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
    this.renderer.setSize(canvas.clientWidth, canvas.clientHeight);
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.grid = new THREE.GridHelper(400, 20, 0x233146, 0x233146);
    this.axes = new THREE.AxesHelper(80);
    this.scene.add(this.grid, this.axes);
    this.pathGroup = new THREE.Group();
    this.scene.add(this.pathGroup);
    this.marker = new THREE.Mesh(
      new THREE.SphereGeometry(2.5, 24, 24),
      new THREE.MeshBasicMaterial({ color: 0xffffff })
    );
    this.scene.add(this.marker);
    this.cutter = new THREE.Mesh(
      new THREE.CylinderGeometry(1, 1, 8, 32),
      new THREE.MeshBasicMaterial({ color: 0x22d3ee, transparent: true, opacity: 0.35 })
    );
    this.cutter.rotation.x = Math.PI / 2;
    this.scene.add(this.cutter);
    this.bboxHelper = null;
    this.toolDiameter = 3;
    this.workOffset = { x: 0, y: 0, z: 0 };
    this.simPath = [];
    this.simSegmentIndex = 0;
    this.simSegmentDistance = 0;
    this.simSpeed = 80;
    this.simulating = false;
    this.clock = new THREE.Clock();
    this.resizeObserver = new ResizeObserver(() => this.onResize());
    this.resizeObserver.observe(this.canvas);
    window.addEventListener("resize", () => this.onResize());
    this.animate();
  }

  setToolDiameter(d) {
    this.toolDiameter = d;
    this.cutter.scale.set(this.toolDiameter / 2, 1, this.toolDiameter / 2);
  }

  load(preview, diameter, workOffset = { x: 0, y: 0, z: 0 }) {
    this.toolDiameter = diameter;
    this.workOffset = {
      x: Number(workOffset.x) || 0,
      y: Number(workOffset.y) || 0,
      z: Number(workOffset.z) || 0,
    };
    while (this.pathGroup.children.length) this.pathGroup.remove(this.pathGroup.children[0]);
    const feedPositions = [];
    const rapidPositions = [];
    const simPoints = [];
    const offsetVec = new THREE.Vector3(this.workOffset.x, this.workOffset.y, this.workOffset.z);
    (preview.segments || []).forEach((s) => {
      const arr = s.rapid ? rapidPositions : feedPositions;
      const startVec = new THREE.Vector3(...s.start).sub(offsetVec);
      const endVec = new THREE.Vector3(...s.end).sub(offsetVec);
      arr.push(startVec.x, startVec.y, startVec.z, endVec.x, endVec.y, endVec.z);
      if (!simPoints.length || !simPoints[simPoints.length - 1].equals(startVec)) simPoints.push(startVec.clone());
      simPoints.push(endVec.clone());
    });
    if (feedPositions.length) {
      const geo = new THREE.BufferGeometry();
      geo.setAttribute("position", new THREE.Float32BufferAttribute(feedPositions, 3));
      this.pathGroup.add(new THREE.LineSegments(geo, new THREE.LineBasicMaterial({ color: 0x22d3ee })));
    }
    if (rapidPositions.length) {
      const geo = new THREE.BufferGeometry();
      geo.setAttribute("position", new THREE.Float32BufferAttribute(rapidPositions, 3));
      const line = new THREE.LineSegments(
        geo,
        new THREE.LineDashedMaterial({ color: 0xf59e0b, dashSize: 2, gapSize: 2 })
      );
      line.computeLineDistances();
      this.pathGroup.add(line);
    }
    if (this.bboxHelper) this.scene.remove(this.bboxHelper);
    const box = new THREE.Box3(
      new THREE.Vector3(...preview.bbox_min).sub(offsetVec),
      new THREE.Vector3(...preview.bbox_max).sub(offsetVec)
    );
    this.bboxHelper = new THREE.Box3Helper(box, 0x475569);
    this.scene.add(this.bboxHelper);
    this.fitCamera(box);
    this.setToolDiameter(diameter);
    this.startSimulation(simPoints);
  }

  fitCamera(box) {
    const size = new THREE.Vector3();
    const center = new THREE.Vector3();
    box.getSize(size);
    box.getCenter(center);
    const maxDim = Math.max(size.x, size.y, size.z, 100);
    const dist = maxDim * 1.5;
    this.camera.position.set(center.x - dist, center.y + dist, center.z + dist);
    this.controls.target.copy(center);
    this.controls.update();
  }

  updatePosition(pos) {
    this.stopSimulation();
    this.updatePositionVec(new THREE.Vector3(pos[0], pos[1], pos[2]));
  }

  updatePositionVec(vec) {
    this.marker.position.copy(vec);
    this.cutter.position.copy(vec);
  }

  onResize() {
    const { clientWidth, clientHeight } = this.canvas;
    this.camera.aspect = clientWidth / clientHeight;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(clientWidth, clientHeight);
  }

  animate() {
    requestAnimationFrame(() => this.animate());
    const delta = this.clock.getDelta();
    this.updateSimulation(delta);
    this.controls.update();
    this.renderer.render(this.scene, this.camera);
  }

  startSimulation(points) {
    if (!points || points.length < 2) {
      this.simPath = [];
      this.simulating = false;
      return;
    }
    this.simPath = points;
    this.simSegmentIndex = 0;
    this.simSegmentDistance = 0;
    this.simulating = true;
    this.updatePositionVec(points[0]);
  }

  stopSimulation() {
    this.simulating = false;
  }

  updateSimulation(delta) {
    if (!this.simulating || this.simPath.length < 2) return;
    let travel = this.simSpeed * delta;
    while (travel > 0 && this.simSegmentIndex < this.simPath.length - 1) {
      const current = this.simPath[this.simSegmentIndex];
      const next = this.simPath[this.simSegmentIndex + 1];
      const segmentLength = current.distanceTo(next);
      if (segmentLength === 0) {
        this.simSegmentIndex++;
        this.simSegmentDistance = 0;
        continue;
      }
      const remaining = segmentLength - this.simSegmentDistance;
      if (travel >= remaining) {
        this.simSegmentIndex++;
        this.simSegmentDistance = 0;
        travel -= remaining;
        this.updatePositionVec(next);
      } else {
        this.simSegmentDistance += travel;
        const ratio = this.simSegmentDistance / segmentLength;
        const pos = current.clone().lerp(next, ratio);
        this.updatePositionVec(pos);
        travel = 0;
      }
    }
    if (this.simSegmentIndex >= this.simPath.length - 1) {
      this.simulating = false;
    }
  }
}

async function init() {
  viewer = new Viewer(document.getElementById("viewport"));
  setManualMode(false);
  wireEvents();
  window.addEventListener("keydown", handleManualKey);
  await loadFiles();
  await loadTools();
  connectWS();
}

init().catch((err) => console.error(err));
