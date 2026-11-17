/**
 * The 3D journey globe (three.js). Loaded lazily so the main bundle stays small.
 *
 * Techniques (learned from studying Flight Viz's WebGL pipeline, implemented independently):
 * - every land dot is one vertex in a single Points draw call, and all hubs are one instanced
 *   mesh, so thousands of markers cost a couple of draw calls;
 * - geometry is built once; per-frame work is only camera, traveler and label updates.
 *
 * Land dots come from ./land (Natural Earth, public domain). No external textures are loaded.
 */
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import type { Journey, LegStatus } from "../api/types";
import { landPositions } from "./land";
import {
  type LegPath,
  type Vec3,
  cumulativeLengths,
  framing,
  journeyPaths,
  latLonToXyz,
  legColor,
  pointAt,
  scale,
} from "./geo";

export interface Hub {
  key: string;
  name: string;
  lat: number;
  lon: number;
}

export interface GlobeOptions {
  reducedMotion: boolean;
  onLabels?: (labels: ScreenLabel[]) => void;
}

export interface ScreenLabel {
  id: string;
  text: string;
  x: number;
  y: number;
  visible: boolean;
  kind: "hub" | "endpoint";
}

export interface GlobeController {
  setHubs(hubs: Hub[]): void;
  setJourney(journey: Journey | null, statuses?: Record<string, LegStatus>): void;
  dispose(): void;
}

const v3 = (p: Vec3) => new THREE.Vector3(p[0], p[1], p[2]);

function atmosphere(): THREE.Mesh {
  const material = new THREE.ShaderMaterial({
    transparent: true,
    side: THREE.BackSide,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
    uniforms: { glow: { value: new THREE.Color("#3b82f6") } },
    vertexShader: /* glsl */ `
      varying vec3 vNormal;
      void main() {
        vNormal = normalize(normalMatrix * normal);
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }`,
    fragmentShader: /* glsl */ `
      uniform vec3 glow;
      varying vec3 vNormal;
      void main() {
        float rim = pow(0.72 - dot(vNormal, vec3(0.0, 0.0, 1.0)), 3.0);
        gl_FragColor = vec4(glow, 1.0) * rim;
      }`,
  });
  return new THREE.Mesh(new THREE.SphereGeometry(1.18, 64, 64), material);
}

function stars(count: number): THREE.Points {
  const positions = new Float32Array(count * 3);
  for (let i = 0; i < count; i++) {
    const u = Math.random() * 2 - 1;
    const t = Math.random() * Math.PI * 2;
    const r = 18 + Math.random() * 12;
    const s = Math.sqrt(1 - u * u);
    positions.set([r * s * Math.cos(t), r * u, r * s * Math.sin(t)], i * 3);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  return new THREE.Points(g, new THREE.PointsMaterial({ color: 0x9fb4d9, size: 0.06, transparent: true, opacity: 0.8 }));
}

function landDots(): THREE.Points {
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.BufferAttribute(landPositions(0.75, 1.001), 3));
  return new THREE.Points(
    g,
    new THREE.PointsMaterial({ color: 0x5f7aa8, size: 0.0085, sizeAttenuation: true, transparent: true, opacity: 0.9 }),
  );
}

export function createGlobe(canvas: HTMLCanvasElement, opts: GlobeOptions): GlobeController {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(42, 1, 0.001, 100);
  const start = framing([]);
  camera.position.copy(v3(scale(start.direction, start.distance)));

  const controls = new OrbitControls(camera, canvas);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.enablePan = false;
  controls.minDistance = 1.15;
  controls.maxDistance = 4;
  controls.rotateSpeed = 0.5;
  controls.zoomSpeed = 0.6;
  controls.autoRotate = !opts.reducedMotion;
  controls.autoRotateSpeed = 0.35;

  scene.add(new THREE.AmbientLight(0xffffff, 0.55));
  const sun = new THREE.DirectionalLight(0xffffff, 1.2);
  sun.position.set(-3, 2, 4);
  scene.add(sun);

  const globe = new THREE.Mesh(
    new THREE.SphereGeometry(1, 96, 96),
    new THREE.MeshPhongMaterial({ color: 0x0b1530, emissive: 0x050a18, shininess: 12, specular: 0x1d3a6b }),
  );
  scene.add(globe, landDots(), atmosphere(), stars(1500));

  // ---- hubs: one instanced mesh for all of them ----
  let hubs: Hub[] = [];
  let hubMesh: THREE.InstancedMesh | null = null;
  const hubGeometry = new THREE.SphereGeometry(0.0065, 12, 12);
  const hubMaterial = new THREE.MeshBasicMaterial({ color: 0x8ab4ff });

  function setHubs(next: Hub[]) {
    hubs = next;
    if (hubMesh) scene.remove(hubMesh);
    hubMesh = new THREE.InstancedMesh(hubGeometry, hubMaterial, Math.max(1, hubs.length));
    const m = new THREE.Matrix4();
    hubs.forEach((h, i) => {
      m.makeTranslation(v3(latLonToXyz(h.lat, h.lon, 1.003)));
      hubMesh!.setMatrixAt(i, m);
    });
    hubMesh.count = hubs.length;
    hubMesh.instanceMatrix.needsUpdate = true;
    scene.add(hubMesh);
  }

  // ---- journey route ----
  const route = new THREE.Group();
  scene.add(route);
  const traveler = new THREE.Mesh(
    new THREE.SphereGeometry(0.009, 16, 16),
    new THREE.MeshBasicMaterial({ color: 0xffffff }),
  );
  const halo = new THREE.Mesh(
    new THREE.SphereGeometry(0.02, 16, 16),
    new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.25, depthWrite: false }),
  );
  traveler.add(halo);
  let pulsing: THREE.MeshBasicMaterial[] = [];
  let travelPoints: Vec3[] = [];
  let travelLengths: number[] = [];
  let endpoints: { id: string; text: string; pos: Vec3 }[] = [];
  let tween: {
    from: THREE.Vector3;
    to: THREE.Vector3;
    fromTarget: THREE.Vector3;
    toTarget: THREE.Vector3;
    t: number;
  } | null = null;
  const origin = new THREE.Vector3();
  const flyTo = (to: THREE.Vector3, target: THREE.Vector3) => {
    tween = { from: camera.position.clone(), to, fromTarget: controls.target.clone(), toTarget: target, t: 0 };
  };

  function clearRoute() {
    route.children.slice().forEach((child) => {
      route.remove(child);
      if (child instanceof THREE.Mesh && child !== traveler) {
        child.geometry.dispose();
        (child.material as THREE.Material).dispose();
      }
    });
  }

  function tube(path: LegPath, small: boolean): THREE.Mesh {
    const curve = new THREE.CatmullRomCurve3(path.points.map(v3));
    const radius = small ? 0.0009 : path.mode === "flight" ? 0.0032 : 0.0024;
    const color = new THREE.Color(legColor(path));
    const broken = path.status === "cancelled" || path.status === "missed_connection";
    const material = new THREE.MeshBasicMaterial({
      color,
      transparent: true,
      opacity: path.status === "needs_replan" ? 0.35 : broken ? 0.95 : 0.9,
    });
    if (broken) pulsing.push(material);
    return new THREE.Mesh(
      new THREE.TubeGeometry(curve, path.points.length * 2, broken ? radius * 1.6 : radius, 8, false),
      material,
    );
  }

  function setJourney(journey: Journey | null, statuses: Record<string, LegStatus> = {}) {
    clearRoute();
    pulsing = [];
    endpoints = [];
    travelPoints = [];
    if (!journey) {
      const f = framing([]);
      flyTo(v3(scale(f.direction, f.distance)), origin.clone());
      controls.minDistance = 1.15; // orbiting the centre: stay outside the globe
      controls.autoRotate = !opts.reducedMotion;
      return;
    }
    const paths = journeyPaths(journey, statuses);
    const all = paths.flatMap((p) => p.points);
    const f = framing(all);
    // Thin tubes when zoomed far out on a long trip keep local legs from looking like blobs.
    const small = f.distance < 1.3;
    paths.forEach((p) => route.add(tube(p, small)));
    travelPoints = all;
    travelLengths = cumulativeLengths(all);
    route.add(traveler);

    const first = journey.legs[0];
    const last = journey.legs[journey.legs.length - 1];
    endpoints = [
      { id: "from", text: first.origin.name, pos: latLonToXyz(first.origin.lat, first.origin.lon, 1.01) },
      { id: "to", text: last.destination.name, pos: latLonToXyz(last.destination.lat, last.destination.lon, 1.01) },
    ];
    controls.autoRotate = false;
    // Aim at the route (just below the surface) rather than the globe's centre.
    const target = v3(scale(f.direction, f.distance < 1.3 ? 0.97 : 0.9));
    flyTo(tilted(f.direction, f.distance), target);
    // Orbiting a point near the surface: allow close zoom without entering the globe.
    controls.minDistance = Math.max(0.06, 1.04 - target.length());
  }

  /** A 3/4 view from the south, so flight arcs show their height instead of looking flat. */
  function tilted(direction: Vec3, distance: number): THREE.Vector3 {
    const dir = v3(direction).normalize();
    const south = new THREE.Vector3(0, -1, 0).projectOnPlane(dir).normalize();
    const angle = THREE.MathUtils.degToRad(28) * Math.min(1, (distance - 1) / 0.6);
    return dir
      .multiplyScalar(Math.cos(angle))
      .add(south.multiplyScalar(Math.sin(angle)))
      .normalize()
      .multiplyScalar(distance);
  }

  // ---- labels: projected to screen each frame, hidden behind the globe ----
  const tmp = new THREE.Vector3();
  function project(id: string, text: string, pos: Vec3, kind: ScreenLabel["kind"]): ScreenLabel {
    tmp.set(pos[0], pos[1], pos[2]);
    const facing = tmp.clone().normalize().dot(camera.position.clone().normalize()) > 0.15;
    tmp.project(camera);
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    return {
      id,
      text,
      kind,
      x: (tmp.x * 0.5 + 0.5) * w,
      y: (-tmp.y * 0.5 + 0.5) * h,
      visible: facing && tmp.z < 1,
    };
  }

  function resize() {
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    if (!w || !h) return;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }
  const observer = new ResizeObserver(resize);
  observer.observe(canvas);
  resize();

  const stopAuto = () => (controls.autoRotate = false);
  controls.addEventListener("start", stopAuto);

  let frame = 0;
  let last = performance.now();
  let travelT = 0;
  let labelTick = 0;
  function loop(now: number) {
    frame = requestAnimationFrame(loop);
    const dt = Math.min(0.05, (now - last) / 1000);
    last = now;
    if (tween) {
      tween.t = Math.min(1, tween.t + dt / 1.4);
      const e = 1 - Math.pow(1 - tween.t, 3);
      // Move along the sphere (not through it) by interpolating direction and distance.
      const dir = tween.from.clone().normalize().lerp(tween.to.clone().normalize(), e).normalize();
      const dist = THREE.MathUtils.lerp(tween.from.length(), tween.to.length(), e);
      camera.position.copy(dir.multiplyScalar(dist));
      controls.target.lerpVectors(tween.fromTarget, tween.toTarget, e);
      if (tween.t >= 1) tween = null;
    }
    controls.update();
    if (travelPoints.length) {
      travelT = opts.reducedMotion ? 1 : (travelT + dt / 9) % 1;
      const p = pointAt(travelPoints, travelLengths, travelT);
      traveler.position.set(p[0], p[1], p[2]);
      halo.scale.setScalar(1 + 0.35 * Math.sin(now / 220));
    }
    // Cancelled or missed legs pulse so they stand out from normal (red) flights.
    const pulse = opts.reducedMotion ? 1 : 0.35 + 0.65 * Math.abs(Math.sin(now / 380));
    pulsing.forEach((m) => (m.opacity = pulse));
    renderer.render(scene, camera);
    if (opts.onLabels && ++labelTick % 2 === 0) {
      const labels: ScreenLabel[] = endpoints.map((e) => project(e.id, e.text, e.pos, "endpoint"));
      if (!endpoints.length) {
        hubs.forEach((h) => labels.push(project(h.key, h.name, latLonToXyz(h.lat, h.lon, 1.01), "hub")));
      }
      opts.onLabels(labels);
    }
  }
  frame = requestAnimationFrame(loop);

  return {
    setHubs,
    setJourney,
    dispose() {
      cancelAnimationFrame(frame);
      observer.disconnect();
      controls.removeEventListener("start", stopAuto);
      controls.dispose();
      clearRoute();
      scene.traverse((obj) => {
        if (obj instanceof THREE.Mesh || obj instanceof THREE.Points) {
          obj.geometry.dispose();
          const mats = Array.isArray(obj.material) ? obj.material : [obj.material];
          mats.forEach((m) => m.dispose());
        }
      });
      renderer.dispose();
    },
  };
}
