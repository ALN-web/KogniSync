/**
 * Landing-page 3D scenes (three.js, lazily loaded).
 * Brushed metal lit by orange key lights, after the reference design. Reflections come from
 * three's procedural RoomEnvironment, so no HDR or texture files are downloaded.
 */
import * as THREE from "three";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";
import { arcPoints, cumulativeLengths, latLonToXyz, pointAt, type Vec3 } from "../globe/geo";
import { landPositions } from "../globe/land";

export interface SceneHandle {
  dispose(): void;
}

interface Built {
  scene: THREE.Scene;
  camera: THREE.PerspectiveCamera;
  update(time: number, dt: number): void;
}

interface RunOptions {
  reducedMotion: boolean;
}

const ORANGE = new THREE.Color("#ff5a2c");

function run(
  canvas: HTMLCanvasElement,
  opts: RunOptions,
  build: (renderer: THREE.WebGLRenderer, pointer: THREE.Vector2) => Built,
): SceneHandle {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;
  const pmrem = new THREE.PMREMGenerator(renderer);
  const env = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;

  const pointer = new THREE.Vector2();
  const built = build(renderer, pointer);
  built.scene.environment = env;

  const resize = () => {
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    if (!w || !h) return;
    renderer.setSize(w, h, false);
    built.camera.aspect = w / h;
    built.camera.updateProjectionMatrix();
  };
  const ro = new ResizeObserver(resize);
  ro.observe(canvas);
  resize();

  const onPointer = (e: PointerEvent) => {
    pointer.set((e.clientX / window.innerWidth) * 2 - 1, (e.clientY / window.innerHeight) * 2 - 1);
  };
  if (!opts.reducedMotion) window.addEventListener("pointermove", onPointer, { passive: true });

  // Only draw while on screen: two WebGL scenes on one page shouldn't both burn GPU.
  let visible = true;
  const io = new IntersectionObserver(([entry]) => {
    visible = entry.isIntersecting;
  });
  io.observe(canvas);

  let frame = 0;
  let last = performance.now();
  const loop = (now: number) => {
    frame = requestAnimationFrame(loop);
    const dt = Math.min(0.05, (now - last) / 1000);
    last = now;
    if (!visible || document.hidden) return;
    built.update(opts.reducedMotion ? 0 : now / 1000, opts.reducedMotion ? 0 : dt);
    renderer.render(built.scene, built.camera);
  };
  // Draw one frame immediately so reduced-motion users still see the scene.
  built.update(0, 0);
  renderer.render(built.scene, built.camera);
  frame = requestAnimationFrame(loop);

  return {
    dispose() {
      cancelAnimationFrame(frame);
      ro.disconnect();
      io.disconnect();
      window.removeEventListener("pointermove", onPointer);
      built.scene.traverse((o) => {
        if (o instanceof THREE.Mesh || o instanceof THREE.Points || o instanceof THREE.InstancedMesh) {
          o.geometry.dispose();
          (Array.isArray(o.material) ? o.material : [o.material]).forEach((m) => m.dispose());
        }
      });
      env.dispose();
      pmrem.dispose();
      renderer.dispose();
    },
  };
}

const brushed = (color: string, roughness = 0.3) =>
  new THREE.MeshStandardMaterial({ color, metalness: 1, roughness, envMapIntensity: 1.1 });

const v3 = (p: Vec3) => new THREE.Vector3(p[0], p[1], p[2]);

// Corridors KogniSync plans door to door.
const ROUTES: [number, number, number, number][] = [
  [12.97, 77.59, 28.63, 77.22], // Bengaluru - Delhi
  [19.08, 72.88, 22.57, 88.36], // Mumbai - Kolkata
  [13.08, 80.27, 28.63, 77.22], // Chennai - Delhi
  [17.39, 78.49, 19.08, 72.88], // Hyderabad - Mumbai
  [18.52, 73.86, 12.97, 77.59], // Pune - Bengaluru
  [26.91, 75.79, 20.3, 85.82], // Jaipur - Bhubaneswar
  [9.93, 76.27, 13.08, 80.27], // Kochi - Chennai
];

/** Hero: dark metal globe, a toothed brushed-steel ring, glowing route arcs over India. */
export function createHero(canvas: HTMLCanvasElement, opts: RunOptions): SceneHandle {
  return run(canvas, opts, (_renderer, pointer) => {
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(32, 1, 0.1, 50);
    camera.position.set(0, 0, 6.2);

    const rig = new THREE.Group(); // pointer parallax
    const world = new THREE.Group(); // globe + routes, India facing the camera
    rig.add(world);
    scene.add(rig);

    world.add(new THREE.Mesh(new THREE.SphereGeometry(1, 96, 96), brushed("#16181c", 0.42)));
    const landGeo = new THREE.BufferGeometry();
    landGeo.setAttribute("position", new THREE.BufferAttribute(landPositions(1.1, 1.004), 3));
    world.add(
      new THREE.Points(
        landGeo,
        new THREE.PointsMaterial({ color: 0xff9a70, size: 0.017, transparent: true, opacity: 0.8 }),
      ),
    );

    const comets: { mesh: THREE.Mesh; pts: Vec3[]; lens: number[]; offset: number; speed: number }[] = [];
    ROUTES.forEach(([la1, lo1, la2, lo2], i) => {
      const pts = arcPoints(latLonToXyz(la1, lo1), latLonToXyz(la2, lo2), "flight", 64);
      const curve = new THREE.CatmullRomCurve3(pts.map(v3));
      world.add(
        new THREE.Mesh(
          new THREE.TubeGeometry(curve, 96, 0.011, 8, false),
          new THREE.MeshBasicMaterial({ color: ORANGE, transparent: true, opacity: 0.95 }),
        ),
      );
      const comet = new THREE.Mesh(new THREE.SphereGeometry(0.03, 16, 16), new THREE.MeshBasicMaterial({ color: 0xffe2d6 }));
      world.add(comet);
      comets.push({ mesh: comet, pts, lens: cumulativeLengths(pts), offset: i / ROUTES.length, speed: 0.12 + (i % 3) * 0.03 });
    });
    const hubGeo = new THREE.SphereGeometry(0.024, 12, 12);
    const hubMat = new THREE.MeshBasicMaterial({ color: 0xffffff });
    ROUTES.flatMap(([a, b, c, d]) => [latLonToXyz(a, b, 1.006), latLonToXyz(c, d, 1.006)]).forEach((p) => {
      const m = new THREE.Mesh(hubGeo, hubMat);
      m.position.copy(v3(p));
      world.add(m);
    });

    // Turn the globe so India (about 21N, 79E) faces the camera, tipped slightly back.
    const india = v3(latLonToXyz(21, 79)).normalize();
    world.quaternion.setFromUnitVectors(india, new THREE.Vector3(0, 0, 1));
    const baseQuat = world.quaternion.clone();

    // Toothed ring: a torus plus instanced teeth (one draw call for all of them).
    const gear = new THREE.Group();
    gear.add(new THREE.Mesh(new THREE.TorusGeometry(1.42, 0.05, 24, 160), brushed("#a3abb5", 0.25)));
    const TEETH = 84;
    const teeth = new THREE.InstancedMesh(new THREE.BoxGeometry(0.06, 0.1, 0.07), brushed("#8c949e", 0.3), TEETH);
    const m4 = new THREE.Matrix4();
    const q = new THREE.Quaternion();
    for (let i = 0; i < TEETH; i++) {
      const a = (i / TEETH) * Math.PI * 2;
      q.setFromAxisAngle(new THREE.Vector3(0, 0, 1), a - Math.PI / 2);
      m4.compose(new THREE.Vector3(Math.cos(a) * 1.5, Math.sin(a) * 1.5, 0), q, new THREE.Vector3(1, 1, 1));
      teeth.setMatrixAt(i, m4);
    }
    gear.add(teeth);
    gear.rotation.set(1.15, 0.35, 0);
    rig.add(gear);

    const halo = new THREE.Mesh(
      new THREE.TorusGeometry(1.66, 0.008, 12, 200),
      new THREE.MeshBasicMaterial({ color: ORANGE, transparent: true, opacity: 0.85 }),
    );
    halo.rotation.set(1.35, -0.5, 0.2);
    rig.add(halo);

    scene.add(new THREE.AmbientLight(0xffffff, 0.15));
    const key = new THREE.PointLight(0xff4d1f, 40, 12, 1.6);
    key.position.set(2.4, -0.6, 2.2);
    const rim = new THREE.PointLight(0xff6a33, 30, 12, 1.6);
    rim.position.set(-2.2, 1.6, -1.6);
    const fill = new THREE.DirectionalLight(0xffffff, 0.9);
    fill.position.set(-2, 3, 4);
    scene.add(key, rim, fill);

    const sway = new THREE.Quaternion();
    return {
      scene,
      camera,
      update(t) {
        sway.setFromEuler(new THREE.Euler(0.05 * Math.sin(t * 0.2), 0.3 * Math.sin(t * 0.12), 0));
        world.quaternion.copy(baseQuat).premultiply(sway);
        gear.rotation.z = t * 0.06;
        halo.rotation.z = -t * 0.04;
        rig.rotation.y += (pointer.x * 0.25 - rig.rotation.y) * 0.05;
        rig.rotation.x += (pointer.y * 0.15 - rig.rotation.x) * 0.05;
        comets.forEach((c) => {
          const p = pointAt(c.pts, c.lens, (c.offset + t * c.speed) % 1);
          c.mesh.position.set(p[0], p[1], p[2]);
        });
      },
    };
  });
}

/** CTA: a dark brushed-metal map pin with an orange core and ground ripples. */
export function createPin(canvas: HTMLCanvasElement, opts: RunOptions): SceneHandle {
  return run(canvas, opts, (_renderer, pointer) => {
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(30, 1, 0.1, 50);
    camera.position.set(0, 0.6, 6);
    camera.lookAt(0, 0, 0);

    const profile = [
      [0, -1.15], [0.07, -0.95], [0.2, -0.62], [0.36, -0.3], [0.52, 0.02], [0.61, 0.3],
      [0.63, 0.45], [0.59, 0.66], [0.48, 0.84], [0.3, 0.97], [0, 1.02],
    ].map(([x, y]) => new THREE.Vector2(x, y));
    const pin = new THREE.Group();
    pin.add(new THREE.Mesh(new THREE.LatheGeometry(profile, 96), brushed("#1d2025", 0.28)));
    const core = new THREE.Mesh(
      new THREE.TorusGeometry(0.24, 0.075, 24, 64),
      new THREE.MeshStandardMaterial({ color: "#ff5a2c", emissive: "#ff3d12", emissiveIntensity: 1.2, metalness: 0.4, roughness: 0.3 }),
    );
    core.position.set(0, 0.45, 0.6);
    pin.add(core);
    const back = core.clone();
    back.position.z = -0.6;
    pin.add(back);
    scene.add(pin);

    const ripples = [0, 1, 2].map(() => {
      const r = new THREE.Mesh(
        new THREE.RingGeometry(0.3, 0.34, 64),
        new THREE.MeshBasicMaterial({ color: 0x1a0d08, transparent: true, side: THREE.DoubleSide }),
      );
      r.rotation.x = -Math.PI / 2;
      r.position.y = -1.18;
      scene.add(r);
      return r;
    });

    scene.add(new THREE.AmbientLight(0xffffff, 0.2));
    const key = new THREE.PointLight(0xff4d1f, 45, 12, 1.5);
    key.position.set(2, 1, 2.5);
    const rim = new THREE.PointLight(0xffa07a, 25, 12, 1.5);
    rim.position.set(-2.5, 2, -1);
    const top = new THREE.DirectionalLight(0xffffff, 1.4);
    top.position.set(-1, 4, 3);
    scene.add(key, rim, top);

    return {
      scene,
      camera,
      update(t) {
        pin.rotation.y = 0.6 * Math.sin(t * 0.5) + pointer.x * 0.3;
        pin.position.y = 0.08 * Math.sin(t * 1.2);
        ripples.forEach((r, i) => {
          const p = (t * 0.35 + i / 3) % 1;
          r.scale.setScalar(1 + p * 3.2);
          (r.material as THREE.MeshBasicMaterial).opacity = 0.55 * (1 - p);
        });
      },
    };
  });
}
