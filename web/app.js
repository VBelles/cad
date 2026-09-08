const statusEl = document.querySelector('#status');
const summaryEl = document.querySelector('#summary');
const bomEl = document.querySelector('#bom');
const notesEl = document.querySelector('#notes');

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
    statusEl.textContent = metadata.status;
    summaryEl.replaceChildren(
      summaryItem('Length', `${mm.format(p.length)} mm`),
      summaryItem('Depth', `${mm.format(p.depth)} mm`),
      summaryItem('Planter height', `${mm.format(p.body_height)} mm`),
      summaryItem('Overall height', `${mm.format(p.trellis_height)} mm`),
      summaryItem('Frame', `${mm.format(p.frame_size)} × ${mm.format(p.frame_size)} × ${mm.format(p.frame_wall)} mm`),
      summaryItem('Parts', `${metadata.parts.length}`),
    );

    bomEl.replaceChildren(...bom.map((item) => {
      const row = document.createElement('tr');
      const profile = document.createElement('td');
      const length = document.createElement('td');
      const quantity = document.createElement('td');

      profile.textContent = item.profile;
      const material = document.createElement('span');
      material.className = 'material';
      material.textContent = item.material;
      profile.append(material);

      length.textContent = `${mm.format(item.length_mm)} mm`;
      quantity.textContent = item.quantity;
      row.append(profile, length, quantity);
      return row;
    }));

    notesEl.replaceChildren(...metadata.notes.map((note) => {
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
