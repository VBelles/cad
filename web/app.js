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

  explodeSelectedButton.textContent = cadViewer?.selectedPartExploded
    ? 'Assemble part'
    : 'Explode part';
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

  if (product) {
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
  productsEl.replaceChildren(...products.map((product) => {
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
    if (product) {
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

async function init() {
  try {
    const [metadataResponse, bomResponse] = await Promise.all([
      fetch('./data/metadata.json'),
      fetch('./data/bom.json'),
    ]);

    if (!metadataResponse.ok || !bomResponse.ok) {
      throw new Error('Generated model metadata is unavailable');
    }

    const [metadata, bom] = await Promise.all([
      metadataResponse.json(),
      bomResponse.json(),
    ]);
    const productsById = new Map((metadata.products ?? []).map((product) => [product.id, product]));

    const p = metadata.parameters;
    const d = metadata.derived;

    statusEl.textContent = metadata.status;
    summaryEl.replaceChildren(
      summaryItem('Envelope', `${mm.format(p.length)} × ${mm.format(p.depth)} × ${mm.format(p.body_height)} mm`),
      summaryItem('Main frame', `${mm.format(p.frame_size)} × ${mm.format(p.frame_size)} × ${mm.format(p.frame_wall)} mm steel`),
      summaryItem('Leg clearance', `${mm.format(d.leg_clearance_mm)} mm`),
      summaryItem('Internal opening', `${mm.format(d.inner_opening_mm)} × ${mm.format(d.inner_opening_mm)} mm`),
      summaryItem('Bag useful space', `${mm.format(d.bag_useful_width_mm)} × ${mm.format(d.bag_useful_width_mm)} × ${mm.format(d.bag_useful_height_mm)} mm`),
      summaryItem('Bag volume', `≈ ${mm.format(d.bag_volume_litres)} L`),
      summaryItem('Bag clamp', `${mm.format(d.bag_clamp_outer_mm)} mm outer · ${mm.format(d.bag_clamp_clearance_each_side_mm)} mm clearance / side`),
      summaryItem('Tray clearance', `${mm.format(d.tray_side_clearance_each_side_mm)} mm / side · ${mm.format(d.tray_to_bottom_frame_vertical_clearance_mm)} mm above`),
      summaryItem('Panel mounting', `${d.panel_frame_fixings_each} concealed frame fixings / face`),
      summaryItem('Parts', `${metadata.parts.length}`),
    );

    renderProducts(metadata.products ?? []);
    renderBom(bom, productsById);

    const notes = [
      ...(metadata.fabrication_notes ?? []),
      ...(metadata.notes ?? []),
    ];
    notesEl.replaceChildren(...notes.map((note) => {
      const li = document.createElement('li');
      li.textContent = note;
      return li;
    }));

    cadViewer = await createCadViewer(viewerEl, metadata, {
      onSelectPart: renderSelectedPart,
    });

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

    resetButton.addEventListener('click', () => {
      cadViewer.reset();
      updateModeButtons();
    });
    explodeAllButton.addEventListener('click', () => {
      cadViewer.explodeAll();
      updateModeButtons();
    });
    explodeSelectedButton.addEventListener('click', () => {
      if (!selectedPart) return;
      cadViewer.toggleSelectedPart();
      updateModeButtons();
    });

    updateModeButtons();
  } catch (error) {
    statusEl.textContent = 'Build / viewer error';
    viewerEl.textContent = error instanceof Error ? error.message : String(error);
    const li = document.createElement('li');
    li.textContent = error instanceof Error ? error.message : String(error);
    notesEl.replaceChildren(li);
    console.error(error);
  }
}

init();
