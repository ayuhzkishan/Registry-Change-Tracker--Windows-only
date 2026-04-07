let snapshots = [];
let selectedSnapshots = [];

// DOM Elements
const grid = document.getElementById('snapshot-grid');
const modal = document.getElementById('modal-snapshot');
const btnNew = document.getElementById('btnNewSnapshot');
const btnCancel = document.getElementById('btnCancelSnapshot');
const btnSubmit = document.getElementById('btnSubmitSnapshot');
const diffSection = document.getElementById('diff-section');
const diffTableBody = document.querySelector('#diff-table tbody');

// Init
document.addEventListener('DOMContentLoaded', fetchSnapshots);

async function fetchSnapshots() {
    try {
        const res = await fetch('/api/snapshots');
        snapshots = await res.json();
        renderSnapshots();
    } catch (e) {
        console.error("Failed to fetch snapshots", e);
    }
}

function renderSnapshots() {
    grid.innerHTML = '';
    
    if (snapshots.length === 0) {
        grid.innerHTML = '<p style="color: var(--text-muted);">No snapshots found. Create one to get started.</p>';
        return;
    }

    snapshots.forEach(s => {
        const d = new Date(s.timestamp).toLocaleString();
        const isSelected = selectedSnapshots.includes(s.id);
        
        const card = document.createElement('div');
        card.className = `snapshot-card ${isSelected ? 'selected' : ''}`;
        card.onclick = () => toggleSelectSnapshot(s.id);
        
        card.innerHTML = `
            <div class="snap-header">
                <span class="snap-title">${escapeHTML(s.label)}</span>
                <span class="snap-id">${s.id}</span>
            </div>
            <div class="snap-path">${escapeHTML(s.hive_path)}</div>
            <div class="snap-footer">
                <span><i class="ph ph-list-numbers"></i> ${s.entries.toLocaleString()} entries</span>
                <span>${d}</span>
            </div>
        `;
        
        // Add a delete button (hidden unless hovered, managed via CSS or JS stopProp)
        grid.appendChild(card);
    });
}

function escapeHTML(str) {
    const div = document.createElement('div');
    div.innerText = str;
    return div.innerHTML;
}

function toggleSelectSnapshot(id) {
    if (selectedSnapshots.includes(id)) {
        selectedSnapshots = selectedSnapshots.filter(i => i !== id);
    } else {
        selectedSnapshots.push(id);
        // Max 2 selections
        if (selectedSnapshots.length > 2) {
            selectedSnapshots.shift();
        }
    }
    
    renderSnapshots();
    
    if (selectedSnapshots.length === 2) {
        runDiff();
    } else {
        diffSection.classList.add('hidden');
    }
}

async function runDiff() {
    try {
        const [idA, idB] = selectedSnapshots;
        // Always pass older snapshot first based on array order (shift appends newest)
        // For accurate diffs, we ideally want oldest vs newest. Let's assume order selected is A -> B
        const res = await fetch(`/api/diff/${idA}/${idB}`);
        const data = await res.json();
        
        if (data.success) {
            renderDiff(data);
        } else {
            alert("Error running diff: " + data.error);
        }
    } catch (e) {
        console.error(e);
    }
}

function renderDiff(data) {
    document.getElementById('stat-added').innerText = `${data.added.length} Added`;
    document.getElementById('stat-deleted').innerText = `${data.deleted.length} Deleted`;
    document.getElementById('stat-modified').innerText = `${data.modified.length} Modified`;
    
    diffTableBody.innerHTML = '';
    
    // Sort array utility
    const byPath = (a, b) => a.path.localeCompare(b.path);
    
    // Render Deleted
    data.deleted.sort(byPath).forEach(d => {
        const tr = document.createElement('tr');
        tr.className = 'row-deleted';
        tr.innerHTML = `
            <td><strong>Deleted</strong></td>
            <td class="code-cell">${escapeHTML(d.path)}</td>
            <td class="code-cell val-old">${escapeHTML(d.value)}</td>
        `;
        diffTableBody.appendChild(tr);
    });
    
    // Render Added
    data.added.sort(byPath).forEach(d => {
        const tr = document.createElement('tr');
        tr.className = 'row-added';
        tr.innerHTML = `
            <td><strong>Added</strong></td>
            <td class="code-cell">${escapeHTML(d.path)}</td>
            <td class="code-cell val-new">${escapeHTML(d.value)}</td>
        `;
        diffTableBody.appendChild(tr);
    });
    
    // Render Modified
    data.modified.sort(byPath).forEach(d => {
        const tr = document.createElement('tr');
        tr.className = 'row-modified';
        tr.innerHTML = `
            <td><strong>Modified</strong></td>
            <td class="code-cell">${escapeHTML(d.path)}</td>
            <td class="code-cell">
                <span class="val-old">${escapeHTML(d.old)}</span>
                <span class="val-new">${escapeHTML(d.new)}</span>
            </td>
        `;
        diffTableBody.appendChild(tr);
    });
    
    diffSection.classList.remove('hidden');
    // Scroll to diff
    diffSection.scrollIntoView({ behavior: 'smooth' });
}

// Modal Handlers
btnNew.onclick = () => {
    modal.classList.add('active');
    document.getElementById('inp-hive-path').focus();
};

btnCancel.onclick = () => {
    modal.classList.remove('active');
};

btnSubmit.onclick = async () => {
    const path = document.getElementById('inp-hive-path').value.trim();
    const label = document.getElementById('inp-label').value.trim() || 'web_snapshot';
    
    if (!path) return alert("Hive Path is required!");
    
    btnSubmit.disabled = true;
    btnSubmit.innerText = 'Capturing...';
    
    try {
        const res = await fetch('/api/snapshots', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({hive_path: path, label: label})
        });
        const data = await res.json();
        
        if (data.success) {
            modal.classList.remove('active');
            document.getElementById('inp-hive-path').value = '';
            document.getElementById('inp-label').value = '';
            fetchSnapshots(); // Reload
        } else {
            alert(data.error);
        }
    } catch(e) {
        alert("Request failed");
    } finally {
        btnSubmit.disabled = false;
        btnSubmit.innerText = 'Capture';
    }
};
