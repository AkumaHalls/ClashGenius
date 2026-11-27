// offline.html — página de fallback do service worker (externo para CSP)
(function () {
    var version = localStorage.getItem('clashgenius_version') || '?';
    document.getElementById('version').textContent = version;

    var data = null;
    try { data = JSON.parse(localStorage.getItem('clashgenius_last_clan') || 'null'); } catch (e) { data = null; }

    if (data) {
        var box = document.getElementById('clan-info');
        box.style.display = 'block';
        // textContent em vez de innerHTML: nada vindo do localStorage é interpretado como HTML.
        [['Clã', data.name], ['Nível', data.level], ['Membros', data.members ? data.members + '/50' : null], ['Último placar', data.score]]
            .forEach(function (pair) {
                if (pair[1] === null || pair[1] === undefined || pair[1] === '') return;
                var row = document.createElement('div');
                var label = document.createElement('span');
                label.textContent = pair[0];
                var value = document.createElement('b');
                value.textContent = String(pair[1]);
                row.appendChild(label);
                row.appendChild(value);
                box.appendChild(row);
            });
    }

    document.getElementById('retry-btn').addEventListener('click', function () {
        window.location.reload();
    });
})();
