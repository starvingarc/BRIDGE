import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

export const regions = [
  { id: 'nt', name: '神经管', en: 'Neural tube', color: '#d69865' },
  { id: 'optic', name: '眼', en: 'Eye', color: '#679bc0' },
  { id: 'otic', name: '耳泡', en: 'Otic vesicle', color: '#b59a51' },
  { id: 'drg', name: '背根神经节', en: 'Dorsal root ganglia', color: '#77a99c' },
  { id: 'heart', name: '心脏', en: 'Heart', color: '#bc7a81' },
  { id: 'liver', name: '肝脏', en: 'Liver', color: '#8c99a5' },
] as const;
export type Region = typeof regions[number]['id'];
export type ViewSettings = { shell: number; tissue: number; solo: boolean; selected: Region; rotate: boolean };

type Part = { mesh: THREE.Mesh; id: Region | 'mask'; material: THREE.MeshStandardMaterial };
function identify(name: string): Region | 'mask' | undefined {
  const n = name.toLowerCase();
  if (n.includes('mask')) return 'mask';
  return regions.find(r => new RegExp(`(^|_)${r.id}($|_|-)`).test(n))?.id;
}
function disposeObject(object: THREE.Object3D) {
  object.traverse(node => {
    if (!(node instanceof THREE.Mesh)) return;
    node.geometry.dispose();
    const materials = Array.isArray(node.material) ? node.material : [node.material];
    materials.forEach((material: THREE.Material) => material.dispose());
  });
}

export function createAnatomyViewer(host: HTMLElement, onSelect: (id: Region) => void) {
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.setClearColor(0, 0);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.25;
  renderer.domElement.setAttribute('aria-label', '可旋转的胚胎解剖模型；也可使用旁边的结构和视角按钮');
  host.appendChild(renderer.domElement);
  const scene = new THREE.Scene();
  scene.add(new THREE.HemisphereLight(0xffffff, 0x929b97, 2.4));
  const light = new THREE.DirectionalLight(0xfff7e9, 3.2);
  light.position.set(4, 5, 6); scene.add(light);
  const rim = new THREE.DirectionalLight(0xdcefff, 2.2);
  rim.position.set(-4, 2, -3); scene.add(rim);
  const camera = new THREE.PerspectiveCamera(32, 1, 0.01, 100);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.enablePan = false;
  controls.autoRotateSpeed = 0.65;
  controls.minDistance = 2;
  controls.maxDistance = 13;
  let parts: Part[] = [];
  let object: THREE.Group | undefined;
  // Visual hypothesis only: source optic local Z spans the bilateral pair.
  // This construction is not a specimen-to-atlas registration.
  const candidate = new THREE.Mesh(new THREE.PlaneGeometry(3.8, 3.8),
    new THREE.MeshBasicMaterial({ color: '#548ba5', transparent: true, opacity: 0.16, side: THREE.DoubleSide, depthWrite: false }));
  const outline = new THREE.LineSegments(new THREE.EdgesGeometry(candidate.geometry), new THREE.LineBasicMaterial({ color: '#548ba5', transparent: true, opacity: 0.75 }));
  candidate.add(outline); candidate.visible = false; scene.add(candidate);
  let candidateOrigin: THREE.Vector3 | undefined;
  let candidateNormal = new THREE.Vector3(1, 0, 0);
  let candidateEnabled = false;
  let candidateOffset = 0;
  function positionCandidate(enabled: boolean, offset: number) {
    candidateEnabled = enabled; candidateOffset = offset;
    candidate.visible = enabled && !!candidateOrigin;
    if (candidateOrigin) candidate.position.copy(candidateOrigin).addScaledVector(candidateNormal, offset);
  }
  let active = true;
  let request = 0;
  let settings: ViewSettings = { shell: 0.13, tissue: 0.60, solo: false, selected: 'nt', rotate: false };
  function reset(view: 'oblique' | 'front' | 'side' = 'oblique') {
    controls.target.set(0, 0, 0);
    const distance = Math.max(6.3, 4.3 / Math.max(camera.aspect, 0.5));
    const direction = view === 'front' ? new THREE.Vector3(0, 0, 1) : view === 'side' ? new THREE.Vector3(1, 0, 0) : new THREE.Vector3(1, 0.12, 0.8);
    camera.position.copy(direction.normalize().multiplyScalar(distance));
    controls.update();
  }
  function resize() {
    const { width, height } = host.getBoundingClientRect();
    camera.aspect = Math.max(width, 1) / Math.max(height, 1);
    camera.updateProjectionMatrix();
    renderer.setSize(width, height);
  }
  const observer = new ResizeObserver(resize); observer.observe(host);
  resize(); reset();
  function update(next: ViewSettings) {
    settings = next;
    controls.autoRotate = next.rotate;
    for (const { mesh, id, material } of parts) {
      const shell = id === 'mask';
      const selected = id === next.selected;
      mesh.visible = shell ? next.shell > 0 && !next.solo : !next.solo || selected;
      material.opacity = shell ? next.shell : selected ? next.tissue : Math.min(next.tissue, 0.22);
      material.emissive.set(selected ? '#5c3619' : '#000000');
      material.emissiveIntensity = selected ? 0.11 : 0;
    }
  }
  async function load(modelUrl: string, stage?: string) {
    const ticket = ++request;
    if (object) { scene.remove(object); disposeObject(object); object = undefined; }
    parts = []; candidateOrigin = undefined; candidate.visible = false;
    const gltf = await new GLTFLoader().loadAsync(modelUrl);
    if (!active || ticket !== request) { disposeObject(gltf.scene); return false; }
    object = gltf.scene;
    const box = new THREE.Box3().setFromObject(object);
    const size = box.getSize(new THREE.Vector3());
    const center = box.getCenter(new THREE.Vector3());
    const scale = 3.4 / Math.max(size.x, size.y, size.z);
    object.scale.setScalar(scale);
    object.position.copy(center.multiplyScalar(-scale));
    object.traverse(node => {
      if (!(node instanceof THREE.Mesh)) return;
      const id = identify(node.name);
      if (!id) { node.visible = false; return; }
      const originals = Array.isArray(node.material) ? node.material : [node.material];
      originals.forEach((m: THREE.Material) => m.dispose());
      const material = new THREE.MeshStandardMaterial({
        color: id === 'mask' ? '#aec1bc' : regions.find(r => r.id === id)!.color,
        roughness: 0.42, metalness: 0.04, transparent: true,
        depthWrite: false, side: THREE.FrontSide,
      });
      node.material = material;
      node.renderOrder = id === 'mask' ? 2 : 1;
      parts.push({ mesh: node, id, material });
    });
    if (parts.length !== 7) {
      disposeObject(object); object = undefined; parts = [];
      throw new Error('模型结构与预期不一致');
    }
    scene.add(object); object.updateMatrixWorld(true);
    if (stage === 'CS15') {
      const optic = parts.find(p => p.id === 'optic')!.mesh;
      optic.geometry.computeBoundingBox();
      candidateOrigin = optic.localToWorld(optic.geometry.boundingBox!.getCenter(new THREE.Vector3()));
      candidateNormal = new THREE.Vector3(0, 0, 1).transformDirection(optic.matrixWorld);
      // Centre the square over the model while preserving its plane equation.
      candidateOrigin.copy(candidateNormal.clone().multiplyScalar(candidateOrigin.dot(candidateNormal)));
      candidate.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), candidateNormal);
    }
    positionCandidate(candidateEnabled, candidateOffset);
    update(settings); reset();
    return true;
  }
  const raycaster = new THREE.Raycaster();
  const pointer = new THREE.Vector2();
  let down = { x: 0, y: 0 };
  function pointerDown(e: PointerEvent) { down = { x: e.clientX, y: e.clientY }; }
  function pointerUp(e: PointerEvent) {
    if (Math.hypot(e.clientX - down.x, e.clientY - down.y) > 5) return;
    const bounds = renderer.domElement.getBoundingClientRect();
    pointer.set((e.clientX - bounds.left) / bounds.width * 2 - 1, -(e.clientY - bounds.top) / bounds.height * 2 + 1);
    raycaster.setFromCamera(pointer, camera);
    const hits = raycaster.intersectObjects(parts.filter(p => p.id !== 'mask' && p.mesh.visible && p.material.opacity > 0).map(p => p.mesh));
    const hit = parts.find(p => p.mesh === hits[0]?.object);
    if (hit && hit.id !== 'mask') onSelect(hit.id);
  }
  renderer.domElement.addEventListener('pointerdown', pointerDown);
  renderer.domElement.addEventListener('pointerup', pointerUp);
  renderer.setAnimationLoop(() => { controls.update(); renderer.render(scene, camera); });
  return {
    load, update, reset, positionCandidate,
    snapshot: (size = 1200) => {
      if (!active || !object) throw new Error('Anatomy is not ready');
      const previousSize = renderer.getSize(new THREE.Vector2()), previousRatio = renderer.getPixelRatio();
      const previousColor = renderer.getClearColor(new THREE.Color()), previousAlpha = renderer.getClearAlpha();
      const exportCamera = camera.clone(); exportCamera.aspect = 1; exportCamera.updateProjectionMatrix();
      try {
        renderer.setPixelRatio(1); renderer.setSize(size, size, false); renderer.setClearColor(0xffffff, 1);
        renderer.render(scene, exportCamera);
        return renderer.domElement.toDataURL('image/png');
      } finally {
        renderer.setPixelRatio(previousRatio); renderer.setSize(previousSize.x, previousSize.y, false);
        renderer.setClearColor(previousColor, previousAlpha); renderer.render(scene, camera);
      }
    },
    faceCandidate: () => {
      if (!candidateOrigin) return;
      controls.target.set(0, 0, 0);
      camera.position.copy(candidateNormal).multiplyScalar(Math.max(6.3, 4.3 / Math.max(camera.aspect, 0.5)));
      controls.update();
    },
    zoom: (factor: number) => { camera.position.multiplyScalar(factor).clampLength(controls.minDistance, controls.maxDistance); controls.update(); },
    dispose: () => {
      active = false; request++; observer.disconnect(); renderer.setAnimationLoop(null);
      renderer.domElement.removeEventListener('pointerdown', pointerDown);
      renderer.domElement.removeEventListener('pointerup', pointerUp);
      controls.dispose(); if (object) disposeObject(object);
      candidate.geometry.dispose(); candidate.material.dispose(); outline.geometry.dispose(); outline.material.dispose();
      renderer.dispose(); renderer.domElement.remove();
    },
  };
}
