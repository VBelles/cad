import { createCadViewer } from './viewer.js';

const statusEl = document.querySelector('#status');
const summaryEl = document.querySelector('#summary');
const bomEl = document.querySelector('#bom');
const notesEl = document.querySelector('#notes');
const productsEl = document.querySelector('#products');
const viewerEl = document.querySelector('#viewer');
const groupControlsEl = document.querySelector('#explode-groups');
const resetButton = document.querySelector('#reset-explosion');
const explodeAllButton = document.querySelector('#explode-all');
const modelSelectEl = document.querySelector('#model-select');
const modelTitleEl = document.querySelector('#model-title');
const stepLinkEl = document.querySelector('#step-link');
const glbLinkEl = document.querySelector('#glb-link');

const selectedEmptyEl = document.querySelector('#selected-empty');
const selectedPartEl = document.querySelector('#selected-part');
const selectedNameEl = document.querySelector('#selected-name');
const selectedIdEl = document.querySelector('#selected-id');
const selectedDetailsEl = document.querySelector('#selected-details');
const selectedProductEl = document.querySelector('#selected-product');
const explodeSelectedButton = document.querySelector('#explode-selected');

const mm = new Intl.NumberFormat('en', { maximumFractionDigits: 1 });
let cadViewer = null;
let selectedPart = null;
const groupButtons = new Map();

function summaryItem(label, value) {
  const wrapper = document.createElement('div');
  const dt = document.createElement('dt');
  const dd = document.createElement('dd');
  dt.textContent = label;
  dd.textContent = value;
  wrapper.append(dt, dd);
  return wrapper;
}

function detailItem(label, value) {
  const wrapper = document.createElement('div');
  const dt = document.createElement('dt');
  const dd = document.createElement('dd');
  dt.textContent = label;
  dd.textContent = value;
  wrapper.append(dt, dd);
  return wrapper;
}

function updateModeButtons() {
  const anyGroupActive = [...groupButtons.keys()].some((id) => cadViewer?.isGroupActive(id));
  resetButton.classList.toggle('active', !anyGroupActive && !cadViewer?.selectedPartExploded);
  explodeAllButton.classList.toggle(
    'active',
    groupButtons.size > 0 && [...groupButtons.keys()].every((id) => cadViewer?.isGroupActive(id)),
  );
  for (const [id, button] of groupButtons) {
    const active = Boolean(cadViewer?.isGroupActive(id));
    button.classList.toggle('active', active);
    button.setAttribute('aria-pressed', String(active));
  }
  explodeSelectedButton.textContent = cadViewer?.selectedPartExploded ? 'Assemble part' : 'Explode part';
}

function renderSelectedPart(part, product) {
  selectedPart = part;
  if (!part) {
    selectedEmptyEl.hidden = false;
    selectedPartEl.hidden = true;
    return;
  }
  selectedEmptyEl.hidden = true;
  selectedPartEl.hidden = false;
  selectedNameEl.textContent = part.name;
  selectedIdEl.textContent = part.id;
  selectedDetailsEl.replaceChildren(
    detailItem('Category', part.category),
    detailItem('Material', part.material),
    detailItem('Profile', part.profile),
    detailItem('Cut / size', part.cut),
  );
  if (product?.url) {
    selectedProductEl.hidden = false;
    selectedProductEl.href = product.url;
    selectedProductEl.textContent = `Open ${product.retailer} · ref. ${product.ref} ↗`;
  } else {
    selectedProductEl.hidden = true;
    selectedProductEl.removeAttribute('href');
  }
  updateModeButtons();
}

function renderProducts(products) {
  productsEl.replaceChildren(...products.filter((product) => product.url).map((product) => {
    const card = document.createElement('a');
    card.className = 'product-card';
    card.href = product.url;
    card.target = '_blank';
    card.rel = 'noopener';
    const title = document.createElement('strong');
    title.textContent = product.name;
    const meta = document.createElement('span');
    meta.textContent = `${product.retailer} · ref. ${product.ref} · buy ${product.suggested_qty}`;
    card.append(title, meta);
    if (product.note) {
      const note = document.createElement('small');
      note.textContent = product.note;
      card.append(note);
    }
    return card;
  }));
}

function renderBom(bom, productsById) {
  bomEl.replaceChildren(...bom.map((item) => {
    const row = document.createElement('tr');
    const profile = document.createElement('td');
    const cut = document.createElement('td');
    const quantity = document.createElement('td');
    const profileLine = document.createElement('div');
    profileLine.className = 'profile-line';
    const profileText = document.createElement('span');
    profileText.textContent = item.profile;
    profileLine.append(profileText);
    const product = item.product_id ? productsById.get(item.product_id) : null;
    if (product?.url) {
      const link = document.createElement('a');
      link.className = 'inline-product-link';
      link.href = product.url;
      link.target = '_blank';
      link.rel = 'noopener';
      link.textContent = '↗';
      link.title = `${product.retailer} · ${product.name}`;
      profileLine.append(link);
    }
    const material = document.createElement('span');
    material.className = 'material';
    material.textContent = item.material;
    profile.append(profileLine, material);
    cut.textContent = item.cut;
    quantity.textContent = item.quantity;
    row.append(profile, cut, quantity);
    return row;
  }));
}

function renderSummary(metadata) {
  const p = metadata.parameters;
  const d = metadata.derived;

  if (metadata.design_scope === 'structure-only') {
    summaryEl.replaceChildren(
      summaryItem('Envelope', `${mm.format(p.length)} × ${mm.format(p.depth)} × ${mm.format(p.body_height)} mm`),
      summaryItem('Study scope', 'Outer structure only'),
      summaryItem('Posts', `${d.post_count} · ${mm.format(p.frame_size)} × ${mm.format(p.frame_size)} × ${mm.format(p.frame_wall)} mm tube`),
      summaryItem('Horizontal rails', `${d.angle_rail_count} · L ${mm.format(p.angle_leg)} × ${mm.format(p.angle_leg)} × ${mm.format(p.angle_thickness)} mm`),
      summaryItem('Clear rail span', `${mm.format(d.clear_span_mm)} mm`),
      summaryItem('Corner connectors', `${d.corner_connector_count} · three-plane fittings`),
      summaryItem('Structural rivets', `${d.structural_rivet_count} · Ø${mm.format(p.rivet_diameter)} mm`),
      summaryItem('Welded joints', `${d.weld_count}`),
      summaryItem('Post caps', `${d.caps_count}`),
      summaryItem('Parts', `${metadata.parts.length}`),
    );
    return;
  }

  const bagVolume = d.bag_module_count > 1
    ? `${mm.format(d.bag_volume_litres_each)} L × ${d.bag_module_count} = ≈ ${mm.format(d.bag_volume_litres_total)} L`
    : `≈ ${mm.format(d.bag_volume_litres_total)} L`;
  summaryEl.replaceChildren(
    summaryItem('Envelope', `${mm.format(p.length)} × ${mm.format(p.depth)} × ${mm.format(p.body_height)} mm`),
    summaryItem('Structural bays', `${d.bay_count} · opening ${mm.format(d.bay_opening_length_mm)} mm each`),
    summaryItem('Main frame', `${mm.format(p.frame_size)} × ${mm.format(p.frame_size)} × ${mm.format(p.frame_wall)} mm steel`),
    summaryItem('Internal depth', `${mm.format(d.inner_depth_mm)} mm`),
    summaryItem('Grow modules', `${d.bag_module_count}`),
    summaryItem('Bag useful space / module', `${mm.format(d.bag_useful_x_mm)} × ${mm.format(d.bag_useful_y_mm)} × ${mm.format(d.bag_useful_height_mm)} mm`),
    summaryItem('Total substrate volume', bagVolume),
    summaryItem('Bag platform Z', `${mm.format(d.bag_support_z_mm)} mm`),
    summaryItem('Bottom supports', `${d.bag_support_rail_count_each} rails / module · ${mm.format(d.bag_support_clear_gap_mm)} mm clear gap`),
    summaryItem('Tray target / module', `${mm.format(d.tray_target_width_mm)} × ${mm.format(d.tray_target_depth_mm)} mm plastic`),
    summaryItem('Timber panel', `${mm.format(p.slat_thickness)} mm slats · ${d.panel_battens_each} battens`),
    summaryItem('Parts', `${metadata.parts.length}`),
  );
}

async function loadModel(entry) {
  statusEl.textContent = 'Loading…';
  viewerEl.innerHTML = '<div class="progress">Loading 3D model…</div>';
  cadViewer?.dispose();
  cadViewer = null;
  selectedPart = null;
  selectedEmptyEl.hidden = false;
  selectedPartEl.hidden = true;
  groupButtons.clear();
  groupControlsEl.replaceChildren();

  const [metadataResponse, bomResponse] = await Promise.all([
    fetch(entry.metadata),
    fetch(entry.bom),
  ]);
  if (!metadataResponse.ok || !bomResponse.ok) throw new Error('Generated model metadata is unavailable');
  const [metadata, bom] = await Promise.all([metadataResponse.json(), bomResponse.json()]);
  const productsById = new Map((metadata.products ?? []).map((product) => [product.id, product]));

  modelTitleEl.textContent = `Planter · ${entry.label}`;
  document.title = `CAD · ${entry.label}`;
  stepLinkEl.href = entry.step;
  glbLinkEl.href = entry.glb;
  statusEl.textContent = metadata.status;
  renderSummary(metadata);
  renderProducts(metadata.products ?? []);
  renderBom(bom, productsById);

  const notes = [...(metadata.fabrication_notes ?? []), ...(metadata.notes ?? [])];
  notesEl.replaceChildren(...notes.map((note) => {
    const li = document.createElement('li');
    li.textContent = note;
    return li;
  }));

  cadViewer = await createCadViewer(viewerEl, metadata, { onSelectPart: renderSelectedPart });
  groupControlsEl.replaceChildren(...cadViewer.groups.map((group) => {
    const button = document.createElement('button');
    button.className = 'group-button';
    button.type = 'button';
    button.textContent = group.label;
    button.setAttribute('aria-pressed', 'false');
    button.addEventListener('click', () => {
      cadViewer.toggleGroup(group.id);
      updateModeButtons();
    });
    groupButtons.set(group.id, button);
    return button;
  }));
  updateModeButtons();
}

async function init() {
  try {
    const response = await fetch('./data/models.json');
    if (!response.ok) throw new Error('Model catalogue is unavailable');
    const models = await response.json();
    if (!models.length) throw new Error('No generated models');

    modelSelectEl.replaceChildren(...models.map((model) => {
      const option = document.createElement('option');
      option.value = model.id;
      option.textContent = model.label;
      return option;
    }));

    const requested = new URLSearchParams(window.location.search).get('model');
    let current = models.find((model) => model.id === requested) ?? models[0];
    modelSelectEl.value = current.id;
    await loadModel(current);

    modelSelectEl.addEventListener('change', async () => {
      current = models.find((model) => model.id === modelSelectEl.value) ?? models[0];
      const url = new URL(window.location.href);
      url.searchParams.set('model', current.id);
      window.history.replaceState({}, '', url);
      try {
        await loadModel(current);
      } catch (error) {
        statusEl.textContent = 'Build / viewer error';
        viewerEl.textContent = error instanceof Error ? error.message : String(error);
        console.error(error);
      }
    });
  } catch (error) {
    statusEl.textContent = 'Build / viewer error';
    viewerEl.textContent = error instanceof Error ? error.message : String(error);
    const li = document.createElement('li');
    li.textContent = error instanceof Error ? error.message : String(error);
    notesEl.replaceChildren(li);
    console.error(error);
  }
}

resetButton.addEventListener('click', () => {
  cadViewer?.reset();
  updateModeButtons();
});
explodeAllButton.addEventListener('click', () => {
  cadViewer?.explodeAll();
  updateModeButtons();
});
explodeSelectedButton.addEventListener('click', () => {
  if (!selectedPart || !cadViewer) return;
  cadViewer.toggleSelectedPart();
  updateModeButtons();
});

init();
