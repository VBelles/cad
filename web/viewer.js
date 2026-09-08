import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

const MM_TO_MODEL = 0.001;

function vectorFromMm(values) {
  return new THREE.Vector3(...values.map((value) => value * MM_TO_MODEL));
}

export async function createCadViewer(container, metadata, options = {}) {
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0xe9ebed);

  // glTF is Y-up. OpenCascade's exporter keeps the original CAD coordinates on
  // child nodes and puts a -90deg X rotation on the root to convert build123d's
  // Z-up geometry to glTF Y-up. Keep the camera/controls in standard Three.js
  // Y-up coordinates; treating the loaded scene as Z-up rotates the planter 90°.
  const camera = new THREE.PerspectiveCamera(38, 1, 0.001, 100);
  camera.up.set(0, 1, 0);

  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;
  container.replaceChildren(renderer.domElement);

  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.screenSpacePanning = true;
  controls.enableRotate = true;
  controls.enableZoom = true;
  controls.enablePan = true;

  // Explicitly leave azimuth unrestricted: the user can rotate continuously
  // around the complete 360° horizontal orbit. Polar limits only avoid the two
  // mathematical singularities exactly above/below the target.
  controls.minAzimuthAngle = -Infinity;
  controls.maxAzimuthAngle = Infinity;
  controls.minPolarAngle = 0.001;
  controls.maxPolarAngle = Math.PI - 0.001;

  scene.add(new THREE.HemisphereLight(0xffffff, 0x777777, 2.2));

  const key = new THREE.DirectionalLight(0xffffff, 2.6);
  key.position.set(-2, 4, 3);
  scene.add(key);

  const fill = new THREE.DirectionalLight(0xffffff, 1.4);
  fill.position.set(3, 2, -1);
  scene.add(fill);

  const loader = new GLTFLoader();
  const gltf = await loader.loadAsync(metadata.viewer?.model_src ?? './models/planter.glb');
  const model = gltf.scene;
  scene.add(model);

  const partsById = new Map((metadata.parts ?? []).map((part) => [part.id, part]));
  const productsById = new Map((metadata.products ?? []).map((product) => [product.id, product]));
  const groupsById = new Map((metadata.viewer?.groups ?? []).map((group) => [group.id, group]));

  const nodeByName = new Map();
  model.traverse((node) => {
    if (node.name) nodeByName.set(node.name, node);
  });

  const movableNodes = new Set();
  for (const group of groupsById.values()) {
    for (const name of group.node_names ?? []) {
      const node = nodeByName.get(name);
      if (node) movableNodes.add(node);
    }
  }
  for (const partId of partsById.keys()) {
    const node = nodeByName.get(partId);
    if (node) movableNodes.add(node);
  }

  const basePositions = new Map();
  for (const node of movableNodes) {
    basePositions.set(node, node.position.clone());
    node.userData.explosionTarget = node.position.clone();
  }

  const activeGroups = new Set();
  let selectedPartId = null;
  let selectedPartExploded = false;
  let selectedOffset = new THREE.Vector3();
  let selectionHelper = null;

  const assembledBounds = new THREE.Box3().setFromObject(model);
  const assembledCenter = assembledBounds.getCenter(new THREE.Vector3());
  const assembledSize = assembledBounds.getSize(new THREE.Vector3());
  const maxDim = Math.max(assembledSize.x, assembledSize.y, assembledSize.z);

  camera.near = Math.max(maxDim / 500, 0.001);
  camera.far = Math.max(maxDim * 100, 10);
  // World Y is vertical after the glTF root conversion. Positive Z looks at the
  // planter from its front side because CAD +Y depth maps to world -Z.
  camera.position.copy(
    assembledCenter.clone().add(new THREE.Vector3(1.25, 1.05, 1.45).multiplyScalar(maxDim * 1.25)),
  );
  controls.target.copy(assembledCenter);
  controls.update();

  // GridHelper is already an XZ ground plane in Three.js/Y-up coordinates.
  const grid = new THREE.GridHelper(maxDim * 3, 20, 0xbfc4c8, 0xd4d7da);
  grid.position.y = assembledBounds.min.y - 0.002;
  scene.add(grid);

  function selectedPartOffset(partNode) {
    const box = new THREE.Box3().setFromObject(partNode);
    const center = box.getCenter(new THREE.Vector3());
    const directionWorld = center.clone().sub(assembledCenter);
    directionWorld.y *= 0.35;
    if (directionWorld.lengthSq() < 1e-6) directionWorld.set(1, 0.25, 0);
    directionWorld.normalize();

    // partNode.position is expressed in its parent's CAD-local coordinates, so
    // transform the world-space outward direction back into that local basis.
    const parentQuaternion = new THREE.Quaternion();
    partNode.parent?.getWorldQuaternion(parentQuaternion);
    const directionLocal = directionWorld.applyQuaternion(parentQuaternion.invert());
    return directionLocal.multiplyScalar(
      (metadata.viewer?.selected_part_offset_mm ?? 260) * MM_TO_MODEL,
    );
  }

  function recomputeTargets() {
    const accumulated = new Map();
    for (const node of movableNodes) accumulated.set(node, new THREE.Vector3());

    for (const groupId of activeGroups) {
      const group = groupsById.get(groupId);
      if (!group) continue;
      // Group offsets are stored in CAD-local XYZ millimetres. Nodes preserve
      // that local basis under the glTF root conversion, so no axis remap here.
      const offset = vectorFromMm(group.offset_mm ?? [0, 0, 0]);
      for (const nodeName of group.node_names ?? []) {
        const node = nodeByName.get(nodeName);
        if (node && accumulated.has(node)) accumulated.get(node).add(offset);
      }
    }

    if (selectedPartExploded && selectedPartId) {
      const selectedNode = nodeByName.get(selectedPartId);
      if (selectedNode && accumulated.has(selectedNode)) {
        accumulated.get(selectedNode).add(selectedOffset);
      }
    }

    for (const node of movableNodes) {
      node.userData.explosionTarget.copy(basePositions.get(node)).add(accumulated.get(node));
    }
  }

  function toggleGroup(groupId) {
    if (!groupsById.has(groupId)) return false;
    if (activeGroups.has(groupId)) activeGroups.delete(groupId);
    else activeGroups.add(groupId);
    recomputeTargets();
    return activeGroups.has(groupId);
  }

  function explodeAll() {
    for (const groupId of groupsById.keys()) activeGroups.add(groupId);
    selectedPartExploded = false;
    recomputeTargets();
  }

  function reset() {
    activeGroups.clear();
    selectedPartExploded = false;
    recomputeTargets();
  }

  function toggleSelectedPart() {
    if (!selectedPartId) return false;
    const node = nodeByName.get(selectedPartId);
    if (!node) return false;
    selectedPartExploded = !selectedPartExploded;
    selectedOffset = selectedPartOffset(node);
    recomputeTargets();
    return selectedPartExploded;
  }

  function resolvePartNode(object) {
    let candidate = object;
    while (candidate && candidate !== model) {
      if (candidate.name && partsById.has(candidate.name)) return candidate;
      candidate = candidate.parent;
    }
    return null;
  }

  function selectPart(partNode) {
    selectedPartId = partNode?.name ?? null;
    selectedPartExploded = false;
    selectedOffset.set(0, 0, 0);
    recomputeTargets();

    if (selectionHelper) {
      scene.remove(selectionHelper);
      selectionHelper.geometry.dispose();
      selectionHelper.material.dispose();
      selectionHelper = null;
    }

    if (partNode) {
      selectionHelper = new THREE.BoxHelper(partNode, 0x2f6fed);
      scene.add(selectionHelper);
    }

    const part = selectedPartId ? partsById.get(selectedPartId) : null;
    const product = part?.product_id ? productsById.get(part.product_id) : null;
    options.onSelectPart?.(part ?? null, product ?? null);
  }

  const raycaster = new THREE.Raycaster();
  const pointer = new THREE.Vector2();
  let pointerDown = null;

  renderer.domElement.addEventListener('pointerdown', (event) => {
    pointerDown = { x: event.clientX, y: event.clientY };
  });

  renderer.domElement.addEventListener('pointerup', (event) => {
    if (!pointerDown) return;
    const distance = Math.hypot(event.clientX - pointerDown.x, event.clientY - pointerDown.y);
    pointerDown = null;
    if (distance > 5) return;

    const rect = renderer.domElement.getBoundingClientRect();
    pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
    raycaster.setFromCamera(pointer, camera);

    const hits = raycaster.intersectObject(model, true);
    const partNode = hits.length ? resolvePartNode(hits[0].object) : null;
    selectPart(partNode);
  });

  function resize() {
    const width = Math.max(container.clientWidth, 1);
    const height = Math.max(container.clientHeight, 1);
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
  }

  const resizeObserver = new ResizeObserver(resize);
  resizeObserver.observe(container);
  resize();

  renderer.setAnimationLoop(() => {
    for (const node of movableNodes) {
      const target = node.userData.explosionTarget;
      if (target) node.position.lerp(target, 0.14);
    }
    if (selectionHelper) selectionHelper.update();
    controls.update();
    renderer.render(scene, camera);
  });

  return {
    groups: [...groupsById.values()],
    toggleGroup,
    explodeAll,
    reset,
    toggleSelectedPart,
    isGroupActive: (groupId) => activeGroups.has(groupId),
    get selectedPartId() {
      return selectedPartId;
    },
    get selectedPartExploded() {
      return selectedPartExploded;
    },
    dispose() {
      resizeObserver.disconnect();
      renderer.setAnimationLoop(null);
      controls.dispose();
      renderer.dispose();
    },
  };
}
