// Utilitários compartilhados entre scripts.js e admin.js

function escapeHtml(str) {
    const map = {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'};
    return String(str).replace(/[&<>"']/g, c => map[c]);
}
