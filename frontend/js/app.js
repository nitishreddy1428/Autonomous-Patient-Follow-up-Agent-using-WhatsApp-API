const API_URL = 'http://localhost:5000/api';

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    // Populate Auth Info
    const doctorData = localStorage.getItem('doctor');
    if (doctorData) {
        const doctor = JSON.parse(doctorData);
        document.getElementById('doctor-name').textContent = `Dr. ${doctor.username}`;
        document.getElementById('doctor-email').textContent = doctor.email;
    }

    // Theme Toggle Logic
    const themeToggle = document.getElementById('themeToggle');
    const body = document.body;

    // Check saved theme
    const savedTheme = localStorage.getItem('theme') || 'dark';
    body.setAttribute('data-theme', savedTheme);
    updateThemeIcon(savedTheme);

    themeToggle.addEventListener('click', () => {
        const currentTheme = body.getAttribute('data-theme');
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        body.setAttribute('data-theme', newTheme);
        localStorage.setItem('theme', newTheme);
        updateThemeIcon(newTheme);
    });

    fetchStats();
    fetchPatients();
    fetchAlerts();

    // Auto refresh every 10 seconds
    setInterval(() => {
        fetchStats();
        fetchPatients();
        fetchAlerts();
    }, 10000);

    // Form Handling
    const patientForm = document.getElementById('patientForm');
    if (patientForm) {
        patientForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const patientId = document.getElementById('edit-patient-id').value;
            const data = {
                name: document.getElementById('p-name').value,
                phone: document.getElementById('p-phone').value,
                surgery_type: document.getElementById('p-surgery').value,
                emergency_phone: document.getElementById('p-emergency') ? document.getElementById('p-emergency').value : null
            };

            try {
                const method = patientId ? 'PUT' : 'POST';
                const url = patientId ? `${API_URL}/patients/${patientId}` : `${API_URL}/patients`;

                const res = await fetch(url, {
                    method: method,
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });

                if (res.ok) {
                    closeModal('patientModal');
                    fetchPatients();
                    fetchStats();
                    patientForm.reset();
                    document.getElementById('edit-patient-id').value = '';
                    showToast(patientId ? '✅ Patient updated successfully' : '✅ Patient added successfully');
                }
            } catch (err) {
                console.error('Error saving patient:', err);
                showToast('❌ Error saving patient profile', 'error');
            }
        });
    }
});

function openAddModal() {
    document.getElementById('modalTitle').textContent = 'Register New Patient';
    document.getElementById('patientForm').reset();
    document.getElementById('edit-patient-id').value = '';
    openModal('patientModal');
}

async function openEditModal(id) {
    try {
        const res = await fetch(`${API_URL}/patients`);
        const patients = await res.json();
        const p = patients.find(x => x.id === id);

        if (p) {
            document.getElementById('modalTitle').textContent = 'Edit Patient Profile';
            document.getElementById('edit-patient-id').value = p.id;
            document.getElementById('p-name').value = p.name;
            document.getElementById('p-phone').value = p.phone;
            document.getElementById('p-surgery').value = p.surgery_type;
            const emergencyInput = document.getElementById('p-emergency');
            if (emergencyInput) emergencyInput.value = p.emergency_phone || '';

            openModal('patientModal');
        }
    } catch (err) {
        console.error('Failed to load patient for edit:', err);
    }
}

async function deletePatient(id, name) {
    if (!confirm(`⚠️ Are you sure you want to PERMANENTLY delete ${name} and all their history? This cannot be undone.`)) return;

    try {
        const res = await fetch(`${API_URL}/patients/${id}`, { method: 'DELETE' });
        if (res.ok) {
            showToast(`🗑️ ${name} deleted from records`);
            fetchPatients();
            fetchStats();
            fetchAlerts();
        }
    } catch (err) {
        console.error('Delete failed:', err);
        showToast('❌ Error deleting patient', 'error');
    }
}

async function fetchStats() {
    try {
        const res = await fetch(`${API_URL}/stats`);
        const stats = await res.json();
        document.getElementById('stat-total-patients').textContent = stats.total_patients;
        document.getElementById('stat-active-alerts').textContent = stats.active_alerts;
        document.getElementById('stat-critical-cases').textContent = stats.critical_cases;
    } catch (err) {
        console.error('Error fetching stats:', err);
    }
}

async function fetchPatients() {
    try {
        const res = await fetch(`${API_URL}/patients`);
        const patients = await res.json();
        const tbody = document.getElementById('patient-list');
        if (!tbody) return;

        tbody.innerHTML = patients.map(p => `
            <tr>
                <td>
                    <div style="font-weight: 600;">${p.name}</div>
                    <div style="font-size: 0.75rem; color: var(--text-muted);">${p.phone}</div>
                </td>
                <td>${p.surgery_type}</td>
                <td>
                    <div style="width: 100px; height: 6px; background: rgba(0,0,0,0.2); border-radius: 3px; margin-bottom: 5px;">
                        <div style="width: ${p.risk_score}%; height: 100%; background: ${getRiskColor(p.risk_score)}; border-radius: 3px;"></div>
                    </div>
                    <span style="font-size: 0.75rem;">${p.risk_score}%</span>
                </td>
                <td><span class="status-badge status-${p.status.toLowerCase()}">${p.status}</span></td>
                <td>
                    <div style="display: flex; gap: 0.5rem;">
                        <button class="btn" style="padding: 0.4rem 0.8rem; font-size: 0.75rem; background: #25D366;" onclick="sendCheckin(${p.id}, '${p.name}')" title="Send WhatsApp">
                            <i class='fa-brands fa-whatsapp'></i> Check-in
                        </button>
                        <button class="btn btn-ghost" style="padding: 0.4rem; font-size: 0.75rem; min-width: 32px; color: #a855f7; border-color: rgba(168, 85, 247, 0.2);" onclick="showSummary(${p.id}, '${p.name}')" title="AI Summary">
                            <i class="fa-solid fa-brain"></i>
                        </button>
                        <button class="btn btn-ghost" style="padding: 0.4rem; font-size: 0.75rem; min-width: 32px; color: var(--accent); border-color: rgba(34, 211, 238, 0.2);" onclick="viewChart(${p.id}, '${p.name}')" title="View Chart">
                            <i class="fa-solid fa-chart-line"></i>
                        </button>
                        <button class="btn btn-ghost" style="padding: 0.4rem; font-size: 0.75rem; min-width: 32px; color: var(--primary); border-color: rgba(37, 99, 235, 0.2);" onclick="startTelehealth(${p.id}, '${p.name}')" title="Video Consult">
                            <i class="fa-solid fa-video"></i>
                        </button>
                        <button class="btn btn-ghost" style="padding: 0.4rem; font-size: 0.75rem; min-width: 32px;" onclick="openEditModal(${p.id})" title="Edit Patient">
                            <i class="fa-solid fa-pen-to-square"></i>
                        </button>
                        <button class="btn btn-ghost" style="padding: 0.4rem; font-size: 0.75rem; min-width: 32px; color: var(--danger); border-color: rgba(239, 68, 68, 0.2);" onclick="deletePatient(${p.id}, '${p.name}')" title="Delete Patient">
                            <i class="fa-solid fa-trash"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `).join('');
    } catch (err) {
        console.error('Error fetching patients:', err);
    }
}

async function fetchAlerts() {
    try {
        const res = await fetch(`${API_URL}/alerts`);
        const alerts = await res.json();
        const container = document.getElementById('alerts-list');
        if (!container) return;

        if (alerts.length === 0) {
            container.innerHTML = '<div style="color: var(--text-muted); text-align: center; padding: 2rem;">No active alerts</div>';
            return;
        }

        container.innerHTML = alerts.map(a => `
            <div class="alert-item severity-${a.severity}">
                <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                    <div style="font-weight: 700;">${a.patient_name}</div>
                    <div style="font-size: 0.7rem; color: var(--text-muted);">${formatTime(a.timestamp)}</div>
                </div>
                <div style="font-size: 0.85rem; margin-top: 0.5rem; opacity: 0.9;">${a.message}</div>
                <div style="margin-top: 0.8rem; display: flex; gap: 0.5rem;">
                    <button class="btn" style="background: var(--bg-dark); font-size: 0.7rem; padding: 0.3rem 0.6rem;" onclick="window.open('tel:${a.phone || '+1234567'}')">Call</button>
                    <button class="btn" style="background: var(--primary); font-size: 0.7rem; padding: 0.3rem 0.6rem;" onclick="startTelehealth(${a.patient_id}, '${a.patient_name}')">Video Consult</button>
                    <button class="btn btn-ghost" style="font-size: 0.7rem; padding: 0.3rem 0.6rem;" onclick="resolveAlert(${a.id})">Resolve</button>
                </div>
            </div>
        `).join('');
    } catch (err) {
        console.error('Error fetching alerts:', err);
    }
}

async function startTelehealth(patientId, name) {
    if (!confirm(`🚀 Start instantaneous video consultation with ${name}?\n\nA secure Jitsi link will be sent to their WhatsApp.`)) return;

    try {
        showToast(`📲 Generating link for ${name}...`);
        const res = await fetch(`${API_URL}/telehealth/${patientId}`, { method: 'POST' });
        const data = await res.json();

        if (data.success) {
            showToast(`✅ Link sent! Opening your consultation room...`);
            window.open(data.link, '_blank');
        } else {
            showToast(`❌ Error: ${data.error}`, 'error');
        }
    } catch (err) {
        console.error('Telehealth failed:', err);
        showToast('❌ Connection error to telehealth service', 'error');
    }
}

async function resolveAlert(alertId) {
    if (!confirm('Mark this alert as resolved?')) return;
    try {
        const res = await fetch(`${API_URL}/alerts/${alertId}/resolve`, { method: 'PUT' });
        if (res.ok) {
            fetchAlerts();
            fetchStats();
            fetchPatients();
        }
    } catch (err) {
        console.error('Resolve failed:', err);
    }
}

let recoveryChart = null;
async function viewChart(patientId, patientName) {
    document.getElementById('chart-patient-name').textContent = `Recovery Trends: ${patientName}`;
    openModal('chartModal');

    try {
        const res = await fetch(`${API_URL}/patients/${patientId}/history`);
        const history = await res.json();

        const ctx = document.getElementById('recoveryChart').getContext('2d');
        if (!ctx) return;

        if (recoveryChart) {
            recoveryChart.destroy();
        }

        recoveryChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: history.map(h => formatTime(h.timestamp)),
                datasets: [
                    {
                        label: 'Pain Level',
                        data: history.map(h => h.pain_level),
                        borderColor: '#ef4444',
                        backgroundColor: 'rgba(239, 68, 68, 0.2)',
                        tension: 0.4
                    },
                    {
                        label: 'Temperature (°C)',
                        data: history.map(h => h.temperature),
                        borderColor: '#2563eb',
                        backgroundColor: 'rgba(37, 99, 235, 0.2)',
                        tension: 0.4,
                        yAxisID: 'y1'
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 10,
                        title: { display: true, text: 'Pain Level (1-10)', color: '#94a3b8' }
                    },
                    y1: {
                        position: 'right',
                        min: 35,
                        max: 42,
                        title: { display: true, text: 'Temp (°C)', color: '#94a3b8' },
                        grid: { drawOnChartArea: false }
                    }
                },
                plugins: {
                    legend: { labels: { color: '#f8fafc' } }
                }
            }
        });
    } catch (err) {
        console.error('Failed to load history:', err);
    }
}

async function simulateCheckIn() {
    try {
        const pRes = await fetch(`${API_URL}/patients`);
        const patients = await pRes.json();
        if (patients.length === 0) {
            alert('Please add a patient first!');
            return;
        }

        const patient = patients[Math.floor(Math.random() * patients.length)];
        const symptomsArr = ["Mild pain", "Fever starting", "Incision looks red", "Feeling great", "Slight dizziness"];
        const symptom = symptomsArr[Math.floor(Math.random() * symptomsArr.length)];
        const pain = Math.floor(Math.random() * 10) + 1;
        const temp = 37.0 + (Math.random() * 2.5);

        await fetch(`${API_URL}/check-in`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                patient_id: patient.id,
                pain_level: pain,
                temperature: parseFloat(temp.toFixed(1)),
                symptoms: symptom
            })
        });

        fetchPatients();
        fetchAlerts();
        fetchStats();
    } catch (err) {
        console.error('Demo failed:', err);
    }
}

function getRiskColor(score) {
    if (score > 70) return 'var(--danger)';
    if (score > 40) return 'var(--warning)';
    return 'var(--success)';
}

function formatTime(iso) {
    const d = new Date(iso);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function openModal(id) {
    const modal = document.getElementById(id);
    if (modal) modal.style.display = 'flex';
}

function closeModal(id) {
    const modal = document.getElementById(id);
    if (modal) modal.style.display = 'none';
}

async function sendCheckin(patientId, patientName) {
    if (!confirm(`Send WhatsApp check-in to ${patientName}?`)) return;
    try {
        const res = await fetch(`${API_URL}/send-checkin/${patientId}`, { method: 'POST' });
        const data = await res.json();
        if (data.success) {
            showToast(`✅ Check-in sent to ${patientName} via WhatsApp!`);
        } else {
            showToast(`⚠️ ${data.error || 'Failed to send check-in'}`, 'warning');
        }
    } catch (err) {
        console.error('Check-in send failed:', err);
        showToast('❌ Network error sending check-in', 'error');
    }
}

async function sendAllCheckins() {
    if (!confirm('Send check-in to ALL recovering patients?')) return;
    try {
        const res = await fetch(`${API_URL}/send-checkin-all`, { method: 'POST' });
        const data = await res.json();
        showToast(`✅ Sent ${data.sent} check-in messages!`);
    } catch (err) {
        console.error('Bulk check-in failed:', err);
    }
}

function showToast(message, type = 'success') {
    const toast = document.createElement('div');
    toast.style.cssText = `
        position: fixed; bottom: 2rem; right: 2rem; z-index: 9999;
        padding: 1rem 1.5rem; border-radius: 0.75rem;
        color: white; font-weight: 600; font-size: 0.9rem;
        animation: slideIn 0.3s ease-out;
        box-shadow: 0 8px 25px rgba(0,0,0,0.3);
        background: ${type === 'success' ? '#10b981' : type === 'warning' ? '#f59e0b' : '#ef4444'};
    `;
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
}

function updateThemeIcon(theme) {
    const icon = document.querySelector('#themeToggle i');
    if (theme === 'dark') {
        icon.className = 'fa-solid fa-moon';
    } else {
        icon.className = 'fa-solid fa-sun';
    }
}

function logout() {
    localStorage.removeItem('doctor');
    window.location.href = 'login.html';
}

// Global Exports
window.viewChart = viewChart;
window.resolveAlert = resolveAlert;
window.openModal = openModal;
window.closeModal = closeModal;
window.simulateCheckIn = simulateCheckIn;
window.sendCheckin = sendCheckin;
window.sendAllCheckins = sendAllCheckins;
window.logout = logout;
window.updateThemeIcon = updateThemeIcon;
async function showSummary(patientId, name) {
    document.getElementById('summary-name').textContent = name;
    document.getElementById('summary-text').innerHTML = `
        <div style="display:flex; flex-direction:column; gap:8px;">
            <div class="skeleton-text" style="width:100%; height:18px; background:rgba(255,255,255,0.05); border-radius:4px; animation: pulse 1.5s infinite;"></div>
            <div class="skeleton-text" style="width:90%; height:18px; background:rgba(255,255,255,0.05); border-radius:4px; animation: pulse 1.5s infinite;"></div>
            <div class="skeleton-text" style="width:70%; height:18px; background:rgba(255,255,255,0.05); border-radius:4px; animation: pulse 1.5s infinite;"></div>
        </div>
    `;
    openModal('summaryModal');

    try {
        const res = await fetch(`${API_URL}/patients/${patientId}/summary`);
        const data = await res.json();
        document.getElementById('summary-text').innerHTML = `<p style="white-space: pre-wrap;">${data.summary}</p>`;
    } catch (err) {
        console.error('Summary failed:', err);
        document.getElementById('summary-text').innerHTML = '<span style="color:var(--danger)">Failed to load AI summary. Please try again.</span>';
    }
}

window.openEditModal = openEditModal;
window.openAddModal = openAddModal;
window.deletePatient = deletePatient;
window.startTelehealth = startTelehealth;
window.showSummary = showSummary;
