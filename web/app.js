const statusEl = document.querySelector('#status');
const summaryEl = document.querySelector('#summary');
const bomEl = document.querySelector('#bom');
const notesEl = document.querySelector('#notes');
const viewer = document.querySelector('#viewer');
const modelButtons = [...document.querySelectorAll('[data-model-src]')];

const mm = new Intl.NumberFormat('en', { maximumFractionDigits: 1 });

function summaryItem(label, value) {
  const wrapper = document.createElement('div');
  const dt = document.createElement('dt');
  const dd = document.createElement('dd');
  dt.textContent = label;
  dd.textContent = value;
  wrapper.append(dt, dd);
  return wrapper;
}

function setModel(button) {
  const src = button.dataset.modelSrc;
  const alt = button.dataset.modelAlt;
  if (!src) return;

  viewer.src = src;
  if (alt) viewer.alt = alt;

  for (const candidate of modelButtons) {
    const active = candidate === button;
    candidate.classList.toggle('active', active);
    candidate.setAttribute('aria-pressed', String(active));
  }
}

for (const button of modelButtons) {
  button.addEventListener('click', () => setModel(button));
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
      summaryItem('Tray clearance', `${mm.format(d.tray_side_clearance_each_side_mm)} mm / side · ${mm.format(d.tray_to_bottom_frame_vertical_clearance_mm)} mm above`),
      summaryItem('Panel mounting', `${d.panel_frame_fixings_each} concealed frame fixings / face`),
      summaryItem('Parts', `${metadata.parts.length}`),
    );

    bomEl.replaceChildren(...bom.map((item) => {
      const row = document.createElement('tr');
      const profile = document.createElement('td');
      const cut = document.createElement('td');
      const quantity = document.createElement('td');

      profile.textContent = item.profile;
      const material = document.createElement('span');
      material.className = 'material';
      material.textContent = item.material;
      profile.append(material);

      cut.textContent = item.cut;
      quantity.textContent = item.quantity;
      row.append(profile, cut, quantity);
      return row;
    }));

    const notes = [
      ...(metadata.fabrication_notes ?? []),
      ...(metadata.notes ?? []),
    ];
    notesEl.replaceChildren(...notes.map((note) => {
      const li = document.createElement('li');
      li.textContent = note;
      return li;
    }));
  } catch (error) {
    statusEl.textContent = 'Build data error';
    const li = document.createElement('li');
    li.textContent = error instanceof Error ? error.message : String(error);
    notesEl.replaceChildren(li);
    console.error(error);
  }
}

init();
