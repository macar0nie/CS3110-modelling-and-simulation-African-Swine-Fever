"""
3D playback viewer.

Python runs the whole simulation first (asf_model.py). This module turns the result into
one HTML page with a Three.js 3D farm that replays the run day by day: the pigs walk along
the positions the model computed, and their colour shows their disease state on that day.

The viewer only DISPLAYS results. It does not change or compute anything in the model.
Three.js is served from the app's own ./static folder (no internet CDN needed).
"""

import json

STATE_COLORS = {
    "S": "#f4a3b5",  # healthy pig pink
    "E": "#facc15",  # yellow
    "I": "#ef4444",  # red
    "R": "#22c55e",  # green
    "D": "#52525b",  # dark grey
    "X": "#52525b",
}

THREE_BASE = "/app/static/three/"


def build_viewer_html(result, autoplay=True, height=620):
    data = {
        "pens": result.pens,
        "isolation": result.isolation_pen,
        "frames": result.frames,
        "states": result.states,
        "daily": result.daily,
        "days": result.settings["days"],
        "colors": STATE_COLORS,
        "autoplay": autoplay,
    }
    payload = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    return (
        HTML_TEMPLATE.replace("__DATA__", payload)
        .replace("__THREE__", THREE_BASE)
        .replace("__HEIGHT__", str(height))
    )


HTML_TEMPLATE = r"""<!doctype html>
<html><head><meta charset="utf-8">
<style>
  html,body{margin:0;height:100%;background:#0f172a;font-family:'Segoe UI',system-ui,sans-serif;color:#e2e8f0;overflow:hidden}
  #wrap{position:relative;width:100%;height:__HEIGHT__px}
  canvas#scene{display:block}
  .panel{position:absolute;background:rgba(15,23,42,.82);border:1px solid #334155;border-radius:10px;padding:8px 10px;font-size:13px}
  #controls{top:10px;left:10px;display:flex;gap:6px;align-items:center}
  button,select{background:#1e293b;color:#e2e8f0;border:1px solid #475569;border-radius:7px;padding:5px 10px;font-size:13px;cursor:pointer}
  button.play{background:#16a34a;border-color:#16a34a;color:white;font-weight:600}
  button.stop{background:#991b1b;border-color:#b91c1c;color:white}
  #day{font-weight:700;font-size:15px;margin-left:6px;min-width:110px}
  #counts{top:10px;right:10px;min-width:170px}
  #counts div{display:flex;justify-content:space-between;gap:12px}
  #counts i{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:6px}
  #chartbox{bottom:10px;right:10px}
  #legend{bottom:10px;left:10px;font-size:12px}
  #legend i{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:6px}
  #err{position:absolute;inset:0;display:none;align-items:center;justify-content:center;text-align:center;padding:30px}
</style>
<script type="importmap">{"imports":{"three":"__THREE__three.module.js","three/addons/":"__THREE__"}}</script>
</head><body>
<div id="wrap">
  <canvas id="scene"></canvas>
  <div id="controls" class="panel">
    <button id="play" class="play">⏸ Pause</button>
    <button id="stop" class="stop">⏹ Stop</button>
    <select id="speed" title="Playback speed">
      <option value="0.5">0.5 day/s</option><option value="1">1 day/s</option>
      <option value="2" selected>2 days/s</option><option value="4">4 days/s</option><option value="8">8 days/s</option>
    </select>
    <span id="day">Day 0</span>
  </div>
  <div id="counts" class="panel"></div>
  <div id="chartbox" class="panel"><canvas id="chart" width="280" height="140"></canvas></div>
  <div id="legend" class="panel"></div>
  <div id="err" class="panel"></div>
</div>
<script type="module">
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/OrbitControls.js';
import { mergeGeometries } from 'three/addons/BufferGeometryUtils.js';

const DATA = __DATA__;
const STEPS = DATA.frames[1] ? DATA.frames[1].length : 6;   // movement steps per day
const N = DATA.states[0].length;                              // number of pigs
const NAMES = {S:'Susceptible',E:'Exposed',I:'Infectious',R:'Recovered',D:'Dead'};

// ---------- timeline: position index 0 = start, then STEPS positions per day ----------
const timeline = [DATA.frames[0][0]];
for (let d = 1; d < DATA.frames.length; d++) for (const f of DATA.frames[d]) timeline.push(f);
const lastIndex = timeline.length - 1;

// ---------- renderer, scene, camera ----------
const wrap = document.getElementById('wrap');
const canvas = document.getElementById('scene');
let renderer;
try { renderer = new THREE.WebGLRenderer({canvas, antialias:true}); }
catch (e) { const el = document.getElementById('err'); el.style.display='flex'; el.textContent='3D view needs WebGL. Please use a recent Chrome or Edge.'; throw e; }
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFShadowMap;
const scene = new THREE.Scene();
scene.background = new THREE.Color('#bfdbfe');
scene.fog = new THREE.Fog('#bfdbfe', 70, 140);
const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 400);
const controls = new OrbitControls(camera, canvas);
controls.enableDamping = true;
controls.maxPolarAngle = Math.PI / 2.1;

function resize(){ const w = wrap.clientWidth, h = wrap.clientHeight; renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix(); }
window.addEventListener('resize', resize); resize();

scene.add(new THREE.HemisphereLight('#ffffff', '#64748b', 1.1));
const sun = new THREE.DirectionalLight('#fff7ed', 2.0);
sun.position.set(15, 30, 12); sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048);
Object.assign(sun.shadow.camera, {left:-35, right:35, top:25, bottom:-25, near:1, far:80});
scene.add(sun);

// ---------- farm ----------
const allRects = [...DATA.pens, DATA.isolation];
const minX = Math.min(...allRects.map(r=>r.min_x)) - 3, maxX = Math.max(...allRects.map(r=>r.max_x)) + 3;
const minZ = Math.min(...allRects.map(r=>r.min_z)) - 3, maxZ = Math.max(...allRects.map(r=>r.max_z)) + 3;
const cx = (minX+maxX)/2, cz = (minZ+maxZ)/2, span = Math.max(maxX-minX, maxZ-minZ);
camera.position.set(cx, span*0.5, cz + span*0.55); controls.target.set(cx, 0, cz);

const ground = new THREE.Mesh(new THREE.PlaneGeometry(400, 400), new THREE.MeshStandardMaterial({color:'#4d7c0f', roughness:1}));
ground.rotation.x = -Math.PI/2; ground.position.y = -0.02; ground.receiveShadow = true; scene.add(ground);
const slab = new THREE.Mesh(new THREE.PlaneGeometry(maxX-minX, maxZ-minZ), new THREE.MeshStandardMaterial({color:'#d6d3d1', roughness:.95}));
slab.rotation.x = -Math.PI/2; slab.position.set(cx, 0, cz); slab.receiveShadow = true; scene.add(slab);

const railMat = new THREE.MeshStandardMaterial({color:'#8b5a2b', roughness:.8});
const postGeo = new THREE.CylinderGeometry(0.06, 0.06, 1.0, 8);
function fence(x1, z1, x2, z2){
  const len = Math.hypot(x2-x1, z2-z1), ang = Math.atan2(z2-z1, x2-x1);
  const g = new THREE.Group(); g.position.set((x1+x2)/2, 0, (z1+z2)/2); g.rotation.y = -ang;
  for (const y of [0.35, 0.75]) { const r = new THREE.Mesh(new THREE.BoxGeometry(len, 0.07, 0.05), railMat); r.position.y = y; r.castShadow = true; g.add(r); }
  const posts = Math.max(2, Math.round(len/2)+1);
  for (let i = 0; i < posts; i++) { const p = new THREE.Mesh(postGeo, railMat); p.position.set(-len/2 + i*len/(posts-1), 0.5, 0); p.castShadow = true; g.add(p); }
  scene.add(g);
}
function label(text, x, y, z){
  const c = document.createElement('canvas'); c.width = 256; c.height = 64; const g = c.getContext('2d');
  g.fillStyle = 'rgba(15,23,42,.8)'; g.beginPath(); g.roundRect(4,4,248,56,14); g.fill();
  g.fillStyle = '#f8fafc'; g.font = 'bold 30px Segoe UI, Arial'; g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText(text, 128, 33);
  const s = new THREE.Sprite(new THREE.SpriteMaterial({map:new THREE.CanvasTexture(c), depthTest:false}));
  s.scale.set(0.1, 0.025, 1); s.material.sizeAttenuation = false; s.position.set(x, y, z); s.renderOrder = 5; scene.add(s);
}
const troughMat = new THREE.MeshStandardMaterial({color:'#78716c'});
const waterMat = new THREE.MeshStandardMaterial({color:'#38bdf8', roughness:.2});
for (const r of allRects){
  const iso = r === DATA.isolation;
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(r.max_x-r.min_x, r.max_z-r.min_z), new THREE.MeshStandardMaterial({color: iso ? '#a5f3fc' : '#e7d8c4', roughness:1}));
  floor.rotation.x = -Math.PI/2; floor.position.set((r.min_x+r.max_x)/2, 0.01, (r.min_z+r.max_z)/2); floor.receiveShadow = true; scene.add(floor);
  fence(r.min_x, r.min_z, r.max_x, r.min_z); fence(r.min_x, r.max_z, r.max_x, r.max_z);
  fence(r.min_x, r.min_z, r.min_x, r.max_z); fence(r.max_x, r.min_z, r.max_x, r.max_z);
  if (!iso) {
    const back = r.max_z < 0 ? r.min_z + 0.35 : r.max_z - 0.35;
    const t = new THREE.Mesh(new THREE.BoxGeometry((r.max_x-r.min_x)*0.5, 0.25, 0.3), troughMat); t.position.set((r.min_x+r.max_x)/2, 0.13, back); t.castShadow = true; scene.add(t);
    const w = new THREE.Mesh(new THREE.CylinderGeometry(0.15, 0.15, 0.45, 12), waterMat); w.position.set(r.max_x-0.45, 0.23, back); scene.add(w);
  }
  label(r.label, (r.min_x+r.max_x)/2, 1.8, r.max_z < 0 ? r.min_z : r.max_z);
}

// ---------- pig model: smooth shapes merged into ONE geometry, drawn with instancing ----------
function part(geo, x, y, z, shade, sx=1, sy=1, sz=1, rx=0, rz=0){
  geo.scale(sx, sy, sz); if (rx) geo.rotateX(rx); if (rz) geo.rotateZ(rz); geo.translate(x, y, z);
  const n = geo.attributes.position.count, col = new Float32Array(n*3).fill(shade);
  geo.setAttribute('color', new THREE.BufferAttribute(col, 3));
  return geo;
}
const parts = [
  part(new THREE.SphereGeometry(0.5, 20, 14), 0, 0.55, 0, 1, 0.56, 0.5, 0.88),            // body
  part(new THREE.SphereGeometry(0.27, 16, 12), 0, 0.68, 0.6, 1),                            // head
  part(new THREE.CylinderGeometry(0.11, 0.12, 0.12, 14), 0, 0.62, 0.86, 0.75, 1,1,1, Math.PI/2), // snout
  part(new THREE.ConeGeometry(0.09, 0.18, 8), 0.14, 0.92, 0.58, 0.85, 1,1,1, 0, -0.4),       // ear
  part(new THREE.ConeGeometry(0.09, 0.18, 8), -0.14, 0.92, 0.58, 0.85, 1,1,1, 0, 0.4),       // ear
  part(new THREE.SphereGeometry(0.035, 8, 6), 0.11, 0.76, 0.83, 0.05),                      // eye
  part(new THREE.SphereGeometry(0.035, 8, 6), -0.11, 0.76, 0.83, 0.05),                     // eye
  part(new THREE.SphereGeometry(0.07, 8, 6), 0, 0.68, -0.86, 0.85),                         // tail
  ...[[0.2,0.32],[-0.2,0.32],[0.2,-0.3],[-0.2,-0.3]].map(([x,z]) => part(new THREE.CylinderGeometry(0.075, 0.065, 0.36, 10), x, 0.18, z, 0.8)), // legs
];
const pigGeo = mergeGeometries(parts.map(g => g.index ? g.toNonIndexed() : g));
const pigMat = new THREE.MeshStandardMaterial({vertexColors:true, roughness:0.55});
const pigs = new THREE.InstancedMesh(pigGeo, pigMat, N);
pigs.castShadow = true; pigs.frustumCulled = false; scene.add(pigs);
const ringGeo = new THREE.RingGeometry(0.55, 0.7, 24); ringGeo.rotateX(-Math.PI/2);
const rings = new THREE.InstancedMesh(ringGeo, new THREE.MeshBasicMaterial({color:'#0891b2'}), N);
rings.frustumCulled = false; scene.add(rings);

// ---------- playback state ----------
let tau = 0;                       // position on the timeline, in movement steps
let playing = !!DATA.autoplay;
let daysPerSecond = 2;
const heading = new Float32Array(N);
const m = new THREE.Matrix4(), q = new THREE.Quaternion(), v = new THREE.Vector3(), one = new THREE.Vector3(1,1,1), zero = new THREE.Vector3(0,0,0);
const yAxis = new THREE.Vector3(0,1,0), lie = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0,0,1), Math.PI/2);
const color = new THREE.Color();

const playBtn = document.getElementById('play');
function setPlaying(p){ playing = p; playBtn.textContent = p ? '⏸ Pause' : '▶ Play'; playBtn.className = p ? '' : 'play'; }
setPlaying(playing);
playBtn.onclick = () => { if (tau >= lastIndex) tau = 0; setPlaying(!playing); };
document.getElementById('stop').onclick = () => { tau = 0; setPlaying(false); };
document.getElementById('speed').onchange = e => daysPerSecond = Number(e.target.value);

// legend
document.getElementById('legend').innerHTML = ['S','E','I','R','D'].map(s => `<div><i style="background:${DATA.colors[s]}"></i>${NAMES[s]}</div>`).join('')
  + '<div><i style="background:none;border:2px solid #0891b2;width:7px;height:7px"></i>In isolation</div><div style="color:#94a3b8">Removed carcasses disappear</div>';

function drawCounts(day){
  const d = DATA.daily[day];
  const rows = [['S',d.S],['E',d.E],['I',d.I],['R',d.R],['D',d.D + d.X]];
  document.getElementById('counts').innerHTML = rows.map(([s,c]) => `<div><span><i style="background:${DATA.colors[s]}"></i>${NAMES[s]}</span><b>${c}</b></div>`).join('')
    + `<div style="margin-top:4px;color:#94a3b8"><span>Total infected</span><b>${d.total_infected}</b></div>`;
}
const chart = document.getElementById('chart'), cg = chart.getContext('2d');
function drawChart(day){
  const W = chart.width, H = chart.height, n = DATA.days, maxY = N;
  cg.clearRect(0,0,W,H); cg.strokeStyle = '#334155'; cg.strokeRect(24, 6, W-30, H-24);
  cg.fillStyle = '#94a3b8'; cg.font = '10px sans-serif'; cg.fillText(String(maxY), 2, 12); cg.fillText('0', 12, H-18); cg.fillText('day', W-24, H-4);
  const series = [['S', d=>d.S], ['E', d=>d.E], ['I', d=>d.I], ['R', d=>d.R], ['D', d=>d.D+d.X]];
  for (const [s, f] of series){
    cg.strokeStyle = DATA.colors[s]; cg.lineWidth = 2; cg.beginPath();
    for (let i = 0; i <= day; i++){ const x = 24 + (W-30)*i/n, y = 6 + (H-24)*(1 - f(DATA.daily[i])/maxY); i ? cg.lineTo(x,y) : cg.moveTo(x,y); }
    cg.stroke();
  }
}

let lastDay = -1, last = performance.now();
function frame(now){
  const dt = Math.min(0.1, Math.max(0, (now - last) / 1000)); last = now;
  if (playing){ tau += dt * daysPerSecond * STEPS; if (tau >= lastIndex){ tau = lastIndex; setPlaying(false); } }
  tau = Math.max(0, tau);
  const i0 = Math.floor(tau), i1 = Math.min(lastIndex, i0 + 1), t = tau - i0;
  const day = Math.min(DATA.days, Math.floor(tau / STEPS));
  const states = DATA.states[day];
  const A = timeline[i0], B = timeline[i1];
  let ringCount = 0;
  for (let p = 0; p < N; p++){
    const raw = states[p], st = raw.toUpperCase(), isolated = raw !== st;
    const ax = A[2*p], az = A[2*p+1], bx = B[2*p], bz = B[2*p+1];
    const x = ax + (bx-ax)*t, z = az + (bz-az)*t;
    const dx = bx-ax, dz = bz-az;
    const jump = dx*dx + dz*dz > 36;  // moved to another pen or isolation: no walking animation
    if (!jump && dx*dx + dz*dz > 1e-4 && st !== 'D' && st !== 'X'){
      let diff = Math.atan2(dx, dz) - heading[p]; diff = Math.atan2(Math.sin(diff), Math.cos(diff)); heading[p] += diff * 0.12;
    }
    q.setFromAxisAngle(yAxis, heading[p]);
    if (st === 'X') m.compose(v.set(x,0,z), q, zero);
    else if (st === 'D') { const qq = q.clone().multiply(lie); m.compose(v.set(x,0.5,z), qq, one); }
    else { const bob = playing && !jump ? Math.abs(Math.sin(now/120 + p))*0.04 : 0; m.compose(v.set(jump ? bx : x, bob, jump ? bz : z), q, one); }
    pigs.setMatrixAt(p, m);
    pigs.setColorAt(p, color.set(DATA.colors[st]));
    if (isolated && st !== 'X'){ m.makeTranslation(x, 0.03, z); rings.setMatrixAt(ringCount++, m); }
  }
  pigs.instanceMatrix.needsUpdate = true; if (pigs.instanceColor) pigs.instanceColor.needsUpdate = true;
  rings.count = ringCount; rings.instanceMatrix.needsUpdate = true;
  if (day !== lastDay){ lastDay = day; document.getElementById('day').textContent = `Day ${day} / ${DATA.days}`; drawCounts(day); drawChart(day); }
  controls.update(); renderer.render(scene, camera);
  requestAnimationFrame(frame);
}
requestAnimationFrame(frame);
</script>
</body></html>
"""
